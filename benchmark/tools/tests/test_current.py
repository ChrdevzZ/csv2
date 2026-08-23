from __future__ import annotations

import argparse
import subprocess
import unittest
from pathlib import Path

import _support  # noqa: F401
from csv2bench import current


class CurrentSuiteTests(unittest.TestCase):
    def test_each_timing_case_uses_one_operation_and_concrete_source(self) -> None:
        commands: list[list[str]] = []

        def run(command, **_kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "ok\n", "")

        current.run_cases(
            Path("benchmark"),
            Path("datasets"),
            (
                ("source/file-read", "file", "one.csv"),
                ("traversal/rows", "buffer", "two.csv"),
            ),
            ("--benchmark_min_time=0.001s",),
            verify=False,
            run_fn=run,
        )

        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertEqual(command.count("--csv2-operation"), 1)
            self.assertEqual(command.count("--csv2-source"), 1)
            self.assertNotIn("all", command)

    def test_case_parser_rejects_aggregate_or_malformed_sources(self) -> None:
        self.assertEqual(
            current.parse_case("traversal/rows|buffer|input.csv"),
            ("traversal/rows", "buffer", "input.csv"),
        )
        for value in ("missing", "operation|all|input.csv", "|buffer|input.csv"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                current.parse_case(value)


if __name__ == "__main__":
    unittest.main()
