from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import _support


MODULE_PATH = _support.BENCHMARK_DIR / "datasets" / "generate.py"
SPEC = importlib.util.spec_from_file_location("csv2_generate_datasets", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
datasets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(datasets)


class DatasetGeneratorTests(unittest.TestCase):
    def generate(self, output: Path, manifest: Path) -> None:
        arguments = [
            str(MODULE_PATH),
            "--output",
            str(output),
            "--manifest",
            str(manifest),
        ]
        with unittest.mock.patch.object(sys, "argv", arguments):
            self.assertEqual(datasets.main(), 0)

    def check(self, output: Path, manifest: Path) -> None:
        arguments = [
            str(MODULE_PATH),
            "--output",
            str(output),
            "--manifest",
            str(manifest),
            "--check",
        ]
        with unittest.mock.patch.object(sys, "argv", arguments):
            datasets.main()

    def test_check_rejects_extra_and_missing_csv_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "fixtures"
            manifest = root / "manifest.json"
            self.generate(output, manifest)

            extra = output / "stale.csv"
            extra.write_bytes(b"stale\n")
            with self.assertRaisesRegex(SystemExit, "unexpected CSV fixtures"):
                self.check(output, manifest)
            extra.unlink()

            missing = output / "short_unquoted.csv"
            missing.unlink()
            with self.assertRaisesRegex(SystemExit, "missing CSV fixtures"):
                self.check(output, manifest)


if __name__ == "__main__":
    unittest.main()
