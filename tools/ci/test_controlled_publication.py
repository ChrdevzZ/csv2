from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from test_classify_changes import commit_all, git, initialize_repository


WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/perf.yml"


@unittest.skipUnless(shutil.which("bash"), "workflow authorization uses bash")
class ControlledPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        initialize_repository(self.root)
        (self.root / "input").write_text("base\n", encoding="utf-8")
        base = commit_all(self.root, "baseline")
        (self.root / "input").write_text("head\n", encoding="utf-8")
        head = commit_all(self.root, "candidate")
        self.env = dict(
            os.environ, ACTOR="owner", TRIGGERING_ACTOR="owner", OWNER="owner",
            DEFAULT_BRANCH="master", DISPATCH_REF="refs/heads/master",
            BASELINE_INPUT=base, CANDIDATE_INPUT=head, OPERATIONS="rows_cells",
            RUNS="20", GITHUB_OUTPUT=str(self.root / "output"),
        )
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        authorization = self.workflow.split("  authorize-controlled:\n", 1)[1]
        authorization = authorization.split("\n  controlled:\n", 1)[0]
        self.script = textwrap.dedent(authorization.split("        run: |\n", 1)[1])

    def authorize(self, approval: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", self.script], cwd=self.root,
            env=dict(self.env, PUBLIC_RUNNER_APPROVED=approval),
            capture_output=True, text=True,
        )

    def test_unconfigured_or_invalid_approval_cannot_schedule_private_runner(self) -> None:
        for approval in ("", "false", "TRUE", "1", "true\n"):
            with self.subTest(approval=approval):
                result = self.authorize(approval)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("dedicated public runner", result.stderr)
                self.assertFalse((self.root / "output").exists())

    def test_public_opt_in_preserves_immutable_revision_authorization(self) -> None:
        result = self.authorize("true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "output").read_text().splitlines(), [
            "baseline_sha=" + self.env["BASELINE_INPUT"],
            "candidate_sha=" + self.env["CANDIDATE_INPUT"],
        ])

    def test_public_opt_in_does_not_bypass_owner_or_revision_requirements(self) -> None:
        for key, value in (("ACTOR", "outsider"), ("TRIGGERING_ACTOR", "outsider"),
                           ("RUNS", "1"), ("DISPATCH_REF", "refs/heads/topic"),
                           ("CANDIDATE_INPUT", "HEAD")):
            with self.subTest(key=key):
                original = self.env[key]
                self.env[key] = value
                result = self.authorize("true")
                self.env[key] = original
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "output").exists())

    def test_self_hosted_job_requires_success_and_dedicated_public_label(self) -> None:
        controlled = self.workflow.split("\n  controlled:\n", 1)[1]
        self.assertRegex(controlled, r"needs: authorize-controlled\n")
        self.assertRegex(controlled, r"if: needs.authorize-controlled.result == 'success'\n")
        labels = re.search(r"runs-on: \[([^\]]+)\]", controlled)
        self.assertIsNotNone(labels)
        self.assertIn("csv2-perf-public", labels.group(1).split(", "))
        self.assertIn("${{ vars.CSV2_PERF_PUBLIC_RUNNER_APPROVED }}", self.workflow)


if __name__ == "__main__":
    unittest.main()
