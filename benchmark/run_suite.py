#!/usr/bin/env python3
"""Alternating benchmark runner with median, MAD, and bootstrap intervals."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
from pathlib import Path
from typing import Iterable


OPERATIONS = (
    "map_only",
    "rows_only",
    "rows_cells",
    "raw_to_string",
    "decoded_to_string",
    "decoded_to_vector",
    "ranges_pipeline",
    "integer_conversion",
    "writer_raw",
    "writer_escaped",
)


def parse_output(output: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in output.strip().split())


def invoke(executable: Path, operation: str, dataset: Path, source: str) -> dict[str, str]:
    completed = subprocess.run(
        [
            str(executable),
            "--operation",
            operation,
            "--input",
            str(dataset),
            "--source",
            source,
            "--iterations",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_output(completed.stdout)


def median_mad(values: list[float]) -> tuple[float, float]:
    median = statistics.median(values)
    mad = statistics.median(abs(value - median) for value in values)
    return median, mad


def bootstrap_ratio(
    baseline: list[float], candidate: list[float], samples: int = 5000
) -> tuple[float, float]:
    generator = random.Random(0x43535632)
    ratios = []
    for _ in range(samples):
        base_sample = [generator.choice(baseline) for _ in baseline]
        candidate_sample = [generator.choice(candidate) for _ in candidate]
        ratios.append(statistics.median(candidate_sample) / statistics.median(base_sample))
    ratios.sort()
    return ratios[int(samples * 0.025)], ratios[int(samples * 0.975)]


def selected(requested: str, available: Iterable[str]) -> list[str]:
    if requested == "all":
        return list(available)
    wanted = [item.strip() for item in requested.split(",") if item.strip()]
    unknown = sorted(set(wanted) - set(available))
    if unknown:
        raise ValueError(f"unknown selections: {', '.join(unknown)}")
    return wanted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--operations", default="all")
    parser.add_argument("--sources", default="buffer,mmap")
    parser.add_argument("--files", default="all")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 20:
        parser.error("--runs must be at least 20 for regression decisions")

    dataset_paths = sorted(args.datasets.glob("*.csv"))
    if not dataset_paths:
        parser.error(f"no CSV datasets found in {args.datasets}")
    datasets = selected(args.files, (path.name for path in dataset_paths))
    by_name = {path.name: path for path in dataset_paths}
    operations = selected(args.operations, OPERATIONS)
    sources = selected(args.sources, ("buffer", "mmap"))
    report: dict[str, object] = {"runs": args.runs, "cases": []}

    for dataset_name in datasets:
        for operation in operations:
            case_sources = ["mmap"] if operation == "map_only" else sources
            for source in case_sources:
                baseline_values: list[float] = []
                candidate_values: list[float] = []
                checksum = None
                for run in range(args.runs):
                    order = ((args.baseline, baseline_values), (args.candidate, candidate_values))
                    if run % 2:
                        order = tuple(reversed(order))
                    for executable, values in order:
                        result = invoke(executable, operation, by_name[dataset_name], source)
                        current_checksum = result["checksum"]
                        if checksum is None:
                            checksum = current_checksum
                        elif current_checksum != checksum:
                            raise RuntimeError(
                                f"checksum mismatch for {dataset_name}/{operation}/{source}"
                            )
                        values.append(float(result["gib_per_second"]))

                base_median, base_mad = median_mad(baseline_values)
                candidate_median, candidate_mad = median_mad(candidate_values)
                low, high = bootstrap_ratio(baseline_values, candidate_values)
                noise = 2.0 * base_mad / base_median if base_median else float("inf")
                threshold = max(0.05, noise)
                regression = candidate_median < base_median * (1.0 - threshold) and high < 1.0
                improvement = candidate_median > base_median * (1.0 + threshold) and low > 1.0
                report["cases"].append(
                    {
                        "dataset": dataset_name,
                        "operation": operation,
                        "source": source,
                        "checksum": checksum,
                        "baseline": {"median": base_median, "mad": base_mad},
                        "candidate": {"median": candidate_median, "mad": candidate_mad},
                        "candidate_over_baseline_95pct": [low, high],
                        "regression_threshold": threshold,
                        "regression": regression,
                        "improvement": improvement,
                    }
                )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
