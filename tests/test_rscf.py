import json
import tempfile
import unittest
from pathlib import Path

from rs import extract_archive


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
                "graphics\\specialfx\\fsfx\\grey_gradient.bmp",
                "graphics\\specialfx\\fsfx\\fsfx_scanlines.tga",
            }
            self.assertEqual(set(files), expected_files)

            for relative_path, entry in files.items():
                extracted = output_dir / relative_path
                self.assertTrue(extracted.exists(), f"missing extracted file {relative_path}")
                self.assertEqual(extracted.stat().st_size, entry["size"])


if __name__ == "__main__":
    unittest.main()
