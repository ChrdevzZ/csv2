#!/usr/bin/env python3
"""Select conservative CI contract owners from a complete Git diff."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import PurePosixPath


OWNERS = ("quick", "benchmark", "fuzz", "perf", "full")
CONTENT_PATH_PREFIXES = (
    "include/",
    "single_include/",
    "test/fixtures/",
    "test/fuzz/corpus/",
    "benchmark/datasets/",
    "third_party/verification/catch2/",
    "third_party/verification/google_benchmark/",
)


def every_owner(value: bool) -> dict[str, bool]:
    return {name: value for name in OWNERS}


def documentation(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in CONTENT_PATH_PREFIXES):
        return False
    value = PurePosixPath(path)
    return (
        value.suffix.lower() in {".md", ".rst"}
        or path.startswith("docs/")
        or (
            value.suffix.lower()
            in {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
            and path.startswith("img/")
        )
    )


def under(path: str, *prefixes: str) -> bool:
    return any(
        path == prefix.removesuffix("/")
        or (prefix.endswith("/") and path.startswith(prefix))
        for prefix in prefixes
    )


def classify_paths(paths: Iterable[str]) -> dict[str, bool]:
    changed = tuple(paths)
    if not changed:
        return every_owner(True)
    if any(
        not path or path.startswith("/") or "\\" in path or "\0" in path
        for path in changed
    ):
        return every_owner(True)
    if all(documentation(path) for path in changed):
        return every_owner(False)

    selected = every_owner(False)
    for path in changed:
        if documentation(path):
            continue
        if under(
            path,
            ".github/workflows/",
            "tools/ci/",
            "cmake/",
            "CMakeLists.txt",
            "csv2Config.cmake.in",
            "csv2.pc.in",
        ):
            return every_owner(True)
        if under(path, "include/", "single_include/"):
            return every_owner(True)
        if under(path, "test/fixtures/"):
            return every_owner(True)
        if under(path, "test/fuzz/", "test/support/", "test/cmake/"):
            selected["quick"] = True
            selected["fuzz"] = True
            selected["full"] = True
            continue
        if under(path, "test/"):
            selected["quick"] = True
            selected["full"] = True
            continue
        if under(path, "benchmark/"):
            selected["benchmark"] = True
            selected["fuzz"] = True
            selected["perf"] = True
            selected["full"] = True
            continue
        if under(path, "third_party/verification/catch2/"):
            selected["quick"] = True
            selected["full"] = True
            continue
        if under(path, "third_party/verification/google_benchmark/"):
            selected["benchmark"] = True
            selected["fuzz"] = True
            selected["perf"] = True
            selected["full"] = True
            continue
        if under(path, "third_party/verification/", "tools/vendor/"):
            return every_owner(True)
        if path == ".clang-format":
            selected["quick"] = True
            selected["full"] = True
            continue
        if path == ".gitignore":
            # Root CMake converts this file into CPACK_SOURCE_IGNORE_FILES.
            return every_owner(True)
        if path == ".gitattributes":
            continue

        # A path without an explicit owner is never assumed harmless.
        return every_owner(True)

    return selected


def git_changed_files(base: str, head: str, *, merge_base: bool) -> list[str]:
    comparison = f"{base}...{head}" if merge_base else f"{base}..{head}"
    completed = subprocess.run(
        ["git", "diff", "--no-renames", "--name-only", "-z", comparison],
        check=True,
        capture_output=True,
    )
    return [
        value.decode("utf-8", errors="strict")
        for value in completed.stdout.split(b"\0")
        if value
    ]


def emit(plan: dict[str, bool]) -> None:
    lines = [f"{name}={'true' if plan[name] else 'false'}" for name in OWNERS]
    print("\n".join(lines))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("\n".join(lines))
            stream.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--merge-base", action="store_true")
    parser.add_argument("--paths-from-stdin", action="store_true")
    args = parser.parse_args()
    if args.paths_from_stdin:
        if args.base or args.head or args.merge_base:
            parser.error(
                "--paths-from-stdin cannot be combined with Git comparison arguments"
            )
    elif not args.base or not args.head:
        parser.error("--base and --head are required for Git diff classification")
    return args


def main() -> int:
    args = parse_args()
    if args.paths_from_stdin:
        paths = [line.removesuffix("\n") for line in sys.stdin if line != "\n"]
        emit(classify_paths(paths))
        return 0
    try:
        paths = git_changed_files(args.base, args.head, merge_base=args.merge_base)
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        emit(every_owner(True))
        return 0
    emit(classify_paths(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
