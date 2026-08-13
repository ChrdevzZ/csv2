#!/usr/bin/env python3
"""Generate deterministic CSV benchmark corpora outside the source tree."""

from __future__ import annotations

import argparse
from pathlib import Path


def repeated(path: Path, record: bytes, rows: int) -> None:
    with path.open("wb") as output:
        for _ in range(rows):
            output.write(record)


def generate(output: Path, rows: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    repeated(output / "short_unquoted.csv", b"12,345,6789,word\n", rows)
    repeated(output / "wide_rows.csv", (b"wide," * 4095) + b"end\n", max(8, rows // 256))
    repeated(output / "quote_heavy.csv", b'"a,b","c\nd","e\r\nf"\n', rows)
    repeated(output / "doubled_quotes.csv", b'"a""b""c","""quoted"""\n', rows)
    repeated(output / "quoted_lf.csv", b'left,"line one\nline two",right\n', rows)
    repeated(output / "crlf.csv", b"12,345,6789,word\r\n", rows)
    repeated(output / "empty_and_trailing.csv", b",,value,,,\n", rows)
    repeated(output / "long_field.csv", (b"x" * (1024 * 1024)) + b",tail\n", 4)
    (output / "small.csv").write_bytes(b"1,2\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=10000)
    args = parser.parse_args()
    if args.rows <= 0:
        parser.error("--rows must be positive")
    generate(args.output, args.rows)


if __name__ == "__main__":
    main()
