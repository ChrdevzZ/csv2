"""Derive benchmark summaries exclusively from primary observations."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from . import statistics


FLOAT_REL_TOLERANCE = 1.0e-12
FLOAT_ABS_TOLERANCE = 1.0e-15
GIBIBYTE = float(1024**3)


def _wire_values(stdout: object) -> dict[str, str]:
    if not isinstance(stdout, str):
        raise RuntimeError("benchmark launch stdout must be a string")
    lines = [line for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("benchmark launch stdout must contain one result line")
    values: dict[str, str] = {}
    for field in lines[0].split():
        if field.count("=") != 1:
            raise RuntimeError(f"malformed benchmark stdout field: {field!r}")
        name, value = field.split("=", 1)
        if not name or not value or name in values:
            raise RuntimeError(f"malformed benchmark stdout field: {field!r}")
        values[name] = value
    return values


def _positive_integer(value: object, label: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise RuntimeError(f"{label} must be unsigned decimal")
    parsed = int(value)
    if parsed <= 0:
        raise RuntimeError(f"{label} must be positive")
    return parsed


def _close(actual: object, expected: float, label: str) -> None:
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        raise RuntimeError(f"{label} must be numeric")
    if not math.isclose(
        float(actual),
        expected,
        rel_tol=FLOAT_REL_TOLERANCE,
        abs_tol=FLOAT_ABS_TOLERANCE,
    ):
        raise RuntimeError(f"{label} is inconsistent with primary observations")


def _close_sequence(actual: object, expected: Sequence[float], label: str) -> None:
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise RuntimeError(f"{label} has the wrong length")
    for index, expected_value in enumerate(expected):
        _close(actual[index], expected_value, f"{label}[{index}]")


def launch_schedule(runs: int, warmups: int) -> list[tuple[str, int, int, str]]:
    schedule: list[tuple[str, int, int, str]] = []
    for phase, count in (("warmup", warmups), ("sample", runs)):
        for round_index in range(count):
            sides = ("baseline", "candidate")
            if round_index % 2:
                sides = tuple(reversed(sides))
            for order, side in enumerate(sides):
                schedule.append((phase, round_index, order, side))
    return schedule


def _throughput(result: Mapping[str, object], expected_iterations: int) -> float:
    byte_count = _positive_integer(result.get("bytes"), "result.bytes")
    iterations = _positive_integer(result.get("iterations"), "result.iterations")
    elapsed_ns = _positive_integer(result.get("elapsed_ns"), "result.elapsed_ns")
    if iterations != expected_iterations:
        raise RuntimeError("result.iterations differs from the report")
    value = byte_count * iterations * 1_000_000_000.0 / elapsed_ns / GIBIBYTE
    if not math.isfinite(value) or value <= 0.0:
        raise RuntimeError("derived throughput must be positive and finite")
    return value


def derive_comparison_case(
    case: Mapping[str, object],
    *,
    runs: int,
    warmups: int,
    iterations: int,
    common_protocol: str,
) -> dict[str, object]:
    launches = case.get("launches")
    if not isinstance(launches, list):
        raise RuntimeError("comparison case launches must be an array")
    schedule = launch_schedule(runs, warmups)
    if len(launches) != len(schedule):
        raise RuntimeError("comparison case launch schedule is incomplete")

    samples: dict[str, list[float]] = {"baseline": [], "candidate": []}
    signature: tuple[str, ...] | None = None
    signature_fields = ("bytes", "iterations", "rows", "cells", "row_bytes", "checksum")
    for index, expected_slot in enumerate(schedule):
        launch = launches[index]
        if not isinstance(launch, dict):
            raise RuntimeError(f"comparison launch {index} must be an object")
        actual_slot = tuple(launch.get(field) for field in ("phase", "round", "order", "side"))
        if actual_slot != expected_slot:
            raise RuntimeError(f"comparison launch {index} violates the alternating schedule")
        result = launch.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"comparison launch {index}.result must be an object")
        parsed_stdout = _wire_values(launch.get("stdout"))
        if parsed_stdout != result:
            raise RuntimeError(f"comparison launch {index} stdout differs from its result")
        if result.get("protocol") != common_protocol:
            raise RuntimeError(f"comparison launch {index} uses the wrong protocol")
        current_signature = tuple(str(result.get(field)) for field in signature_fields)
        if signature is None:
            signature = current_signature
        elif current_signature != signature:
            raise RuntimeError("comparison launch semantic signatures differ")
        throughput = _throughput(result, iterations)
        _close(
            launch.get("throughput_gib_per_second"),
            throughput,
            f"comparison launch {index}.throughput_gib_per_second",
        )
        if expected_slot[0] == "sample":
            samples[expected_slot[3]].append(throughput)

    baseline_median, baseline_mad = statistics.median_mad(samples["baseline"])
    candidate_median, candidate_mad = statistics.median_mad(samples["candidate"])
    low, high = statistics.paired_bootstrap_ratio(
        samples["baseline"], samples["candidate"]
    )
    measured_noise = max(
        2.0 * baseline_mad / baseline_median,
        2.0 * candidate_mad / candidate_median,
    )
    calibration_noise = case.get("calibration_noise")
    if isinstance(calibration_noise, bool) or not isinstance(calibration_noise, (int, float)):
        raise RuntimeError("comparison case calibration_noise must be numeric")
    calibration_value = float(calibration_noise)
    if not math.isfinite(calibration_value) or calibration_value < 0.0:
        raise RuntimeError("comparison case calibration_noise must be finite and non-negative")
    threshold = statistics.regression_threshold(measured_noise, calibration_value)
    regression = candidate_median < baseline_median * (1.0 - threshold) and high < 1.0
    improvement = candidate_median > baseline_median * (1.0 + threshold) and low > 1.0
    observed_noise = max(
        abs(candidate_median / baseline_median - 1.0),
        abs(low - 1.0),
        abs(high - 1.0),
    )
    return {
        "semantic_signature": list(signature or ()),
        "baseline": {
            "median": baseline_median,
            "mad": baseline_mad,
            "samples": samples["baseline"],
        },
        "candidate": {
            "median": candidate_median,
            "mad": candidate_mad,
            "samples": samples["candidate"],
        },
        "candidate_over_baseline_95pct": [low, high],
        "measured_noise": measured_noise,
        "calibration_noise": calibration_value,
        "observed_noise": observed_noise,
        "regression_threshold": threshold,
        "regression": regression,
        "improvement": improvement,
    }


def validate_comparison_case(
    case: Mapping[str, object],
    *,
    runs: int,
    warmups: int,
    iterations: int,
    common_protocol: str,
    label: str,
) -> None:
    derived = derive_comparison_case(
        case,
        runs=runs,
        warmups=warmups,
        iterations=iterations,
        common_protocol=common_protocol,
    )
    for field in (
        "measured_noise",
        "calibration_noise",
        "observed_noise",
        "regression_threshold",
    ):
        _close(case.get(field), float(derived[field]), f"{label}.{field}")
    for field in ("regression", "improvement"):
        if case.get(field) is not derived[field]:
            raise RuntimeError(f"{label}.{field} is inconsistent with primary observations")
    if case.get("semantic_signature") != derived["semantic_signature"]:
        raise RuntimeError(f"{label}.semantic_signature is inconsistent with primary observations")
    _close_sequence(
        case.get("candidate_over_baseline_95pct"),
        derived["candidate_over_baseline_95pct"],  # type: ignore[arg-type]
        f"{label}.candidate_over_baseline_95pct",
    )
    for side in ("baseline", "candidate"):
        actual = case.get(side)
        expected = derived[side]
        if not isinstance(actual, dict) or not isinstance(expected, dict):
            raise RuntimeError(f"{label}.{side} must be an object")
        _close(actual.get("median"), float(expected["median"]), f"{label}.{side}.median")
        _close(actual.get("mad"), float(expected["mad"]), f"{label}.{side}.mad")
        _close_sequence(
            actual.get("samples"),
            expected["samples"],  # type: ignore[arg-type]
            f"{label}.{side}.samples",
        )


def validate_timing_summary(timing: Mapping[str, object], label: str) -> None:
    samples = timing.get("samples")
    if not isinstance(samples, list) or not samples:
        raise RuntimeError(f"{label}.samples must be a non-empty array")
    benchmark = timing.get("benchmark")
    bytes_per_second: list[float] = []
    seconds: list[float] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise RuntimeError(f"{label}.samples[{index}] must be an object")
        if sample.get("name") != benchmark:
            raise RuntimeError(f"{label}.samples[{index}].name differs from benchmark")
        for field, destination in (
            ("bytes_per_second", bytes_per_second),
            ("seconds", seconds),
        ):
            value = sample.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeError(f"{label}.samples[{index}].{field} must be numeric")
            destination.append(float(value))
    for field, values in (("bytes_per_second", bytes_per_second), ("seconds", seconds)):
        median, mad = statistics.median_mad(values)
        summary = timing.get(field)
        if not isinstance(summary, dict):
            raise RuntimeError(f"{label}.{field} must be an object")
        _close(summary.get("median"), median, f"{label}.{field}.median")
        _close(summary.get("mad"), mad, f"{label}.{field}.mad")
