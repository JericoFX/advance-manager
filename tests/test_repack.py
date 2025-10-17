import unittest

from rs import RSFL_ENTRY_STRUCT, RSFLParsingError, _apply_replacements


class ApplyReplacementsTests(unittest.TestCase):
    def test_rsfl_entries_can_grow(self) -> None:
        # Create a fake archive where the RSFL table sits at the beginning and
        # the payload starts at offset 16.
        table_offset = 0
        payload_offset = 16
        original_payload = b"DATA"

        archive = bytearray(b"\x00" * 32)
        archive[payload_offset : payload_offset + len(original_payload)] = original_payload

        entry = {
            "relative_path": "textures/foo.tga",
            "offset": payload_offset,
            "size": len(original_payload),
            "unk": 0,
            "offset_anchor": 0,
            "table_offset": table_offset,
            "raw_offset": payload_offset,
            "layout": "rsfl",
        }
        RSFL_ENTRY_STRUCT.pack_into(
            archive, table_offset, entry["raw_offset"], entry["size"], entry["unk"]
        )

        new_payload = b"UPDATED-PAYLOAD"
        updated, updated_entries = _apply_replacements(
            bytes(archive), [entry], {entry["relative_path"]: new_payload}
        )

        self.assertEqual(len(updated_entries), 1)
        patched_entry = updated_entries[0]
        self.assertEqual(patched_entry["size"], len(new_payload))
        self.assertNotEqual(patched_entry["offset"], payload_offset)
        self.assertEqual(
            updated[patched_entry["offset"] : patched_entry["offset"] + patched_entry["size"]],
            new_payload,
        )

        raw_offset, size, unk = RSFL_ENTRY_STRUCT.unpack_from(updated, table_offset)
        self.assertEqual(size, len(new_payload))
        self.assertEqual(unk, 0)
        self.assertEqual(raw_offset, patched_entry["raw_offset"])

    def test_rscf_entries_must_preserve_size(self) -> None:
        archive = b"0123456789ABCDEF"
        entry = {
            "relative_path": "textures/bar.dds",
            "offset": 4,
            "size": 4,
            "layout": "rscf",
        }

        with self.assertRaises(RSFLParsingError):
            _apply_replacements(archive, [entry], {entry["relative_path"]: b"123456"})


if __name__ == "__main__":
    unittest.main()
