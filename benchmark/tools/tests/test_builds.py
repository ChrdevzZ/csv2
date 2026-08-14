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


class BuildTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
