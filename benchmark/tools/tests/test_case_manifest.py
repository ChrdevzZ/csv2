from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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

    def test_registry_only_validates_coverage_without_executing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "input.csv"
            dataset.write_bytes(b"a\n")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "csv2-benchmark-case-manifest-v2",
                        "cases": [
                            {
                                "operation": "traversal/rows",
                                "source": "buffer",
                                "dataset": dataset.name,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            commands: list[list[str]] = []

            def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                if command[1:] != ["--csv2-list"]:
                    raise AssertionError(f"registry-only executed a case: {command}")
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "traversal/rows source=buffer\n",
                    "",
                )

            arguments = [
                str(MODULE),
                "--executable",
                sys.executable,
                "--source-root",
                str(root),
                "--manifest",
                str(manifest),
                "--registry-only",
            ]
            with mock.patch.object(sys, "argv", arguments), mock.patch.object(
                case_manifest, "run", side_effect=fake_run
            ):
                case_manifest.main()

            self.assertEqual(len(commands), 1)


if __name__ == "__main__":
    unittest.main()
