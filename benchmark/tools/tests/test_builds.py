from __future__ import annotations

import copy
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _support
from csv2bench import BUILD_SCHEMA, artifacts, builds


REPOSITORY = _support.BENCHMARK_DIR.parent


def valid_current_compile_topology() -> tuple[
    dict[str, dict[str, object]], dict[str, list[str]], Path, str, tuple[str, ...]
]:
    source_root = Path("/csv2-source")
    revision = "a" * 40
    compiler_flags = ("-O3", "-DNDEBUG")
    public_include = str(source_root / "include")
    common_defines = {"BENCHMARK_STATIC_DEFINE", "CSV2_HAS_MMAP=1"}

    def profile(
        target_type: str,
        sources: set[str],
        defines: set[str],
        *,
        include_public: bool = True,
    ) -> dict[str, object]:
        includes = {"/csv2-source/benchmark/current"}
        if include_public:
            includes.add(public_include)
        return {
            "type": target_type,
            "sources": sources,
            "groups": [
                {
                    "fragments": "-O3 -DNDEBUG -std=c++23 -Wall",
                    "defines": defines,
                    "includes": includes,
                    "standard": "23",
                }
            ],
        }

    frontend_sources = set(builds.CURRENT_FRONTEND_SOURCES)
    core_sources = set(builds.CURRENT_CORE_SOURCES)
    config_sources = set(builds.CURRENT_BUILD_CONFIG_SOURCES)
    all_sources = frontend_sources | core_sources | config_sources
    revision_define = f'CSV2_BENCHMARK_REVISION="{revision}"'
    input_define = (
        "CSV2_BENCHMARK_DEFAULT_INPUT="
        f'"{(source_root / "benchmark/datasets/fixtures/short_unquoted.csv").as_posix()}"'
    )
    owners = {
        "csv2_benchmark": profile("EXECUTABLE", frontend_sources, set(common_defines)),
        "csv2_benchmark_allocations": profile(
            "EXECUTABLE",
            frontend_sources,
            common_defines | {"CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1"},
        ),
        "csv2_benchmark_core": profile("OBJECT_LIBRARY", core_sources, set(common_defines)),
        "csv2_benchmark_build_config": profile(
            "OBJECT_LIBRARY",
            config_sources,
            {revision_define, input_define},
            include_public=False,
        ),
        "csv2_benchmark_observer_audit": profile(
            "EXECUTABLE",
            all_sources,
            common_defines
            | {
                "CSV2_BENCHMARK_OBSERVER_AUDIT=1",
                revision_define,
                input_define,
            },
        ),
    }
    closures = {
        "csv2_benchmark": [
            "csv2_benchmark",
            "csv2_benchmark_core",
            "csv2_benchmark_build_config",
        ],
        "csv2_benchmark_allocations": [
            "csv2_benchmark_allocations",
            "csv2_benchmark_core",
            "csv2_benchmark_build_config",
        ],
        "csv2_benchmark_observer_audit": ["csv2_benchmark_observer_audit"],
    }
    return owners, closures, source_root, revision, compiler_flags


class BuildTests(unittest.TestCase):
    def validate_current_topology(
        self,
        owners: dict[str, dict[str, object]],
        closures: dict[str, list[str]],
        source_root: Path,
        revision: str,
        compiler_flags: tuple[str, ...],
    ) -> None:
        builds.validate_current_compile_topology(
            owners=owners,
            target_closures=closures,
            source_root=source_root,
            revision=revision,
            compiler_flags=compiler_flags,
        )

    def test_current_compile_topology_accepts_exact_macro_ownership(self) -> None:
        self.validate_current_topology(*valid_current_compile_topology())

    def test_current_compile_topology_requires_shared_core_dependency(self) -> None:
        topology = valid_current_compile_topology()
        topology[1]["csv2_benchmark"].remove("csv2_benchmark_core")
        with self.assertRaisesRegex(RuntimeError, "compile closure"):
            self.validate_current_topology(*topology)

    def test_current_compile_topology_rejects_different_core(self) -> None:
        topology = valid_current_compile_topology()
        topology[0]["csv2_benchmark_allocations_core"] = copy.deepcopy(
            topology[0]["csv2_benchmark_core"]
        )
        topology[1]["csv2_benchmark_allocations"].remove("csv2_benchmark_core")
        topology[1]["csv2_benchmark_allocations"].append(
            "csv2_benchmark_allocations_core"
        )
        with self.assertRaisesRegex(RuntimeError, "compile owner set|compile closure"):
            self.validate_current_topology(*topology)

    def test_current_compile_topology_rejects_allocation_macro_leak(self) -> None:
        topology = valid_current_compile_topology()
        topology[0]["csv2_benchmark_core"]["groups"][0]["defines"].add(
            "CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1"
        )
        with self.assertRaisesRegex(RuntimeError, "forbidden define"):
            self.validate_current_topology(*topology)

    def test_current_compile_topology_requires_allocation_tracking_macro(self) -> None:
        topology = valid_current_compile_topology()
        topology[0]["csv2_benchmark_allocations"]["groups"][0]["defines"].remove(
            "CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1"
        )
        with self.assertRaisesRegex(RuntimeError, "allocation tracking"):
            self.validate_current_topology(*topology)

    def test_current_compile_topology_requires_revision_on_build_config_only(self) -> None:
        topology = valid_current_compile_topology()
        config_defines = topology[0]["csv2_benchmark_build_config"]["groups"][0][
            "defines"
        ]
        revision_define = next(
            value for value in config_defines if value.startswith("CSV2_BENCHMARK_REVISION=")
        )
        config_defines.remove(revision_define)
        topology[0]["csv2_benchmark_core"]["groups"][0]["defines"].add(revision_define)
        with self.assertRaisesRegex(RuntimeError, "revision define|forbidden define"):
            self.validate_current_topology(*topology)

    def test_current_compile_topology_checks_flags_per_owner(self) -> None:
        topology = valid_current_compile_topology()
        topology[0]["csv2_benchmark_build_config"]["groups"][0]["fragments"] = (
            "-DNDEBUG -std=c++23 -Wall"
        )
        with self.assertRaisesRegex(RuntimeError, "requested compiler flags"):
            self.validate_current_topology(*topology)

    def test_current_compile_topology_requires_independent_observer_target(self) -> None:
        topology = valid_current_compile_topology()
        topology[1]["csv2_benchmark_observer_audit"].append("csv2_benchmark_core")
        with self.assertRaisesRegex(RuntimeError, "compile closure"):
            self.validate_current_topology(*topology)

    def test_current_build_verification_rejects_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = builds.export_git_tree(
                REPOSITORY, "HEAD", root / "source", ("CMakeLists.txt",)
            )

            def create_artifact(name: str, contents: bytes) -> dict[str, object]:
                path = root / name
                path.write_bytes(contents)
                return artifacts.metadata(path)

            compiler = create_artifact("compiler", b"compiler")
            cmake = create_artifact("cmake", b"cmake")
            ninja = create_artifact("ninja", b"ninja")
            compile_commands = create_artifact("compile_commands.json", b"[]")
            corpus_manifest = create_artifact("corpus.json", b"{}")
            benchmark = create_artifact("benchmark", b"benchmark")
            allocations = create_artifact("benchmark-allocations", b"allocations")
            for target in (benchmark, allocations):
                target["revision"] = source["commit"]
            tool = lambda identity: {
                "artifact": identity,
                "version": {
                    "command": [identity["path"], "--version"],
                    "returncode": 0,
                    "stdout": "version",
                    "stderr": "",
                },
            }
            manifest: dict[str, object] = {
                "schema": BUILD_SCHEMA,
                "kind": "current-tree",
                "generated_at_utc": "now",
                "revision": source["commit"],
                "source_export": source,
                "compiler": tool(compiler),
                "compiler_flags": ["-O3", "-DNDEBUG"],
                "cmake": tool(cmake),
                "ninja": tool(ninja),
                "configure_argv": ["cmake", "configure"],
                "normalized_configure_argv": ["cmake", "configure"],
                "build_argv": ["cmake", "--build"],
                "configure_log": {
                    "returncode": 0,
                    "seconds": 1.0,
                    "stdout": "",
                    "stderr": "",
                },
                "build_log": {
                    "returncode": 0,
                    "seconds": 1.0,
                    "stdout": "",
                    "stderr": "",
                },
                "file_api": {},
                "compile_commands": compile_commands,
                "targets": {
                    "csv2_benchmark": benchmark,
                    "csv2_benchmark_allocations": allocations,
                },
                "corpus_manifest": corpus_manifest,
                "source_root": source["root"],
                "build_root": str(root),
            }
            manifest["identity_digest"] = builds.current_build_identity_digest(manifest)
            manifest["digest"] = builds.document_digest(manifest)
            builds.verify_current_build_manifest(manifest)

            exported = Path(source["root"]) / "CMakeLists.txt"
            exported.write_bytes(exported.read_bytes() + b"\n")
            with self.assertRaisesRegex(RuntimeError, "changed after extraction"):
                builds.verify_current_build_manifest(manifest)

    def test_msvc_owned_build_normalizes_source_paths_reproducibly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            headers = builds.export_git_tree(
                REPOSITORY, "HEAD", root / "headers", ("include",)
            )
            adapter = builds.export_git_tree(
                REPOSITORY,
                "HEAD",
                root / "adapter",
                ("benchmark/compare/common_driver.cpp",),
            )
            compiler = root / "cl.exe"
            shutil.copy2(sys.executable, compiler)

            def fake_run(command, **kwargs):
                del kwargs
                if "/Bv" in command:
                    return subprocess.CompletedProcess(
                        command, 0, "fake MSVC compiler 1\n", ""
                    )
                output = next(
                    Path(argument.removeprefix("/Fe:"))
                    for argument in command
                    if argument.startswith("/Fe:")
                )
                output.write_bytes(b"owned-driver")
                return subprocess.CompletedProcess(command, 0, "", "")

            manifest = builds.compile_common_driver(
                header_export=headers,
                adapter_export=adapter,
                compiler=compiler,
                compiler_flags=("/O2", "/DNDEBUG"),
                output=root / "driver.exe",
                run_fn=fake_run,
            )

        normalized = manifest["normalized_argv"]
        self.assertIn("/experimental:deterministic", normalized)
        self.assertIn("/Brepro", normalized)
        self.assertIn("/pathmap:{header_root}=/_csv2/source", normalized)
        self.assertIn("/pathmap:{adapter_root}=/_csv2/adapter", normalized)

    def test_git_paths_reject_cross_platform_escape_forms(self) -> None:
        self.assertEqual(
            builds.safe_git_path("include/csv2/reader.hpp").as_posix(),
            "include/csv2/reader.hpp",
        )
        for value in (
            "../escape",
            "a/../escape",
            "a//escape",
            "a/./escape",
            "/absolute",
            r"..\..\escape",
            r"C:\escape",
            r"\\server\share\escape",
            "file:stream",
            "line\nbreak",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "unsafe Git path"):
                    builds.safe_git_path(value)

    def test_tree_parser_rejects_symlink_submodule_and_unsafe_path(self) -> None:
        object_id = b"a" * 40
        for record in (
            b"120000 blob " + object_id + b"\tlink\0",
            b"160000 commit " + object_id + b"\tsubmodule\0",
            b"100644 blob " + object_id + b"\t..\\escape\0",
        ):
            with self.subTest(record=record):
                with self.assertRaises(RuntimeError):
                    builds.parse_ls_tree(record)

    def test_export_reads_exact_git_blobs_and_records_oids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "export"
            manifest = builds.export_git_tree(
                REPOSITORY,
                "HEAD",
                destination,
                ("include", "benchmark/compare/common_driver.cpp"),
            )
            self.assertEqual(manifest["schema"], "csv2-git-export-v1")
            self.assertRegex(str(manifest["commit"]), r"^[0-9a-f]{40,64}$")
            self.assertRegex(str(manifest["tree"]), r"^[0-9a-f]{40,64}$")
            self.assertTrue(manifest["files"])
            for entry in manifest["files"]:
                exported = destination.joinpath(*Path(entry["path"]).parts)
                self.assertEqual(
                    hashlib.sha256(exported.read_bytes()).hexdigest(), entry["sha256"]
                )
                blob = subprocess.run(
                    ["git", "-C", str(REPOSITORY), "cat-file", "blob", entry["oid"]],
                    check=True,
                    capture_output=True,
                ).stdout
                self.assertEqual(exported.read_bytes(), blob)

    def test_export_rejects_missing_selection_and_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "selection is missing"):
                builds.export_git_tree(REPOSITORY, "HEAD", root / "missing", ("absent",))
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                builds.export_git_tree(REPOSITORY, "HEAD", existing, ("include",))

    def test_export_verification_rejects_content_drift_and_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changed = builds.export_git_tree(
                REPOSITORY, "HEAD", root / "changed", ("include/csv2/reader.hpp",)
            )
            changed_path = Path(changed["root"]) / "include" / "csv2" / "reader.hpp"
            changed_path.write_bytes(changed_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(RuntimeError, "changed after extraction"):
                builds.verify_git_export(changed)

            extra = builds.export_git_tree(
                REPOSITORY, "HEAD", root / "extra", ("include/csv2/reader.hpp",)
            )
            (Path(extra["root"]) / "unmanifested").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unmanifested"):
                builds.verify_git_export(extra)

    def test_owned_build_manifest_binds_objects_compiler_argv_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            headers = builds.export_git_tree(
                REPOSITORY, "HEAD", root / "headers", ("include",)
            )
            adapter = builds.export_git_tree(
                REPOSITORY,
                "HEAD",
                root / "adapter",
                ("benchmark/compare/common_driver.cpp",),
            )
            output = root / "driver.bin"

            def fake_run(command, **kwargs):
                del kwargs
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "fake compiler 1\n", "")
                output_index = command.index("-o") + 1
                Path(command[output_index]).write_bytes(b"owned-driver")
                return subprocess.CompletedProcess(command, 0, "compile stdout", "compile stderr")

            manifest = builds.compile_common_driver(
                header_export=headers,
                adapter_export=adapter,
                compiler=Path(sys.executable),
                compiler_flags=("-std=c++11", "-O3", "-DNDEBUG"),
                output=output,
                run_fn=fake_run,
            )
            self.assertEqual(manifest["schema"], BUILD_SCHEMA)
            self.assertEqual(manifest["revision"], headers["commit"])
            self.assertEqual(manifest["output"]["sha256"], hashlib.sha256(b"owned-driver").hexdigest())
            self.assertIn("{include_root}", " ".join(manifest["normalized_argv"]))
            self.assertIn("{revision}", " ".join(manifest["normalized_argv"]))
            self.assertIn("{output}", " ".join(manifest["normalized_argv"]))
            self.assertEqual(manifest["build_log"]["returncode"], 0)
            self.assertRegex(manifest["digest"], r"^[0-9a-f]{64}$")

            missing_flags = copy.deepcopy(manifest)
            missing_flags["compiler_flags"] = []
            missing_flags["identity_digest"] = builds.common_build_identity_digest(
                missing_flags
            )
            unsigned_missing_flags = dict(missing_flags)
            unsigned_missing_flags.pop("digest")
            missing_flags["digest"] = builds.document_digest(unsigned_missing_flags)
            with self.assertRaisesRegex(RuntimeError, "normalization"):
                builds.validate_build_manifest(missing_flags)

            compatible = copy.deepcopy(manifest)
            builds.assert_compatible_builds(manifest, compatible)
            compatible["normalized_argv"][1] += "-fno-compatible"
            compatible["identity_digest"] = builds.common_build_identity_digest(
                compatible
            )
            unsigned = dict(compatible)
            unsigned.pop("digest")
            compatible["digest"] = builds.document_digest(unsigned)
            with self.assertRaisesRegex(RuntimeError, "normalized build commands"):
                builds.assert_compatible_builds(manifest, compatible)

    def test_common_driver_capabilities_are_explicit_and_legacy_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            headers = builds.export_git_tree(
                REPOSITORY, "HEAD", root / "headers", ("include",)
            )
            adapter = builds.export_git_tree(
                REPOSITORY,
                "HEAD",
                root / "adapter",
                ("benchmark/compare/common_driver.cpp",),
            )

            def fake_run(command, **kwargs):
                del kwargs
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "fake compiler 1\n", "")
                output_index = command.index("-o") + 1
                Path(command[output_index]).write_bytes(b"owned-driver")
                return subprocess.CompletedProcess(command, 0, "", "")

            legacy = builds.compile_common_driver(
                header_export=headers,
                adapter_export=adapter,
                compiler=Path(sys.executable),
                compiler_flags=("-std=c++11", "-O3", "-DNDEBUG"),
                output=root / "legacy-driver",
                run_fn=fake_run,
            )
            modern = builds.compile_common_driver(
                header_export=headers,
                adapter_export=adapter,
                compiler=Path(sys.executable),
                compiler_flags=("-std=c++11", "-O3", "-DNDEBUG"),
                output=root / "modern-driver",
                enable_modern_writer_operations=True,
                run_fn=fake_run,
            )
            for reserved_flags in (
                ("-O3", "-DCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=1"),
                ("-O3", "/DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1"),
                ("-O3", "-D", "CSV2_BENCHMARK_TIMER_SCOPE_AUDIT=1"),
                ("-O3", "/D", "CSV2_BENCHMARK_REVISION=forged"),
                ("-O3", "-Wp,-DCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=1"),
            ):
                with self.subTest(reserved_flags=reserved_flags):
                    with self.assertRaisesRegex(RuntimeError, "reserved"):
                        builds.compile_common_driver(
                            header_export=headers,
                            adapter_export=adapter,
                            compiler=Path(sys.executable),
                            compiler_flags=reserved_flags,
                            output=root / "reserved-driver",
                            run_fn=fake_run,
                        )
            for opaque_flags, message in (
                (("-O3", "@flags.rsp"), "response files"),
                (("-O3", "-Wp,@flags.rsp"), "response files"),
                (("-O3", "-Wp,-include,defines.hpp"), "pass-through"),
                (("-O3", "-include", "defines.hpp"), "preprocessor input"),
                (("-O3", "/FIdefines.hpp"), "preprocessor input"),
            ):
                with self.subTest(opaque_flags=opaque_flags):
                    with self.assertRaisesRegex(RuntimeError, message):
                        builds.compile_common_driver(
                            header_export=headers,
                            adapter_export=adapter,
                            compiler=Path(sys.executable),
                            compiler_flags=opaque_flags,
                            output=root / "opaque-driver",
                            run_fn=fake_run,
                        )

        modern_definition = "CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1"
        legacy_definition = "CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=0"
        audit_definition = "CSV2_BENCHMARK_TIMER_SCOPE_AUDIT=0"
        self.assertTrue(any(legacy_definition in argument for argument in legacy["argv"]))
        self.assertFalse(any(modern_definition in argument for argument in legacy["argv"]))
        self.assertTrue(any(modern_definition in argument for argument in modern["argv"]))
        self.assertEqual(
            sum(audit_definition in argument for argument in legacy["argv"]), 1
        )
        self.assertEqual(
            sum(audit_definition in argument for argument in modern["argv"]), 1
        )


if __name__ == "__main__":
    unittest.main()
