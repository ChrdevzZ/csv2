from __future__ import annotations

import importlib.util
import json
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
    def test_manifest_records_exact_strict_validation_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "fixtures"
            manifest = root / "manifest.json"
            self.generate(output, manifest)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            records = {record["name"]: record for record in document["datasets"]}

        self.assertEqual(
            records["invalid_early.csv"]["strict_error"],
            {"code": "unexpected_quote", "byte_offset": 1, "row": 1, "column": 1},
        )
        self.assertEqual(
            records["invalid_middle.csv"]["strict_error"],
            {"code": "unclosed_quote", "byte_offset": 8, "row": 3, "column": 1},
        )
        self.assertEqual(
            records["invalid_late.csv"]["strict_error"],
            {
                "code": "characters_after_closing_quote",
                "byte_offset": 20,
                "row": 4,
                "column": 1,
            },
        )
        self.assertEqual(records["short_unquoted.csv"]["strict_error"]["code"], "none")

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
