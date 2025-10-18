import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rs


def _build_rsfl_archive(path: Path) -> None:
    """Create a small RSFL archive suitable for patch tests."""

    name = b"textures\\test.tga\x00"
    while len(name) % 4:
        name += b"\x00"
    payload = b"PAYLOAD"

    table = bytearray()
    table.extend(name)
    table.extend(struct.pack("<III", 16, len(payload), 0))

    inner_size = rs.RSFL_CHUNK_HEADER.size + len(table) + len(payload)
    chunk_body = bytearray()
    chunk_body.extend(rs.RSFL_CHUNK_HEADER.pack(0x5246534C, inner_size, 1, 2, 1))
    chunk_body.extend(table)
    chunk_body.extend(payload)

    chunk_size = rs.CHUNK_HEADER.size + len(chunk_body)
    archive = bytearray(rs.ASURA_MAGIC)
    archive.extend(rs.CHUNK_HEADER.pack(b"LFSR", chunk_size, 0, 0))
    archive.extend(chunk_body)
    path.write_bytes(bytes(archive))


class PatchArchiveTests(unittest.TestCase):
    def test_write_patch_archive_rscf(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        archive_path = repo_root / "WolfMask_Dark_Red.en"
        self.assertTrue(archive_path.exists(), "fixture archive is missing")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = rs.extract_archive(archive_path, tmp)
            manifest = json.loads(manifest_path.read_text())
            entry = manifest.get("files", [])[0]
            exported_relative = entry.get("exported_path", entry["relative_path"])
            exported = tmp / Path(*exported_relative.split("/"))
            original_payload = exported.read_bytes()
            modified_payload = original_payload.replace(b"DDS ", b"PCH ", 1)
            exported.write_bytes(modified_payload)

            patch_path = tmp / "wolf_patch.asr"
            written = rs.write_patch_archive(archive_path, manifest_path, tmp, patch_path)

            self.assertTrue(patch_path.exists())
            self.assertIn(entry["relative_path"], written)

            patch_bytes, layout_info, entries, _wrapper = rs.load_archive(patch_path)
            try:
                self.assertEqual(layout_info.get("layout"), "rscf")
                self.assertEqual(len(entries), 1)
                patched_entry = entries[0]
                payload = patch_bytes[
                    patched_entry["offset"] : patched_entry["offset"] + patched_entry["size"]
                ]
                self.assertEqual(payload, modified_payload)
            finally:
                rs._release_archive_buffer(patch_bytes)

    def test_write_patch_archive_rsfl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            archive_path = tmp / "sample.asr"
            _build_rsfl_archive(archive_path)

            output_dir = tmp / "extract"
            manifest_path = rs.extract_archive(archive_path, output_dir)
            manifest = json.loads(manifest_path.read_text())
            entry = manifest.get("files", [])[0]
            exported_relative = entry.get("exported_path", entry["relative_path"])
            exported = output_dir / Path(*exported_relative.split("/"))
            original_payload = exported.read_bytes()
            modified_payload = original_payload + b"!PATCH!"
            exported.write_bytes(modified_payload)

            patch_path = tmp / "sample_patch.asr"
            written = rs.write_patch_archive(archive_path, manifest_path, output_dir, patch_path)

            self.assertTrue(patch_path.exists())
            self.assertIn(entry["relative_path"], written)

            patch_bytes, layout_info, entries, _wrapper = rs.load_archive(patch_path)
            try:
                self.assertEqual(layout_info.get("layout"), "rsfl")
                self.assertEqual(len(entries), 1)
                patched_entry = entries[0]
                payload = patch_bytes[
                    patched_entry["offset"] : patched_entry["offset"] + patched_entry["size"]
                ]
                self.assertEqual(payload, modified_payload)
            finally:
                rs._release_archive_buffer(patch_bytes)

    def test_gui_patch_helper_generates_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            archive_path = tmp / "gui_source.asr"
            _build_rsfl_archive(archive_path)

            archive_bytes, layout_info, entries, _wrapper = rs.load_archive(archive_path)
            try:
                gui = object.__new__(rs.TextureManagerGUI)
                gui.archive_path = archive_path
                gui.archive_bytes = archive_bytes
                entries_copy = [copy.deepcopy(entry) for entry in entries]
                if not entries_copy:
                    self.fail("expected at least one entry in test archive")
                gui.entries = entries_copy
                gui.layout_info = layout_info
                gui.wrapper_info = {"kind": "raw"}

                first_entry = entries_copy[0]
                original_payload = archive_bytes[
                    first_entry["offset"] : first_entry["offset"] + first_entry["size"]
                ]
                replacements = {
                    first_entry["relative_path"]: original_payload[::-1],
                }

                patch_path = tmp / "gui_patch.asr"
                written = gui._create_patch_archive(patch_path, replacements)

                self.assertTrue(patch_path.exists())
                self.assertEqual(written, [first_entry["relative_path"]])

                patch_bytes, _info, patch_entries, _ = rs.load_archive(patch_path)
                try:
                    self.assertEqual(len(patch_entries), 1)
                    patched = patch_bytes[
                        patch_entries[0]["offset"] : patch_entries[0]["offset"]
                        + patch_entries[0]["size"]
                    ]
                    self.assertEqual(patched, original_payload[::-1])
                finally:
                    rs._release_archive_buffer(patch_bytes)
            finally:
                rs._release_archive_buffer(archive_bytes)


if __name__ == "__main__":
    unittest.main()
