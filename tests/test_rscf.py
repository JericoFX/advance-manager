import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rs import (
    CHUNK_HEADER,
    _apply_replacements,
    _release_archive_buffer,
    extract_archive,
    load_archive,
    repack_archive,
)


class RSCFExtractionTests(unittest.TestCase):
    def test_extract_alien_vision_archive(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        archive_path = repo_root / "avp2004_alien_vision.asr"
        self.assertTrue(archive_path.exists(), "fixture archive is missing")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest_path = extract_archive(archive_path, output_dir)
            self.assertTrue(manifest_path.exists())

            manifest = json.loads(manifest_path.read_text())
            layout_info = manifest.get("rsfl") or {}
            self.assertEqual(layout_info.get("layout"), "rscf")

            files = {entry["relative_path"]: entry for entry in manifest.get("files", [])}
            expected_files = {
                "graphics/specialfx/fsfx/grey_gradient.bmp",
                "graphics/specialfx/fsfx/fsfx_scanlines.tga",
            }
            self.assertEqual(set(files), expected_files)

            for relative_path, entry in files.items():
                exported_relative = entry.get("exported_path", relative_path)
                exported = output_dir / Path(*exported_relative.split("/"))
                self.assertTrue(
                    exported.exists(), f"missing exported file {exported_relative}"
                )
                self.assertEqual(exported.stat().st_size, entry["size"])
                if "exported_path" in entry:
                    self.assertEqual(entry.get("original_path"), relative_path)
                    original = output_dir / Path(*relative_path.split("/"))
                    self.assertFalse(
                        original.exists(), f"unexpected original path {relative_path}"
                    )
                    self.assertNotEqual(
                        Path(relative_path).suffix.lower(),
                        Path(exported_relative).suffix.lower(),
                    )
                    self.assertEqual(Path(exported_relative).suffix.lower(), ".dds")

    def test_extract_creates_directory_tree_posix(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        archive_path = repo_root / "avp2004_alien_vision.asr"
        self.assertTrue(archive_path.exists(), "fixture archive is missing")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest_path = extract_archive(archive_path, output_dir)
            self.assertTrue(manifest_path.exists())

            manifest = json.loads(manifest_path.read_text())
            files = {entry["relative_path"]: entry for entry in manifest.get("files", [])}

            for entry in files.values():
                exported_relative = entry.get("exported_path", entry["relative_path"])
                extracted = output_dir / Path(*exported_relative.split("/"))
                self.assertTrue(
                    extracted.exists(), f"missing exported file {exported_relative}"
                )
                for parent in extracted.parents:
                    if parent == output_dir:
                        break
                    self.assertTrue(parent.exists(), f"missing directory {parent}")
                    self.assertTrue(parent.is_dir(), f"expected directory for {parent}")

    def test_extract_wolf_mask_archive(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        archive_path = repo_root / "WolfMask_Dark_Red.en"
        self.assertTrue(archive_path.exists(), "fixture archive is missing")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest_path = extract_archive(archive_path, output_dir)
            self.assertTrue(manifest_path.exists())

            manifest = json.loads(manifest_path.read_text())
            files = {entry["relative_path"]: entry for entry in manifest.get("files", [])}

            expected_path = "graphics/characters/predator/wolfmask_col.tga"
            self.assertIn(expected_path, files)

            entry = files[expected_path]
            exported_relative = entry.get("exported_path", expected_path)
            self.assertEqual(entry.get("original_path"), expected_path)
            extracted = output_dir / Path(*exported_relative.split("/"))
            self.assertTrue(
                extracted.exists(), f"missing exported file {exported_relative}"
            )
            self.assertEqual(extracted.stat().st_size, entry["size"])
            self.assertEqual(Path(exported_relative).suffix.lower(), ".dds")

    def test_repack_accepts_files_with_adjusted_extension(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        archive_path = repo_root / "WolfMask_Dark_Red.en"
        self.assertTrue(archive_path.exists(), "fixture archive is missing")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest_path = extract_archive(archive_path, output_dir)
            manifest = json.loads(manifest_path.read_text())
            entry = manifest.get("files", [])[0]

            exported_relative = entry.get("exported_path")
            self.assertIsNotNone(exported_relative, "expected exported path metadata")
            exported_path = output_dir / Path(*exported_relative.split("/"))
            self.assertTrue(exported_path.exists())

            new_size = entry["size"] + 8
            new_payload = b"DDS " + b"X" * (new_size - 4)
            exported_path.write_bytes(new_payload)

            patched_path = Path(tmpdir) / "patched.en"
            repack_archive(archive_path, manifest_path, output_dir, patched_path)

            patched_bytes, _info, entries, _wrapper = load_archive(patched_path)
            try:
                patched_entry = next(
                    item for item in entries if item["relative_path"] == entry["relative_path"]
                )
                patched_payload = patched_bytes[
                    patched_entry["offset"] : patched_entry["offset"] + patched_entry["size"]
                ]
                self.assertEqual(patched_payload, new_payload)
            finally:
                _release_archive_buffer(patched_bytes)


class RSCFReplacementTests(unittest.TestCase):
    def _build_chunk(self, name: str, payload: bytes) -> tuple[bytes, dict]:
        encoded_name = name.encode("utf-8") + b"\x00"
        while len(encoded_name) % 4:
            encoded_name += b"\x00"

        rscf_header = struct.pack("<III", 2, 0, len(payload))
        chunk_body = rscf_header + encoded_name + payload
        chunk_size = CHUNK_HEADER.size + len(chunk_body)
        header = struct.pack("<4sIII", b"RSCF", chunk_size, 0, 0)

        entry = {
            "relative_path": name.replace("\\", "/"),
            "layout": "rscf",
            "chunk_offset": 0,
            "chunk_size": chunk_size,
            "header_offset": CHUNK_HEADER.size,
            "header_version": 2,
            "header_data_offset": 0,
            "header_data_span": len(payload),
            "offset": CHUNK_HEADER.size + len(rscf_header) + len(encoded_name),
            "offset_anchor": CHUNK_HEADER.size + len(rscf_header) + len(encoded_name),
            "size": len(payload),
        }

        return header + chunk_body, entry

    def _build_archive(self) -> tuple[bytes, list[dict]]:
        chunks = []
        entries = []
        for name, payload in (
            ("textures/foo.tga", b"AAAA"),
            ("textures/bar.tga", b"BBBB"),
        ):
            chunk, entry = self._build_chunk(name, payload)
            offset = sum(len(existing) for existing, _ in chunks)
            adjusted = dict(entry)
            adjusted["chunk_offset"] = offset + entry["chunk_offset"]
            adjusted["header_offset"] = offset + entry["header_offset"]
            adjusted["offset"] = offset + entry["offset"]
            adjusted["offset_anchor"] = adjusted["offset"]
            chunks.append((chunk, adjusted))
            entries.append(adjusted)

        archive = bytearray()
        for chunk, _ in chunks:
            archive.extend(chunk)
        archive.extend(b"TAIL")

        return bytes(archive), entries

    def test_apply_replacements_resizes_rscf_chunks(self) -> None:
        archive, entries = self._build_archive()
        original_first = dict(entries[0])
        original_second = dict(entries[1])

        new_payload = b"AAAAXXXX"
        updated, updated_entries = _apply_replacements(
            archive, entries, {entries[0]["relative_path"]: new_payload}
        )

        self.assertEqual(len(updated_entries), 2)
        first = updated_entries[0]
        second = updated_entries[1]

        delta = len(new_payload) - original_first["size"]
        self.assertEqual(first["size"], len(new_payload))
        self.assertEqual(first["header_data_span"], len(new_payload))
        self.assertEqual(first["chunk_size"], original_first["chunk_size"] + delta)
        self.assertEqual(
            struct.unpack_from("<I", updated, first["chunk_offset"] + 4)[0],
            first["chunk_size"],
        )
        self.assertEqual(
            struct.unpack_from("<I", updated, first["header_offset"] + 8)[0],
            len(new_payload),
        )
        self.assertEqual(
            updated[first["offset"] : first["offset"] + len(new_payload)], new_payload
        )

        self.assertEqual(second["chunk_offset"], original_second["chunk_offset"] + delta)
        self.assertEqual(second["offset"], original_second["offset"] + delta)
        self.assertEqual(second["offset_anchor"], original_second["offset_anchor"] + delta)
        self.assertEqual(second["header_offset"], original_second["header_offset"] + delta)
        self.assertTrue(updated.endswith(b"TAIL"))

    def test_apply_replacements_shrinks_rscf_chunks(self) -> None:
        archive, entries = self._build_archive()
        original_first = dict(entries[0])
        original_second = dict(entries[1])

        new_payload = b"AA"
        updated, updated_entries = _apply_replacements(
            archive, entries, {entries[0]["relative_path"]: new_payload}
        )

        first = updated_entries[0]
        second = updated_entries[1]
        delta = len(new_payload) - original_first["size"]

        self.assertEqual(first["size"], len(new_payload))
        self.assertEqual(first["chunk_size"], original_first["chunk_size"] + delta)
        self.assertEqual(
            struct.unpack_from("<I", updated, first["chunk_offset"] + 4)[0],
            first["chunk_size"],
        )
        self.assertEqual(second["chunk_offset"], original_second["chunk_offset"] + delta)
        self.assertEqual(second["offset"], original_second["offset"] + delta)
        self.assertEqual(updated[first["offset"] : first["offset"] + len(new_payload)], new_payload)
        self.assertTrue(updated.endswith(b"TAIL"))

if __name__ == "__main__":
    unittest.main()
