#!/usr/bin/env python3
"""Resolve exact CI event objects without substituting another patch."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys


EVENTS = ("push", "pull_request", "merge_group", "workflow_dispatch")


def commit_id(value: str) -> str:
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", value):
        raise ValueError("expected a full commit object ID")
    return value.lower()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


def has_commit(sha: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def ensure_commit(sha: str, role: str) -> None:
    if has_commit(sha):
        return
    print(f"Fetching the missing comparison {role} from origin.", file=sys.stderr)
    fetched = subprocess.run(
        ["git", "fetch", "--no-tags", "--no-write-fetch-head", "origin", sha],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if fetched.returncode != 0 or not has_commit(sha):
        raise ValueError(
            f"Cannot retrieve the comparison {role}; the patch was NOT checked. "
            "For an intentional history rewrite, dispatch CI on the rewritten "
            "branch to validate its current revision separately. "
            "Do not substitute HEAD or skip the patch check."
        )


def resolve(event: str, base: str, head: str) -> dict[str, str]:
    head = commit_id(head)
    # A shallow boundary can masquerade as a root or hide a PR merge base.
    if git("rev-parse", "--is-shallow-repository") != "false":
        raise ValueError("CI comparison requires complete history (fetch-depth: 0).")
    if event not in EVENTS:
        raise ValueError("unsupported CI event")
    if event != "workflow_dispatch":
        base = commit_id(base)
        if len(base) != len(head):
            raise ValueError("base and head object formats differ")
        if event != "push" and not int(base, 16):
            raise ValueError("a pull request or merge group requires a real base")
    ensure_commit(head, "head")
    mode = "event-range"
    if event == "workflow_dispatch":
        # Manual CI validates this revision, not a lost historical push range.
        parents = git("rev-list", "--parents", "-n", "1", head).split()[1:]
        base = parents[0] if parents else "0" * len(head)
        mode = "manual-current-revision"
    elif not int(base, 16):
        mode = "new-branch-snapshot"
    if int(base, 16):
        ensure_commit(base, "base")
    return {
        "base": base, "head": head, "mode": mode,
        "force_all": "false" if mode == "event-range" else "true",
    }


def diff_range(event: str, base: str, head: str) -> str:
    if not int(base, 16):
        # Compute the empty tree in the repository's object format, including
        # SHA-256 repositories, and make it available to git diff.
        base = subprocess.run(
            ["git", "hash-object", "-t", "tree", "-w", "--stdin"],
            input="", check=True, capture_output=True, text=True,
        ).stdout.strip()
    separator = "..." if event in ("pull_request", "merge_group") else ".."
    return f"{base}{separator}{head}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, choices=EVENTS)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    try:
        resolved = resolve(args.event, args.base, args.head)
    except (ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    lines = "".join(f"{key}={value}\n" for key, value in resolved.items())
    print(lines, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
