from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rs


def _build_dds_header(
    *,
    fourcc: bytes,
    pf_flags: int,
    rgb_bit_count: int = 0,
    masks: tuple[int, int, int, int] = (0, 0, 0, 0),
    dx10_format: int | None = None,
) -> bytes:
    header = bytearray(b"DDS ")
    header.extend(struct.pack("<I", 124))  # dwSize
    header.extend(struct.pack("<6I", 0, 0, 0, 0, 0, 0))  # flags..mipMapCount
    header.extend(struct.pack("<11I", *([0] * 11)))  # reserved1
    header.extend(
        struct.pack(
            "<II4sI4I",
            32,
            pf_flags,
            fourcc,
            rgb_bit_count,
            masks[0],
            masks[1],
            masks[2],
            masks[3],
        )
    )
    header.extend(struct.pack("<5I", 0, 0, 0, 0, 0))  # caps and reserved2
    if fourcc == b"DX10" and dx10_format is not None:
        header.extend(struct.pack("<5I", dx10_format, 3, 0, 1, 0))
    return bytes(header)


class DDSHeaderParsingTests(unittest.TestCase):
    def test_parse_dxt1_fourcc(self) -> None:
        payload = _build_dds_header(fourcc=b"DXT1", pf_flags=rs.DDPF_FOURCC)
        info = rs._parse_dds_header(payload)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.get("compression"), "DXT1")
        self.assertEqual(info.get("channel_masks"), {"R": 0, "G": 0, "B": 0, "A": 0})

    def test_parse_uncompressed_rgba_masks(self) -> None:
        masks = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        payload = _build_dds_header(
            fourcc=b"\x00\x00\x00\x00",
            pf_flags=rs.DDPF_RGB | rs.DDPF_ALPHAPIXELS,
            rgb_bit_count=32,
            masks=masks,
        )
        info = rs._parse_dds_header(payload)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.get("compression"), "Uncompressed 32-bit RGBA")
        self.assertEqual(info.get("channel_masks"), {"R": masks[0], "G": masks[1], "B": masks[2], "A": masks[3]})

    def test_parse_dx10_bc7_format(self) -> None:
        payload = _build_dds_header(
            fourcc=b"DX10",
            pf_flags=rs.DDPF_FOURCC,
            dx10_format=98,
        )
        info = rs._parse_dds_header(payload)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.get("compression"), "BC7")
        self.assertEqual(info.get("channel_masks"), {"R": 0, "G": 0, "B": 0, "A": 0})


if __name__ == "__main__":  # pragma: no cover - manual test runner support
    unittest.main()
