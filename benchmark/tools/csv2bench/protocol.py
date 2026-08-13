"""Strict parsers for the versioned CSV2 benchmark wire protocols."""

from __future__ import annotations

import math
from typing import Iterable

from . import COMMON_PROTOCOL, CURRENT_PROTOCOL

UINT64_MAX = (1 << 64) - 1


def parse_key_value_line(output: str, required: Iterable[str]) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("benchmark must print exactly one non-empty result line")
    result: dict[str, str] = {}
    for part in lines[0].split():
        if part.count("=") != 1:
            raise RuntimeError(f"malformed benchmark field: {part!r}")
        key, value = part.split("=", 1)
        if not key or not value:
            raise RuntimeError(f"malformed benchmark field: {part!r}")
        if key in result:
            raise RuntimeError(f"duplicate key in benchmark output: {key}")
        result[key] = value
    missing = sorted(set(required) - result.keys())
    if missing:
        raise RuntimeError(f"benchmark output is missing required fields: {', '.join(missing)}")
    return result


def require_protocol(values: dict[str, str], expected: str) -> None:
    actual = values.get("protocol")
    if actual != expected:
        raise RuntimeError(f"unsupported benchmark protocol: expected {expected}, got {actual}")


def parse_common(output: str, required: Iterable[str]) -> dict[str, str]:
    result = parse_key_value_line(output, {"protocol", *required})
    require_protocol(result, COMMON_PROTOCOL)
    return result


def parse_operation_contracts(encoded: str) -> dict[str, tuple[str, frozenset[str]]]:
    contracts: dict[str, tuple[str, frozenset[str]]] = {}
    if not encoded:
        raise RuntimeError("operation contracts must not be empty")
    for entry in encoded.split(";"):
        parts = entry.split(":")
        if len(parts) != 3 or not all(parts):
            raise RuntimeError(f"malformed operation contract: {entry!r}")
        operation, scope, encoded_sources = parts
        if operation in contracts:
            raise RuntimeError(f"duplicate operation contract: {operation}")
        if scope not in {"traversal_only", "mmap_and_traversal", "writer_only"}:
            raise RuntimeError(f"unsupported operation scope: {scope}")
        source_entries = encoded_sources.split("+")
        if (
            any(source not in {"buffer", "mmap"} for source in source_entries)
            or len(source_entries) != len(set(source_entries))
        ):
            raise RuntimeError(f"invalid operation sources: {encoded_sources}")
        contracts[operation] = (scope, frozenset(source_entries))
    return contracts


def parse_current(output: str) -> dict[str, str]:
    required = {
        "protocol",
        "revision",
        "operation",
        "source",
        "dataset",
        "checksum",
        "bytes",
        "rows",
        "cells",
        "allocations",
        "allocated_bytes",
    }
    result = parse_key_value_line(output, required)
    require_protocol(result, CURRENT_PROTOCOL)
    for field in ("checksum", "bytes", "rows", "cells", "allocations", "allocated_bytes"):
        try:
            value = int(result[field])
        except ValueError as error:
            raise RuntimeError(f"benchmark field must be an integer: {field}") from error
        if value < 0 or value > UINT64_MAX:
            raise RuntimeError(f"benchmark field is outside uint64 range: {field}")
    return result


def finite_nonnegative(value: object, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} must be numeric") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise RuntimeError(f"{label} must be finite and non-negative")
    return parsed


def decision_eligible(evidence_level: str, status: str) -> bool:
    """Return whether a completed report may support a regression decision."""
    return evidence_level == "controlled" and status == "completed"


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{label} must be an array")
    return value


def _required(document: dict[str, object], names: Iterable[str], label: str) -> None:
    missing = sorted(set(names) - document.keys())
    if missing:
        raise RuntimeError(f"{label} is missing required fields: {', '.join(missing)}")


def _closed(
    document: dict[str, object], names: Iterable[str], label: str
) -> None:
    unexpected = sorted(document.keys() - set(names))
    if unexpected:
        raise RuntimeError(f"{label} has unknown fields: {', '.join(unexpected)}")


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RuntimeError(f"{label} must be an integer >= {minimum}")
    return value


def _string(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise RuntimeError(f"{label} must be a non-empty string")
    return value


def _artifact(value: object, label: str, *, revision: bool) -> dict[str, object]:
    artifact = _object(value, label)
    required = {"path", "size", "sha256", "mtime_ns"}
    if revision:
        required.add("revision")
    _required(artifact, required, label)
    _string(artifact["path"], f"{label}.path")
    _integer(artifact["size"], f"{label}.size")
    _string(artifact["sha256"], f"{label}.sha256")
    _integer(artifact["mtime_ns"], f"{label}.mtime_ns")
    if revision:
        _string(artifact["revision"], f"{label}.revision")
    return artifact


def _source_bundle(value: object, label: str) -> dict[str, object]:
    bundle = _object(value, label)
    _required(bundle, {"kind", "root", "revision", "sha256", "files"}, label)
    if bundle["kind"] != "source-bundle":
        raise RuntimeError(f"{label}.kind must be source-bundle")
    _string(bundle["root"], f"{label}.root")
    _string(bundle["revision"], f"{label}.revision")
    _string(bundle["sha256"], f"{label}.sha256")
    members = _array(bundle["files"], f"{label}.files")
    if not members:
        raise RuntimeError(f"{label}.files must not be empty")
    seen: set[str] = set()
    for index, value in enumerate(members):
        member_label = f"{label}.files[{index}]"
        member = _object(value, member_label)
        _required(member, {"path", "size", "sha256", "mtime_ns"}, member_label)
        path = _string(member["path"], f"{member_label}.path")
        if path in seen:
            raise RuntimeError(f"{label}.files contains duplicate paths")
        seen.add(path)
        _integer(member["size"], f"{member_label}.size")
        _string(member["sha256"], f"{member_label}.sha256")
        _integer(member["mtime_ns"], f"{member_label}.mtime_ns")
    return bundle


def _invocation(value: object, label: str) -> dict[str, object]:
    invocation = _object(value, label)
    _required(invocation, {"command", "stdout", "stderr"}, label)
    command = _array(invocation["command"], f"{label}.command")
    if not command or not all(isinstance(item, str) and item for item in command):
        raise RuntimeError(f"{label}.command must contain non-empty strings")
    for stream in ("stdout", "stderr"):
        if not isinstance(invocation[stream], str):
            raise RuntimeError(f"{label}.{stream} must be a string")
    return invocation


def _number(
    value: object, label: str, *, minimum: float = 0.0, positive: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < minimum or (positive and parsed <= 0):
        qualifier = "positive" if positive else f">= {minimum}"
        raise RuntimeError(f"{label} must be finite and {qualifier}")
    return parsed


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise RuntimeError(f"{label} must be a boolean")
    return value


def _uint64_string(value: object, label: str) -> int:
    text = _string(value, label)
    if not text.isascii() or not text.isdecimal() or (len(text) > 1 and text[0] == "0"):
        raise RuntimeError(f"{label} must be canonical unsigned decimal")
    parsed = int(text)
    if parsed > UINT64_MAX:
        raise RuntimeError(f"{label} is outside uint64 range")
    return parsed


def _sample_statistics(
    value: object, label: str, expected_runs: int
) -> list[float]:
    stats = _object(value, label)
    _required(stats, {"median", "mad", "samples"}, label)
    _number(stats["median"], f"{label}.median", positive=True)
    _number(stats["mad"], f"{label}.mad")
    samples = _array(stats["samples"], f"{label}.samples")
    if len(samples) != expected_runs:
        raise RuntimeError(f"{label}.samples has the wrong length")
    return [
        _number(sample, f"{label}.samples[{index}]", positive=True)
        for index, sample in enumerate(samples)
    ]


def _timing(
    value: object, label: str, expected_runs: int, *, require_pmu: bool = False
) -> dict[str, object]:
    timing = _object(value, label)
    _required(
        timing,
        {"benchmark", "runs", "samples", "bytes_per_second", "seconds"},
        label,
    )
    _string(timing["benchmark"], f"{label}.benchmark")
    if _integer(timing["runs"], f"{label}.runs", 1) != expected_runs:
        raise RuntimeError(f"{label}.runs is inconsistent")
    samples = _array(timing["samples"], f"{label}.samples")
    if len(samples) != expected_runs:
        raise RuntimeError(f"{label}.samples has the wrong length")
    for index, sample_value in enumerate(samples):
        sample_label = f"{label}.samples[{index}]"
        sample = _object(sample_value, sample_label)
        _required(
            sample,
            {"name", "seconds", "bytes_per_second", "items_per_second"},
            sample_label,
        )
        _string(sample["name"], f"{sample_label}.name")
        _number(sample["seconds"], f"{sample_label}.seconds", positive=True)
        _number(sample["bytes_per_second"], f"{sample_label}.bytes_per_second")
        _number(sample["items_per_second"], f"{sample_label}.items_per_second")
        if require_pmu:
            counters = _object(sample.get("pmu"), f"{sample_label}.pmu")
            _required(
                counters,
                {"cycles", "instructions", "branch-misses"},
                f"{sample_label}.pmu",
            )
            for counter in ("cycles", "instructions", "branch-misses"):
                _number(counters[counter], f"{sample_label}.pmu.{counter}")
    for summary_name in ("bytes_per_second", "seconds"):
        summary_label = f"{label}.{summary_name}"
        summary = _object(timing[summary_name], summary_label)
        _required(summary, {"median", "mad"}, summary_label)
        _number(
            summary["median"],
            f"{summary_label}.median",
            positive=summary_name == "seconds",
        )
        _number(summary["mad"], f"{summary_label}.mad")
    return timing


def _clean_build(value: object, label: str) -> dict[str, object]:
    build = _object(value, label)
    _required(build, {"command", "seconds", "stdout", "stderr"}, label)
    _invocation(
        {key: build[key] for key in ("command", "stdout", "stderr")}, label
    )
    _number(build["seconds"], f"{label}.seconds", positive=True)
    return build


def _peak_rss(value: object, label: str) -> dict[str, object]:
    rss = _object(value, label)
    _required(rss, {"scope", "kib", "command", "stdout", "stderr"}, label)
    _string(rss["scope"], f"{label}.scope")
    _integer(rss["kib"], f"{label}.kib", 1)
    _invocation({key: rss[key] for key in ("command", "stdout", "stderr")}, label)
    return rss


def _code_size(value: object, label: str, *, require_sections: bool) -> dict[str, object]:
    size = _object(value, label)
    if require_sections:
        fields = {"text_bytes", "data_bytes", "bss_bytes", "total_bytes", "command"}
        _required(size, fields, label)
        text = _integer(size["text_bytes"], f"{label}.text_bytes")
        data = _integer(size["data_bytes"], f"{label}.data_bytes")
        bss = _integer(size["bss_bytes"], f"{label}.bss_bytes")
        total = _integer(size["total_bytes"], f"{label}.total_bytes", 1)
        if total != text + data + bss:
            raise RuntimeError(f"{label}.total_bytes is inconsistent")
        command = _array(size["command"], f"{label}.command")
        if not command or not all(isinstance(item, str) and item for item in command):
            raise RuntimeError(f"{label}.command must contain non-empty strings")
    else:
        if "file_bytes" in size:
            _integer(size["file_bytes"], f"{label}.file_bytes", 1)
            _string(size.get("method"), f"{label}.method")
        else:
            _code_size(size, label, require_sections=True)
    return size


def validate_comparison_report(report: object) -> None:
    document = _object(report, "comparison report")
    allowed = {
        "schema", "mode", "status", "evidence_level", "decision_eligible",
        "generated_at_utc", "completed_at_utc", "error", "runs", "warmups",
        "iterations_per_run", "compiler", "compiler_flags", "host", "runner",
        "adapter_source", "baseline", "candidate", "datasets", "calibration",
        "cases",
    }
    required = allowed - {"completed_at_utc", "error"}
    _required(document, required, "comparison report")
    _closed(document, allowed, "comparison report")
    if document["schema"] != "csv2-benchmark-report-v3":
        raise RuntimeError("comparison report has an unsupported schema")
    if document["mode"] not in {"aa", "compare"}:
        raise RuntimeError("comparison report mode is invalid")
    if document["status"] not in {"running", "completed", "failed"}:
        raise RuntimeError("comparison report status is invalid")
    if document["evidence_level"] not in {"exploratory", "controlled"}:
        raise RuntimeError("comparison report evidence level is invalid")
    expected_eligible = decision_eligible(
        str(document["evidence_level"]), str(document["status"])
    )
    if type(document["decision_eligible"]) is not bool or document[
        "decision_eligible"
    ] != expected_eligible:
        raise RuntimeError("comparison report decision eligibility is inconsistent")

    runs = _integer(document["runs"], "comparison report.runs", 1)
    warmups = _integer(document["warmups"], "comparison report.warmups")
    iterations = _integer(
        document["iterations_per_run"], "comparison report.iterations_per_run", 1
    )
    _string(document["generated_at_utc"], "comparison report.generated_at_utc")
    _string(document["compiler"], "comparison report.compiler")
    _string(document["compiler_flags"], "comparison report.compiler_flags", allow_empty=True)

    host = _object(document["host"], "comparison report.host")
    _required(
        host,
        {
            "platform", "node", "machine", "processor", "cpu_model",
            "cpu_model_source", "logical_cpus", "process_affinity", "python",
        },
        "comparison report.host",
    )
    _integer(host["logical_cpus"], "comparison report.host.logical_cpus", 1)
    _source_bundle(document["runner"], "comparison report.runner")
    adapter = _artifact(
        document["adapter_source"],
        "comparison report.adapter_source",
        revision=True,
    )

    revisions: list[str] = []
    capabilities: list[dict[str, tuple[str, frozenset[str]]]] = []
    for side in ("baseline", "candidate"):
        side_document = _object(document[side], f"comparison report.{side}")
        _required(
            side_document,
            {"artifact", "description", "description_invocation"},
            f"comparison report.{side}",
        )
        artifact = _artifact(
            side_document["artifact"], f"comparison report.{side}.artifact", revision=True
        )
        description = _object(
            side_document["description"], f"comparison report.{side}.description"
        )
        _required(
            description,
            {"protocol", "revision", "operations", "sources", "operation_contracts"},
            f"comparison report.{side}.description",
        )
        if description["protocol"] != COMMON_PROTOCOL:
            raise RuntimeError(f"comparison report.{side} protocol is invalid")
        if description["revision"] != artifact["revision"]:
            raise RuntimeError(f"comparison report.{side} revision is inconsistent")
        revisions.append(str(artifact["revision"]))
        operations = {entry for entry in str(description["operations"]).split(",") if entry}
        sources = {entry for entry in str(description["sources"]).split(",") if entry}
        if not operations or not sources:
            raise RuntimeError(f"comparison report.{side} capabilities are empty")
        contracts = parse_operation_contracts(str(description["operation_contracts"]))
        if set(contracts) != operations:
            raise RuntimeError(
                f"comparison report.{side} operation list and contracts differ"
            )
        contract_sources = {
            source
            for _, supported_sources in contracts.values()
            for source in supported_sources
        }
        if sources != contract_sources:
            raise RuntimeError(
                f"comparison report.{side} source list and contracts differ"
            )
        capabilities.append(contracts)
        _invocation(
            side_document["description_invocation"],
            f"comparison report.{side}.description_invocation",
        )

    datasets = _array(document["datasets"], "comparison report.datasets")
    cases = _array(document["cases"], "comparison report.cases")
    if document["status"] == "completed":
        _string(document.get("completed_at_utc"), "comparison report.completed_at_utc")
        if not datasets or not cases:
            raise RuntimeError("completed comparison report requires datasets and cases")
    elif document["status"] == "failed":
        _string(document.get("error"), "comparison report.error")

    dataset_sizes: dict[str, int] = {}
    for index, value in enumerate(datasets):
        label = f"comparison report.datasets[{index}]"
        dataset = _object(value, label)
        _required(dataset, {"name", "path", "size", "sha256"}, label)
        name = _string(dataset["name"], f"{label}.name")
        if name in dataset_sizes:
            raise RuntimeError("comparison report contains duplicate datasets")
        _string(dataset["path"], f"{label}.path")
        dataset_sizes[name] = _integer(dataset["size"], f"{label}.size", 1)
        _string(dataset["sha256"], f"{label}.sha256")
    case_keys: set[tuple[str, str, str]] = set()
    for index, value in enumerate(cases):
        label = f"comparison report.cases[{index}]"
        case = _object(value, label)
        _required(
            case,
            {
                "dataset", "operation", "source", "semantic_signature",
                "baseline", "candidate", "candidate_over_baseline_95pct",
                "measured_noise", "calibration_noise", "observed_noise",
                "regression_threshold", "regression", "improvement", "launches",
            },
            label,
        )
        dataset_name = _string(case["dataset"], f"{label}.dataset")
        if dataset_name not in dataset_sizes:
            raise RuntimeError(f"{label}.dataset is not in report datasets")
        operation = _string(case["operation"], f"{label}.operation")
        source = _string(case["source"], f"{label}.source")
        if source not in {"buffer", "mmap"}:
            raise RuntimeError(f"{label}.source is invalid")
        case_key = (dataset_name, operation, source)
        if case_key in case_keys:
            raise RuntimeError("comparison report contains duplicate cases")
        case_keys.add(case_key)
        operation_capabilities = [contracts.get(operation) for contracts in capabilities]
        if any(
            contract is None or source not in contract[1]
            for contract in operation_capabilities
        ):
            raise RuntimeError(f"{label} is not supported by both artifacts")
        expected_scopes = {contract[0] for contract in operation_capabilities if contract}
        if len(expected_scopes) != 1:
            raise RuntimeError(f"{label} scope differs between artifacts")
        expected_scope = next(iter(expected_scopes))
        signature_values = _array(
            case["semantic_signature"], f"{label}.semantic_signature"
        )
        if len(signature_values) != 6:
            raise RuntimeError(f"{label}.semantic_signature has the wrong length")
        signature = tuple(
            _string(entry, f"{label}.semantic_signature[{position}]")
            for position, entry in enumerate(signature_values)
        )
        for position, field in enumerate(
            ("bytes", "iterations", "rows", "cells", "row_bytes", "checksum")
        ):
            _uint64_string(signature[position], f"{label}.semantic_signature.{field}")
        if int(signature[0]) != dataset_sizes[dataset_name] or int(signature[1]) != iterations:
            raise RuntimeError(f"{label}.semantic_signature context is inconsistent")

        baseline_samples = _sample_statistics(
            case["baseline"], f"{label}.baseline", runs
        )
        candidate_samples = _sample_statistics(
            case["candidate"], f"{label}.candidate", runs
        )
        interval = _array(
            case["candidate_over_baseline_95pct"],
            f"{label}.candidate_over_baseline_95pct",
        )
        if len(interval) != 2:
            raise RuntimeError(f"{label}.candidate_over_baseline_95pct has the wrong length")
        low = _number(interval[0], f"{label}.candidate_over_baseline_95pct[0]", positive=True)
        high = _number(interval[1], f"{label}.candidate_over_baseline_95pct[1]", positive=True)
        if low > high:
            raise RuntimeError(f"{label}.candidate_over_baseline_95pct is reversed")
        for field in (
            "measured_noise",
            "calibration_noise",
            "observed_noise",
            "regression_threshold",
        ):
            minimum = 0.05 if field == "regression_threshold" else 0.0
            _number(case[field], f"{label}.{field}", minimum=minimum)
        regression = _boolean(case["regression"], f"{label}.regression")
        improvement = _boolean(case["improvement"], f"{label}.improvement")
        if regression and improvement:
            raise RuntimeError(f"{label} cannot be both a regression and improvement")

        launches = _array(case["launches"], f"{label}.launches")
        if document["status"] == "completed" and len(launches) != 2 * (runs + warmups):
            raise RuntimeError(f"{label}.launches has the wrong length")
        measured: dict[str, list[float]] = {"baseline": [], "candidate": []}
        phase_counts = {
            "baseline": {"warmup": 0, "sample": 0},
            "candidate": {"warmup": 0, "sample": 0},
        }
        for launch_index, launch_value in enumerate(launches):
            launch_label = f"{label}.launches[{launch_index}]"
            launch = _object(launch_value, launch_label)
            _required(
                launch,
                {
                    "phase", "round", "order", "side", "command", "stdout",
                    "stderr", "throughput_gib_per_second", "result",
                },
                launch_label,
            )
            phase = _string(launch["phase"], f"{launch_label}.phase")
            side = _string(launch["side"], f"{launch_label}.side")
            if phase not in {"warmup", "sample"} or side not in {
                "baseline",
                "candidate",
            }:
                raise RuntimeError(f"{launch_label} phase or side is invalid")
            round_index = _integer(launch["round"], f"{launch_label}.round")
            expected_rounds = warmups if phase == "warmup" else runs
            if round_index >= expected_rounds:
                raise RuntimeError(f"{launch_label}.round is out of range")
            if _integer(launch["order"], f"{launch_label}.order") not in {0, 1}:
                raise RuntimeError(f"{launch_label}.order is invalid")
            _invocation(
                {key: launch[key] for key in ("command", "stdout", "stderr")},
                launch_label,
            )
            throughput = _number(
                launch["throughput_gib_per_second"],
                f"{launch_label}.throughput_gib_per_second",
                positive=True,
            )
            result = _object(launch["result"], f"{launch_label}.result")
            result_fields = {
                "protocol", "revision", "operation", "scope", "source", "bytes",
                "iterations", "elapsed_ns", "rows", "cells", "row_bytes", "checksum",
                "timed_reader_steps",
            }
            _required(result, result_fields, f"{launch_label}.result")
            if result["protocol"] != COMMON_PROTOCOL:
                raise RuntimeError(f"{launch_label}.result protocol is invalid")
            expected_revision = revisions[0 if side == "baseline" else 1]
            if result["revision"] != expected_revision:
                raise RuntimeError(f"{launch_label}.result revision is inconsistent")
            if result["operation"] != operation or result["source"] != source:
                raise RuntimeError(f"{launch_label}.result context is inconsistent")
            if result["scope"] != expected_scope:
                raise RuntimeError(f"{launch_label}.result scope is inconsistent")
            for field in (
                "bytes", "iterations", "rows", "cells", "row_bytes", "checksum",
                "timed_reader_steps",
            ):
                _uint64_string(result[field], f"{launch_label}.result.{field}")
            if expected_scope == "writer_only" and result["timed_reader_steps"] != "0":
                raise RuntimeError(
                    f"{launch_label}.result performed Reader work in writer-only scope"
                )
            result_signature = tuple(
                result[field]
                for field in ("bytes", "iterations", "rows", "cells", "row_bytes", "checksum")
            )
            if result_signature != signature:
                raise RuntimeError(f"{launch_label}.result signature is inconsistent")
            if _uint64_string(result["elapsed_ns"], f"{launch_label}.result.elapsed_ns") < 1:
                raise RuntimeError(f"{launch_label}.result.elapsed_ns must be positive")
            phase_counts[side][phase] += 1
            if phase == "sample":
                measured[side].append(throughput)
        for side, expected_samples in (
            ("baseline", baseline_samples),
            ("candidate", candidate_samples),
        ):
            if phase_counts[side] != {"warmup": warmups, "sample": runs}:
                raise RuntimeError(f"{label} has incomplete {side} launches")
            if measured[side] != expected_samples:
                raise RuntimeError(f"{label}.{side}.samples do not match launches")

    controlled = document["evidence_level"] == "controlled"
    if controlled:
        if runs < 20 or warmups < 3:
            raise RuntimeError("controlled comparison requires 20 runs and three warmups")
        affinity = host.get("process_affinity")
        if not isinstance(affinity, list) or not affinity:
            raise RuntimeError("controlled comparison requires process affinity")
        if document["mode"] == "compare" and not isinstance(document["calibration"], dict):
            raise RuntimeError("controlled comparison requires calibration provenance")
    if isinstance(document["calibration"], dict):
        calibration = document["calibration"]
        _required(
            calibration,
            {"path", "size", "sha256", "schema"},
            "comparison report.calibration",
        )
        _string(calibration["path"], "comparison report.calibration.path")
        _integer(calibration["size"], "comparison report.calibration.size", 1)
        _string(calibration["sha256"], "comparison report.calibration.sha256")
        if calibration["schema"] != "csv2-benchmark-report-v3":
            raise RuntimeError("comparison report calibration schema is invalid")
    if document["mode"] == "aa" and document["calibration"] is not None:
        raise RuntimeError("A/A comparison must not reference another calibration")
    if document["mode"] == "aa" and revisions[0] != revisions[1]:
        raise RuntimeError("A/A comparison revisions must match")
    if document["mode"] == "aa":
        baseline_hash = document["baseline"]["artifact"]["sha256"]
        candidate_hash = document["candidate"]["artifact"]["sha256"]
        if baseline_hash != candidate_hash:
            raise RuntimeError("A/A comparison artifacts must be byte-identical")
    if adapter["revision"] != "shared-source":
        raise RuntimeError("comparison report adapter revision is invalid")


def validate_fixed_metrics_report(report: object) -> None:
    document = _object(report, "fixed-machine report")
    allowed = {
        "schema", "status", "evidence_level", "decision_eligible",
        "generated_at_utc", "completed_at_utc", "error", "machine", "compiler",
        "compiler_identity", "compiler_flags", "operation", "source", "runs",
        "artifacts", "clean_build", "post_build", "verification", "allocations", "timing",
        "timing_invocation", "pmu", "pmu_invocation", "peak_rss", "code_size",
    }
    required = {
        "schema", "status", "evidence_level", "decision_eligible",
        "generated_at_utc", "machine", "compiler", "compiler_identity",
        "compiler_flags", "operation", "source", "runs", "artifacts", "clean_build",
        "post_build",
    }
    _required(document, required, "fixed-machine report")
    _closed(document, allowed, "fixed-machine report")
    if document["schema"] != "csv2-fixed-machine-metrics-v3":
        raise RuntimeError("fixed-machine report has an unsupported schema")
    status = document["status"]
    evidence = document["evidence_level"]
    if status not in {"running", "completed", "failed"}:
        raise RuntimeError("fixed-machine report status is invalid")
    if evidence not in {"exploratory", "controlled"}:
        raise RuntimeError("fixed-machine report evidence level is invalid")
    expected_eligible = decision_eligible(str(evidence), str(status))
    if type(document["decision_eligible"]) is not bool or document[
        "decision_eligible"
    ] != expected_eligible:
        raise RuntimeError("fixed-machine report decision eligibility is inconsistent")
    runs = _integer(document["runs"], "fixed-machine report.runs", 1)
    _string(document["generated_at_utc"], "fixed-machine report.generated_at_utc")
    _string(document["compiler"], "fixed-machine report.compiler")
    _string(document["compiler_flags"], "fixed-machine report.compiler_flags", allow_empty=True)
    _string(document["operation"], "fixed-machine report.operation")
    if document["source"] not in {"buffer", "mmap", "file"}:
        raise RuntimeError("fixed-machine report source is invalid")
    machine = _object(document["machine"], "fixed-machine report.machine")
    _required(
        machine,
        {
            "system", "release", "machine", "node", "cpu_model",
            "cpu_model_source", "logical_cpus", "process_affinity", "python",
        },
        "fixed-machine report.machine",
    )
    _integer(machine["logical_cpus"], "fixed-machine report.machine.logical_cpus", 1)
    identities = _object(document["artifacts"], "fixed-machine report.artifacts")
    _required(
        identities,
        {"collector", "executable", "allocation_executable", "dataset"},
        "fixed-machine report.artifacts",
    )
    _source_bundle(identities["collector"], "fixed-machine report.artifacts.collector")
    executable = _artifact(
        identities["executable"],
        "fixed-machine report.artifacts.executable",
        revision=True,
    )
    allocation = _artifact(
        identities["allocation_executable"],
        "fixed-machine report.artifacts.allocation_executable",
        revision=True,
    )
    _artifact(identities["dataset"], "fixed-machine report.artifacts.dataset", revision=False)
    if executable["revision"] != allocation["revision"]:
        raise RuntimeError("fixed-machine executable revisions are inconsistent")

    if status == "completed":
        _required(
            document,
            {"completed_at_utc", "verification", "allocations", "timing", "timing_invocation"},
            "completed fixed-machine report",
        )
        _string(document["completed_at_utc"], "fixed-machine report.completed_at_utc")
        verification = _object(document["verification"], "fixed-machine report.verification")
        _required(verification, {"result", "invocation"}, "fixed-machine report.verification")
        result = _object(verification["result"], "fixed-machine report.verification.result")
        current_fields = {
            "protocol", "revision", "operation", "source", "dataset", "checksum",
            "bytes", "rows", "cells", "allocations", "allocated_bytes",
        }
        _required(result, current_fields, "fixed-machine report.verification.result")
        if result["protocol"] != "csv2-current-v2":
            raise RuntimeError("fixed-machine verification protocol is invalid")
        if result["revision"] != executable["revision"]:
            raise RuntimeError("fixed-machine verification revision is inconsistent")
        if result["operation"] != document["operation"] or result["source"] != document["source"]:
            raise RuntimeError("fixed-machine verification context is inconsistent")
        for field in (
            "checksum", "bytes", "rows", "cells", "allocations", "allocated_bytes"
        ):
            _uint64_string(result[field], f"fixed-machine report.verification.result.{field}")
        _string(result["dataset"], "fixed-machine report.verification.result.dataset")
        _invocation(verification["invocation"], "fixed-machine report.verification.invocation")
        allocations = _object(document["allocations"], "fixed-machine report.allocations")
        _required(
            allocations,
            {"count", "bytes", "invocation"},
            "fixed-machine report.allocations",
        )
        _integer(allocations["count"], "fixed-machine report.allocations.count")
        _integer(allocations["bytes"], "fixed-machine report.allocations.bytes")
        _invocation(
            allocations["invocation"], "fixed-machine report.allocations.invocation"
        )
        _timing(document["timing"], "fixed-machine report.timing", runs)
        _invocation(document["timing_invocation"], "fixed-machine report.timing_invocation")
        if document["clean_build"] is not None:
            _clean_build(document["clean_build"], "fixed-machine report.clean_build")
        if document.get("post_build") is not None:
            _invocation(document["post_build"], "fixed-machine report.post_build")
        if document.get("pmu") is not None:
            _timing(
                document["pmu"],
                "fixed-machine report.pmu",
                runs,
                require_pmu=True,
            )
            _invocation(
                document.get("pmu_invocation"),
                "fixed-machine report.pmu_invocation",
            )
        if document.get("peak_rss") is not None:
            _peak_rss(document["peak_rss"], "fixed-machine report.peak_rss")
        if document.get("code_size") is not None:
            _code_size(
                document["code_size"],
                "fixed-machine report.code_size",
                require_sections=False,
            )
    elif status == "failed":
        _string(document.get("error"), "fixed-machine report.error")

    if evidence == "controlled":
        if runs < 20:
            raise RuntimeError("controlled fixed-machine report requires 20 runs")
        affinity = machine.get("process_affinity")
        if not isinstance(affinity, list) or not affinity:
            raise RuntimeError("controlled fixed-machine report requires process affinity")
        compiler_identity = _object(
            document["compiler_identity"],
            "fixed-machine report.compiler_identity",
        )
        _required(
            compiler_identity,
            {
                "artifact",
                "compile_command_matches",
                "version_command",
                "version_stdout",
                "version_stderr",
            },
            "fixed-machine report.compiler_identity",
        )
        _integer(
            compiler_identity["compile_command_matches"],
            "fixed-machine report.compiler_identity.compile_command_matches",
            1,
        )
        compiler_artifact = _artifact(
            compiler_identity["artifact"],
            "fixed-machine report.compiler_identity.artifact",
            revision=False,
        )
        version_command = _array(
            compiler_identity["version_command"],
            "fixed-machine report.compiler_identity.version_command",
        )
        if not version_command or not all(
            isinstance(item, str) and item for item in version_command
        ):
            raise RuntimeError("fixed-machine compiler version command is invalid")
        _string(
            compiler_identity["version_stdout"],
            "fixed-machine report.compiler_identity.version_stdout",
        )
        _string(
            compiler_identity["version_stderr"],
            "fixed-machine report.compiler_identity.version_stderr",
            allow_empty=True,
        )
        _required(
            identities,
            {"compiler_executable", "compile_commands"},
            "controlled fixed-machine artifacts",
        )
        recorded_compiler = _artifact(
            identities["compiler_executable"],
            "controlled compiler executable",
            revision=False,
        )
        if compiler_artifact["sha256"] != recorded_compiler["sha256"]:
            raise RuntimeError("fixed-machine compiler identities are inconsistent")
        _artifact(identities["compile_commands"], "controlled compile commands", revision=False)
        if status == "completed":
            _required(
                document,
                {"pmu", "pmu_invocation", "peak_rss", "code_size", "post_build"},
                "completed controlled fixed-machine report",
            )
            _clean_build(document["clean_build"], "fixed-machine report.clean_build")
            _invocation(document["post_build"], "fixed-machine report.post_build")
            _timing(
                document["pmu"],
                "fixed-machine report.pmu",
                runs,
                require_pmu=True,
            )
            _invocation(document["pmu_invocation"], "fixed-machine report.pmu_invocation")
            _peak_rss(document["peak_rss"], "fixed-machine report.peak_rss")
            _code_size(
                document["code_size"],
                "fixed-machine report.code_size",
                require_sections=True,
            )
