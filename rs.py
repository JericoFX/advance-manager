#!/usr/bin/env python3
"""Utility helpers for extracting and repacking Asura RS managed archives.

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

The *repack* command keeps the layout of the original archive intact.  RSFL
entries can grow or shrink in size – the script appends resized payloads to the
end of the archive and updates the offset table accordingly.  RSCF controlled
entries must preserve their original size because their payload is embedded
inside fixed-width chunks whose headers would otherwise need to be rewritten.

While this script is intentionally conservative it enables a fast edit cycle:
extract ➜ tweak asset ➜ repack.  The RSFL manifest contains enough contextual
information so that a future enhancement could also rebuild the RSCF chunk
headers when supporting payloads that change size.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import struct
import zlib
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

Image = None
ImageTk = None
UnidentifiedImageError = Exception
PIL_AVAILABLE = False
PIL_IMAGETK_AVAILABLE = False
try:  # pragma: no cover - Pillow availability depends on the environment.
    from PIL import Image, UnidentifiedImageError

    PIL_AVAILABLE = True
except Exception:  # pragma: no cover - Pillow availability depends on the environment.
    pass

if PIL_AVAILABLE:
    try:  # pragma: no cover - ImageTk availability depends on the environment.
        from PIL import ImageTk

        PIL_IMAGETK_AVAILABLE = True
    except Exception:  # pragma: no cover - ImageTk availability depends on the environment.
        pass

ASURA_MAGIC = b"Asura   "
ASURA_ZLB_MAGIC = b"AsuraZlb"
ASURA_ZBB_MAGIC = b"AsuraZbb"
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


def normalize_relative_path(name: str) -> str:
    """Return a normalised relative path using forward slashes."""

    normalised = name.replace("\\", "/")
    return normalised.lstrip("/")


def _unwrap_asura_container(data: bytes) -> Tuple[bytes, Dict[str, object]]:
    """Return the raw Asura archive payload and compression metadata."""

    if data.startswith(ASURA_MAGIC):
        return data, {"kind": "raw"}

    if data.startswith(ASURA_ZLB_MAGIC):
        if len(data) < 20:
            raise RSFLParsingError("truncated AsuraZlb header")

        unknown = struct.unpack_from("<I", data, 8)[0]
        compressed_size = struct.unpack_from("<I", data, 12)[0]
        expected_size = struct.unpack_from("<I", data, 16)[0]
        payload = data[20:]
        if compressed_size and compressed_size <= len(payload):
            payload = payload[:compressed_size]
        try:
            uncompressed = zlib.decompress(payload)
        except zlib.error as exc:  # pragma: no cover - depends on archive contents
            raise RSFLParsingError(f"failed to decompress AsuraZlb archive: {exc}") from exc
        if expected_size and len(uncompressed) != expected_size:
            expected_size = len(uncompressed)
        return uncompressed, {
            "kind": "zlb",
            "unknown": unknown,
            "expected_size": expected_size,
        }

    if data.startswith(ASURA_ZBB_MAGIC):
        if len(data) < 16:
            raise RSFLParsingError("truncated AsuraZbb header")

        total_compressed = struct.unpack_from("<I", data, 8)[0]
        total_size = struct.unpack_from("<I", data, 12)[0]
        cursor = 16
        output = bytearray()
        chunk_sizes: List[int] = []

        while cursor + 8 <= len(data):
            chunk_compressed = struct.unpack_from("<I", data, cursor)[0]
            chunk_size = struct.unpack_from("<I", data, cursor + 4)[0]
            cursor += 8
            if chunk_compressed == 0:
                break
            chunk_payload = data[cursor : cursor + chunk_compressed]
            if len(chunk_payload) != chunk_compressed:
                raise RSFLParsingError("truncated AsuraZbb chunk payload")
            cursor += chunk_compressed
            try:
                chunk_data = zlib.decompress(chunk_payload)
            except zlib.error as exc:  # pragma: no cover - depends on archive contents
                raise RSFLParsingError(f"failed to decompress AsuraZbb chunk: {exc}") from exc
            if chunk_size and len(chunk_data) != chunk_size:
                raise RSFLParsingError(
                    "decompressed chunk size does not match the value stored in the header"
                )
            output.extend(chunk_data)
            chunk_sizes.append(len(chunk_data))
            if total_size and len(output) >= total_size:
                break

        if total_size and len(output) != total_size:
            total_size = len(output)

        return bytes(output), {
            "kind": "zbb",
            "chunk_sizes": chunk_sizes,
            "total_size": total_size,
        }

    raise RSFLParsingError(
        "unsupported Asura container wrapper; try running the QuickBMS script first"
    )


def _wrap_asura_container(data: bytes, wrapper: Dict[str, object]) -> bytes:
    """Reapply the original Asura wrapper (if any) after patching."""

    kind = wrapper.get("kind") if wrapper else "raw"
    if kind == "raw":
        return data

    if kind == "zlb":
        compressed = zlib.compress(data)
        unknown = int(wrapper.get("unknown", 0))
        header = struct.pack(
            "<8sIII", ASURA_ZLB_MAGIC, unknown, len(compressed), len(data)
        )
        return header + compressed

    if kind == "zbb":
        chunk_sizes = list(wrapper.get("chunk_sizes") or [])
        if not chunk_sizes:
            chunk_sizes = [len(data)]
        payload = bytearray()
        total_compressed = 0
        cursor = 0
        size_index = 0
        default_size = chunk_sizes[-1]
        while cursor < len(data):
            size_hint = chunk_sizes[size_index] if size_index < len(chunk_sizes) else default_size
            if size_hint <= 0:
                size_hint = default_size or len(data)
            end = min(len(data), cursor + size_hint)
            chunk = data[cursor:end]
            compressed_chunk = zlib.compress(chunk)
            payload.extend(struct.pack("<II", len(compressed_chunk), len(chunk)))
            payload.extend(compressed_chunk)
            total_compressed += len(compressed_chunk)
            cursor = end
            size_index += 1

        header = struct.pack("<8sII", ASURA_ZBB_MAGIC, total_compressed, len(data))
        return header + payload

    raise RSFLParsingError(f"unsupported wrapper kind: {kind}")


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


def _scan_for_rsfl(data: bytes) -> Dict[str, object]:
    """Locate RS managed chunks and describe their layout."""

    if not data.startswith(ASURA_MAGIC):
        raise RSFLParsingError("file is not an Asura archive")

    cursor = len(ASURA_MAGIC)
    rscf_chunks: List[Dict[str, object]] = []

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
            return {
                "layout": "rsfl",
                "chunks": [
                    {
                        "offset": header_start,
                        "chunk_size": size,
                        "type1": type1,
                        "type2": type2,
                        "rsfl": {
                            "inner_size": rsfl_size,
                            "type1": rsfl_type1,
                            "type2": rsfl_type2,
                            "entry_count": count,
                        },
                    }
                ],
            }

        if magic == b"RSCF":
            header_offset = cursor + 16
            if header_offset + 12 > len(data):
                raise RSFLParsingError("truncated RSCF header")
            version, data_offset, data_span = struct.unpack_from("<III", data, header_offset)
            rscf_chunks.append(
                {
                    "offset": cursor,
                    "chunk_size": size,
                    "type1": type1,
                    "type2": type2,
                    "rscf": {
                        "version": version,
                        "data_offset": data_offset,
                        "data_span": data_span,
                    },
                }
            )

        cursor += size

    if rscf_chunks:
        return {"layout": "rscf", "chunks": rscf_chunks}

    raise RSFLParsingError("unable to locate RS controlled chunks")


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


def _parse_rscf_entries(data: bytes, chunk_info: Dict[str, object]) -> List[Dict[str, object]]:
    """Parse a single RSCF chunk and return its entry description."""

    chunk_offset = int(chunk_info["offset"])
    chunk_size = int(chunk_info["chunk_size"])
    header = dict(chunk_info.get("rscf") or {})

    header_offset = chunk_offset + 16
    if header_offset + 12 > len(data):
        raise RSFLParsingError("truncated RSCF chunk header")

    version = int(header.get("version", 0))
    data_offset = int(header.get("data_offset", 0))
    data_span = int(header.get("data_span", 0))

    string_offset = header_offset + 12
    name, consumed = _read_padded_string(data, string_offset)
    string_end = string_offset + consumed

    chunk_end = chunk_offset + chunk_size

    candidate_offsets: List[int] = []

    def _register_candidate(value: int) -> None:
        if value not in candidate_offsets:
            candidate_offsets.append(value)

    _register_candidate(string_end + data_offset)

    masked_offset = data_offset & 0x00FFFFFF
    if masked_offset != data_offset:
        _register_candidate(string_end + masked_offset)

    _register_candidate(chunk_end - data_span)

    payload_offset = None
    payload_end = None
    for candidate in candidate_offsets:
        if candidate < string_end:
            continue
        end = candidate + data_span
        if end > chunk_end or end > len(data):
            continue
        payload_offset = candidate
        payload_end = end
        break

    if payload_offset is None or payload_end is None:
        raise RSFLParsingError("RSCF payload exceeds chunk bounds")

    relative_name = normalize_relative_path(name)

    entry = {
        "layout": "rscf",
        "name": name,
        "relative_path": str(relative_name),
        "offset": payload_offset,
        "size": data_span,
        "raw_offset": None,
        "table_offset": None,
        "offset_anchor": payload_offset,
        "anchor_kind": "absolute",
        "chunk_offset": chunk_offset,
        "chunk_size": chunk_size,
        "header_offset": header_offset,
        "header_version": version,
        "header_data_offset": data_offset,
        "header_data_span": data_span,
    }

    return [entry]


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
        relative_name = normalize_relative_path(entry["name"])
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
                "layout": "rsfl",
            }
        )
    return normalised


def load_archive(
    archive_path: Path,
) -> Tuple[bytes, Dict[str, object], List[Dict[str, object]], Dict[str, object]]:
    """Read an Asura archive and return its bytes, metadata and entries."""

    original_bytes = archive_path.read_bytes()
    data, wrapper = _unwrap_asura_container(original_bytes)
    layout_info = _scan_for_rsfl(data)

    layout = layout_info.get("layout")
    entries: List[Dict[str, object]] = []

    if layout == "rsfl":
        chunk = layout_info["chunks"][0]
        rsfl_details = chunk.get("rsfl") or {}
        rsfl_offset = int(chunk["offset"])
        rsfl_chunk_size = int(chunk["chunk_size"])
        rsfl_type1 = int(rsfl_details.get("type1", 0))
        rsfl_type2 = int(rsfl_details.get("type2", 0))
        entry_count = int(rsfl_details.get("entry_count", 0))

        entries_raw, table_end = _parse_rsfl_entries(
            data, rsfl_offset, rsfl_chunk_size, entry_count
        )
        entries = _normalise_entries(entries_raw, data, rsfl_offset, rsfl_chunk_size)

        chunk_info: Dict[str, object] = {
            "layout": "rsfl",
            "offset": rsfl_offset,
            "chunk_size": rsfl_chunk_size,
            "type1": rsfl_type1,
            "type2": rsfl_type2,
            "table_end": table_end,
            "entry_count": entry_count,
        }
    elif layout == "rscf":
        chunk_info = {
            "layout": "rscf",
            "chunks": [],
        }
        for chunk in layout_info.get("chunks", []):
            chunk_entries = _parse_rscf_entries(data, chunk)
            entries.extend(chunk_entries)
            chunk_info["chunks"].append(
                {
                    "offset": int(chunk["offset"]),
                    "chunk_size": int(chunk["chunk_size"]),
                    "type1": int(chunk["type1"]),
                    "type2": int(chunk["type2"]),
                    "header": dict(chunk.get("rscf") or {}),
                }
            )
    else:  # pragma: no cover - defensive, should not happen
        raise RSFLParsingError("unsupported resource layout")

    return data, chunk_info, entries, wrapper


def is_image_entry(entry_name: str) -> bool:
    """Return True if the entry looks like an image based on its extension."""

    suffix = Path(entry_name).suffix.lower()
    return suffix in IMAGE_EXTENSIONS


def extract_archive(archive_path: Path, output_dir: Path) -> Path:
    """Extract RSFL controlled files and write a manifest.

    Returns the path to the generated manifest file.
    """

    data, rsfl_info, entries, wrapper = load_archive(archive_path)

    archive_name = archive_path.name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Dump all files controlled by the RSFL table.
    extracted_files: List[Dict[str, object]] = []
    for entry in entries:
        payload = data[entry["offset"] : entry["offset"] + entry["size"]]
        relative_path = entry["relative_path"]
        relative_target = Path(*relative_path.split("/")) if relative_path else Path()
        target_path = output_dir / relative_target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)
        extracted_files.append(entry)

    manifest = {
        "archive": archive_name,
        "rsfl": rsfl_info,
        "wrapper": wrapper,
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

        layout = entry.get("layout", "rsfl")

        if layout == "rscf":
            if new_size != entry["size"]:
                raise RSFLParsingError(
                    f"replacement for {rel_path} must preserve the original size in RSCF archives"
                )
            updated[start:end] = payload
            entry["offset"] = start
            entry["size"] = new_size
            continue

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

    archive_bytes, _rsfl_info, entries, wrapper = load_archive(original_archive)
    manifest_wrapper = manifest.get("wrapper") or {"kind": "raw"}
    if manifest_wrapper.get("kind") != wrapper.get("kind"):
        raise RSFLParsingError(
            "manifest was generated from an archive with a different compression wrapper"
        )
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
    wrapped = _wrap_asura_container(bytes(updated), wrapper)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(wrapped)


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
        self.wrapper_info: Dict[str, object] | None = None

        self._build_ui()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)

        list_frame = tk.Frame(self.root)
        list_frame.grid(row=0, column=0, sticky="nsew")

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self._on_entry_selected)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        preview_frame = tk.Frame(self.root, borderwidth=1, relief=tk.SUNKEN)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 10), pady=10)
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.columnconfigure(1, weight=0)

        self.preview_canvas = tk.Canvas(preview_frame, highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        self.preview_vscroll = tk.Scrollbar(
            preview_frame, orient=tk.VERTICAL, command=self.preview_canvas.yview
        )
        self.preview_vscroll.grid(row=0, column=1, sticky="ns", rowspan=2)

        self.preview_hscroll = tk.Scrollbar(
            preview_frame, orient=tk.HORIZONTAL, command=self.preview_canvas.xview
        )
        self.preview_hscroll.grid(row=1, column=0, sticky="ew")

        self.preview_canvas.configure(
            yscrollcommand=self.preview_vscroll.set,
            xscrollcommand=self.preview_hscroll.set,
        )

        self.preview_inner = tk.Frame(self.preview_canvas)
        self.preview_window = self.preview_canvas.create_window(
            (0, 0), window=self.preview_inner, anchor="nw"
        )

        def _update_scroll_region(event: object) -> None:
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

        self.preview_inner.bind("<Configure>", _update_scroll_region)

        def _on_mousewheel(event: object) -> str | None:
            delta = getattr(event, "delta", 0)
            if delta:
                step = int(delta / 120) if delta % 120 == 0 else int(delta / abs(delta))
                if getattr(event, "state", 0) & 0x0001:  # Shift pressed
                    self.preview_canvas.xview_scroll(-step, "units")
                else:
                    self.preview_canvas.yview_scroll(-step, "units")
                return "break"

        def _on_shift_wheel(event: object) -> str | None:
            delta = getattr(event, "delta", 0)
            if delta:
                step = int(delta / 120) if delta % 120 == 0 else int(delta / abs(delta))
                self.preview_canvas.xview_scroll(-step, "units")
                return "break"

        def _on_wheel_up(event: object) -> str:
            self.preview_canvas.yview_scroll(-1, "units")
            return "break"

        def _on_wheel_down(event: object) -> str:
            self.preview_canvas.yview_scroll(1, "units")
            return "break"

        self.preview_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.preview_canvas.bind("<Shift-MouseWheel>", _on_shift_wheel)
        self.preview_canvas.bind("<Button-4>", _on_wheel_up)
        self.preview_canvas.bind("<Button-5>", _on_wheel_down)

        self.preview_label = tk.Label(
            self.preview_inner,
            text="Select a texture to preview",
            anchor="center",
            justify="center",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        self.preview_image = None
        self.preview_source_image = None

        channel_frame = tk.Frame(preview_frame)
        channel_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 2))
        for column in range(4):
            channel_frame.columnconfigure(column, weight=1)

        self.channel_vars = {}
        self.channel_buttons = {}
        for idx, channel in enumerate("RGBA"):
            var = tk.IntVar(value=1)
            btn = tk.Checkbutton(
                channel_frame,
                text=channel,
                variable=var,
                command=self._update_channel_preview,
            )
            btn.grid(row=0, column=idx, padx=2)
            self.channel_vars[channel] = var
            self.channel_buttons[channel] = btn
        self._set_channel_controls_state("disabled")

        button_frame = tk.Frame(self.root)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
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
        status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

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

    def _update_preview_scrollregion(self, reset_position: bool = False) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        bbox = self.preview_canvas.bbox("all")
        if bbox is None:
            bbox = (0, 0, 0, 0)
        self.preview_canvas.configure(scrollregion=bbox)
        if reset_position:
            self.preview_canvas.xview_moveto(0)
            self.preview_canvas.yview_moveto(0)

    def _clear_preview(self, message: str | None = None) -> None:
        if message is None:
            message = "Select a texture to preview"
        if hasattr(self.preview_label, "configure"):
            self.preview_label.configure(image="", text=message)
            self.preview_label.image = None
        self._update_preview_scrollregion(reset_position=True)
        self.preview_image = None
        self.preview_source_image = None
        self._set_channel_controls_state("disabled")

    def _set_channel_controls_state(self, state: str) -> None:
        for button in self.channel_buttons.values():
            button.configure(state=state)
        if state == "disabled":
            for var in self.channel_vars.values():
                var.set(1)

    def _update_channel_preview(self) -> None:
        if self.preview_source_image is None or not PIL_IMAGETK_AVAILABLE:
            return

        rgba = self.preview_source_image.split()
        if len(rgba) != 4:
            # Defensive: ensure we always have 4 channels to merge.
            self.preview_label.configure(image="", text="Unsupported image mode")
            self.preview_label.image = None
            self.preview_image = None
            return

        r, g, b, a = rgba
        if not self.channel_vars["R"].get():
            r = Image.new("L", self.preview_source_image.size, 0)
        if not self.channel_vars["G"].get():
            g = Image.new("L", self.preview_source_image.size, 0)
        if not self.channel_vars["B"].get():
            b = Image.new("L", self.preview_source_image.size, 0)
        if not self.channel_vars["A"].get():
            a = Image.new("L", self.preview_source_image.size, 255)

        composed = Image.merge("RGBA", (r, g, b, a))
        photo = ImageTk.PhotoImage(composed)
        self.preview_label.configure(image=photo, text="")
        self.preview_label.image = photo
        self.preview_image = photo
        self._update_preview_scrollregion()

    def _on_entry_selected(self, _event: object) -> None:
        if self.archive_bytes is None or not self.entries:
            self._clear_preview("Open an archive to preview textures")
            return

        selection = self.listbox.curselection()
        if not selection:
            self._clear_preview()
            return

        if not PIL_AVAILABLE:
            self._clear_preview("Pillow is not installed; preview unavailable")
            self._set_status(
                "Preview unavailable: install Pillow to enable texture previews"
            )
            return

        if not PIL_IMAGETK_AVAILABLE:
            self._clear_preview("Install Pillow's ImageTk support to preview textures")
            self._set_status(
                "Preview unavailable: install pillow[tk] or python3-tk for ImageTk"
            )
            return

        index = selection[-1]
        entry = self.entries[index]
        payload = self.archive_bytes[entry["offset"] : entry["offset"] + entry["size"]]
        if not payload:
            self._clear_preview("Empty payload; nothing to preview")
            self._set_status(f"Entry {entry['relative_path']} has no data to preview")
            return

        format_hint = None
        detected_format = None
        try:
            stream = io.BytesIO(payload)
            if payload.startswith(b"DDS "):
                format_hint = "DDS"
            image = Image.open(stream)
            image.load()
            detected_format = image.format
            image = image.convert("RGBA")
            photo = ImageTk.PhotoImage(image)
        except UnidentifiedImageError as exc:
            self._clear_preview("Unsupported texture format")
            self._set_status(
                f"Unsupported texture format for {entry['relative_path']}: {exc}"
            )
            return
        except Exception as exc:  # pragma: no cover - depends on payload contents
            self._clear_preview("Unable to preview texture")
            self._set_status(
                f"Failed to render {entry['relative_path']}: {exc}".strip()
            )
            return

        self.preview_source_image = image
        self._set_channel_controls_state("normal")
        self.preview_label.configure(image=photo, text="")
        self.preview_label.image = photo
        self.preview_image = photo
        self._update_preview_scrollregion(reset_position=True)
        format_display = format_hint or detected_format or "unknown"
        self._set_status(f"Previewing {entry['relative_path']} ({format_display})")
        self._update_channel_preview()

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
            data, _rsfl_info, entries, wrapper = load_archive(Path(filename))
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
        self.wrapper_info = wrapper
        self._refresh_list()
        self._clear_preview()
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
            relative_path = entry["relative_path"]
            relative_target = Path(*relative_path.split("/")) if relative_path else Path()
            target = destination_path / relative_target
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

        wrapped = _wrap_asura_container(bytes(updated), self.wrapper_info or {"kind": "raw"})
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(wrapped)

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
