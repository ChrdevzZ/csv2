from __future__ import annotations

import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import _support  # noqa: F401
from csv2bench import metrics


class MetricsTests(unittest.TestCase):
    def test_owned_collection_reuses_the_built_compiler_identity(self) -> None:
        class ReportCollected(Exception):
            pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            compiler = root / "canonical-cxx"
            executable = root / "benchmark"
            allocation = root / "benchmark_allocations"
            dataset = root / "input.csv"
            commands = root / "compile_commands.json"
            for path in (compiler, executable, allocation, dataset):
                path.write_text("fixture", encoding="utf-8")
            commands.write_text(json.dumps([
                {"arguments": [str(compiler), "-c", "source.cpp"]}
            ]), encoding="utf-8")
            owned = {
                "revision": "a" * 40,
                "compiler": {
                    "artifact": metrics.artifacts.metadata(compiler),
                    "version": {"command": [str(compiler), "--version"],
                                "stdout": "test compiler", "stderr": ""},
                },
                "targets": {"csv2_benchmark": {"path": str(executable)},
                            "csv2_benchmark_allocations": {"path": str(allocation)}},
                "compile_commands": {"path": str(commands)},
                "build_argv": ["cmake", "--build", str(root / "build")],
                "build_log": {"seconds": 1.0, "stdout": "built", "stderr": ""},
            }
            for argument in ("g++", str(compiler)):
                with self.subTest(argument=argument), unittest.mock.patch(
                    "sys.argv", ["collect_metrics", "--candidate-ref", "HEAD",
                                 "--compiler-executable", argument,
                                 "--compiler-flags=-O3 -DNDEBUG", "--input", str(dataset),
                                 "--operation", "traversal/rows-cells",
                                 "--output", str(root / "report.json")]
                ), unittest.mock.patch.object(
                    metrics.builds, "build_current_tree", return_value=owned
                ), unittest.mock.patch.object(
                    metrics.protocol, "validate_fixed_metrics_report", side_effect=ReportCollected
                ) as validate:
                    with self.assertRaises(ReportCollected):
                        metrics.main()
                    report = validate.call_args.args[0]
                    self.assertEqual(report["compiler_identity"]["artifact"], owned["compiler"]["artifact"])
                    self.assertEqual(report["compiler_identity"]["compile_command_matches"], 1)
                    self.assertIsNone(report["post_build"])

    def test_external_hooks_rebind_commands_and_preserve_drift_checks(self) -> None:
        cases = (
            ("same", "build", None),
            ("matches", "post", None),
            ("mismatch", "post", "declared compiler"),
            ("drift", "build", "compile_commands changed during collection"),
            ("compiler", "build", "compiler_executable changed during collection"),
            ("report-alias", "post", "aliases compile commands"),
            ("manifest-alias", "post", "aliases compile commands"),
        )
        for case, phase, error in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                compiler = root / "cxx"
                executable = root / "benchmark"
                allocation = root / "benchmark_allocations"
                dataset = root / "input.csv"
                commands = root / "compile_commands.json"
                output = root / "report.json"
                manifest = root / "report.json.sha256.json"
                for path in (compiler, executable, allocation, dataset):
                    path.write_text("x", encoding="utf-8")
                entry = {"arguments": [str(compiler), "-c", "source.cpp"]}
                commands.write_text(json.dumps([entry]), encoding="utf-8")
                before = metrics.artifacts.metadata(commands)
                original_compiler = metrics.artifacts.metadata(compiler)
                rebuilt = None

                def invoke(command, **kwargs):
                    nonlocal rebuilt
                    stdout = ""
                    if command == [phase]:
                        if case.endswith("-alias"):
                            target = output if case == "report-alias" else manifest
                            if not target.exists():
                                target.write_text("reserved", encoding="utf-8")
                            commands.unlink()
                            os.link(target, commands)
                        else:
                            entries = [entry] * (2 if case == "matches" else 1)
                            if case == "mismatch":
                                entries = [{"arguments": [str(executable), "-c", "source.cpp"]}]
                            commands.write_text(json.dumps(entries), encoding="utf-8")
                            changed_time = before["mtime_ns"] + 2_000_000_000
                            os.utime(commands, ns=(changed_time, changed_time))
                            rebuilt = metrics.artifacts.metadata(commands)
                        if case == "compiler":
                            compiler.write_text("replacement compiler", encoding="utf-8")
                    elif command in (["build"], ["post"]):
                        pass
                    elif command == [str(compiler), "--version"]:
                        stdout = "test compiler"
                    elif "--csv2-verify" in command:
                        stdout = (
                            "protocol=csv2-current-v4 revision=candidate "
                            "operation=traversal/rows-cells source=buffer dataset=input.csv "
                            "semantic_case_id=csv2.traversal.rows-cells.v1 scope=traversal_only "
                            "byte_basis=input_corpus checksum=1 bytes=1 rows=1 cells=1 "
                            "allocations=0 allocated_bytes=0"
                        )
                    else:
                        timing_output = next(value.split("=", 1)[1] for value in command
                                             if value.startswith("--benchmark_out="))
                        Path(timing_output).write_text(json.dumps({"benchmarks": [{
                            "name": "csv2/traversal/rows-cells/buffer/input.csv/real_time",
                            "real_time": 1, "time_unit": "s",
                            "bytes_per_second": 1, "items_per_second": 1,
                        }]}), encoding="utf-8")
                        if case == "drift":
                            commands.write_text("[]", encoding="utf-8")
                    return unittest.mock.Mock(stdout=stdout, stderr="")

                argv = [
                    "collect_metrics", "--external-artifacts", "--executable", str(executable),
                    "--compiler-executable", str(compiler), "--compile-commands", str(commands),
                    "--revision", "candidate", "--operation", "traversal/rows-cells",
                    "--input", str(dataset), "--runs", "1", "--build-command", "build",
                    "--skip-pmu", "--skip-rss", "--skip-size", "--output", str(output),
                ]
                if phase == "post":
                    argv.extend(["--post-build-command", "post"])
                with unittest.mock.patch("sys.argv", argv), unittest.mock.patch.object(
                    metrics, "run", side_effect=invoke
                ):
                    if error is None:
                        metrics.main()
                    else:
                        with self.assertRaisesRegex(RuntimeError, error):
                            metrics.main()
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "completed" if error is None else "failed")
                self.assertEqual(report["compiler_identity"]["artifact"], original_compiler)
                if error is None:
                    self.assertNotEqual(before["mtime_ns"], rebuilt["mtime_ns"])
                    if case == "same":
                        self.assertEqual(before["sha256"], rebuilt["sha256"])
                    self.assertEqual(report["artifacts"]["compile_commands"], rebuilt)
                    self.assertEqual(report["compiler_identity"]["compile_command_matches"],
                                     2 if case == "matches" else 1)
                    saved_manifest = json.loads(manifest.read_text(encoding="utf-8"))
                    self.assertEqual(saved_manifest["inputs"]["artifacts"], report["artifacts"])

    def test_darwin_optional_metrics_do_not_invoke_gnu_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "benchmark"
            executable.write_bytes(b"executable fixture")
            with unittest.mock.patch.object(
                metrics.platform, "system", return_value="Darwin"
            ), unittest.mock.patch.object(Path, "is_file", return_value=True), unittest.mock.patch.object(
                metrics.shutil, "which", return_value="/usr/bin/size"
            ), unittest.mock.patch.object(metrics, "run", side_effect=AssertionError("GNU tool invoked")) as run:
                with self.subTest(metric="peak_rss"):
                    self.assertIsNone(metrics.collect_peak_rss(unittest.mock.Mock()))
                with self.subTest(metric="code_size"):
                    self.assertEqual(metrics.collect_code_size(executable), {
                        "file_bytes": executable.stat().st_size, "method": "filesystem"
                    })
                self.assertEqual(run.call_count, 0)

    def test_linux_peak_rss_preserves_gnu_backend_failures(self) -> None:
        args = unittest.mock.Mock(
            executable=Path("benchmark"), input=Path("input.csv"),
            operation="traversal/rows", source="buffer", minimum_time="0.1s"
        )

        def collect(command, *, environment):
            self.assertEqual(command[:3], ["/usr/bin/time", "-v", "-o"])
            self.assertEqual(environment["LC_ALL"], "C")
            Path(command[3]).write_text(output, encoding="utf-8")
            return unittest.mock.Mock(stdout="", stderr="")

        with unittest.mock.patch.object(
            metrics.platform, "system", return_value="Linux"
        ), unittest.mock.patch.object(Path, "is_file", return_value=True):
            output = "Maximum resident set size (kbytes): 1234\n"
            with unittest.mock.patch.object(metrics, "run", side_effect=collect):
                self.assertEqual(metrics.collect_peak_rss(args)["kib"], 1234)
                output = "unsupported output\n"
                with self.assertRaisesRegex(RuntimeError, "did not report peak RSS"):
                    metrics.collect_peak_rss(args)
            with unittest.mock.patch.object(
                metrics, "run", side_effect=RuntimeError("benchmark failed")
            ):
                with self.assertRaisesRegex(RuntimeError, "benchmark failed"):
                    metrics.collect_peak_rss(args)

    def test_linux_code_size_preserves_gnu_backend_failures(self) -> None:
        with unittest.mock.patch.object(
            metrics.platform, "system", return_value="Linux"
        ), unittest.mock.patch.object(metrics.shutil, "which", return_value="/usr/bin/size"):
            with unittest.mock.patch.object(metrics, "run", return_value=unittest.mock.Mock(
                stdout="text data bss dec hex filename\n10 20 30 60 3c benchmark\n"
            )) as run:
                result = metrics.collect_code_size(Path("benchmark"))
                self.assertEqual(result["text_bytes"], 10)
                self.assertEqual(result["total_bytes"], 60)
                self.assertEqual(run.call_args.args[0], [
                    "/usr/bin/size", "--format=berkeley", "benchmark"
                ])
                self.assertEqual(run.call_args.kwargs["environment"]["LC_ALL"], "C")
                run.return_value.stdout = "unsupported output\n"
                with self.assertRaisesRegex(RuntimeError, "unexpected size tool output"):
                    metrics.collect_code_size(Path("benchmark"))
            with unittest.mock.patch.object(
                metrics, "run", side_effect=RuntimeError("size failed")
            ):
                with self.assertRaisesRegex(RuntimeError, "size failed"):
                    metrics.collect_code_size(Path("benchmark"))

    def test_verify_command_uses_current_v4_cli(self) -> None:
        command = metrics.verify_command(
            Path("bench"), "traversal/rows", Path("input.csv"), "buffer"
        )
        self.assertEqual(command[-1], "--csv2-verify")
        self.assertIn("--csv2-operation", command)
        self.assertNotIn("--operation", command)

    def test_verification_rejects_revision_mismatch(self) -> None:
        with unittest.mock.patch.object(
            metrics,
            "run",
            return_value=unittest.mock.Mock(
                stdout=(
                    "protocol=csv2-current-v4 revision=other operation=traversal/rows "
                    "source=buffer dataset=x.csv semantic_case_id=csv2.traversal.rows.v1 "
                    "scope=traversal_only byte_basis=input_corpus "
                    "checksum=1 bytes=1 rows=1 cells=0 "
                    "allocations=0 allocated_bytes=0\n"
                ),
                stderr="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "revision"):
                metrics.verify(
                    Path("bench"), "traversal/rows", Path("input.csv"), "buffer", "expected"
                )

    def test_timing_command_binds_operation_source_and_json(self) -> None:
        command = metrics.timing_command(
            Path("bench"),
            "writer/raw-direct",
            Path("input.csv"),
            "buffer",
            Path("result.json"),
            20,
            "0.5s",
            0.1,
        )
        self.assertIn("--benchmark_repetitions=20", command)
        self.assertIn("--benchmark_out_format=json", command)
        self.assertTrue(any("writer/raw-direct" in value for value in command))

    def test_timing_report_requires_exact_iteration_count(self) -> None:
        document = {
            "benchmarks": [
                {
                    "name": "csv2/traversal/rows/buffer/x.csv",
                    "run_type": "iteration",
                    "real_time": 10,
                    "time_unit": "ns",
                    "bytes_per_second": 100,
                    "items_per_second": 10,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            parsed = metrics.parse_timing_report(path, 1)
            self.assertEqual(parsed["runs"], 1)
            with self.assertRaisesRegex(RuntimeError, "expected 2"):
                metrics.parse_timing_report(path, 2)

    def test_timing_report_rejects_mixed_benchmark_names(self) -> None:
        records = []
        for name in ("one", "two"):
            records.append(
                {
                    "name": name,
                    "real_time": 1,
                    "time_unit": "ns",
                    "bytes_per_second": 1,
                    "items_per_second": 1,
                }
            )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps({"benchmarks": records}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "exactly one benchmark"):
                metrics.parse_timing_report(path, 2)

    def test_timing_report_rejects_skipped_or_error_samples(self) -> None:
        for marker in ({"error_occurred": True, "error_message": "read failed"},
                       {"skipped": True}):
            record = {
                "name": "csv2/source/file-read-cached/file/x.csv",
                "run_type": "iteration",
                "real_time": 1,
                "time_unit": "ns",
                "bytes_per_second": 1,
                "items_per_second": 1,
                **marker,
            }
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "result.json"
                path.write_text(json.dumps({"benchmarks": [record]}), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "failed or skipped"):
                    metrics.parse_timing_report(path, 1)

    def test_controlled_timing_requires_every_pmu_counter(self) -> None:
        document = {
            "benchmarks": [
                {
                    "name": "csv2/traversal/rows/buffer/x.csv",
                    "real_time": 1,
                    "time_unit": "ns",
                    "bytes_per_second": 1,
                    "items_per_second": 1,
                    "cycles": 1,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "missing required PMU counters"):
                metrics.parse_timing_report(path, 1, require_pmu=True)

    def test_affinity_parser_is_strict_and_canonical(self) -> None:
        self.assertEqual(metrics.parse_affinity("2,0,2"), [0, 2])
        for value in ("", "-1", "x"):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    metrics.parse_affinity(value)

    def test_compile_commands_bind_the_declared_compiler(self) -> None:
        compiler = Path(__import__("sys").executable).resolve()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compile_commands.json"
            path.write_text(
                json.dumps([{"arguments": [str(compiler), "-c", "source.cpp"]}]),
                encoding="utf-8",
            )
            self.assertEqual(metrics.validate_compile_commands(path, compiler), 1)
            path.write_text(
                json.dumps([{"arguments": [str(path), "-c", "source.cpp"]}]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "declared compiler"):
                metrics.validate_compile_commands(path, compiler)


if __name__ == "__main__":
    unittest.main()
