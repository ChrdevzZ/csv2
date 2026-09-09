from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _support


@unittest.skipUnless(shutil.which("cmake"), "CMake is required")
class CMakeWireTests(unittest.TestCase):
    def test_process_status_and_exact_stdout_fields(self) -> None:
        validator = _support.BENCHMARK_DIR / "checks" / "verify_wire.cmake"
        with tempfile.TemporaryDirectory(prefix="csv2 wire ") as directory:
            child = Path(directory) / "child.py"
            child.write_text(
                "import sys\n"
                "print(sys.argv[1], file=sys.stderr if sys.argv[3] == 'stderr' else sys.stdout)\n"
                "raise SystemExit(int(sys.argv[2]))\n", encoding="utf-8"
            )
            cases = (
                ("rows=3 cells=9 allocations=1", 0, "stdout", True),
                ("rows=3 cells=9 allocations=1", 17, "stdout", False),
                ("rows=30 cells=90 allocations=1", 0, "stdout", False),
                ("rows=3 cells=9 allocations=1", 0, "stderr", False),
                ("rows=3 allocations=1", 0, "stdout", False),
                ("rows=3 cells=9 allocations=10junk", 0, "stdout", False),
                ("rows=3 cells=9 allocations=0", 0, "stdout", False),
                ("rows=3 rows=30 cells=9 allocations=1", 0, "stdout", False),
            )
            for wire, status, channel, accepted in cases:
                with self.subTest(wire=wire, status=status, channel=channel):
                    result = subprocess.run(
                        [shutil.which("cmake"), "-DCSV2_EXPECTED_ROWS=3",
                         "-DCSV2_EXPECTED_CELLS=9", "-DCSV2_POSITIVE_FIELDS=allocations",
                         "-P", str(validator), "--", sys.executable, str(child),
                         wire, str(status), channel], text=True, capture_output=True,
                    )
                    self.assertEqual(result.returncode == 0, accepted, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
