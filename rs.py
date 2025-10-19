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
import mmap
import os
import shutil
import struct
import threading
import zlib
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Set, Tuple

import copy

tk = None
filedialog = None
messagebox = None
try:
    # Tkinter is optional – only needed when launching the GUI helper.
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

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

# Files above this size will be memory-mapped instead of fully loaded into RAM.
MEMORY_MAP_THRESHOLD = int(os.environ.get("RS_MEMORY_MAP_THRESHOLD", 256 * 1024 * 1024))

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

MAGIC_TO_IMAGE_FORMAT = (
    (b"DDS ", "DDS", ".dds"),
    (b"\x89PNG\r\n\x1a\n", "PNG", ".png"),
    (b"BM", "BMP", ".bmp"),
    (b"GIF8", "GIF", ".gif"),
    (b"\xff\xd8\xff", "JPEG", ".jpg"),
    (b"II*\x00", "TIFF", ".tif"),
    (b"MM\x00*", "TIFF", ".tif"),
)


class RSFLParsingError(RuntimeError):
    """Raised when the archive layout does not match expectations."""


def normalize_relative_path(name: str) -> str:
    """Return a normalised relative path using forward slashes."""

    normalised = name.replace("\\", "/")
    return normalised.lstrip("/")


def _unwrap_asura_container(
    data: bytes | mmap.mmap,
) -> Tuple[bytes | mmap.mmap, Dict[str, object]]:
    """Return the raw Asura archive payload and compression metadata."""

    if data[: len(ASURA_MAGIC)] == ASURA_MAGIC:
        return data, {"kind": "raw"}

    if data[: len(ASURA_ZLB_MAGIC)] == ASURA_ZLB_MAGIC:
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

    if data[: len(ASURA_ZBB_MAGIC)] == ASURA_ZBB_MAGIC:
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


def _write_bytes_in_chunks(
    path: Path,
    data: bytes,
    *,
    chunk_size: int = 2 * 1024 * 1024,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> Tuple[str, Exception | None]:
    """Write *data* to *path* in chunks while reporting progress.

    Returns a tuple ``(status, error)`` where *status* is ``"success"``,
    ``"cancelled"``, or ``"error"``.  When an error occurs, *error* contains the
    exception raised while attempting to write the file.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    total = len(data)
    written = 0
    status = "success"

    try:
        with path.open("wb") as handle:
            if total == 0 and progress_callback is not None:
                progress_callback(0)

            for start in range(0, total, chunk_size):
                if cancel_event is not None and cancel_event.is_set():
                    status = "cancelled"
                    break

                chunk = data[start : start + chunk_size]
                handle.write(chunk)
                written += len(chunk)
                if progress_callback is not None:
                    progress_callback(written)

        if status != "success":
            try:
                path.unlink()
            except FileNotFoundError:
                pass

        return status, None

    except Exception as exc:  # pragma: no cover - depends on filesystem errors.
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return "error", exc


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


def _read_archive_bytes(path: Path) -> bytes | mmap.mmap:
    """Return the bytes for ``path`` using a memory map when appropriate."""

    try:
        size = path.stat().st_size
    except OSError as exc:  # pragma: no cover - filesystem dependent
        raise RSFLParsingError(f"unable to stat archive: {exc}") from exc

    if size >= max(0, MEMORY_MAP_THRESHOLD):
        flags = os.O_RDONLY
        # Windows requires the O_BINARY flag to avoid implicit newline conversion.
        flags |= getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        try:
            return mmap.mmap(fd, length=0, access=mmap.ACCESS_READ)
        finally:
            os.close(fd)

    return path.read_bytes()


def _release_archive_buffer(buffer: object) -> None:
    """Release buffers that expose a ``close`` method (e.g. memory maps)."""

    close = getattr(buffer, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass


def load_archive(
    archive_path: Path,
) -> Tuple[bytes | mmap.mmap, Dict[str, object], List[Dict[str, object]], Dict[str, object]]:
    """Read an Asura archive and return its bytes, metadata and entries."""

    original_bytes = _read_archive_bytes(archive_path)
    data, wrapper = _unwrap_asura_container(original_bytes)
    if data is not original_bytes:
        _release_archive_buffer(original_bytes)
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


def detect_image_format(payload: bytes) -> Tuple[str | None, str | None]:
    """Return a tuple of (format_name, extension) for recognised image payloads."""

    for magic, format_name, extension in MAGIC_TO_IMAGE_FORMAT:
        if payload.startswith(magic):
            return format_name, extension
    return None, None


def resolve_export_relative_path(relative_path: str, payload: bytes) -> Tuple[str, str | None]:
    """Return the preferred export path for ``relative_path`` based on ``payload``."""

    original = Path(*relative_path.split("/")) if relative_path else Path()
    _, extension = detect_image_format(payload)
    if extension and original.suffix.lower() != extension:
        adjusted = original.with_suffix(extension)
        return str(adjusted.as_posix()), str(original.as_posix())
    return str(original.as_posix()), None


def extract_archive(archive_path: Path, output_dir: Path) -> Path:
    """Extract RSFL controlled files and write a manifest.

    Returns the path to the generated manifest file.
    """

    data, rsfl_info, entries, wrapper = load_archive(archive_path)

    try:
        archive_name = archive_path.name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Dump all files controlled by the RSFL table.
        extracted_files: List[Dict[str, object]] = []
        for entry in entries:
            payload = data[entry["offset"] : entry["offset"] + entry["size"]]
            relative_path = entry["relative_path"]
            export_relative, original_relative = resolve_export_relative_path(
                relative_path, payload
            )
            relative_target = (
                Path(*export_relative.split("/")) if export_relative else Path()
            )
            target_path = output_dir / relative_target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(payload)
            entry_copy = dict(entry)
            if original_relative is not None:
                entry_copy["exported_path"] = export_relative
                entry_copy["original_path"] = original_relative
            extracted_files.append(entry_copy)

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
    finally:
        _release_archive_buffer(data)


def _apply_replacements(
    archive_bytes: bytes | mmap.mmap,
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
            chunk_offset = entry.get("chunk_offset")
            header_offset = entry.get("header_offset")
            if chunk_offset is None or header_offset is None:
                raise RSFLParsingError(
                    f"replacement for {rel_path} is missing chunk metadata"
                )

            old_size = entry["size"]
            delta = new_size - old_size

            updated[start:end] = payload
            entry["offset"] = start
            entry["size"] = new_size

            struct.pack_into("<I", updated, header_offset + 8, new_size)
            entry["header_data_span"] = new_size

            if delta:
                new_chunk_size = entry["chunk_size"] + delta
                if new_chunk_size <= 0:
                    raise RSFLParsingError(
                        f"replacement for {rel_path} would shrink the RSCF chunk below zero bytes"
                    )

                struct.pack_into("<I", updated, chunk_offset + 4, new_chunk_size)
                entry["chunk_size"] = new_chunk_size

                for other in entries:
                    if other is entry:
                        continue
                    if other.get("layout") != "rscf":
                        continue
                    other_chunk_offset = other.get("chunk_offset")
                    if other_chunk_offset is None:
                        continue
                    if other_chunk_offset <= chunk_offset:
                        continue

                    other["chunk_offset"] = other_chunk_offset + delta
                    other_offset = other.get("offset")
                    if other_offset is not None:
                        other["offset"] = other_offset + delta
                    other_anchor = other.get("offset_anchor")
                    if other_anchor is not None:
                        other["offset_anchor"] = other_anchor + delta
                    other_header_offset = other.get("header_offset")
                    if other_header_offset is not None:
                        other["header_offset"] = other_header_offset + delta

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


def _collect_replacement_payloads(
    files_info: Sequence[Dict[str, object]],
    modified_dir: Path,
) -> Dict[str, bytes]:
    """Return payloads for files that exist inside *modified_dir*."""

    replacements: Dict[str, bytes] = {}
    for manifest_entry in files_info:
        rel_path = manifest_entry.get("relative_path")
        if not isinstance(rel_path, str) or not rel_path:
            continue

        candidates: List[str] = []
        exported_relative = manifest_entry.get("exported_path")
        if isinstance(exported_relative, str) and exported_relative:
            candidates.append(exported_relative)
        candidates.append(rel_path)

        payload_path: Path | None = None
        for candidate in candidates:
            candidate_path = modified_dir / Path(*candidate.split("/"))
            if candidate_path.exists():
                payload_path = candidate_path
                break

        if payload_path is None:
            continue

        replacements[rel_path] = payload_path.read_bytes()

    return replacements


def _extract_chunk_type_overrides(
    layout_info: Dict[str, object],
    archive_bytes: bytes | mmap.mmap | None,
) -> Dict[int, Tuple[int, int]]:
    """Return chunk header type overrides keyed by chunk offset."""

    overrides: Dict[int, Tuple[int, int]] = {}
    if not archive_bytes:
        return overrides

    layout = layout_info.get("layout")
    if layout == "rscf":
        for chunk in layout_info.get("chunks", []):
            offset = int(chunk.get("offset", -1))
            if offset < 0:
                continue
            try:
                _magic, _size, type1, type2 = CHUNK_HEADER.unpack_from(archive_bytes, offset)
            except struct.error:
                continue
            overrides[offset] = (type1, type2)
    elif layout == "rsfl":
        offset = int(layout_info.get("offset", -1))
        if offset >= 0:
            try:
                _magic, _size, type1, type2 = CHUNK_HEADER.unpack_from(archive_bytes, offset)
            except struct.error:
                type1 = type2 = 0
            overrides[offset] = (type1, type2)

    return overrides


def _encode_rscf_chunk(
    *,
    type1: int,
    type2: int,
    version: int,
    data_offset: int,
    name: str,
    payload: bytes,
) -> bytes:
    """Return the bytes for a single RSCF chunk."""

    try:
        encoded_name = name.encode("utf-8")
    except UnicodeEncodeError:
        encoded_name = name.encode("latin-1", errors="replace")
    encoded_name += b"\x00"
    while len(encoded_name) % 4:
        encoded_name += b"\x00"

    rscf_header = struct.pack("<III", version & 0xFFFFFFFF, data_offset & 0xFFFFFFFF, len(payload))
    chunk_body = bytearray()
    chunk_body.extend(rscf_header)
    chunk_body.extend(encoded_name)
    chunk_body.extend(payload)

    chunk_size = CHUNK_HEADER.size + len(chunk_body)
    chunk_header = CHUNK_HEADER.pack(b"RSCF", chunk_size, type1 & 0xFFFFFFFF, type2 & 0xFFFFFFFF)
    return chunk_header + bytes(chunk_body)


def _build_rscf_patch(
    layout_info: Dict[str, object],
    patch_entries: Sequence[Tuple[Dict[str, object], bytes]],
    chunk_type_overrides: Dict[int, Tuple[int, int]],
) -> Tuple[bytes, List[str]]:
    """Return a patch archive for RSCF controlled entries."""

    archive = bytearray(ASURA_MAGIC)
    chunk_map = {int(chunk.get("offset", -1)): chunk for chunk in layout_info.get("chunks", [])}
    written: List[str] = []

    for manifest_entry, payload in patch_entries:
        rel_path = manifest_entry["relative_path"]
        chunk_offset = int(manifest_entry.get("chunk_offset", -1))
        chunk_details = chunk_map.get(chunk_offset) or {}
        type1, type2 = chunk_type_overrides.get(chunk_offset, (0, 0))
        if not type1 and not type2:
            type1 = int(chunk_details.get("type1", 0))
            type2 = int(chunk_details.get("type2", 0))

        header = dict(chunk_details.get("header") or {})
        version = int(manifest_entry.get("header_version", header.get("version", 0)))
        data_offset = int(
            manifest_entry.get("header_data_offset", header.get("data_offset", 0))
        )
        name = manifest_entry.get("name") or rel_path.replace("/", "\\")

        archive.extend(
            _encode_rscf_chunk(
                type1=type1,
                type2=type2,
                version=version,
                data_offset=data_offset,
                name=name,
                payload=payload,
            )
        )
        written.append(rel_path)

    return bytes(archive), written


def _build_rsfl_patch(
    layout_info: Dict[str, object],
    patch_entries: Sequence[Tuple[Dict[str, object], bytes]],
    chunk_type_overrides: Dict[int, Tuple[int, int]],
) -> Tuple[bytes, List[str]]:
    """Return a patch archive for RSFL controlled entries."""

    if not patch_entries:
        return b"", []

    archive = bytearray(ASURA_MAGIC)
    table = bytearray()
    struct_offsets: List[int] = []
    payload_offsets: List[int] = []
    payload_area = bytearray()
    written: List[str] = []

    for manifest_entry, payload in patch_entries:
        rel_path = manifest_entry["relative_path"]
        name = manifest_entry.get("name") or rel_path.replace("/", "\\")
        try:
            encoded = name.encode("utf-8")
        except UnicodeEncodeError:
            encoded = name.encode("latin-1", errors="replace")
        encoded += b"\x00"
        while len(encoded) % 4:
            encoded += b"\x00"
        table.extend(encoded)
        struct_offsets.append(len(table))
        table.extend(b"\x00" * RSFL_ENTRY_STRUCT.size)

        padding = (-len(payload_area)) % 4
        if padding:
            payload_area.extend(b"\x00" * padding)
        payload_offsets.append(len(payload_area))
        payload_area.extend(payload)
        written.append(rel_path)

    rsfl_type1 = int(layout_info.get("type1", 0))
    rsfl_type2 = int(layout_info.get("type2", 0))
    inner_size = RSFL_CHUNK_HEADER.size + len(table) + len(payload_area)
    count = len(patch_entries)

    # Populate RSFL entry structs now that we know the final layout.
    for (manifest_entry, payload), struct_offset, payload_offset in zip(
        patch_entries, struct_offsets, payload_offsets
    ):
        raw_offset = CHUNK_HEADER.size + RSFL_CHUNK_HEADER.size + len(table) + payload_offset
        if raw_offset > 0xFFFFFFFF:
            raise RSFLParsingError(
                f"replacement for {manifest_entry['relative_path']} exceeds 32-bit offset capacity"
            )
        unk = int(manifest_entry.get("unk", 0)) & 0xFFFFFFFF
        RSFL_ENTRY_STRUCT.pack_into(table, struct_offset, raw_offset, len(payload), unk)

    chunk_body = bytearray()
    chunk_body.extend(
        RSFL_CHUNK_HEADER.pack(0x5246534C, inner_size, rsfl_type1 & 0xFFFFFFFF, rsfl_type2 & 0xFFFFFFFF, count)
    )
    chunk_body.extend(table)
    chunk_body.extend(payload_area)

    chunk_size = CHUNK_HEADER.size + len(chunk_body)
    chunk_offset = int(layout_info.get("offset", 8))
    type1, type2 = chunk_type_overrides.get(chunk_offset, (0, 0))
    chunk_header = CHUNK_HEADER.pack(b"LFSR", chunk_size, type1 & 0xFFFFFFFF, type2 & 0xFFFFFFFF)

    archive.extend(chunk_header)
    archive.extend(chunk_body)
    return bytes(archive), written


def generate_patch_archive(
    manifest: Dict[str, object],
    replacements: Dict[str, bytes],
    *,
    archive_bytes: bytes | mmap.mmap | None = None,
    original_entries: Sequence[Dict[str, object]] | None = None,
) -> Tuple[bytes, List[str]]:
    """Build a minimal Asura archive containing the provided replacements."""

    files_info = manifest.get("files", [])
    if not files_info:
        raise RSFLParsingError("manifest does not contain any file entries")

    layout_info = manifest.get("rsfl") or {}
    layout_kind = layout_info.get("layout")
    if layout_kind not in {"rsfl", "rscf"}:
        raise RSFLParsingError("manifest does not describe a supported layout")

    manifest_index = {entry.get("relative_path"): entry for entry in files_info}
    entry_index = (
        {entry.get("relative_path"): entry for entry in original_entries}
        if original_entries
        else {}
    )

    patch_entries: List[Tuple[Dict[str, object], bytes]] = []
    for rel_path, payload in replacements.items():
        manifest_entry = manifest_index.get(rel_path)
        if manifest_entry is None:
            continue

        if original_entries is not None and archive_bytes is not None:
            original_entry = entry_index.get(rel_path)
            if original_entry is None:
                continue
            start = int(original_entry.get("offset", 0))
            size = int(original_entry.get("size", 0))
            original_payload = archive_bytes[start : start + size]
            if payload == original_payload:
                continue

        patch_entries.append((manifest_entry, payload))

    if not patch_entries:
        raise RSFLParsingError("no modified files differ from the original archive")

    overrides = _extract_chunk_type_overrides(layout_info, archive_bytes)

    if layout_kind == "rscf":
        return _build_rscf_patch(layout_info, patch_entries, overrides)
    return _build_rsfl_patch(layout_info, patch_entries, overrides)


def write_patch_archive(
    original_archive: Path,
    manifest_path: Path,
    modified_dir: Path,
    output_path: Path,
) -> List[str]:
    """Write a minimal patch archive for files modified in ``modified_dir``."""

    manifest = json.loads(manifest_path.read_text())
    if original_archive.name != manifest.get("archive"):
        raise RSFLParsingError(
            "original archive file name does not match manifest metadata"
        )

    files_info = manifest.get("files", [])
    if not files_info:
        raise RSFLParsingError("manifest does not contain any file entries")

    archive_bytes, layout_info, entries, _wrapper = load_archive(original_archive)
    try:
        replacements = _collect_replacement_payloads(files_info, modified_dir)
        if not replacements:
            raise RSFLParsingError("no modified files found in the provided directory")

        patch_bytes, written = generate_patch_archive(
            {"rsfl": layout_info, "files": files_info, "archive": manifest.get("archive")},
            replacements,
            archive_bytes=archive_bytes,
            original_entries=entries,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(patch_bytes)
        return written
    finally:
        _release_archive_buffer(archive_bytes)


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

    archive_bytes, layout_info, entries, wrapper = load_archive(original_archive)
    try:
        manifest_wrapper = manifest.get("wrapper") or {"kind": "raw"}
        if manifest_wrapper.get("kind") != wrapper.get("kind"):
            raise RSFLParsingError(
                "manifest was generated from an archive with a different compression wrapper"
            )
        replacements = _collect_replacement_payloads(files_info, modified_dir)
        if not replacements:
            raise RSFLParsingError("no modified files found in the provided directory")

        updated, _ = _apply_replacements(archive_bytes, entries, replacements)
        wrapped = _wrap_asura_container(bytes(updated), wrapper)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(wrapped)
    finally:
        _release_archive_buffer(archive_bytes)


class TextureManagerGUI:
    """Minimal Tk based browser for previewing and patching texture entries."""

    def __init__(self) -> None:
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is not available on this platform")

        self.root = tk.Tk()
        self.root.title("RSFL Texture Manager")
        self.root.geometry("720x480")

        self.archive_path: Path | None = None
        self.archive_bytes: bytes | mmap.mmap | None = None
        self.all_entries: List[Dict[str, object]] = []
        self.entries: List[Dict[str, object]] = []
        self.replacements: Dict[str, bytes] = {}
        self.wrapper_info: Dict[str, object] | None = None
        self.layout_info: Dict[str, object] | None = None
        self.node_to_entry: Dict[str, Dict[str, object]] = {}
        self.entry_nodes: Dict[str, str] = {}
        self.node_to_path: Dict[str, Tuple[str, ...]] = {}
        self.last_activated_path: str | None = None
        self._expand_all_on_refresh = False

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)

        list_frame = tk.Frame(self.root)
        list_frame.grid(row=0, column=0, sticky="nsew")

        list_frame.rowconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=0)
        list_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("size",),
            show="tree headings",
            selectmode="extended",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.column("#0", anchor="w", stretch=True, width=360)
        self.tree.column("size", anchor="e", stretch=False, width=140)
        self.tree.bind("<<TreeviewSelect>>", self._on_entry_selected)
        self.tree.bind("<ButtonRelease-1>", self._remember_last_active)
        self.tree.tag_configure("modified", foreground="#d9534f")

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        control_frame = tk.Frame(list_frame)
        control_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        tk.Button(control_frame, text="Expand All", command=self._expand_all_nodes).grid(
            row=0, column=0, padx=2, sticky="ew"
        )
        tk.Button(control_frame, text="Collapse All", command=self._collapse_all_nodes).grid(
            row=0, column=1, padx=2, sticky="ew"
        )

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
        for i in range(6):
            button_frame.columnconfigure(i, weight=1)

        tk.Button(button_frame, text="Open Archive", command=self.open_archive).grid(
            row=0, column=0, padx=4
        )
        tk.Button(button_frame, text="Export Selected", command=self.export_selected).grid(
            row=0, column=1, padx=4
        )
        tk.Button(button_frame, text="Export All", command=self.export_all).grid(
            row=0, column=2, padx=4
        )
        tk.Button(button_frame, text="Import Replacement", command=self.import_replacement).grid(
            row=0, column=3, padx=4
        )
        tk.Button(button_frame, text="Create Patch", command=self.create_patch_archive).grid(
            row=0, column=4, padx=4
        )
        tk.Button(button_frame, text="Save Patched Archive", command=self.save_patched_archive).grid(
            row=0, column=5, padx=4
        )

        self.status = tk.StringVar(
            value=(
                "Select an archive to begin. "
                "'Save Patched Archive' writes a full copy while "
                "'Create Patch' exports only modified files."
            )
        )
        status_bar = tk.Label(self.root, textvariable=self.status, anchor="w")
        status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

    # ------------------------------------------------------------- utilities --
    def _refresh_list(self) -> None:
        if not hasattr(self, "tree"):
            return

        selected_paths = []
        for node_id in self.tree.selection():
            entry = self.node_to_entry.get(node_id)
            if entry is not None:
                selected_paths.append(entry["relative_path"])

        if self._expand_all_on_refresh:
            expanded_paths: Set[Tuple[str, ...]] | None = None
        else:
            expanded_paths = {
                path
                for node_id, path in self.node_to_path.items()
                if path
                and self.tree.exists(node_id)
                and self.tree.item(node_id, "open")
            }

        children = self.tree.get_children("")
        if children:
            self.tree.delete(*children)

        self.node_to_entry.clear()
        self.entry_nodes.clear()
        self.node_to_path.clear()

        folder_nodes: Dict[Tuple[str, ...], str] = {(): ""}

        def ensure_folder(path_segments: Sequence[str]) -> str:
            key = tuple(path_segments)
            if key in folder_nodes:
                return folder_nodes[key]

            parent_id = ensure_folder(path_segments[:-1]) if path_segments else ""
            node_text = path_segments[-1]
            path_tuple = tuple(path_segments)
            should_open = self._expand_all_on_refresh or (
                expanded_paths is not None and path_tuple in expanded_paths
            )
            node_id = self.tree.insert(
                parent_id,
                "end",
                text=node_text,
                values=("",),
                open=should_open,
            )
            folder_nodes[key] = node_id
            self.node_to_path[node_id] = path_tuple
            return node_id

        for entry in self.entries:
            relative_path = entry["relative_path"]
            segments = [segment for segment in relative_path.split("/") if segment]
            parent_segments = segments[:-1]
            parent_id = ensure_folder(parent_segments) if parent_segments else ""
            replacement = self.replacements.get(relative_path)
            size_text = f"{entry['size']} bytes"
            tags: Tuple[str, ...] = ()
            name_display = segments[-1] if segments else relative_path
            if replacement is not None:
                replacement_size = len(replacement)
                if replacement_size != entry["size"]:
                    size_text += f" → {replacement_size} bytes"
                name_display += " *"
                tags = ("modified",)
            node_id = self.tree.insert(
                parent_id,
                "end",
                text=name_display,
                values=(size_text,),
                tags=tags,
            )
            path_tuple = tuple(segments) if segments else (relative_path,)
            self.node_to_entry[node_id] = entry
            self.entry_nodes[relative_path] = node_id
            self.node_to_path[node_id] = path_tuple

        new_selection = [
            self.entry_nodes[path]
            for path in selected_paths
            if path in self.entry_nodes
        ]
        if new_selection:
            self.tree.selection_set(new_selection)
            focus_node = new_selection[-1]
            self.tree.focus(focus_node)
            self.tree.see(focus_node)

        if self.last_activated_path and self.last_activated_path not in self.entry_nodes:
            self.last_activated_path = None

        self._expand_all_on_refresh = False

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
        self.last_activated_path = None

    def _shutdown(self) -> None:
        _release_archive_buffer(self.archive_bytes)
        self.archive_bytes = None
        self.root.destroy()

    def _remember_last_active(self, event: object) -> None:
        if not hasattr(event, "y"):
            return
        try:
            node_id = self.tree.identify_row(event.y)
        except tk.TclError:
            return
        if node_id and node_id in self.node_to_entry:
            entry = self.node_to_entry[node_id]
            self.last_activated_path = entry["relative_path"]

    def _expand_all_nodes(self) -> None:
        for node_id, path in list(self.node_to_path.items()):
            if not path or node_id in self.node_to_entry:
                continue
            try:
                self.tree.item(node_id, open=True)
            except tk.TclError:
                continue

    def _collapse_all_nodes(self) -> None:
        for node_id, path in list(self.node_to_path.items()):
            if not path or node_id in self.node_to_entry:
                continue
            try:
                self.tree.item(node_id, open=False)
            except tk.TclError:
                continue

    def _export_entries(
        self, destination_path: Path, entries: Sequence[Dict[str, object]]
    ) -> Tuple[int, List[Tuple[str, str]]]:
        count = 0
        renamed: List[Tuple[str, str]] = []
        for entry in entries:
            payload = self.archive_bytes[entry["offset"] : entry["offset"] + entry["size"]]
            relative_path = entry["relative_path"]
            export_relative, original_relative = resolve_export_relative_path(
                relative_path, payload
            )
            relative_target = (
                Path(*export_relative.split("/")) if export_relative else Path()
            )
            target = destination_path / relative_target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            if original_relative is not None:
                renamed.append((original_relative, export_relative))
            count += 1
        return count, renamed

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

        selected_nodes = [
            node_id for node_id in self.tree.selection() if node_id in self.node_to_entry
        ]
        if not selected_nodes:
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

        focus_node = self.tree.focus()
        if focus_node not in selected_nodes:
            focus_node = None

        if focus_node is None and self.last_activated_path is not None:
            candidate = self.entry_nodes.get(self.last_activated_path)
            if candidate in selected_nodes:
                focus_node = candidate

        if focus_node is None:
            focus_node = selected_nodes[-1]

        self.tree.focus(focus_node)
        self.tree.see(focus_node)

        entry = self.node_to_entry[focus_node]
        self.last_activated_path = entry["relative_path"]
        replacement = self.replacements.get(entry["relative_path"])
        if replacement is not None:
            payload = replacement
        else:
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

        previous_buffer = self.archive_bytes

        try:
            data, layout_info, entries, wrapper = load_archive(Path(filename))
        except Exception as exc:  # pragma: no cover - GUI path
            messagebox.showerror("Unable to open archive", str(exc))
            return

        all_entries = copy.deepcopy(entries)
        image_entries = [
            entry for entry in all_entries if is_image_entry(entry["relative_path"])
        ]
        if not image_entries:
            messagebox.showinfo(
                "No textures found",
                "The selected archive does not contain recognised image entries.",
            )

        _release_archive_buffer(previous_buffer)
        self.archive_path = Path(filename)
        self.archive_bytes = data
        self.all_entries = all_entries
        self.entries = image_entries
        self.replacements.clear()
        self.wrapper_info = wrapper
        self.layout_info = layout_info
        self._expand_all_on_refresh = True
        self._refresh_list()
        self._clear_preview()
        self._set_status(
            f"Loaded {len(image_entries)} image entries from {self.archive_path.name}"
        )

    def export_selected(self) -> None:
        if self.archive_bytes is None:
            messagebox.showwarning("No archive", "Open an archive before exporting.")
            return

        node_ids = [
            node_id for node_id in self.tree.selection() if node_id in self.node_to_entry
        ]
        if not node_ids:
            messagebox.showinfo("Nothing selected", "Select one or more entries to export.")
            return

        destination = filedialog.askdirectory(title="Select export directory")
        if not destination:
            return

        destination_path = Path(destination)
        entries = [self.node_to_entry[node_id] for node_id in node_ids]
        count, renamed = self._export_entries(destination_path, entries)
        rename_note = (
            f"; adjusted extensions for {len(renamed)} file(s)"
            if renamed
            else ""
        )
        self._set_status(f"Exported {count} file(s) to {destination_path}{rename_note}")

    def export_all(self) -> None:
        if self.archive_bytes is None:
            messagebox.showwarning("No archive", "Open an archive before exporting.")
            return
        if not self.entries:
            messagebox.showinfo("No entries", "Open an archive with textures before exporting.")
            return

        destination = filedialog.askdirectory(title="Select export directory")
        if not destination:
            return

        destination_path = Path(destination)
        count, renamed = self._export_entries(destination_path, self.entries)
        rename_note = (
            f"; adjusted extensions for {len(renamed)} file(s)"
            if renamed
            else ""
        )
        self._set_status(f"Exported {count} file(s) to {destination_path}{rename_note}")

    def import_replacement(self) -> None:
        if self.archive_bytes is None:
            messagebox.showwarning("No archive", "Open an archive before importing replacements.")
            return

        node_ids = [
            node_id for node_id in self.tree.selection() if node_id in self.node_to_entry
        ]
        if len(node_ids) != 1:
            messagebox.showinfo(
                "Select a texture",
                "Choose a single texture entry before importing a replacement.",
            )
            return

        entry = self.node_to_entry[node_ids[0]]
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
        node_id = self.entry_nodes.get(entry["relative_path"])
        if node_id is not None:
            self.tree.selection_set(node_id)
            self.tree.focus(node_id)
            self.tree.see(node_id)
            self.last_activated_path = entry["relative_path"]
            self._on_entry_selected(None)
        self._set_status(
            f"Queued replacement for {entry['relative_path']} ({len(payload)} bytes)"
        )

    def _ask_patch_destination(
        self,
        archive_output: Path,
        *,
        require_confirmation: bool = True,
    ) -> Path | None:
        """Return the destination path for an optional patch archive."""

        if self.layout_info is None:
            return None

        default_patch = archive_output.with_suffix(archive_output.suffix + ".patch.asr")
        if require_confirmation:
            try:
                confirm = messagebox.askyesno(
                    "Create patch archive?",
                    "Would you like to generate a separate patch archive containing only the modified files?",
                )
            except tk.TclError:
                confirm = False

            if not confirm:
                return None

        filename = filedialog.asksaveasfilename(
            title="Save patch archive",
            defaultextension=".asr",
            initialfile=default_patch.name,
            filetypes=[
                ("Asura archives", "*.asr *.pc *.es *.en *.fr *.de"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return None
        return Path(filename)

    def _create_patch_archive(
        self,
        patch_path: Path,
        replacements: Dict[str, bytes],
        *,
        archive_bytes: bytes | mmap.mmap | None = None,
        entries: Sequence[Dict[str, object]] | None = None,
    ) -> List[str]:
        """Write a patch archive reflecting *replacements* to *patch_path*."""

        archive_bytes = archive_bytes if archive_bytes is not None else self.archive_bytes
        entries = entries if entries is not None else self.all_entries

        if archive_bytes is None or self.layout_info is None or entries is None:
            raise RSFLParsingError("open an archive before creating a patch")

        manifest = {
            "archive": self.archive_path.name if self.archive_path else "",
            "rsfl": copy.deepcopy(self.layout_info),
            "files": [copy.deepcopy(entry) for entry in entries],
        }

        patch_bytes, written = generate_patch_archive(
            manifest,
            replacements,
            archive_bytes=archive_bytes,
            original_entries=entries,
        )

        if not written:
            raise RSFLParsingError("no replacements require a patch archive")

        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_bytes(patch_bytes)
        return written

    def create_patch_archive(self) -> None:
        if self.archive_bytes is None or self.archive_path is None:
            messagebox.showwarning(
                "No archive", "Open an archive before creating a patch."
            )
            return
        if not self.replacements:
            messagebox.showinfo("No replacements", "Import at least one texture first.")
            return

        patch_destination = self._ask_patch_destination(
            self.archive_path, require_confirmation=False
        )
        if patch_destination is None:
            return

        pending_replacements = dict(self.replacements)

        try:
            written = self._create_patch_archive(patch_destination, pending_replacements)
        except RSFLParsingError as exc:  # pragma: no cover - GUI path
            messagebox.showinfo("Patch archive not created", str(exc))
            return
        except Exception as exc:  # pragma: no cover - GUI path
            messagebox.showerror("Unable to create patch archive", str(exc))
            return

        count = len(written)
        self._set_status(
            f"Patch archive written to {patch_destination} ({count} file(s))"
        )
        messagebox.showinfo(
            "Patch archive saved",
            (
                f"Patch archive written to {patch_destination} ({count} file(s))\n"
                "Use 'Save Patched Archive' to write the full archive if you need a complete file."
            ),
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

        previous_buffer = self.archive_bytes
        staged_entries = copy.deepcopy(self.all_entries)
        pending_replacements = dict(self.replacements)

        try:
            updated, updated_entries = _apply_replacements(
                previous_buffer, staged_entries, self.replacements
            )
        except Exception as exc:  # pragma: no cover - GUI path
            messagebox.showerror("Unable to apply replacements", str(exc))
            return

        new_archive_bytes = bytes(updated)
        wrapped = _wrap_asura_container(new_archive_bytes, self.wrapper_info or {"kind": "raw"})
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_size = len(wrapped)
        maximum = max(total_size, 1)
        self._set_status("Saving patched archive...")

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Saving patched archive")
        progress_window.transient(self.root)
        progress_window.resizable(False, False)

        progress_message = tk.StringVar(value="Preparing to save archive...")
        tk.Label(progress_window, textvariable=progress_message).pack(
            padx=20, pady=(15, 5)
        )

        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(
            progress_window,
            maximum=maximum,
            variable=progress_var,
            length=320,
            mode="determinate",
        )
        progress_bar.pack(padx=20, pady=5, fill="x")

        cancel_event = threading.Event()

        def request_cancel() -> None:
            if cancel_event.is_set():
                return
            cancel_event.set()
            progress_message.set("Cancelling...")
            try:
                cancel_button.configure(state="disabled")
            except tk.TclError:
                pass

        cancel_button = tk.Button(progress_window, text="Cancel", command=request_cancel)
        cancel_button.pack(padx=20, pady=(5, 15))

        progress_window.protocol("WM_DELETE_WINDOW", request_cancel)
        progress_window.focus_set()
        progress_window.grab_set()

        def update_progress(written: int) -> None:
            progress_var.set(min(written, maximum))
            if total_size:
                percent = min(100.0, (written / total_size) * 100)
            else:
                percent = 100.0
            progress_message.set(f"Saving archive... {percent:.0f}%")

        def finalize(status: str, error: Exception | None) -> None:
            if status == "success":
                update_progress(total_size)
            if progress_window.winfo_exists():
                try:
                    progress_window.grab_release()
                except tk.TclError:
                    pass
                progress_window.destroy()

            if status == "success":
                _release_archive_buffer(previous_buffer)
                self.archive_bytes = new_archive_bytes
                self.all_entries = updated_entries
                self.entries = [
                    entry
                    for entry in updated_entries
                    if is_image_entry(entry["relative_path"])
                ]
                self.replacements.clear()
                self._refresh_list()
                self._set_status(f"Saved patched archive to {output_path}")
                messagebox.showinfo(
                    "Archive saved", f"Patched archive written to {output_path}"
                )
            elif status == "cancelled":
                self._set_status("Archive save cancelled")
                messagebox.showinfo(
                    "Save cancelled", "Archive save was cancelled before completion."
                )
            else:
                self._set_status("Failed to save archive")
                detail = str(error) if error else "Unknown error while saving archive."
                messagebox.showerror("Unable to save archive", detail)

        def report_progress(written: int) -> None:
            self.root.after(0, update_progress, written)

        def background_write() -> None:
            status, error = _write_bytes_in_chunks(
                output_path,
                wrapped,
                chunk_size=4 * 1024 * 1024,
                cancel_event=cancel_event,
                progress_callback=report_progress,
            )
            self.root.after(0, finalize, status, error)

        thread = threading.Thread(target=background_write, daemon=True)
        thread.start()

    # ----------------------------------------------------------------- public --
    def run(self) -> None:
        self.root.mainloop()


def launch_gui() -> None:
    """Launch the Tk based texture browser."""

    gui = TextureManagerGUI()
    gui.run()


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract and repack Asura RSFL archives")
    subparsers = parser.add_subparsers(dest="command")
    parser.set_defaults(command="gui")

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

    patch_parser = subparsers.add_parser(
        "patch",
        help="generate a minimal archive containing only modified files",
    )
    patch_parser.add_argument("archive", type=Path, help="original archive used during extraction")
    patch_parser.add_argument(
        "manifest", type=Path, help="manifest generated by the extract command"
    )
    patch_parser.add_argument(
        "input_dir", type=Path, help="directory containing the modified files"
    )
    patch_parser.add_argument("output", type=Path, help="path of the patch archive")

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
    elif args.command == "patch":
        written = write_patch_archive(args.archive, args.manifest, args.input_dir, args.output)
        print(
            f"Patch archive written to {args.output} ({len(written)} file(s) included)"
        )
    elif args.command == "gui":
        if not TK_AVAILABLE:
            raise SystemExit("Tkinter is not available on this platform; GUI mode is disabled.")
        launch_gui()
    else:
        parser.error("unknown command")


if __name__ == "__main__":
    main()
