from __future__ import annotations

import importlib.util
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
    def test_wire_comparison_is_exact(self) -> None:
        fields = checks.parse_wire(
            "protocol=csv2-current-v3 checksum=1239 operation=x source=buffer"
        )
        self.assertNotEqual(fields["checksum"], "123")

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
