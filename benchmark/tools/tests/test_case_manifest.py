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
    def test_wire_requires_exact_independent_contract(self) -> None:
        contract = {
            "semantic_case_id": "csv2.writer.raw-direct.decoded-content.v1",
            "scope": "writer_only",
            "byte_basis": "input_corpus",
        }
        wire = (
            "protocol=csv2-current-v4 operation=writer/raw-direct source=buffer "
            "semantic_case_id=csv2.writer.raw-direct.decoded-content.v1 "
            "scope=writer_only byte_basis=input_corpus"
        )
        case_manifest.verify_wire(wire, "writer/raw-direct", "buffer", contract)
        for old, replacement in (
            ("decoded-content.v1", "v1"),
            ("decoded-content", "raw-fields"),
            ("writer_only", "traversal_only"),
            ("input_corpus", "output_bytes"),
        ):
            with self.subTest(replacement=replacement), self.assertRaises(RuntimeError):
                case_manifest.verify_wire(
                    wire.replace(old, replacement), "writer/raw-direct", "buffer", contract
                )

    def test_duplicate_operation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "input.csv"
            dataset.write_bytes(b"a\n")
            case = {
                "operation": "traversal/rows",
                "source": "buffer",
                "dataset": dataset.name,
                "semantic_case_id": "csv2.traversal.rows.v1",
                "scope": "traversal_only",
                "byte_basis": "input_corpus",
            }
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "csv2-benchmark-case-manifest-v3",
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
                        "schema": "csv2-benchmark-case-manifest-v3",
                        "cases": [
                            {
                                "operation": "traversal/rows",
                                "source": "buffer",
                                "dataset": dataset.name,
                                "semantic_case_id": "csv2.traversal.rows.v1",
                                "scope": "traversal_only",
                                "byte_basis": "input_corpus",
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
                    "traversal/rows source=buffer scope=traversal_only "
                    "semantic_case_id=csv2.traversal.rows.v1 byte_basis=input_corpus "
                    "zero_allocations=true\n",
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
            valid_run = fake_run([str(sys.executable), "--csv2-list"])
            for old, replacement in (
                ("csv2.traversal.rows.v1", "csv2.traversal.rows-cells.v1"),
                ("traversal_only", "writer_only"),
                ("input_corpus", "output_bytes"),
            ):
                changed = subprocess.CompletedProcess(
                    valid_run.args, 0, valid_run.stdout.replace(old, replacement), ""
                )
                with (
                    self.subTest(replacement=replacement),
                    mock.patch.object(sys, "argv", arguments),
                    mock.patch.object(case_manifest, "run", return_value=changed),
                    self.assertRaises(RuntimeError),
                ):
                    case_manifest.main()


if __name__ == "__main__":
    unittest.main()
