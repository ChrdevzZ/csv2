from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import _support


MODULE_PATH = _support.BENCHMARK_DIR / "checks" / "verify_expected_checksums.py"
SPEC = importlib.util.spec_from_file_location("verify_expected_checksums", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)


class ChecksumManifestTests(unittest.TestCase):
    def test_verify_rejects_semantic_wire_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "benchmark"
            executable.write_bytes(b"executable")
            dataset = root / "input.csv"
            dataset.write_bytes(b"x")
            manifest = root / "checks.json"
            check = {
                "operation": "traversal/rows",
                "source": "buffer",
                "dataset": "input.csv",
                "semantic_case_id": "csv2.traversal.rows.v1",
                "scope": "traversal_only",
                "byte_basis": "input_corpus",
                "checksum": "1",
                "bytes": "1",
                "rows": "1",
                "cells": "0",
                "allocations": "0",
                "allocated_bytes": "0",
            }
            manifest.write_text(
                json.dumps({"protocol": "csv2-current-v4", "checks": [check]}),
                encoding="utf-8",
            )
            wire = (
                "protocol=csv2-current-v4 revision=revision "
                "operation=traversal/rows source=buffer dataset=input.csv "
                "semantic_case_id=csv2.traversal.rows.v1 scope=writer_only "
                "byte_basis=input_corpus checksum=1 bytes=1 rows=1 cells=0 "
                "allocations=0 allocated_bytes=0\n"
            )
            completed = subprocess.CompletedProcess([], 0, wire, "")
            with unittest.mock.patch.object(checks.subprocess, "run", return_value=completed):
                with self.assertRaisesRegex(RuntimeError, "scope mismatch"):
                    checks.verify(executable, root, manifest, "revision")

    def test_checksum_requires_canonical_uint64(self) -> None:
        self.assertEqual(checks.validate_checksum("0"), "0")
        for value in ("", "01", "-1", "+1", str(1 << 64)):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    checks.validate_checksum(value)

    def test_dataset_must_remain_under_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            outside = Path(directory) / "outside.csv"
            outside.write_bytes(b"x")
            with self.assertRaisesRegex(RuntimeError, "escapes"):
                checks.resolve_dataset(root, "../outside.csv")


if __name__ == "__main__":
    unittest.main()
