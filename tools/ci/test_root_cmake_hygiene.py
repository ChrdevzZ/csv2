from __future__ import annotations

import os
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

    def test_benchmark_audits_follow_checks_default_build(self) -> None:
        cmake = shutil.which("cmake")
        self.assertIsNotNone(cmake, "cmake is required for CI policy tests")
        audits = ("csv2_benchmark_observer_audit", "csv2_common_benchmark_timer_audit")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            benchmark = source / "benchmark"
            benchmark.mkdir(parents=True)
            # Exercise real target declarations with cheap translation units;
            # runtime audit semantics belong to the benchmark checksum owner.
            for relative in ("CMakeLists.txt", "current/CMakeLists.txt", "compare/CMakeLists.txt"):
                destination = benchmark / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(SOURCE_ROOT / "benchmark" / relative, destination)
            shutil.copytree(SOURCE_ROOT / "benchmark/cmake", benchmark / "cmake")
            for component in ("datasets", "checks", "tools"):
                (benchmark / component).mkdir()
                (benchmark / component / "CMakeLists.txt").write_text("", encoding="utf-8")
            for component in ("current", "compare"):
                for original in (SOURCE_ROOT / "benchmark" / component).rglob("*.cpp"):
                    destination = benchmark / original.relative_to(SOURCE_ROOT / "benchmark")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(
                        "int main() { return 0; }\n"
                        if original.name in ("main.cpp", "common_driver.cpp") else "\n",
                        encoding="utf-8",
                    )
            (benchmark / "cmake/Csv2BenchmarkDependencies.cmake").write_text(
                "function(csv2_load_google_benchmark)\n"
                "  add_library(benchmark INTERFACE)\n"
                "  add_library(benchmark::benchmark ALIAS benchmark)\n"
                "endfunction()\n", encoding="utf-8",
            )
            (source / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(audit_build_graph LANGUAGES CXX)\n"
                "add_library(csv2 INTERFACE)\n"
                "add_library(csv2::csv2 ALIAS csv2)\n"
                "set(CSV2_HAS_MMAP 0)\n"
                "set(csv2_supported_standards 20)\n"
                "function(csv2_configure_python_audits)\nendfunction()\n"
                "function(csv2_enable_test_options target)\nendfunction()\n"
                "function(csv2_set_test_standard target standard)\n"
                "  set_property(TARGET ${target} PROPERTY CXX_STANDARD ${standard})\n"
                "endfunction()\n"
                "add_subdirectory(benchmark)\n"
                'file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/audits-$<CONFIG>.txt" CONTENT "'
                + "".join(f"$<TARGET_FILE:{target}>\\n" for target in audits)
                + '")\n', encoding="utf-8",
            )

            def run(*arguments: str) -> None:
                completed = subprocess.run(
                    list(arguments), capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

            generator = ["-G", os.environ.get("CMAKE_GENERATOR", "Ninja")]
            for checks in ("OFF", "ON"):
                with self.subTest(checks=checks):
                    build = Path(directory) / checks
                    run(cmake, "-S", str(source), "-B", str(build), *generator,
                        "-DCMAKE_BUILD_TYPE=Debug", "-DCSV2_BUILD_BENCHMARK_CHECKS=" + checks)
                    executables = [Path(path) for path in (build / "audits-Debug.txt").read_text().splitlines()]
                    run(cmake, "--build", str(build), "--config", "Debug", "--parallel", "2")
                    for executable in executables:
                        self.assertEqual(executable.exists(), checks == "ON", str(executable))
                    if checks == "OFF":
                        run(cmake, "--build", str(build), "--config", "Debug", "--parallel", "2",
                            "--target", *audits)
                    for executable in executables:
                        run(str(executable))

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
