from __future__ import annotations

import json
import io
import argparse
import subprocess
import shlex
import contextlib
import sys
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import _support  # noqa: F401
from csv2bench import metrics, protocol


class MetricsTests(unittest.TestCase):
    def test_external_compiler_identity_command_and_failure(self):
        for name, arguments in (("CL.EXE", ["/Bv", "/?"]), ("g++", ["--version"])):
            for returncode, stdout, stderr, message in (
                (0, "", "compiler identity", "identity accepted"),
                (0, " ", "\n", "no identity"),
                (7, "", "unsupported option", "exit: 7"),
            ):
                with self.subTest(name=name, returncode=returncode, stderr=stderr), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory).resolve()
                    compiler = root / name
                    executable, dataset = root / "driver", root / "input.csv"
                    for path in (compiler, executable, dataset):
                        path.write_text("x", encoding="utf-8")
                    argv = ["collect_metrics", "--external-artifacts", "--executable", str(executable),
                            "--allocation-executable", str(executable), "--compiler-executable", str(compiler), "--revision", "candidate",
                            "--operation", "traversal/rows-cells", "--input", str(dataset),
                            "--skip-pmu", "--skip-rss", "--skip-size", "--output", str(root / "report.json")]
                    completed = subprocess.CompletedProcess([str(compiler), *arguments], returncode, stdout, stderr)
                    with unittest.mock.patch.object(sys, "argv", argv), \
                         unittest.mock.patch.object(metrics.subprocess, "run", return_value=completed) as invoke, \
                         unittest.mock.patch.object(metrics, "machine_metadata", side_effect=RuntimeError("identity accepted")):
                        with self.assertRaisesRegex(RuntimeError, message):
                            metrics.main()
                    invoke.assert_called_once_with([str(compiler), *arguments], capture_output=True, text=True, env=None)

    def test_hook_argv_preserves_argument_boundaries(self) -> None:
        import test_protocol
        from _schema_subset import validate as validate_schema

        report = test_protocol.fixed_metrics_report()
        schema_path = Path(__file__).resolve().parents[2] / "protocol/schemas/fixed-machine-v7.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        arguments = [sys.executable, "-c", "import json, sys; print(json.dumps(sys.argv[1:]))",
                     r"C:\Program Files\tool\input.csv", "with spaces", "", 'embedded"quote',
                     "$HOME; echo unwanted", "trailing\\"]
        parsed = metrics.parse_hook_argv(json.dumps(arguments))
        self.assertEqual(parsed, arguments)
        for field, invoke in (("clean_build", metrics.time_build), ("post_build", metrics.run_post_build)):
            with self.subTest(hook=invoke.__name__):
                result = invoke(parsed)
                self.assertEqual(result["command"], arguments)
                self.assertEqual(json.loads(result["stdout"]), arguments[3:])
                report[field] = result
                protocol.validate_fixed_metrics_report(report)
                validate_schema(report, schema)

    def test_hook_argv_rejects_invalid_cli_input_before_build(self) -> None:
        invalid = ["not json", "{}", '"command"', "[]", '[""]', '[1]',
                   '["tool", null]', '["tool", false]', '["tool", ["arg"]]',
                   json.dumps(["tool", "nul\0arg"]), json.dumps(["nul\0tool"])]
        base = ["collect_metrics", "--candidate-ref", "HEAD", "--compiler-executable", "cc",
                "--operation", "traversal/rows-cells", "--input", "input.csv", "--output", "out.json"]
        external = ["collect_metrics", "--external-artifacts", "--executable", "driver",
                    "--revision", "HEAD", "--operation", "traversal/rows-cells",
                    "--input", "input.csv", "--output", "out.json"]
        cases = [(base + ["--build-argv", value], "hook argv") for value in invalid]
        cases.extend([
            (base + ["--build-argv", '["build"]'], "external build"),
            (base + ["--post-build-argv", '["post"]'], "external build"),
            (base + ["--build-arg", '["build"]'], "unrecognized arguments"),
            (external + ["--post-build-argv", '["post"]'], "requires --build-argv"),
            (external + ["--compile-commands", "commands.json"], "requires --compiler-executable"),
            (external + ["--compile-commands", "commands.json", "--build-argv", '["build"]',
                         "--post-build-argv", '["post"]'], "requires --compiler-executable"),
        ])
        for argv, message in cases:
            stderr = io.StringIO()
            with self.subTest(argv=argv), contextlib.ExitStack() as stack:
                stack.enter_context(unittest.mock.patch.object(sys, "argv", argv))
                stack.enter_context(contextlib.redirect_stderr(stderr))
                build = stack.enter_context(unittest.mock.patch.object(metrics.builds, "build_current_tree"))
                with self.assertRaises(SystemExit) as raised:
                    metrics.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn(message, stderr.getvalue())
                build.assert_not_called()

    def test_runtime_boundaries_prevent_completed_publication_after_drift(self) -> None:
        import test_protocol

        for level, drift in (("controlled", "before"), ("controlled", "after"),
                             ("controlled", None), ("exploratory", None)):
            with self.subTest(level=level, drift=drift), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                executable = root / "driver"
                executable.write_text("fixture", encoding="utf-8")
                dataset = root / "input.csv"
                dataset.write_text("x", encoding="utf-8")
                commands = root / "compile_commands.json"
                commands.write_text(json.dumps([
                    {"directory": str(root), "arguments": [str(executable), "-c", "source.cpp"]}
                ]), encoding="utf-8")
                fixture = test_protocol.controlled_metrics_report()
                owned = fixture["build"]
                owned["compiler"]["artifact"] = metrics.artifacts.metadata(executable)
                for target in owned["targets"].values():
                    target["path"] = str(executable)
                owned["compile_commands"]["path"] = str(commands)
                profile = {"artifact": metrics.artifacts.metadata(executable),
                           "observation": {"process_affinity": [2]}}
                events = []

                def check(binding):
                    self.assertEqual(binding, profile)
                    phase = "after" if "sample" in events else "before"
                    events.append(phase)
                    if drift == phase:
                        raise RuntimeError("runtime state changed: governor")

                def sample(*args, **kwargs):
                    events.append("pmu" if kwargs.get("pmu") else "sample")
                    return {}, {}

                output = root / "report.json"
                argv = ["collect_metrics", "--candidate-ref", "HEAD",
                        "--compiler-executable", str(executable), "--compiler-flags=-O3",
                        "--input", str(dataset), "--operation", "traversal/rows-cells",
                        "--runs", "20", "--evidence-level", level, "--output", str(output)]
                if level == "controlled":
                    argv += ["--cpu-affinity", "2", "--machine-profile", str(executable)]
                verified = fixture["verification"]
                with contextlib.ExitStack() as stack:
                    stack.enter_context(unittest.mock.patch.object(sys, "argv", argv))
                    for obj, name, kwargs in (
                        (metrics.platform, "system", {"return_value": "Linux"}),
                        (metrics.os, "sched_getaffinity", {"return_value": {2}, "create": True}),
                        (metrics.builds, "build_current_tree", {"return_value": owned}),
                        (metrics.builds, "verify_current_build_manifest", {}),
                        (metrics.machine, "load", {"return_value": profile}),
                        (metrics.machine, "verify_runtime", {"side_effect": check}),
                        (metrics, "verify", {"return_value": (verified["result"], verified["invocation"])}),
                        (metrics, "collect_timing", {"side_effect": sample}),
                        (metrics, "collect_peak_rss", {"return_value": {}}),
                        (metrics, "collect_code_size", {"return_value": {}}),
                        (metrics.protocol, "validate_fixed_metrics_report", {}),
                        (metrics.protocol, "validate_artifact_manifest", {}),
                    ):
                        stack.enter_context(unittest.mock.patch.object(obj, name, **kwargs))
                    if drift:
                        with self.assertRaisesRegex(RuntimeError, "runtime state changed"):
                            metrics.main()
                    else:
                        metrics.main()
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "failed" if drift else "completed")
                self.assertEqual(output.with_suffix(".json.sha256.json").exists(), drift is None)
                self.assertEqual(events, ["before"] if drift == "before" else
                                 ["before", "sample", "pmu", "after"] if level == "controlled" else
                                 ["sample", "pmu"])

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
                {"directory": str(root), "arguments": [str(compiler), "-c", "source.cpp"]}
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
            ("compiler-only", "post", None),
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
                entry = {"directory": str(root), "arguments": [str(compiler), "-c", "source.cpp"]}
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
                                entries = [{"directory": str(root), "arguments": [str(executable), "-c", "source.cpp"]}]
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
                    "--input", str(dataset), "--runs", "1", "--build-argv", '["build"]',
                    "--skip-pmu", "--skip-rss", "--skip-size", "--output", str(output),
                ]
                if case == "compiler-only":
                    index = argv.index("--compile-commands")
                    del argv[index:index + 2]
                if phase == "post":
                    argv.extend(["--post-build-argv", '["post"]'])
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
                    if case == "compiler-only":
                        self.assertNotIn("compile_commands", report["artifacts"])
                        self.assertIsNone(report["compiler_identity"]["compile_command_matches"])
                    else:
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

    def test_compile_commands_resolve_in_the_compilation_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            build = root / "project" / "build"
            collector = root / "review" / "build"
            for directory in (build, collector):
                directory.mkdir(parents=True)
                (directory.parent / "toolchain").mkdir()
            name = "cxx.exe" if os.name == "nt" else "cxx"
            compiler = build.parent / "toolchain" / name
            interference = collector.parent / "toolchain" / name
            for executable in (compiler, interference):
                executable.write_text("compiler fixture", encoding="utf-8")
                executable.chmod(0o755)
            database = root / "compile_commands.json"
            probe = (
                "from pathlib import Path; from csv2bench.metrics import validate_compile_commands; "
                "import sys; print(validate_compile_commands(Path(sys.argv[1]), Path(sys.argv[2])))"
            )
            environment = {**os.environ, "PYTHONPATH": str(Path(metrics.__file__).parents[1]),
                           "PATH": os.pathsep.join(("../toolchain", ""))}
            for representation in ("arguments", "command"):
                for executable in ("../toolchain/" + name, name, str(compiler)):
                    with self.subTest(representation=representation, executable=executable):
                        arguments = [executable, "-c", "source.cpp"]
                        entry = {"directory": str(build), representation:
                                 arguments if representation == "arguments" else
                                 subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)}
                        database.write_text(json.dumps([entry]), encoding="utf-8")
                        for declared, expected in ((compiler, 0), (interference, 1)):
                            result = subprocess.run(
                                [sys.executable, "-c", probe, str(database), str(declared)],
                                cwd=collector, env=environment, capture_output=True, text=True,
                            )
                            self.assertEqual(result.returncode, expected, result.stderr)
            # An empty PATH component searches the compilation directory itself.
            database.write_text(json.dumps([{"directory": str(compiler.parent),
                "arguments": [name]}]), encoding="utf-8")
            with unittest.mock.patch.dict(os.environ, {"PATH": ""}):
                self.assertEqual(metrics.validate_compile_commands(database, compiler), 1)
            for directory in (None, "", "relative", str(root / "missing"), str(compiler)):
                with self.subTest(directory=directory):
                    database.write_text(json.dumps([{"directory": directory,
                        "arguments": [str(compiler)]}]), encoding="utf-8")
                    with self.assertRaisesRegex(RuntimeError, "compilation directory"):
                        metrics.validate_compile_commands(database, compiler)

    @unittest.skipUnless(os.name == "nt", "Windows drive-relative path semantics")
    def test_windows_compiler_paths_require_an_absolute_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            compiler = root / "cxx.exe"
            compiler.write_text("compiler fixture", encoding="utf-8")
            database = root / "compile_commands.json"
            drive = root.drive
            other_drive = "D:" if drive.upper() == "C:" else "C:"
            for executable in (drive + "cxx.exe", str(compiler)[len(drive):]):
                database.write_text(json.dumps([{"directory": str(root),
                    "arguments": [executable]}]), encoding="utf-8")
                self.assertEqual(metrics.validate_compile_commands(database, compiler), 1)
            for executable, search in ((other_drive + "cxx.exe", str(root)),
                                       ("cxx.exe", other_drive + "tools")):
                with self.subTest(executable=executable, search=search):
                    database.write_text(json.dumps([{"directory": str(root),
                        "arguments": [executable]}]), encoding="utf-8")
                    with unittest.mock.patch.dict(os.environ, {"PATH": search}):
                        with self.assertRaisesRegex(RuntimeError, "cannot be anchored"):
                            metrics.validate_compile_commands(database, compiler)

    def test_windows_bare_compiler_respects_pathext_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            compiler = root / "cxx.exe"
            compiler.write_text("compiler fixture", encoding="utf-8")
            compiler.chmod(0o755)
            database = root / "compile_commands.json"
            database.write_text(json.dumps([{"directory": str(root),
                "arguments": ["cxx"]}]), encoding="utf-8")

            interference = root / "cxx.com.exe"
            interference.write_text("second expansion interference", encoding="utf-8")
            interference.chmod(0o755)

            with unittest.mock.patch.object(metrics.platform, "system", return_value="Windows"), \
                    unittest.mock.patch.dict(os.environ, {"PATH": str(root), "PATHEXT": ".com;.exe"}):
                self.assertEqual(metrics.validate_compile_commands(database, compiler), 1)
                other = root / "cxx.com"
                other.write_text("earlier extension", encoding="utf-8")
                other.chmod(0o755)
                with self.assertRaisesRegex(RuntimeError, "declared compiler"):
                    metrics.validate_compile_commands(database, compiler)
                self.assertEqual(metrics.validate_compile_commands(database, other), 1)

    def test_compile_commands_reject_malformed_commands_and_use_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            database = root / "compile_commands.json"
            compiler = Path(sys.executable).resolve()
            for invalid in ({"arguments": [""]}, {"command": '"unterminated'}):
                with self.subTest(invalid=invalid):
                    database.write_text(json.dumps([{"directory": str(root), **invalid}]), encoding="utf-8")
                    with self.assertRaisesRegex(RuntimeError, "empty executable|malformed command"):
                        metrics.validate_compile_commands(database, compiler)
            database.write_text(json.dumps([{"directory": str(root),
                "arguments": [compiler.name]}]), encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if key.upper() != "PATH"}
            with unittest.mock.patch.dict(os.environ, environment, clear=True), unittest.mock.patch.object(
                os, "defpath", str(compiler.parent)
            ):
                self.assertEqual(metrics.validate_compile_commands(database, compiler), 1)

    def test_measurements_filter_benchmark_environment_but_hooks_inherit_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "probe.py"
            script.write_text(
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "print(json.dumps(dict(os.environ)))\n"
                "options = dict(arg.split('=', 1) for arg in sys.argv[1:] if '=' in arg)\n"
                "if '--benchmark_out' in options:\n"
                "    record = dict(name='probe', real_time=1, time_unit='s', bytes_per_second=1)\n"
                "    if '--benchmark_perf_counters' in options:\n"
                "        record.update({key: 1 for key in options['--benchmark_perf_counters'].split(',')})\n"
                "    Path(options['--benchmark_out']).write_text(json.dumps({'benchmarks': [record]}))\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(executable=Path(sys.executable), input=Path("input.csv"),
                operation="traversal/rows", source="buffer", runs=1,
                minimum_time="0.1s", warmup_seconds=0.0)
            original_command = metrics.timing_command

            def command(*args, **kwargs):
                argv = original_command(*args, **kwargs)
                return [argv[0], str(script), *argv[1:]]

            injected = {"BENCHMARK_DRY_RUN": "1", "benchmark_perf_counters": "cycles",
                        "BeNcHmArK_FUTURE_FLAG": "1", "CSV2_ENV_SENTINEL": "retained", "LC_ALL": "POSIX"}
            with unittest.mock.patch.dict(os.environ, injected), unittest.mock.patch.object(
                metrics, "timing_command", side_effect=command
            ):
                for pmu in (False, True):
                    result, invocation = metrics.collect_timing(args, pmu=pmu)
                    environment = json.loads(invocation["stdout"])
                    self.assertFalse(any(key.upper().startswith("BENCHMARK_") for key in environment))
                    self.assertEqual(environment["CSV2_ENV_SENTINEL"], "retained")
                    self.assertEqual("pmu" in result["samples"][0], pmu)
                if sys.platform.startswith("linux") and Path("/usr/bin/time").is_file():
                    rss = metrics.collect_peak_rss(args)
                    environment = json.loads(rss["stdout"])
                    self.assertFalse(any(key.upper().startswith("BENCHMARK_") for key in environment))
                    self.assertEqual(environment["LC_ALL"], "C")
                    self.assertEqual(environment["CSV2_ENV_SENTINEL"], "retained")
                hook = [sys.executable, str(script)]
                for invoke in (metrics.time_build, metrics.run_post_build):
                    environment = json.loads(invoke(hook)["stdout"])
                    for key, value in injected.items():
                        self.assertEqual({name.upper(): item for name, item in environment.items()}[key.upper()], value)


if __name__ == "__main__":
    unittest.main()
