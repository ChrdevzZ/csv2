from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).with_name("run_fuzz_targets.py")
SPEC = importlib.util.spec_from_file_location("run_fuzz_targets", MODULE)
assert SPEC and SPEC.loader
run_fuzz_targets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_fuzz_targets)


class RunFuzzTargetsTests(unittest.TestCase):
    def run_pair(self, reader_status: int, writer_status: int) -> tuple[int, list[list[str]], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        reader = root / "reader"
        writer = root / "writer"
        reader_corpus = root / "reader-corpus"
        writer_corpus = root / "writer-corpus"
        for path in (reader, writer):
            path.write_bytes(b"executable")
        for path in (reader_corpus, writer_corpus):
            path.mkdir()
        calls: list[list[str]] = []

        def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
            self.assertFalse(check)
            calls.append(command)
            status = reader_status if Path(command[0]) == reader else writer_status
            if status:
                prefix = next(
                    value.removeprefix("-artifact_prefix=")
                    for value in command
                    if value.startswith("-artifact_prefix=")
                )
                (Path(prefix) / "crash-deadbeef").write_bytes(b"reproducer")
            return subprocess.CompletedProcess(command, status)

        status = run_fuzz_targets.run_pair(
            reader=reader,
            writer=writer,
            reader_corpus=reader_corpus,
            writer_corpus=writer_corpus,
            runs=5000,
            artifact_root=root / "artifacts",
            run_fn=fake_run,
        )
        return status, calls, root

    def test_reader_failure_does_not_skip_writer_and_preserves_reproducer(self) -> None:
        status, calls, root = self.run_pair(1, 0)
        self.assertEqual(status, 1)
        self.assertEqual([Path(call[0]).name for call in calls], ["reader", "writer"])
        self.assertTrue((root / "artifacts" / "reader" / "crash-deadbeef").is_file())

    def test_writer_failure_runs_after_reader_and_preserves_reproducer(self) -> None:
        status, calls, root = self.run_pair(0, 1)
        self.assertEqual(status, 1)
        self.assertEqual([Path(call[0]).name for call in calls], ["reader", "writer"])
        self.assertTrue((root / "artifacts" / "writer" / "crash-deadbeef").is_file())

    def test_both_failures_preserve_both_reproducers_and_statuses(self) -> None:
        status, calls, root = self.run_pair(17, 23)
        self.assertEqual(status, 1)
        self.assertEqual([Path(call[0]).name for call in calls], ["reader", "writer"])
        self.assertTrue((root / "artifacts" / "reader" / "crash-deadbeef").is_file())
        self.assertTrue((root / "artifacts" / "writer" / "crash-deadbeef").is_file())
        self.assertEqual(
            (root / "artifacts" / "reader" / "status.txt").read_text(
                encoding="utf-8"
            ),
            "exit_code=17\n",
        )
        self.assertEqual(
            (root / "artifacts" / "writer" / "status.txt").read_text(
                encoding="utf-8"
            ),
            "exit_code=23\n",
        )

    def test_success_runs_both_targets_with_isolated_artifact_prefixes(self) -> None:
        status, calls, root = self.run_pair(0, 0)
        self.assertEqual(status, 0)
        self.assertEqual(len(calls), 2)
        self.assertIn(
            f"-artifact_prefix={(root / 'artifacts' / 'reader').as_posix()}/",
            calls[0],
        )
        self.assertIn(
            f"-artifact_prefix={(root / 'artifacts' / 'writer').as_posix()}/",
            calls[1],
        )
        self.assertIn("-runs=5000", calls[0])
        self.assertIn("-runs=5000", calls[1])

    def test_launch_error_does_not_skip_the_other_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name for name in ("reader", "writer")]
            corpora = [root / name for name in ("reader-corpus", "writer-corpus")]
            for path in paths:
                path.write_bytes(b"executable")
            for path in corpora:
                path.mkdir()
            calls: list[list[str]] = []

            def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
                self.assertFalse(check)
                calls.append(command)
                if len(calls) == 1:
                    raise OSError("cannot launch reader")
                return subprocess.CompletedProcess(command, 0)

            status = run_fuzz_targets.run_pair(
                reader=paths[0],
                writer=paths[1],
                reader_corpus=corpora[0],
                writer_corpus=corpora[1],
                runs=1,
                artifact_root=root / "artifacts",
                run_fn=fake_run,
            )
            self.assertEqual(status, 1)
            self.assertEqual(len(calls), 2)
            self.assertEqual(
                (root / "artifacts" / "reader" / "status.txt").read_text(
                    encoding="utf-8"
                ),
                "launch_error=cannot launch reader\n",
            )


if __name__ == "__main__":
    unittest.main()
