from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[2] / "checks" / "verify_case_manifest.py"
SPEC = importlib.util.spec_from_file_location("csv2_case_manifest_check", MODULE)
assert SPEC is not None and SPEC.loader is not None
case_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(case_manifest)


class CaseManifestTests(unittest.TestCase):
    def test_duplicate_operation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "input.csv"
            dataset.write_bytes(b"a\n")
            case = {
                "operation": "traversal/rows",
                "source": "buffer",
                "dataset": dataset.name,
            }
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "csv2-benchmark-case-manifest-v2",
                        "cases": [case, case],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                case_manifest.load_manifest(manifest, root)


if __name__ == "__main__":
    unittest.main()
