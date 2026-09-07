from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[2]


class RootCMakeHygieneTests(unittest.TestCase):
    def test_verification_rejects_in_source_before_loading_components(self) -> None:
        cmake = shutil.which("cmake")
        if cmake is None:
            self.fail("cmake is required for CI policy tests")

        cases = [
            ("CSV2_BUILD_TESTS", False),
            ("CSV2_BUILD_BENCHMARKS", False),
            ("CSV2_BUILD_FUZZERS", False),
            ("CSV2_BUILD_TESTS", True),
        ]
        for option, alias in cases:
            with (
                self.subTest(option=option, alias=alias),
                tempfile.TemporaryDirectory() as directory,
            ):
                source = Path(directory) / "source"
                modules = source / "cmake/verification"
                modules.mkdir(parents=True)
                shutil.copy2(SOURCE_ROOT / "CMakeLists.txt", source)
                shutil.copy2(
                    SOURCE_ROOT / "cmake/verification/Csv2VerificationOptions.cmake",
                    modules,
                )
                marker = source / "verification-loaded"
                (modules / "Csv2VerificationStandards.cmake").write_text(
                    'file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/verification-loaded" "loaded")\n'
                    'message(FATAL_ERROR "verification components must not be loaded")\n',
                    encoding="utf-8",
                )
                build = source
                if alias:
                    build = Path(directory) / "source-alias"
                    try:
                        build.symlink_to(source, target_is_directory=True)
                    except OSError:
                        continue
                completed = subprocess.run(
                    [
                        cmake, "-H" + str(source), "-B" + str(build),
                        "-D" + option + "=ON",
                    ],
                    capture_output=True, text=True, timeout=120,
                )
                output = completed.stdout + completed.stderr
                self.assertNotEqual(completed.returncode, 0, output)
                self.assertIn("CSV2 verification requires an out-of-source build", output)
                self.assertFalse(marker.exists(), output)

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
                    "-H" + str(SOURCE_ROOT),
                    "-B" + str(build),
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
