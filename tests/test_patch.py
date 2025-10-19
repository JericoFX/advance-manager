import copy
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from typing import Sequence, Tuple
from unittest import mock

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

    def test_gui_on_entry_selected_uses_replacement_payload(self) -> None:
        class DummyTree:
            def __init__(self, node_id: str) -> None:
                self._selection = (node_id,)
                self._focus = node_id

            def selection(self) -> Tuple[str, ...]:
                return self._selection

            def focus(self, value: str | None = None) -> str:
                if value is None:
                    return self._focus
                self._focus = value
                return self._focus

            def see(self, _value: str) -> None:
                pass

        class DummyLabel:
            def __init__(self) -> None:
                self.configure_calls: List[Dict[str, object]] = []
                self.image = None

            def configure(self, **kwargs: object) -> None:
                self.configure_calls.append(kwargs)

        class FakeImageModule:
            last_opened_payload: bytes | None = None

            class FakeImage:
                def __init__(self, payload: bytes) -> None:
                    self.payload = payload
                    self.format = "FAKE"

                def load(self) -> None:
                    pass

                def convert(self, _mode: str) -> "FakeImageModule.FakeImage":
                    return self

            @staticmethod
            def open(stream: io.BytesIO) -> "FakeImageModule.FakeImage":
                data = stream.getvalue()
                FakeImageModule.last_opened_payload = data
                return FakeImageModule.FakeImage(data)

        class FakeImageTkModule:
            last_photo_image: object | None = None

            @staticmethod
            def PhotoImage(image: object) -> object:
                FakeImageTkModule.last_photo_image = image
                return object()

        replacement_payload = b"replacement-bytes"
        original_payload = b"original-bytes"
        entry = {
            "relative_path": "textures/test.dds",
            "offset": 0,
            "size": len(original_payload),
        }

        gui = object.__new__(rs.TextureManagerGUI)
        gui.archive_bytes = original_payload
        gui.entries = [entry]
        gui.replacements = {
            entry["relative_path"]: {
                "payload": replacement_payload,
                "metadata": {"source": "test"},
            }
        }
        gui.node_to_entry = {"node-1": entry}
        gui.entry_nodes = {entry["relative_path"]: "node-1"}
        gui.tree = DummyTree("node-1")
        gui.last_activated_path = None
        gui.preview_label = DummyLabel()
        gui._set_channel_controls_state = lambda *_args, **_kwargs: None
        gui._update_channel_preview = lambda *_args, **_kwargs: None
        gui._update_preview_scrollregion = lambda *_args, **_kwargs: None
        cleared_messages: List[str | None] = []
        gui._clear_preview = lambda message=None: cleared_messages.append(message)
        status_messages: List[str] = []
        gui._set_status = lambda message: status_messages.append(message)

        original_image = rs.Image
        original_image_tk = rs.ImageTk
        original_unidentified = rs.UnidentifiedImageError
        original_pil_available = rs.PIL_AVAILABLE
        original_pil_imagetk_available = rs.PIL_IMAGETK_AVAILABLE
        rs.Image = FakeImageModule
        rs.ImageTk = FakeImageTkModule
        rs.UnidentifiedImageError = RuntimeError
        rs.PIL_AVAILABLE = True
        rs.PIL_IMAGETK_AVAILABLE = True
        try:
            gui._on_entry_selected(None)
        finally:
            rs.Image = original_image
            rs.ImageTk = original_image_tk
            rs.UnidentifiedImageError = original_unidentified
            rs.PIL_AVAILABLE = original_pil_available
            rs.PIL_IMAGETK_AVAILABLE = original_pil_imagetk_available

        self.assertFalse(cleared_messages, "replacement preview should not clear the preview")
        self.assertIsNotNone(gui.preview_source_image)
        self.assertEqual(gui.preview_source_image.payload, replacement_payload)
        self.assertEqual(FakeImageModule.last_opened_payload, replacement_payload)
        self.assertTrue(status_messages)
        self.assertIn(entry["relative_path"], status_messages[-1])

    def test_gui_patch_helper_uses_all_entries_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            archive_path = tmp / "gui_source.asr"
            _build_rsfl_archive(archive_path)

            archive_bytes, layout_info, entries, _wrapper = rs.load_archive(archive_path)
            try:
                gui = object.__new__(rs.TextureManagerGUI)
                gui.archive_path = archive_path
                gui.archive_bytes = archive_bytes
                gui.all_entries = [copy.deepcopy(entry) for entry in entries]
                gui.layout_info = layout_info
                gui.wrapper_info = {"kind": "raw"}

                first_entry = gui.all_entries[0]
                original_payload = archive_bytes[
                    first_entry["offset"] : first_entry["offset"] + first_entry["size"]
                ]
                replacements = {
                    first_entry["relative_path"]: original_payload[::-1],
                }

                patch_path = tmp / "gui_patch_all_entries.asr"
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

    def test_gui_export_selected_uses_replacement_payload(self) -> None:
        class DummyTree:
            def __init__(self, nodes: Sequence[str]):
                self._nodes = list(nodes)

            def selection(self) -> Tuple[str, ...]:
                return tuple(self._nodes)

        class DummyStatus:
            def __init__(self) -> None:
                self.message: str | None = None

            def set(self, message: str) -> None:
                self.message = message

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            archive_path = tmp / "export_source.asr"
            _build_rsfl_archive(archive_path)

            archive_bytes, layout_info, entries, _wrapper = rs.load_archive(archive_path)
            try:
                gui = object.__new__(rs.TextureManagerGUI)
                entry = copy.deepcopy(entries[0])
                gui.archive_path = archive_path
                gui.archive_bytes = archive_bytes
                gui.entries = [entry]
                gui.replacements = {
                    entry["relative_path"]: {
                        "payload": b"DDS replacement payload",  # recognised as DDS
                        "source_info": {
                            "metadata": {
                                "relative_path": entry["relative_path"],
                                "offset": 321,
                                "size": len(b"DDS replacement payload"),
                            }
                        },
                    }
                }
                gui.node_to_entry = {"node": entry}
                gui.entry_nodes = {entry["relative_path"]: "node"}
                gui.status = DummyStatus()
                gui._set_status = rs.TextureManagerGUI._set_status.__get__(gui)
                gui._export_entries = rs.TextureManagerGUI._export_entries.__get__(gui)

                export_dir = tmp / "export"
                export_dir.mkdir()

                gui.tree = DummyTree(["node"])

                with mock.patch.object(rs, "filedialog") as mock_filedialog:
                    mock_filedialog.askdirectory.return_value = str(export_dir)
                    gui.export_selected()

                expected_relative, _original = rs.resolve_export_relative_path(
                    entry["relative_path"], b"DDS replacement payload"
                )
                exported_path = export_dir / Path(*expected_relative.split("/"))
                self.assertTrue(exported_path.exists())
                self.assertEqual(
                    exported_path.read_bytes(), b"DDS replacement payload"
                )

                metadata = json.loads(exported_path.with_suffix(exported_path.suffix + ".rsmeta").read_text())
                self.assertEqual(metadata["relative_path"], entry["relative_path"])
                self.assertEqual(metadata["size"], len(b"DDS replacement payload"))
                self.assertEqual(metadata["offset"], 321)
                self.assertEqual(metadata["source_archive"], archive_path.name)
            finally:
                rs._release_archive_buffer(archive_bytes)


class ReplacementLogTests(unittest.TestCase):
    def test_build_replacement_log_captures_metadata(self) -> None:
        archive_path = Path("/tmp/archive.asr")
        replacements = {
            "textures/example.dds": {
                "payload": b"IGNORED",
                "offset": 12,
                "size": 34,
                "source_info": {
                    "path": "/tmp/example.dds",
                    "metadata_path": "/tmp/example.dds.rsmeta",
                    "metadata": {"relative_path": "textures/example.dds"},
                },
            }
        }

        log_payload = rs.build_replacement_log(replacements, archive_path=archive_path)

        self.assertEqual(log_payload.get("schema"), 1)
        self.assertEqual(log_payload.get("archive"), str(archive_path))
        self.assertIsInstance(log_payload.get("generated"), str)

        replacements_list = log_payload.get("replacements")
        self.assertIsInstance(replacements_list, list)
        self.assertEqual(len(replacements_list), 1)

        entry = replacements_list[0]
        self.assertEqual(entry["relative_path"], "textures/example.dds")
        self.assertEqual(entry["offset"], 12)
        self.assertEqual(entry["size"], 34)
        self.assertNotIn("payload", entry)
        self.assertEqual(entry["source"]["path"], "/tmp/example.dds")
        self.assertEqual(entry["source"]["metadata_path"], "/tmp/example.dds.rsmeta")
        self.assertEqual(entry["metadata"], {"relative_path": "textures/example.dds"})

    def test_write_replacement_log_creates_json_file(self) -> None:
        replacements = {
            "textures/sample.dds": {
                "payload": b"data",
                "source_info": {"path": "/tmp/sample.dds"},
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            patch_path = tmp / "sample_patch.asr"
            patch_path.write_bytes(b"patch")

            log_path = rs.write_replacement_log(patch_path, replacements)

            self.assertTrue(log_path.exists())
            payload = json.loads(log_path.read_text())
            self.assertEqual(payload["replacements"][0]["relative_path"], "textures/sample.dds")


if __name__ == "__main__":
    unittest.main()
