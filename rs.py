#!/usr/bin/env python3
"""Utility helpers for extracting and repacking Asura RSFL archives.

The original RSFL_ASR.cpp tool published by Trololp/Vhetration only supported
extracting data from an RSFL chunk.  This script extends that behaviour so the
extracted payloads can be modified and written back into the original archive
without rebuilding the whole container from scratch.

Two subcommands are provided:

```
python rsfl_tool.py extract <archive.asr> <output_dir>
python rsfl_tool.py repack <archive.asr> <manifest.json> <input_dir> <output.asr>
```

The *extract* command mirrors the behaviour of the legacy tool: it pulls every
resource referenced by the RSFL table into ``<output_dir>``.  In addition it
creates ``manifest.json`` which records the offsets and sizes of all entries as
they appear in the archive.  The manifest is later consumed by *repack*.

The *repack* command keeps the layout of the original archive intact.  It
produces an updated copy where each entry listed in ``manifest.json`` is
replaced by the corresponding file located inside ``<input_dir>``.  Repacking is
safe as long as the modified files keep their original size – that is the
requirement imposed by the RSFL table because changing the size would break the
offset map for the rest of the archive.

While this script is intentionally conservative it enables a fast edit cycle:
extract ➜ tweak asset ➜ repack.  The RSFL manifest contains enough contextual
information so that a future enhancement could also grow/shrink assets and
rebuild the RSFL table from scratch.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

tk = None
filedialog = None
messagebox = None
try:
    # Tkinter is optional – only needed when launching the GUI helper.
    import tkinter as tk
    from tkinter import filedialog, messagebox

    TK_AVAILABLE = True
except Exception:  # pragma: no cover - Tkinter availability is platform specific.
    TK_AVAILABLE = False

ASURA_MAGIC = b"Asura   "
CHUNK_HEADER = struct.Struct("<4sIII")
RSFL_ENTRY_STRUCT = struct.Struct("<III")
RSFL_CHUNK_HEADER = struct.Struct("<5I")  # magic, size_with_header, type, type2, count

IMAGE_EXTENSIONS = {
    ".bmp",
    ".dds",
    ".gif",
    ".jpg",
    ".jpeg",
    ".png",
    ".tga",
    ".tif",
    ".tiff",
}


class RSFLParsingError(RuntimeError):
    """Raised when the archive layout does not match expectations."""


def _read_padded_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Return a null-terminated string padded to 4-byte boundaries.

    The function returns the decoded string and the total amount of bytes
    consumed (including the padding).
    """

    cursor = offset
    chunks: List[int] = []
    while cursor < len(data):
        block = data[cursor : cursor + 4]
        chunks.append(block)
        cursor += 4
        if b"\x00" in block:
            break
    else:
        raise RSFLParsingError("unterminated padded string inside RSFL table")

    raw = b"".join(chunks)
    string_bytes = raw.split(b"\x00", 1)[0]
    try:
        text = string_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = string_bytes.decode("latin-1")
    return text, cursor - offset


def _scan_for_rsfl(data: bytes) -> Tuple[int, int, int, int, int]:
    """Locate the RSFL chunk and return its metadata.

    Returns a tuple ``(chunk_offset, chunk_size, type1, type2, entry_count)``.
    ``chunk_size`` already includes the 16 byte chunk header.
    """

    if not data.startswith(ASURA_MAGIC):
        raise RSFLParsingError("file is not an Asura archive")

    cursor = len(ASURA_MAGIC)
    while cursor + CHUNK_HEADER.size <= len(data):
        magic, size, type1, type2 = CHUNK_HEADER.unpack_from(data, cursor)
        if size == 0:
            raise RSFLParsingError("encountered zero-sized chunk while scanning")
        if magic == b"LFSR":
            header_start = cursor
            header_end = cursor + 16
            rsfl_magic, rsfl_size, rsfl_type1, rsfl_type2, count = RSFL_CHUNK_HEADER.unpack_from(
                data, header_end
            )
            if rsfl_magic != 0x5246534C:  # 'LFSR'
                raise RSFLParsingError("corrupted RSFL inner header")
            return header_start, size, rsfl_type1, rsfl_type2, count
        cursor += size

    raise RSFLParsingError("unable to locate RSFL chunk")


def _parse_rsfl_entries(
    data: bytes, rsfl_offset: int, rsfl_chunk_size: int, entry_count: int
) -> Tuple[List[Dict[str, int]], int]:
    """Parse RSFL entries and return both the entry list and the end offset."""

    entries: List[Dict[str, int]] = []
    table_offset = rsfl_offset + 16 + RSFL_CHUNK_HEADER.size
    cursor = table_offset
    for _ in range(entry_count):
        name, consumed = _read_padded_string(data, cursor)
        cursor += consumed
        entry_struct_offset = cursor
        raw_offset, size, unk = RSFL_ENTRY_STRUCT.unpack_from(data, cursor)
        cursor += RSFL_ENTRY_STRUCT.size
        entries.append(
            {
                "name": name,
                "raw_offset": raw_offset,
                "size": size,
                "unk": unk,
                "table_offset": entry_struct_offset,
            }
        )
    return entries, cursor


def _resolve_entry_offset(raw_offset: int, size: int, data_length: int, rsfl_offset: int, rsfl_chunk_size: int) -> int:
    """Translate the offset stored in the RSFL table into an absolute position."""

    offset_relative = raw_offset + rsfl_chunk_size
    if offset_relative + size > data_length:
        offset_relative = raw_offset + rsfl_offset
    if offset_relative + size > data_length:
        raise RSFLParsingError("entry points outside of archive bounds")
    return offset_relative


def _normalise_entries(
    entries: List[Dict[str, int]],
    data: bytes,
    rsfl_offset: int,
    rsfl_chunk_size: int,
) -> List[Dict[str, object]]:
    normalised: List[Dict[str, object]] = []
    for entry in entries:
        absolute_offset = _resolve_entry_offset(
            entry["raw_offset"], entry["size"], len(data), rsfl_offset, rsfl_chunk_size
        )
        relative_name = entry["name"].lstrip("/\\")
        chunk_end = rsfl_offset + rsfl_chunk_size
        offset_anchor = absolute_offset - entry["raw_offset"]
        normalised.append(
            {
                "name": entry["name"],
                "relative_path": str(relative_name),
                "offset": absolute_offset,
                "size": entry["size"],
                "unk": entry["unk"],
                "raw_offset": entry["raw_offset"],
                "table_offset": entry["table_offset"],
                "offset_anchor": offset_anchor,
                "anchor_kind": (
                    "chunk_end"
                    if offset_anchor == chunk_end
                    else "chunk_start"
                    if offset_anchor == rsfl_offset
                    else "absolute"
                ),
            }
        )
    return normalised


def load_archive(archive_path: Path) -> Tuple[bytes, Dict[str, object], List[Dict[str, object]]]:
    """Read an Asura archive and return its bytes, RSFL metadata and entries."""

    data = archive_path.read_bytes()
    rsfl_offset, rsfl_chunk_size, rsfl_type1, rsfl_type2, entry_count = _scan_for_rsfl(data)
    entries_raw, table_end = _parse_rsfl_entries(data, rsfl_offset, rsfl_chunk_size, entry_count)
    entries = _normalise_entries(entries_raw, data, rsfl_offset, rsfl_chunk_size)

    rsfl_info = {
        "offset": rsfl_offset,
        "chunk_size": rsfl_chunk_size,
        "type1": rsfl_type1,
        "type2": rsfl_type2,
        "table_end": table_end,
    }
    return data, rsfl_info, entries


def is_image_entry(entry_name: str) -> bool:
    """Return True if the entry looks like an image based on its extension."""

    suffix = Path(entry_name).suffix.lower()
    return suffix in IMAGE_EXTENSIONS


def extract_archive(archive_path: Path, output_dir: Path) -> Path:
    """Extract RSFL controlled files and write a manifest.

    Returns the path to the generated manifest file.
    """

    data, rsfl_info, entries = load_archive(archive_path)

    archive_name = archive_path.name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Dump all files controlled by the RSFL table.
    extracted_files: List[Dict[str, object]] = []
    for entry in entries:
        payload = data[entry["offset"] : entry["offset"] + entry["size"]]
        target_path = output_dir / entry["relative_path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)
        extracted_files.append(entry)

    manifest = {
        "archive": archive_name,
        "rsfl": rsfl_info,
        "files": extracted_files,
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Store pristine copy of the archive next to the extraction to simplify repacking.
    shutil.copy2(archive_path, output_dir / archive_name)
    return manifest_path


def _apply_replacements(
    archive_bytes: bytes,
    entries: List[Dict[str, object]],
    replacements: Dict[str, bytes],
) -> Tuple[bytearray, List[Dict[str, object]]]:
    """Return a new archive with the requested replacements applied."""

    updated = bytearray(archive_bytes)
    # The RSFL table typically stores offsets relative to either the chunk start
    # or the chunk end.  ``offset_anchor`` records the absolute position that was
    # used for the original entry so we can preserve the same addressing mode.
    for entry in entries:
        rel_path = entry["relative_path"]
        payload = replacements.get(rel_path)
        if payload is None:
            continue

        new_size = len(payload)
        start = entry["offset"]
        end = start + entry["size"]

        if new_size == entry["size"]:
            new_offset = start
            updated[start:end] = payload
        else:
            # The new payload does not fit in place; append it to the archive and
            # realign to 4 bytes to keep offsets consistent with the original
            # layout.
            padding = (-len(updated)) % 4
            if padding:
                updated.extend(b"\x00" * padding)
            new_offset = len(updated)
            updated.extend(payload)

        anchor = entry["offset_anchor"]
        raw_offset = new_offset - anchor
        if raw_offset < 0:
            raise RSFLParsingError(
                f"replacement for {rel_path} would produce a negative offset"
            )
        if raw_offset > 0xFFFFFFFF:
            raise RSFLParsingError(
                f"replacement for {rel_path} exceeds 32-bit offset capacity"
            )

        RSFL_ENTRY_STRUCT.pack_into(updated, entry["table_offset"], raw_offset, new_size, entry["unk"])
        entry["offset"] = new_offset
        entry["size"] = new_size
        entry["raw_offset"] = raw_offset

    return updated, entries


def repack_archive(original_archive: Path, manifest_path: Path, modified_dir: Path, output_path: Path) -> None:
    """Create a patched copy of the archive using files stored on disk."""

    manifest = json.loads(manifest_path.read_text())
    if original_archive.name != manifest.get("archive"):
        raise RSFLParsingError(
            "original archive file name does not match manifest metadata"
        )

    files_info = manifest.get("files", [])
    if not files_info:
        raise RSFLParsingError("manifest does not contain any file entries")

    archive_bytes, _rsfl_info, entries = load_archive(original_archive)
    manifest_index = {entry["relative_path"]: entry for entry in files_info}

    replacements: Dict[str, bytes] = {}
    for entry in entries:
        rel_path = entry["relative_path"]
        manifest_entry = manifest_index.get(rel_path)
        if manifest_entry is None:
            # Ignore files that were not part of the extraction.
            continue
        payload_path = modified_dir / rel_path
        if not payload_path.exists():
            continue
        replacements[rel_path] = payload_path.read_bytes()

    if not replacements:
        raise RSFLParsingError("no modified files found in the provided directory")

    updated, _ = _apply_replacements(archive_bytes, entries, replacements)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(updated)


class TextureManagerGUI:
    """Minimal Tk based browser for previewing and patching texture entries."""

    def __init__(self) -> None:
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is not available on this platform")

        self.root = tk.Tk()
        self.root.title("RSFL Texture Manager")
        self.root.geometry("720x480")

        self.archive_path: Path | None = None
        self.archive_bytes: bytes | None = None
        self.entries: List[Dict[str, object]] = []
        self.replacements: Dict[str, bytes] = {}

        self._build_ui()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        list_frame = tk.Frame(self.root)
        list_frame.grid(row=0, column=0, sticky="nsew")

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE)
        self.listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        button_frame = tk.Frame(self.root)
        button_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        for i in range(4):
            button_frame.columnconfigure(i, weight=1)

        tk.Button(button_frame, text="Open Archive", command=self.open_archive).grid(
            row=0, column=0, padx=4
        )
        tk.Button(button_frame, text="Export Selected", command=self.export_selected).grid(
            row=0, column=1, padx=4
        )
        tk.Button(button_frame, text="Import Replacement", command=self.import_replacement).grid(
            row=0, column=2, padx=4
        )
        tk.Button(button_frame, text="Save Patched Archive", command=self.save_patched_archive).grid(
            row=0, column=3, padx=4
        )

        self.status = tk.StringVar(value="Select an archive to begin")
        status_bar = tk.Label(self.root, textvariable=self.status, anchor="w")
        status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

    # ------------------------------------------------------------- utilities --
    def _refresh_list(self) -> None:
        self.listbox.delete(0, tk.END)
        for entry in self.entries:
            display = f"{entry['relative_path']} ({entry['size']} bytes)"
            replacement = self.replacements.get(entry["relative_path"])
            if replacement is not None:
                replacement_size = len(replacement)
                if replacement_size != entry["size"]:
                    display += f" → {replacement_size} bytes"
                display += " *"
            self.listbox.insert(tk.END, display)

    def _set_status(self, message: str) -> None:
        self.status.set(message)

    # ------------------------------------------------------------- callbacks --
    def open_archive(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select Asura archive",
            filetypes=[
                ("Asura archives", "*.asr *.pc *.es *.en *.fr *.de"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        try:
            data, _rsfl_info, entries = load_archive(Path(filename))
        except Exception as exc:  # pragma: no cover - GUI path
            messagebox.showerror("Unable to open archive", str(exc))
            return

        image_entries = [entry for entry in entries if is_image_entry(entry["relative_path"])]
        if not image_entries:
            messagebox.showinfo(
                "No textures found",
                "The selected archive does not contain recognised image entries.",
            )

        self.archive_path = Path(filename)
        self.archive_bytes = data
        self.entries = image_entries
        self.replacements.clear()
        self._refresh_list()
        self._set_status(
            f"Loaded {len(image_entries)} image entries from {self.archive_path.name}"
        )

    def export_selected(self) -> None:
        if self.archive_bytes is None:
            messagebox.showwarning("No archive", "Open an archive before exporting.")
            return

        indices = self.listbox.curselection()
        if not indices:
            messagebox.showinfo("Nothing selected", "Select one or more entries to export.")
            return

        destination = filedialog.askdirectory(title="Select export directory")
        if not destination:
            return

        destination_path = Path(destination)
        count = 0
        for index in indices:
            entry = self.entries[index]
            payload = self.archive_bytes[entry["offset"] : entry["offset"] + entry["size"]]
            target = destination_path / entry["relative_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            count += 1

        self._set_status(f"Exported {count} file(s) to {destination_path}")

    def import_replacement(self) -> None:
        if self.archive_bytes is None:
            messagebox.showwarning("No archive", "Open an archive before importing replacements.")
            return

        indices = self.listbox.curselection()
        if len(indices) != 1:
            messagebox.showinfo(
                "Select a texture",
                "Choose a single texture entry before importing a replacement.",
            )
            return

        entry = self.entries[indices[0]]
        filename = filedialog.askopenfilename(
            title="Select replacement texture",
            filetypes=[
                ("Image files", "*.dds *.png *.tga *.bmp *.jpg *.jpeg *.gif *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        try:
            payload = Path(filename).read_bytes()
        except Exception as exc:  # pragma: no cover - GUI path
            messagebox.showerror("Unable to read texture", str(exc))
            return

        self.replacements[entry["relative_path"]] = payload
        self._refresh_list()
        self._set_status(
            f"Queued replacement for {entry['relative_path']} ({len(payload)} bytes)"
        )

    def save_patched_archive(self) -> None:
        if self.archive_bytes is None or self.archive_path is None:
            messagebox.showwarning("No archive", "Open an archive before saving.")
            return
        if not self.replacements:
            messagebox.showinfo("No replacements", "Import at least one texture first.")
            return

        filename = filedialog.asksaveasfilename(
            title="Save patched archive",
            defaultextension=self.archive_path.suffix,
            initialfile=self.archive_path.name,
            filetypes=[
                ("Asura archives", "*.asr *.pc *.es *.en *.fr *.de"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        try:
            updated, updated_entries = _apply_replacements(
                self.archive_bytes, self.entries, self.replacements
            )
        except Exception as exc:  # pragma: no cover - GUI path
            messagebox.showerror("Unable to apply replacements", str(exc))
            return

        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(updated)

        self.archive_bytes = bytes(updated)
        self.entries = updated_entries
        self.replacements.clear()
        self._refresh_list()
        self._set_status(f"Saved patched archive to {output_path}")
        messagebox.showinfo("Archive saved", f"Patched archive written to {output_path}")

    # ----------------------------------------------------------------- public --
    def run(self) -> None:
        self.root.mainloop()


def launch_gui() -> None:
    """Launch the Tk based texture browser."""

    gui = TextureManagerGUI()
    gui.run()


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract and repack Asura RSFL archives")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="extract files and emit a manifest")
    extract_parser.add_argument(
        "archive",
        type=Path,
        help="path to the Asura archive (.asr / .pc / .es, etc.)",
    )
    extract_parser.add_argument("output", type=Path, help="directory that will receive the extracted files")

    repack_parser = subparsers.add_parser("repack", help="repackage modified files back into an archive")
    repack_parser.add_argument("archive", type=Path, help="original archive used during extraction")
    repack_parser.add_argument("manifest", type=Path, help="manifest generated by the extract command")
    repack_parser.add_argument("input_dir", type=Path, help="directory containing the modified files")
    repack_parser.add_argument("output", type=Path, help="path of the repacked archive")

    subparsers.add_parser("gui", help="launch a texture focused graphical interface")

    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_cli()
    args = parser.parse_args(argv)

    if args.command == "extract":
        manifest = extract_archive(args.archive, args.output)
        print(f"Extraction complete. Manifest written to {manifest}")
    elif args.command == "repack":
        repack_archive(args.archive, args.manifest, args.input_dir, args.output)
        print(f"Repacked archive written to {args.output}")
    elif args.command == "gui":
        if not TK_AVAILABLE:
            raise SystemExit("Tkinter is not available on this platform; GUI mode is disabled.")
        launch_gui()
    else:
        parser.error("unknown command")


if __name__ == "__main__":
    main()
