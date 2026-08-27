from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("evaluate_gate.py")


def evaluate(*jobs: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT)]
    for job in jobs:
        command.extend(("--job", job))
    return subprocess.run(command, capture_output=True, text=True)


class EvaluateGateTests(unittest.TestCase):
    def test_all_required_jobs_succeed(self) -> None:
        completed = evaluate(
            "classify:true:success",
            "preflight:true:success",
            "linux:true:success",
            "full:false:skipped",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_required_skipped_job_fails_gate(self) -> None:
        completed = evaluate("linux:true:skipped")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("required job linux ended as skipped", completed.stderr)

    def test_required_canceled_job_fails_gate(self) -> None:
        completed = evaluate("full:true:cancelled")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("required job full ended as cancelled", completed.stderr)

    def test_optional_failure_is_not_hidden(self) -> None:
        completed = evaluate("perf:false:failure")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("optional job perf unexpectedly ended as failure", completed.stderr)

    def test_optional_skipped_job_is_accepted(self) -> None:
        completed = evaluate("perf:false:skipped")
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_malformed_job_state_fails_closed(self) -> None:
        completed = evaluate("linux:maybe:success")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invalid required flag", completed.stderr)


if __name__ == "__main__":
    unittest.main()
