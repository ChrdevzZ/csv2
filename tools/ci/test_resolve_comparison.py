from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_classify_changes import commit_all, git, initialize_repository


SCRIPT = Path(__file__).with_name("resolve_comparison.py")
CHECK = Path(__file__).with_name("check_patch_whitespace.py")


class ResolveComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        initialize_repository(self.repo)
        (self.repo / "file.txt").write_text("root whitespace \n", encoding="utf-8")
        self.head = commit_all(self.repo, "root")

    def resolve(self, event: str, base: str, head: str,
                repo: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, GITHUB_OUTPUT=str(self.root / "output"))
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--event", event,
             "--base", base, "--head", head],
            cwd=repo or self.repo, env=env, capture_output=True, text=True,
        )

    def test_manual_root_is_explicit_and_not_an_empty_self_diff(self) -> None:
        result = self.resolve("workflow_dispatch", "", self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=manual-current-revision", result.stdout)
        self.assertIn("base=" + "0" * 40, result.stdout)
        checked = subprocess.run(
            [sys.executable, str(CHECK), "--event", "workflow_dispatch",
             "--base", "0" * 40, "--head", self.head],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("trailing whitespace", checked.stdout)

    def test_new_branch_is_explicit_and_selects_all_owners(self) -> None:
        result = self.resolve("push", "0" * 40, self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=new-branch-snapshot", result.stdout)
        self.assertIn("force_all=true", result.stdout)

    def test_missing_push_base_never_becomes_a_parent(self) -> None:
        for base in ("", "f" * 40, "HEAD^", "--all"):
            with self.subTest(base=base):
                result = self.resolve("push", base, self.head)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertFalse((self.root / "output").exists())

    def test_missing_event_head_never_becomes_checkout_head(self) -> None:
        result = self.resolve("push", self.head, "f" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("comparison head", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_pr_and_merge_group_reject_zero_base(self) -> None:
        for event in ("pull_request", "merge_group"):
            result = self.resolve(event, "0" * 40, self.head)
            self.assertNotEqual(result.returncode, 0)

    def test_valid_event_ids_are_preserved(self) -> None:
        (self.repo / "file.txt").write_text("clean\n", encoding="utf-8")
        head = commit_all(self.repo, "second")
        result = self.resolve("push", self.head, head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(dict(line.split("=", 1) for line in result.stdout.splitlines()),
                         dict(base=self.head, head=head, mode="event-range", force_all="false"))
        self.assertEqual((self.root / "output").read_text(), result.stdout)

    def test_shallow_parent_is_not_misclassified_as_root(self) -> None:
        (self.repo / "file.txt").write_text("second\n", encoding="utf-8")
        head = commit_all(self.repo, "second")
        clone = self.root / "shallow"
        git(self.root, "clone", "--quiet", "--depth=1", self.repo.as_uri(), str(clone))
        result = self.resolve("workflow_dispatch", "", head, clone)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("complete history", result.stderr)


if __name__ == "__main__":
    unittest.main()
