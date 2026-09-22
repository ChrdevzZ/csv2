#!/usr/bin/env python3
"""Check the requested patch, fetching an absent base after a history rewrite."""

from __future__ import annotations

import argparse
import subprocess
import sys

from resolve_comparison import EVENTS, diff_range, resolve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument(
        "--event", required=True,
        choices=EVENTS,
    )
    args = parser.parse_args()
    try:
        resolved = resolve(args.event, args.base, args.head)
        comparison = diff_range(args.event, resolved["base"], resolved["head"])
    except (ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Whitespace scope: {resolved['mode']}", file=sys.stderr)
    return subprocess.run(
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--check",
         comparison, "--"],
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
