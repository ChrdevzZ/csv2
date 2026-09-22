#!/usr/bin/env python3
"""Check the requested patch, fetching an absent base after a history rewrite."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys


def commit_id(value: str) -> str:
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", value):
        raise argparse.ArgumentTypeError("expected a full commit object ID")
    return value


def has_commit(sha: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=commit_id)
    parser.add_argument("--head", required=True, type=commit_id)
    parser.add_argument(
        "--event", required=True,
        choices=("push", "pull_request", "merge_group", "workflow_dispatch"),
    )
    args = parser.parse_args()
    if not has_commit(args.head):
        print("Patch head is absent from the checkout; refusing to change the range.",
              file=sys.stderr)
        return 1
    if not has_commit(args.base):
        # Jobs have separate object databases. The classifier's fetch does not
        # make a discarded push base available in this preflight checkout.
        print("Fetching the missing comparison base from origin.", file=sys.stderr)
        fetched = subprocess.run(
            ["git", "fetch", "--no-tags", "--no-write-fetch-head", "origin", args.base],
            check=False,
        )
        if fetched.returncode != 0 or not has_commit(args.base):
            print(
                "Cannot retrieve the comparison base; the patch was NOT checked. "
                "For an intentional history rewrite, dispatch CI on the rewritten "
                "branch to validate its current revision separately. "
                "Do not substitute HEAD or skip the patch check.",
                file=sys.stderr,
            )
            return 1
    separator = "..." if args.event in ("pull_request", "merge_group") else ".."
    return subprocess.run(
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--check",
         f"{args.base}{separator}{args.head}", "--"],
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
