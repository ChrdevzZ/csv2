from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[2]


class RootCMakeHygieneTests(unittest.TestCase):
    def test_installed_package_discovery_contract(self) -> None:
        cmake = shutil.which("cmake")
        self.assertIsNotNone(cmake, "cmake is required for CI policy tests")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / "producer"
            prefix = root / "installed package"

            def run(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [str(cmake), *args], capture_output=True, text=True, timeout=120,
                )

            for args in (
                ("-H" + str(SOURCE_ROOT), "-B" + str(build),
                 "-DCMAKE_INSTALL_PREFIX=" + str(prefix),
                 "-DCSV2_BUILD_TESTS=OFF", "-DCSV2_BUILD_BENCHMARKS=OFF",
                 "-DCSV2_BUILD_BENCHMARK_CHECKS=OFF", "-DCSV2_BUILD_FUZZERS=OFF"),
                ("--build", str(build), "--target", "install", "--config", "Release"),
            ):
                result = run(*args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            configs = list(prefix.rglob("csv2Config.cmake"))
            self.assertEqual(len(configs), 1)
            # These consumers exercise package metadata, not native 32-bit code.
            for width in (4, 8):
                for request, accepted in (
                    ("", True), ("1.8.0", True), ("1.7.0", True),
                    ("9.0.0", False),
                    ("COMPONENTS absent_component", False),
                    ("OPTIONAL_COMPONENTS absent_component", True),
                ):
                    with self.subTest(width=width, request=request):
                        consumer = root / (str(width) + "-" + request.replace(" ", "_"))
                        consumer.mkdir()
                        (consumer / "CMakeLists.txt").write_text(
                            "cmake_minimum_required(VERSION 3.10)\n"
                            "project(package_contract LANGUAGES NONE)\n"
                            f"set(CMAKE_SIZEOF_VOID_P {width})\n"
                            f"find_package(csv2 {request} CONFIG REQUIRED)\n"
                            "if(NOT TARGET csv2::csv2)\n"
                            '  message(FATAL_ERROR "missing interface target")\n'
                            "endif()\n", encoding="utf-8",
                        )
                        result = run("-H" + str(consumer), "-B" + str(consumer / "build"),
                                     "-Dcsv2_DIR=" + str(configs[0].parent))
                        self.assertEqual(result.returncode == 0, accepted,
                                         result.stdout + result.stderr)

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

    @unittest.skipIf(os.name == "nt", "include_next fixtures require GCC or Clang")
    def test_generated_test_inputs_preserve_incremental_builds(self) -> None:
        cmake = shutil.which("cmake")
        self.assertIsNotNone(cmake, "cmake is required for CI policy tests")
        targets = (
            "csv2_standard_contract_partial_headers_module_cxx20",
            "csv2_standard_contract_empty_headers_module_cxx20",
            "csv2_minitest_registry_capacity",
            "csv2_minitest_registry_duplicate",
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            build = Path(directory) / "build"
            source.mkdir()
            for name in ("cmake", "include", "single_include", "test"):
                shutil.copytree(SOURCE_ROOT / name, source / name)
            for name in ("CMakeLists.txt", "csv2Config.cmake.in", "csv2.pc.in"):
                shutil.copy2(SOURCE_ROOT / name, source / name)

            def run(*args: str) -> None:
                completed = subprocess.run(
                    [str(cmake), *args], capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(
                    completed.returncode, 0, completed.stdout + completed.stderr,
                )

            def configure() -> None:
                run("-S", str(source), "-B", str(build),
                    "-G", os.environ.get("CMAKE_GENERATOR", "Ninja"),
                    "-DCSV2_BUILD_TESTS=ON",
                    "-DCSV2_TEST_ASSERTION_BACKEND=minitest")

            def compile_consumers() -> None:
                run("--build", str(build), "--target", *targets, "--parallel", "2")

            def objects() -> dict[Path, int]:
                return {path: path.stat().st_mtime_ns for path in build.rglob("*.o")}

            configure()
            compile_consumers()
            generated = sorted(build.glob("test/contracts/*standard_library/*"))
            generated += sorted(build.glob("test/support/minitest_registry_*.cpp"))
            self.assertTrue(generated)
            contents = {path: path.read_bytes() for path in generated}
            # Age dependencies and objects so even coarse filesystem clocks
            # distinguish a subsequent write; keep objects newer than inputs.
            for path in generated:
                os.utime(path, (946684800, 946684800))
            for path in objects():
                os.utime(path, (946684802, 946684802))
            compile_consumers()
            before = objects()
            self.assertTrue(before)
            timestamps = {path: path.stat().st_mtime_ns for path in generated}
            configure()
            compile_consumers()
            self.assertEqual(objects(), before)
            self.assertEqual(
                {path: path.stat().st_mtime_ns for path in generated}, timestamps,
            )
            self.assertEqual({path: path.read_bytes() for path in generated}, contents)

            # Missing generated inputs must be restored by reconfiguration.
            for path in generated:
                path.unlink()
            configure()
            self.assertEqual({path: path.read_bytes() for path in generated}, contents)
            compile_consumers()

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
