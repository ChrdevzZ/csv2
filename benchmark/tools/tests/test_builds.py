from __future__ import annotations

import copy
import hashlib
import json
import os
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


def fake_dependencies(command):
    source = next(value for value in command if value.endswith("common_driver.cpp"))
    include = next(value[2:] for value in command if value.startswith(("-I", "/I")))
    header = str(Path(include) / "csv2" / "reader.hpp")
    if "-MF" in command:
        Path(command[command.index("-MF") + 1]).write_text("output: " + source + " " + header + "\n")
    else:
        Path(command[command.index("/sourceDependencies") + 1]).write_text(json.dumps({"Data": {"Source": source, "Includes": [header]}}))


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

    def test_current_compile_topology_rejects_overridden_release_flags(self) -> None:
        cases = (
            (
                "-O3 -O0 -DNDEBUG -std=c++23 -Wall",
                ("-O3", "-DNDEBUG"),
                "effective optimized compile flag",
            ),
            (
                "-O3 -DNDEBUG -UNDEBUG -std=c++23 -Wall",
                ("-O3", "-DNDEBUG"),
                "effective NDEBUG",
            ),
            (
                "/O2 /Od /DNDEBUG /std:c++20 /W4",
                ("/O2", "/DNDEBUG"),
                "effective optimized compile flag",
            ),
            (
                "/O2 /DNDEBUG /UNDEBUG /std:c++20 /W4",
                ("/O2", "/DNDEBUG"),
                "effective NDEBUG",
            ),
            (
                "-O3 -DCSV2_NDEBUG_MARKER -std=c++23 -Wall",
                ("-O3", "-DCSV2_NDEBUG_MARKER"),
                "effective NDEBUG",
            ),
        )
        for fragments, compiler_flags, diagnostic in cases:
            with self.subTest(fragments=fragments):
                topology = valid_current_compile_topology()
                for owner in topology[0].values():
                    owner["groups"][0]["fragments"] = fragments
                with self.assertRaisesRegex(RuntimeError, diagnostic):
                    self.validate_current_topology(
                        topology[0],
                        topology[1],
                        topology[2],
                        topology[3],
                        compiler_flags,
                    )

    def test_current_compile_topology_rejects_opaque_release_flags(self) -> None:
        cases = (
            (
                "-O3 -DNDEBUG @flags.rsp -std=c++23 -Wall",
                "response files",
            ),
            (
                "-O3 -DNDEBUG -include overrides.hpp -std=c++23 -Wall",
                "preprocessor input",
            ),
            (
                "-O3 -DNDEBUG -Wp,-UNDEBUG -std=c++23 -Wall",
                "pass-through",
            ),
            (
                "-O3 -DNDEBUG -includeoverrides.hpp -std=c++23 -Wall",
                "preprocessor input",
            ),
            (
                "-O3 -DNDEBUG -Xpreprocessor -U -Xpreprocessor NDEBUG "
                "-std=c++23 -Wall",
                "pass-through",
            ),
            (
                "-O3 -DNDEBUG -Xclang -U -Xclang NDEBUG -std=c++23 -Wall",
                "pass-through",
            ),
        )
        for fragments, diagnostic in cases:
            with self.subTest(fragments=fragments):
                topology = valid_current_compile_topology()
                for owner in topology[0].values():
                    owner["groups"][0]["fragments"] = fragments
                with self.assertRaisesRegex(RuntimeError, diagnostic):
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
                REPOSITORY, "HEAD", root / "source"
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
                "input_policy": builds.owned_inputs.environment()[1],
                "dependencies": {"schema": "csv2-compile-dependencies-v2", "files": [{"export": "source", "path": entry["path"], "sha256": entry["sha256"]} for entry in source["files"]], "units": [{"owner": owner, "source": relative, "inputs": [str(Path(source["root"]) / entry["path"]) for entry in source["files"]]} for owner, sources in builds.current_dependency_owners().items() for relative in sources], "trusted_system_inputs": [], "trusted_system_roots": []},
                "file_api": {"targets": {}},
                "compile_commands": compile_commands,
                "targets": {
                    "csv2_benchmark": benchmark,
                    "csv2_benchmark_allocations": allocations,
                },
                "corpus_manifest": corpus_manifest,
                "source_root": source["root"],
                "build_root": str(root),
            }
            manifest["configure_argv"] = [
                manifest["cmake"]["artifact"]["path"], "-S", manifest["source_root"],
                "-B", manifest["build_root"], "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                "-DCMAKE_CXX_COMPILER=" + manifest["compiler"]["artifact"]["path"],
                "-DCMAKE_CXX_FLAGS=", "-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG",
                "-DCSV2_BUILD_BENCHMARKS=ON", "-DCSV2_BUILD_BENCHMARK_CHECKS=ON",
                "-DCSV2_VERIFICATION_PROFILE=perf", "-DCSV2_BENCHMARK_CORPUS_SCALE=1",
                "-DCSV2_BENCHMARK_REVISION=" + manifest["revision"], "-DCSV2_REQUIRE_PYTHON_AUDITS=ON",
            ]
            manifest["normalized_configure_argv"] = builds.normalize_build_argv(
                manifest["configure_argv"], (
                    (manifest["source_root"], "{source_root}"), (manifest["build_root"], "{build_root}"),
                    (manifest["compiler"]["artifact"]["path"], "{compiler}"), (manifest["revision"], "{revision}"),
                ),
            )
            manifest["build_argv"] = [
                manifest["cmake"]["artifact"]["path"], "--build", manifest["build_root"], "--target",
                "csv2_benchmark", "csv2_benchmark_allocations", "csv2_benchmark_corpus", "--parallel",
            ]
            manifest["identity_digest"] = builds.current_build_identity_digest(manifest)
            manifest["digest"] = builds.document_digest(manifest)
            builds.verify_current_build_manifest(manifest)

            for units in ([], [None], manifest["dependencies"]["units"][1:]):
                changed = copy.deepcopy(manifest)
                changed["dependencies"]["units"] = units
                changed["identity_digest"] = builds.current_build_identity_digest(changed)
                changed.pop("digest")
                changed["digest"] = builds.document_digest(changed)
                with self.assertRaises(RuntimeError):
                    builds.verify_current_build_manifest(changed)

            contradictory_flags = copy.deepcopy(manifest)
            contradictory_flags["compiler_flags"] = [
                "-O3",
                "-O0",
                "-DNDEBUG",
            ]
            contradictory_flags["identity_digest"] = (
                builds.current_build_identity_digest(contradictory_flags)
            )
            contradictory_flags.pop("digest", None)
            contradictory_flags["digest"] = builds.document_digest(
                contradictory_flags
            )
            with self.assertRaisesRegex(
                RuntimeError, "effective optimized compile flag"
            ):
                builds.verify_current_build_manifest(contradictory_flags)

            exported = Path(source["root"]) / "CMakeLists.txt"
            exported.write_bytes(exported.read_bytes() + b"\n")
            with self.assertRaisesRegex(RuntimeError, "changed after extraction"):
                builds.verify_current_build_manifest(manifest)

    def test_current_build_rejects_release_overrides_before_workspace_setup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            with self.assertRaisesRegex(
                RuntimeError, "effective optimized compile flag"
            ):
                builds.build_current_tree(
                    repository=root / "missing-repository",
                    reference="HEAD",
                    compiler=root / "missing-compiler",
                    compiler_flags=("-O3", "-O0", "-DNDEBUG"),
                    workspace=workspace,
                )
            self.assertFalse(workspace.exists())

    def test_owned_flags_reject_redirects_and_unknown_tokens(self):
        for suffix in [("-I/tmp/shadow",), ("-I", "/tmp/shadow"),
                       ("-isystem/tmp/shadow",), ("-Xclang=-include",),
                       ("--config=/tmp/config",), ("--config", "/tmp/config"),
                       ("-B/tmp/tools",), ("/Ishadow",), ("-D", "CSV2_HAS_MMAP=0"),
                       ("-fplugin=shadow.so",), ("extra.cpp",), ("-specs=x",)]:
            flags = ["-O3", "-DNDEBUG", *suffix]
            with self.subTest(flags=flags):
                with self.assertRaises(RuntimeError):
                    builds._validate_common_compiler_flags(flags)
                with self.assertRaises(RuntimeError):
                    builds._validate_effective_release_flags(flags, "test")
        for flags in [("-O3", "-D", "NDEBUG", "-std=c++11", "-march=native"),
                      ("-O2", "-DNDEBUG", "-stdlib=libc++", "-mavx2"),
                      ("/O2", "/D", "NDEBUG", "/EHsc", "/arch:AVX2")]:
            builds._validate_common_compiler_flags(flags)

    def test_msvc_option_and_macro_spelling_is_case_sensitive(self):
        for flags in [("/O2", "/DNDEBUG"), ("/O2", "/D", "NDEBUG")]:
            builds.owned_inputs.flags(flags, "msvc")
            builds._validate_effective_release_flags(flags, "test")
        for flags in [("/o2", "/DNDEBUG"), ("/O2", "/dNDEBUG"),
                      ("/O2", "/Dndebug"), ("/O2", "/DNDEBUG", "/Od"),
                      ("/O2", "/DNDEBUG", "/UNDEBUG")]:
            with self.subTest(flags=flags), self.assertRaises(RuntimeError):
                builds._validate_effective_release_flags(flags, "test")
        definitions = builds._common_build_definitions(
            ["/dCSV2_BENCHMARK_TIMER_SCOPE_AUDIT=0"])
        self.assertEqual(definitions["CSV2_BENCHMARK_TIMER_SCOPE_AUDIT"], [])

    def test_git_batch_reads_binary_empty_and_duplicate_blobs(self):
        for algorithm in (hashlib.sha1, hashlib.sha256):
            blobs = [b"", b"a\0b\nmissing\n"]
            oids = [algorithm(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()
                    for blob in blobs]
            wire = b"".join(oid.encode() + b" blob " + str(len(blob)).encode()
                            + b"\n" + blob + b"\n" for oid, blob in zip(oids, blobs))
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                self.assertEqual(kwargs["input"], ("\n".join(oids) + "\n").encode())
                return subprocess.CompletedProcess(command, 0, wire, b"")

            self.assertEqual(builds.read_git_blobs(REPOSITORY, [*oids, oids[0]], run_fn=run),
                             dict(zip(oids, blobs)))
            self.assertEqual(len(calls), 1)

    def test_git_batch_rejects_inconsistent_object_frames(self):
        blob = b"body\n"
        oid = hashlib.sha1(b"blob 5\0" + blob).hexdigest()
        valid = oid.encode() + b" blob 5\n" + blob + b"\n"
        for wire in (valid[:-1], valid[:-3], valid + b"extra", b"",
                     valid.replace(b" blob ", b" tree "),
                     valid.replace(b"blob 5", b"blob 05"),
                     valid.replace(blob, b"evil\n"),
                     b"0" * 40 + valid[40:], oid.encode() + b" missing\n"):
            def run(command, **kwargs):
                return subprocess.CompletedProcess(command, 0, wire, b"")
            with self.subTest(wire=wire), self.assertRaises(RuntimeError):
                builds.read_git_blobs(REPOSITORY, [oid], run_fn=run)

    def test_dependency_binding_rejects_missing_and_outside_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = builds.export_git_tree(REPOSITORY, "HEAD", root / "source", ("include",))
            header = Path(source["root"]) / "include/csv2/reader.hpp"
            outside = root / "shadow.hpp"
            outside.write_text("shadow")
            for paths, required in [([], set()), ([str(header), str(outside)], set()),
                                    ([str(header)], {("source", "missing.cpp")})]:
                with self.assertRaises(RuntimeError):
                    builds.owned_inputs.bind_dependencies(paths, {"source": source}, cwd=root, required_sources=required)

    def test_compiler_environment_removes_injection_preserves_sdk(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"CPATH": "/shadow", "CL": "/FIshadow", "INCLUDE": "/sdk", "PATH": "/tools"}):
            env, policy = builds.owned_inputs.environment()
        self.assertNotIn("CPATH", env)
        self.assertNotIn("CL", env)
        self.assertEqual(env["INCLUDE"], "/sdk")
        self.assertEqual(policy["bound"]["PATH"], "/tools")

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
                if "-v" in command:
                    return subprocess.CompletedProcess(command, 0, "", "#include <...> search starts here:\n /usr/include\nEnd of search list.\n")
                if "/Bv" in command:
                    return subprocess.CompletedProcess(
                        command, 0, "fake MSVC compiler 1\n", ""
                    )
                output = next(
                    Path(argument.removeprefix("/Fe:"))
                    for argument in command
                    if argument.startswith("/Fe:")
                )
                fake_dependencies(command)
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

    def test_git_export_ignores_replacements_throughout_object_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()

            def git(*arguments):
                return subprocess.check_output(
                    ["git", "-C", str(repository), *arguments],
                    stderr=subprocess.PIPE, text=True, timeout=30,
                ).strip()

            git("init", "-q")
            git("config", "user.name", "CSV2 export test")
            git("config", "user.email", "csv2-test@example.invalid")
            header = repository / "header.hpp"
            revisions = []
            for content in ("original\n", "replacement\n"):
                header.write_text(content, encoding="utf-8")
                git("add", "header.hpp")
                git("-c", "commit.gpgsign=false", "commit", "-qm", content.strip())
                revisions.append(tuple(git("rev-parse", ref) for ref in (
                    "HEAD", "HEAD^{tree}", "HEAD:header.hpp")))
            original, replacement = revisions
            pristine = builds.export_git_tree(repository, original[0], root / "pristine")
            forged = builds.export_git_tree(repository, replacement[0], root / "forged")
            forged["commit"] = original[0]
            forged.pop("digest")
            forged["digest"] = builds.document_digest(forged)
            for kind, source, target in zip(("commit", "tree", "blob"), original, replacement):
                with self.subTest(kind=kind):
                    git("replace", source, target)
                    try:
                        exported = builds.export_git_tree(repository, original[0], root / kind)
                        self.assertEqual(exported["tree"], original[1])
                        self.assertEqual((root / kind / "header.hpp").read_bytes(), b"original\n")
                        builds.verify_git_export(pristine)
                        builds.verify_git_export(exported)
                        with self.assertRaises(RuntimeError):
                            builds.verify_git_export(forged)
                    finally:
                        git("replace", "-d", source)

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
                if "-v" in command:
                    return subprocess.CompletedProcess(command, 0, "", "#include <...> search starts here:\n /usr/include\nEnd of search list.\n")
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "fake compiler 1\n", "")
                fake_dependencies(command)
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

            for malformed in (None, {}, {**manifest["dependencies"], "files": [None]},
                              {**manifest["dependencies"], "files": [{"export": "headers", "path": "../escape", "sha256": "a" * 64}]}):
                changed = copy.deepcopy(manifest)
                changed["dependencies"] = malformed
                changed["identity_digest"] = builds.common_build_identity_digest(changed)
                changed.pop("digest")
                changed["digest"] = builds.document_digest(changed)
                with self.assertRaises(RuntimeError):
                    builds.validate_build_manifest(changed)

            missing_flags = copy.deepcopy(manifest)
            missing_flags["compiler_flags"] = []
            missing_flags["identity_digest"] = builds.common_build_identity_digest(
                missing_flags
            )
            unsigned_missing_flags = dict(missing_flags)
            unsigned_missing_flags.pop("digest")
            missing_flags["digest"] = builds.document_digest(unsigned_missing_flags)
            with self.assertRaisesRegex(RuntimeError, "controlled command contract"):
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
                if "-v" in command:
                    return subprocess.CompletedProcess(command, 0, "", "#include <...> search starts here:\n /usr/include\nEnd of search list.\n")
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "fake compiler 1\n", "")
                fake_dependencies(command)
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
