from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_classify_changes import commit_all, git, initialize_repository


SCRIPT = Path(__file__).with_name("check_patch_whitespace.py")


class PatchWhitespaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "origin"
        self.source.mkdir()
        initialize_repository(self.source)
        git(self.source, "config", "core.autocrlf", "false")
        git(self.source, "config", "commit.gpgsign", "false")
        (self.source / "data.txt").write_text("initial\n", encoding="utf-8")
        self.common = commit_all(self.source, "common")

    def check(self, repo: Path, base: str, head: str,
              event: str = "push") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--base", base, "--head", head,
             "--event", event], cwd=repo, capture_output=True, text=True,
        )

    def rewritten_checkout(self, text: str) -> tuple[Path, str, str]:
        git(self.source, "switch", "--quiet", "--create", "discarded")
        (self.source / "data.txt").write_text("old head\n", encoding="utf-8")
        old = commit_all(self.source, "old history")
        git(self.source, "switch", "--quiet", "--create", "rewritten", self.common)
        (self.source / "data.txt").write_text(text, encoding="utf-8")
        new = commit_all(self.source, "rewritten history")
        clone = self.root / "checkout"
        git(self.root, "clone", "--quiet", "--no-local", "--single-branch",
            "--branch", "rewritten", str(self.source), str(clone))
        missing = subprocess.run(
            ["git", "cat-file", "-e", f"{old}^{{commit}}"], cwd=clone,
            capture_output=True,
        )
        self.assertNotEqual(missing.returncode, 0)
        return clone, old, new

    def test_existing_base_does_not_need_a_remote(self) -> None:
        (self.source / "data.txt").write_text("clean patch\n", encoding="utf-8")
        head = commit_all(self.source, "clean patch")
        result = self.check(self.source, self.common, head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Fetching", result.stderr)

    def test_missing_rewritten_base_is_fetched_without_changing_refs(self) -> None:
        clone, old, new = self.rewritten_checkout("old head\n")
        refs = git(clone, "show-ref")
        result = self.check(clone, old, new)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Fetching", result.stderr)
        self.assertEqual(git(clone, "show-ref"), refs)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), new)
        self.assertFalse((clone / ".git" / "shallow").exists())
        self.assertFalse((clone / ".git" / "FETCH_HEAD").exists())

    def test_classifier_fetch_is_repeated_in_separate_preflight_checkout(self) -> None:
        classify_checkout, old, new = self.rewritten_checkout("bad patch \n")
        preflight_checkout = self.root / "preflight"
        git(self.root, "clone", "--quiet", "--no-local", "--single-branch",
            "--branch", "rewritten", str(self.source), str(preflight_checkout))
        resolved = subprocess.run(
            [sys.executable, str(SCRIPT.with_name("resolve_comparison.py")),
             "--event", "push", "--base", old, "--head", new],
            cwd=classify_checkout, capture_output=True, text=True,
        )
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        self.assertIn("base=" + old, resolved.stdout)
        missing = subprocess.run(
            ["git", "cat-file", "-e", f"{old}^{{commit}}"],
            cwd=preflight_checkout, capture_output=True,
        )
        self.assertNotEqual(missing.returncode, 0)
        checked = self.check(preflight_checkout, old, new)
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("Fetching", checked.stderr)
        self.assertIn("trailing whitespace", checked.stdout)

    def test_fetched_base_does_not_hide_whitespace_errors(self) -> None:
        clone, old, new = self.rewritten_checkout("bad patch \n")
        result = self.check(clone, old, new)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("trailing whitespace", result.stdout)

    def test_unavailable_base_fails_with_recovery_guidance(self) -> None:
        clone, _, new = self.rewritten_checkout("clean patch\n")
        result = self.check(clone, "f" * 40, new)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("patch was NOT checked", result.stderr)
        self.assertIn("dispatch CI", result.stderr)

    def test_missing_head_is_not_replaced_with_checkout_head(self) -> None:
        result = self.check(self.source, self.common, "f" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot retrieve the comparison head", result.stderr)

    def test_pull_request_and_merge_group_keep_merge_base_semantics(self) -> None:
        # The base branch fixes inherited whitespace. A PR does not reintroduce
        # that whitespace unless its patch against the common ancestor adds it.
        (self.source / "inherited.txt").write_text("inherited \n", encoding="utf-8")
        ancestor = commit_all(self.source, "inherited whitespace")
        (self.source / "inherited.txt").write_text("inherited\n", encoding="utf-8")
        base = commit_all(self.source, "base branch fix")
        git(self.source, "switch", "--quiet", "--detach", ancestor)
        (self.source / "data.txt").write_text("clean topic change\n", encoding="utf-8")
        head = commit_all(self.source, "topic change")
        for event in ("pull_request", "merge_group"):
            with self.subTest(event=event):
                result = self.check(self.source, base, head, event)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for event in ("push",):
            with self.subTest(event=event):
                result = self.check(self.source, base, head, event)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("trailing whitespace", result.stdout)

    def test_root_and_new_branch_check_the_snapshot(self) -> None:
        (self.source / "data.txt").write_text("bad snapshot \n", encoding="utf-8")
        head = commit_all(self.source, "bad snapshot")
        result = self.check(self.source, "0" * 40, head)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("trailing whitespace", result.stdout)
        self.assertIn("new-branch-snapshot", result.stderr)

    def test_manual_scope_checks_first_parent_not_supplied_old_base(self) -> None:
        (self.source / "data.txt").write_text("bad manual patch \n", encoding="utf-8")
        head = commit_all(self.source, "bad manual patch")
        result = self.check(self.source, "f" * 40, head, "workflow_dispatch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("trailing whitespace", result.stdout)
        self.assertIn("manual-current-revision", result.stderr)

    def test_missing_head_is_fetched_exactly_without_switching_checkout(self) -> None:
        clone, old, new = self.rewritten_checkout("clean patch\n")
        result = self.check(clone, self.common, old)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), new)

    def test_revision_expressions_are_rejected(self) -> None:
        result = self.check(self.source, "HEAD^", self.common)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("full commit object ID", result.stderr)


if __name__ == "__main__":
    unittest.main()
