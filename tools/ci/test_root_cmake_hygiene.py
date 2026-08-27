from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[2]


class RootCMakeHygieneTests(unittest.TestCase):
    def test_configure_ignores_ambient_conan1_build_metadata(self) -> None:
        cmake = shutil.which("cmake")
        if cmake is None:
            self.fail("cmake is required for CI policy tests")

        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory) / "build"
            build.mkdir()
            marker = "ambient Conan 1 metadata was executed"
            (build / "conanbuildinfo.cmake").write_text(
                f'message(FATAL_ERROR "{marker}")\n', encoding="utf-8"
            )
            completed = subprocess.run(
                [
                    cmake,
                    "-S",
                    str(SOURCE_ROOT),
                    "-B",
                    str(build),
                    "-DCSV2_BUILD_TESTS=OFF",
                    "-DCSV2_BUILD_BENCHMARKS=OFF",
                    "-DCSV2_BUILD_BENCHMARK_CHECKS=OFF",
                    "-DCSV2_BUILD_FUZZERS=OFF",
                ],
                capture_output=True,
                text=True,
            )
            output = completed.stdout + completed.stderr
            self.assertEqual(completed.returncode, 0, output)
            self.assertNotIn(marker, output)


if __name__ == "__main__":
    unittest.main()
