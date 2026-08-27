from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("classify_changes.py")
OWNERS = ("quick", "benchmark", "fuzz", "perf", "full")


def parse_plan(completed: subprocess.CompletedProcess[str]) -> dict[str, bool]:
    if completed.returncode != 0:
        raise AssertionError(
            f"classifier failed ({completed.returncode})\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    result: dict[str, bool] = {}
    for line in completed.stdout.splitlines():
        name, value = line.split("=", 1)
        result[name] = value == "true"
    return result


def classify(*paths: str) -> dict[str, bool]:
    return parse_plan(
        subprocess.run(
            [sys.executable, str(SCRIPT), "--paths-from-stdin"],
            input="".join(f"{path}\n" for path in paths),
            capture_output=True,
            text=True,
        )
    )


def classify_git(
    repository: Path, base: str, head: str, *, merge_base: bool = False
) -> dict[str, bool]:
    command = [sys.executable, str(SCRIPT), "--base", base, "--head", head]
    if merge_base:
        command.append("--merge-base")
    return parse_plan(
        subprocess.run(
            command,
            cwd=repository,
            capture_output=True,
            text=True,
        )
    )


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def initialize_repository(root: Path) -> None:
    git(root, "init", "--quiet")
    git(root, "config", "user.name", "CSV2 CI Test")
    git(root, "config", "user.email", "csv2-ci@example.invalid")


def commit_all(root: Path, message: str) -> str:
    git(root, "add", "--all")
    git(root, "commit", "--quiet", "--message", message)
    return git(root, "rev-parse", "HEAD")


class ClassifyChangesTests(unittest.TestCase):
    def test_documentation_only_skips_every_heavy_owner(self) -> None:
        self.assertEqual(
            classify(
                "README.md",
                "docs/ci.md",
                "benchmark/README.md",
                "img/logo.png",
            ),
            {name: False for name in OWNERS},
        )

    def test_unknown_path_fails_open_to_every_owner(self) -> None:
        self.assertEqual(
            classify("unclassified/new-contract.data"),
            {name: True for name in OWNERS},
        )

    def test_empty_diff_fails_open_to_every_owner(self) -> None:
        self.assertEqual(classify(), {name: True for name in OWNERS})

    def test_public_header_requires_every_owner(self) -> None:
        self.assertEqual(
            classify("include/csv2/reader.hpp"),
            {name: True for name in OWNERS},
        )

    def test_runtime_test_change_stays_with_quick_and_full_owners(self) -> None:
        self.assertEqual(
            classify("test/runtime/reader/scan.cpp"),
            {
                "quick": True,
                "benchmark": False,
                "fuzz": False,
                "perf": False,
                "full": True,
            },
        )

    def test_benchmark_change_selects_benchmark_fuzz_perf_and_full(self) -> None:
        self.assertEqual(
            classify("benchmark/current/registry.cpp"),
            {
                "quick": False,
                "benchmark": True,
                "fuzz": True,
                "perf": True,
                "full": True,
            },
        )

    def test_test_fixture_change_requires_every_owner(self) -> None:
        self.assertEqual(
            classify("test/fixtures/upstream/test_01.csv"),
            {name: True for name in OWNERS},
        )

    def test_binary_fixture_is_not_misclassified_as_documentation(self) -> None:
        self.assertEqual(
            classify("test/fixtures/upstream/preview.png"),
            {name: True for name in OWNERS},
        )

    def test_markdown_fixture_is_not_misclassified_as_documentation(self) -> None:
        self.assertEqual(
            classify("test/fixtures/upstream/contract.md"),
            {name: True for name in OWNERS},
        )

    def test_installed_license_files_select_installation_owners(self) -> None:
        for path in ("LICENSE", "LICENSE.mio"):
            with self.subTest(path=path):
                self.assertEqual(classify(path), {name: True for name in OWNERS})

    def test_gitignore_change_selects_source_package_owners(self) -> None:
        self.assertEqual(classify(".gitignore"), {name: True for name in OWNERS})

    def test_owner_prefix_does_not_match_a_lookalike_directory(self) -> None:
        self.assertEqual(
            classify("third_party/verification/catch2-shadow/source.cpp"),
            {name: True for name in OWNERS},
        )

    def test_complete_input_is_classified_beyond_three_thousand_paths(self) -> None:
        paths = [f"docs/generated-{index}.md" for index in range(3001)]
        paths.append("include/csv2/reader.hpp")
        self.assertEqual(classify(*paths), {name: True for name in OWNERS})

    def test_git_rename_classifies_both_old_and_new_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            header = root / "include" / "csv2" / "critical.hpp"
            header.parent.mkdir(parents=True)
            header.write_text("#pragma once\n", encoding="utf-8")
            base = commit_all(root, "base header")
            (root / "docs").mkdir()
            git(root, "mv", str(header.relative_to(root)), "docs/critical.md")
            head = commit_all(root, "rename header to documentation")

            self.assertEqual(
                classify_git(root, base, head, merge_base=True),
                {name: True for name in OWNERS},
            )

    def test_two_dot_push_comparison_covers_non_fast_forward_removals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            common = commit_all(root, "common")
            git(root, "switch", "--quiet", "--create", "old")
            header = root / "include" / "csv2" / "risky.hpp"
            header.parent.mkdir(parents=True)
            header.write_text("#pragma once\n", encoding="utf-8")
            old_head = commit_all(root, "old protected header")
            git(root, "switch", "--quiet", "--detach", common)
            (root / "README.md").write_text("replacement history\n", encoding="utf-8")
            new_head = commit_all(root, "new documentation history")

            self.assertEqual(
                classify_git(root, old_head, new_head),
                {name: True for name in OWNERS},
            )

    def test_merge_base_mode_ignores_changes_unique_to_the_base_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            common = commit_all(root, "common")
            git(root, "switch", "--quiet", "--create", "feature")
            (root / "README.md").write_text("feature docs\n", encoding="utf-8")
            feature = commit_all(root, "feature docs")
            git(root, "switch", "--quiet", "--detach", common)
            header = root / "include" / "csv2" / "base-only.hpp"
            header.parent.mkdir(parents=True)
            header.write_text("#pragma once\n", encoding="utf-8")
            base_tip = commit_all(root, "base-only header")

            self.assertEqual(
                classify_git(root, base_tip, feature, merge_base=True),
                {name: False for name in OWNERS},
            )


if __name__ == "__main__":
    unittest.main()
