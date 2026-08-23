"""Strict parsers for the versioned CSV2 benchmark wire protocols."""

from __future__ import annotations

import math
from typing import Iterable

from . import COMPARISON_SCHEMA, CURRENT_PROTOCOL, EVIDENCE_SCHEMA, METRICS_SCHEMA
from . import COMMON_PROTOCOL
from . import derivation

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


def parse_operation_contracts(
    encoded: str,
) -> dict[str, tuple[str, frozenset[str], str, str]]:
    contracts: dict[str, tuple[str, frozenset[str], str, str]] = {}
    if not encoded:
        raise RuntimeError("operation contracts must not be empty")
    for entry in encoded.split(";"):
        parts = entry.split(":")
        if len(parts) != 5 or not all(parts):
            raise RuntimeError(f"malformed operation contract: {entry!r}")
        operation, scope, encoded_sources, semantic_case_id, byte_basis = parts
        if operation in contracts:
            raise RuntimeError(f"duplicate operation contract: {operation}")
        if scope not in {"traversal_only", "mmap_and_traversal", "writer_only"}:
            raise RuntimeError(f"unsupported operation scope: {scope}")
        if not semantic_case_id.startswith("csv2.") or not semantic_case_id.endswith(".v1"):
            raise RuntimeError(f"unsupported semantic case ID: {semantic_case_id}")
        if byte_basis != "input_corpus":
            raise RuntimeError(f"unsupported byte basis: {byte_basis}")
        source_entries = encoded_sources.split("+")
        if (
            any(source not in {"buffer", "mmap"} for source in source_entries)
            or len(source_entries) != len(set(source_entries))
        ):
            raise RuntimeError(f"invalid operation sources: {encoded_sources}")
        contracts[operation] = (
            scope,
            frozenset(source_entries),
            semantic_case_id,
            byte_basis,
        )
    return contracts


def parse_current(output: str) -> dict[str, str]:
    required = {
        "protocol",
        "revision",
        "operation",
        "source",
        "dataset",
        "semantic_case_id",
        "scope",
        "byte_basis",
        "checksum",
        "bytes",
        "rows",
        "cells",
        "allocations",
        "allocated_bytes",
    }
    result = parse_key_value_line(output, required)
    require_protocol(result, CURRENT_PROTOCOL)
    if not result["semantic_case_id"].startswith("csv2."):
        raise RuntimeError("benchmark semantic case ID is invalid")
    if not result["scope"].endswith("_only"):
        raise RuntimeError("benchmark scope is invalid")
    if result["byte_basis"] != "input_corpus":
        raise RuntimeError("benchmark byte basis is invalid")
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


def controlled_complete(
    evidence_level: str, status: str, *, owned_build: bool = True
) -> bool:
    """Return whether one component satisfies its controlled evidence contract."""
    return evidence_level == "controlled" and status == "completed" and owned_build


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
    _hex_digest(artifact["sha256"], f"{label}.sha256", (64,))
    _integer(artifact["mtime_ns"], f"{label}.mtime_ns")
    if revision:
        _string(artifact["revision"], f"{label}.revision")
    return artifact


def _manifest_artifact(
    value: object, label: str, *, revision: bool
) -> dict[str, object]:
    artifact = _artifact(value, label, revision=revision)
    fields = {"path", "size", "sha256", "mtime_ns"}
    if revision:
        fields.add("revision")
    _closed(artifact, fields, label)
    return artifact


def _machine_profile(value: object, label: str) -> dict[str, object]:
    binding = _object(value, label)
    binding_fields = {"artifact", "profile", "digest", "observation"}
    _required(binding, binding_fields, label)
    _closed(binding, binding_fields, label)
    artifact = _manifest_artifact(binding["artifact"], f"{label}.artifact", revision=False)
    digest = _hex_digest(binding["digest"], f"{label}.digest", (64,))
    if digest != artifact["sha256"]:
        raise RuntimeError(f"{label}.digest differs from its artifact")
    profile = _object(binding["profile"], f"{label}.profile")
    profile_fields = {
        "schema", "id", "system", "architecture", "cpu_model",
        "logical_cpus", "allowed_affinity", "kernel_release", "governor",
        "turbo_boost",
    }
    _required(profile, profile_fields, f"{label}.profile")
    _closed(profile, profile_fields, f"{label}.profile")
    if profile["schema"] != "csv2-machine-profile-v1":
        raise RuntimeError(f"{label}.profile schema is invalid")
    for field in profile_fields - {"logical_cpus", "allowed_affinity"}:
        _string(profile[field], f"{label}.profile.{field}")
    logical_cpus = _integer(
        profile["logical_cpus"], f"{label}.profile.logical_cpus", 1
    )
    allowed = _array(profile["allowed_affinity"], f"{label}.profile.allowed_affinity")
    if (
        not allowed
        or any(
            isinstance(cpu, bool) or not isinstance(cpu, int) or cpu < 0
            for cpu in allowed
        )
        or allowed != sorted(set(allowed))
        or allowed[-1] >= logical_cpus
    ):
        raise RuntimeError(f"{label}.profile allowed affinity is invalid")
    observation = _object(binding["observation"], f"{label}.observation")
    observation_fields = {
        "system", "architecture", "cpu_model", "logical_cpus",
        "process_affinity", "kernel_release", "governor", "turbo_boost",
    }
    _required(observation, observation_fields, f"{label}.observation")
    _closed(observation, observation_fields, f"{label}.observation")
    for field in observation_fields - {"logical_cpus", "process_affinity"}:
        _string(observation[field], f"{label}.observation.{field}")
    _integer(observation["logical_cpus"], f"{label}.observation.logical_cpus", 1)
    affinity = _array(
        observation["process_affinity"], f"{label}.observation.process_affinity"
    )
    if not affinity or any(
        isinstance(cpu, bool) or not isinstance(cpu, int) or cpu < 0
        for cpu in affinity
    ):
        raise RuntimeError(f"{label}.observation affinity is invalid")
    for field in (
        "system", "architecture", "cpu_model", "logical_cpus", "kernel_release",
        "governor", "turbo_boost",
    ):
        if profile[field] != observation[field]:
            raise RuntimeError(f"{label} profile and observation differ for {field}")
    if not set(affinity) <= set(allowed):
        raise RuntimeError(f"{label}.observation affinity is outside the profile")
    return binding


def _source_bundle(value: object, label: str) -> dict[str, object]:
    bundle = _object(value, label)
    fields = {"kind", "root", "revision", "sha256", "files"}
    _required(bundle, fields, label)
    _closed(bundle, fields, label)
    if bundle["kind"] != "source-bundle":
        raise RuntimeError(f"{label}.kind must be source-bundle")
    _string(bundle["root"], f"{label}.root")
    _string(bundle["revision"], f"{label}.revision")
    _hex_digest(bundle["sha256"], f"{label}.sha256", (64,))
    members = _array(bundle["files"], f"{label}.files")
    if not members:
        raise RuntimeError(f"{label}.files must not be empty")
    seen: set[str] = set()
    for index, value in enumerate(members):
        member_label = f"{label}.files[{index}]"
        member = _object(value, member_label)
        member_fields = {"path", "size", "sha256", "mtime_ns"}
        _required(member, member_fields, member_label)
        _closed(member, member_fields, member_label)
        path = _string(member["path"], f"{member_label}.path")
        components = path.split("/")
        if (
            "\\" in path
            or path.startswith("/")
            or any(component in {"", ".", ".."} for component in components)
            or any(":" in component for component in components)
        ):
            raise RuntimeError(f"{member_label}.path must be a safe relative path")
        if path in seen:
            raise RuntimeError(f"{label}.files contains duplicate paths")
        seen.add(path)
        _integer(member["size"], f"{member_label}.size")
        _hex_digest(member["sha256"], f"{member_label}.sha256", (64,))
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
    derivation.validate_timing_summary(timing, label)
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


def _hex_digest(value: object, label: str, lengths: tuple[int, ...]) -> str:
    text = _string(value, label)
    if len(text) not in lengths or any(character not in "0123456789abcdef" for character in text):
        raise RuntimeError(f"{label} is not a lowercase hexadecimal digest")
    return text


def _git_export(value: object, label: str) -> dict[str, object]:
    from . import builds as audited_builds

    export = _object(value, label)
    fields = {
        "schema", "repository", "reference", "commit", "tree", "selections",
        "root", "files", "digest",
    }
    _required(export, fields, label)
    _closed(export, fields, label)
    if export["schema"] != "csv2-git-export-v1":
        raise RuntimeError(f"{label}.schema is unsupported")
    for field in ("repository", "reference", "root"):
        _string(export[field], f"{label}.{field}")
    _hex_digest(export["commit"], f"{label}.commit", (40, 64))
    _hex_digest(export["tree"], f"{label}.tree", (40, 64))
    selections = _array(export["selections"], f"{label}.selections")
    if not selections or not all(isinstance(item, str) and item for item in selections):
        raise RuntimeError(f"{label}.selections must contain strings")
    files = _array(export["files"], f"{label}.files")
    if not files:
        raise RuntimeError(f"{label}.files must not be empty")
    paths: set[str] = set()
    for index, value in enumerate(files):
        file_label = f"{label}.files[{index}]"
        entry = _object(value, file_label)
        entry_fields = {"mode", "type", "oid", "path", "size", "sha256"}
        _required(entry, entry_fields, file_label)
        _closed(entry, entry_fields, file_label)
        if entry["mode"] not in {"100644", "100755"} or entry["type"] != "blob":
            raise RuntimeError(f"{file_label} is not a regular Git blob")
        _hex_digest(entry["oid"], f"{file_label}.oid", (40, 64))
        path = _string(entry["path"], f"{file_label}.path")
        audited_builds.safe_git_path(path)
        if path in paths:
            raise RuntimeError(f"{label}.files contains duplicate paths")
        paths.add(path)
        _integer(entry["size"], f"{file_label}.size")
        _hex_digest(entry["sha256"], f"{file_label}.sha256", (64,))
    digest = _hex_digest(export["digest"], f"{label}.digest", (64,))
    unsigned = dict(export)
    unsigned.pop("digest")
    if audited_builds.document_digest(unsigned) != digest:
        raise RuntimeError(f"{label}.digest is inconsistent")
    return export


def _common_build(value: object, label: str) -> dict[str, object]:
    from . import BUILD_SCHEMA
    from . import builds as audited_builds

    build = _object(value, label)
    fields = {
        "schema", "kind", "generated_at_utc", "revision", "header_export",
        "adapter_export", "compiler", "compiler_flags", "argv", "normalized_argv",
        "build_log", "output", "identity_digest", "digest",
    }
    _required(build, fields, label)
    _closed(build, fields, label)
    if build["schema"] != BUILD_SCHEMA or build["kind"] != "common-driver":
        raise RuntimeError(f"{label} has the wrong schema or kind")
    _string(build["generated_at_utc"], f"{label}.generated_at_utc")
    revision = _hex_digest(build["revision"], f"{label}.revision", (40, 64))
    headers = _git_export(build["header_export"], f"{label}.header_export")
    adapter = _git_export(build["adapter_export"], f"{label}.adapter_export")
    if headers["commit"] != revision:
        raise RuntimeError(f"{label} revision differs from its headers")
    if any(
        entry["path"] != "include" and not entry["path"].startswith("include/")
        for entry in headers["files"]
    ):
        raise RuntimeError(f"{label} header export contains non-header paths")
    if [entry["path"] for entry in adapter["files"]] != [
        "benchmark/compare/common_driver.cpp"
    ]:
        raise RuntimeError(f"{label} adapter export is not the common driver")
    compiler = _object(build["compiler"], f"{label}.compiler")
    _required(compiler, {"artifact", "version"}, f"{label}.compiler")
    _closed(compiler, {"artifact", "version"}, f"{label}.compiler")
    _artifact(compiler["artifact"], f"{label}.compiler.artifact", revision=False)
    version = _object(compiler["version"], f"{label}.compiler.version")
    _required(version, {"command", "returncode", "stdout", "stderr"}, f"{label}.compiler.version")
    _closed(version, {"command", "returncode", "stdout", "stderr"}, f"{label}.compiler.version")
    _invocation(
        {"command": version["command"], "stdout": version["stdout"], "stderr": version["stderr"]},
        f"{label}.compiler.version",
    )
    if _integer(version["returncode"], f"{label}.compiler.version.returncode") != 0:
        raise RuntimeError(f"{label}.compiler.version did not succeed")
    for field in ("compiler_flags", "argv", "normalized_argv"):
        values = _array(build[field], f"{label}.{field}")
        if not values or not all(
            isinstance(item, str) and item for item in values
        ):
            raise RuntimeError(f"{label}.{field} is malformed")
    if len(build["argv"]) != len(build["normalized_argv"]):
        raise RuntimeError(f"{label} normalized command length differs")
    normalized_text = "\n".join(build["normalized_argv"])
    for placeholder in ("{revision}", "{include_root}", "{adapter_source}", "{output}"):
        if placeholder not in normalized_text:
            raise RuntimeError(f"{label} normalized command lacks {placeholder}")
    if build["argv"][0] != compiler["artifact"]["path"]:
        raise RuntimeError(f"{label} command did not invoke the recorded compiler")
    log = _object(build["build_log"], f"{label}.build_log")
    _required(log, {"returncode", "stdout", "stderr"}, f"{label}.build_log")
    if _integer(log["returncode"], f"{label}.build_log.returncode") != 0:
        raise RuntimeError(f"{label}.build_log did not succeed")
    for stream in ("stdout", "stderr"):
        if not isinstance(log[stream], str):
            raise RuntimeError(f"{label}.build_log.{stream} must be a string")
    output = _artifact(build["output"], f"{label}.output", revision=True)
    if output["revision"] != revision:
        raise RuntimeError(f"{label}.output revision is inconsistent")
    identity = _hex_digest(build["identity_digest"], f"{label}.identity_digest", (64,))
    try:
        actual_identity = audited_builds.common_build_identity_digest(build)
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"{label}.identity_digest cannot be reconstructed") from error
    if identity != actual_identity:
        raise RuntimeError(f"{label}.identity_digest is inconsistent")
    digest = _hex_digest(build["digest"], f"{label}.digest", (64,))
    unsigned = dict(build)
    unsigned.pop("digest")
    if audited_builds.document_digest(unsigned) != digest:
        raise RuntimeError(f"{label}.digest is inconsistent")
    return build


def _tool_identity(value: object, label: str) -> dict[str, object]:
    tool = _object(value, label)
    _required(tool, {"artifact", "version"}, label)
    _closed(tool, {"artifact", "version"}, label)
    _artifact(tool["artifact"], f"{label}.artifact", revision=False)
    version = _object(tool["version"], f"{label}.version")
    _required(version, {"command", "returncode", "stdout", "stderr"}, f"{label}.version")
    _closed(version, {"command", "returncode", "stdout", "stderr"}, f"{label}.version")
    _invocation(
        {"command": version["command"], "stdout": version["stdout"], "stderr": version["stderr"]},
        f"{label}.version",
    )
    if _integer(version["returncode"], f"{label}.version.returncode") != 0:
        raise RuntimeError(f"{label}.version did not succeed")
    return tool


def _current_build(value: object, label: str) -> dict[str, object]:
    from . import BUILD_SCHEMA
    from . import builds as audited_builds

    build = _object(value, label)
    fields = {
        "schema", "kind", "generated_at_utc", "revision", "source_export",
        "compiler", "compiler_flags", "cmake", "ninja", "configure_argv",
        "normalized_configure_argv",
        "build_argv", "configure_log", "build_log", "file_api", "compile_commands",
        "targets", "corpus_manifest", "source_root", "build_root", "identity_digest",
        "digest",
    }
    _required(build, fields, label)
    _closed(build, fields, label)
    if build["schema"] != BUILD_SCHEMA or build["kind"] != "current-tree":
        raise RuntimeError(f"{label} has the wrong schema or kind")
    _string(build["generated_at_utc"], f"{label}.generated_at_utc")
    revision = _hex_digest(build["revision"], f"{label}.revision", (40, 64))
    source = _git_export(build["source_export"], f"{label}.source_export")
    if source["commit"] != revision or source["selections"] != ["<full-tree>"]:
        raise RuntimeError(f"{label} is not bound to a full candidate tree")
    for tool_name in ("compiler", "cmake", "ninja"):
        _tool_identity(build[tool_name], f"{label}.{tool_name}")
    compiler_flags = _array(build["compiler_flags"], f"{label}.compiler_flags")
    if not compiler_flags or not all(
        isinstance(flag, str) and flag for flag in compiler_flags
    ):
        raise RuntimeError(f"{label}.compiler_flags is malformed")
    for field in ("configure_argv", "normalized_configure_argv", "build_argv"):
        values = _array(build[field], f"{label}.{field}")
        if not values or not all(isinstance(item, str) and item for item in values):
            raise RuntimeError(f"{label}.{field} is malformed")
    if len(build["configure_argv"]) != len(build["normalized_configure_argv"]):
        raise RuntimeError(f"{label} normalized configure command differs in length")
    normalized = "\n".join(build["normalized_configure_argv"])
    for placeholder in ("{source_root}", "{build_root}", "{compiler}", "{revision}"):
        if placeholder not in normalized:
            raise RuntimeError(f"{label} configure command lacks {placeholder}")
    expected_flag_argument = "-DCMAKE_CXX_FLAGS_RELEASE=" + " ".join(compiler_flags)
    if expected_flag_argument not in build["configure_argv"]:
        raise RuntimeError(f"{label} configure command differs from compiler_flags")
    for log_name in ("configure_log", "build_log"):
        log = _object(build[log_name], f"{label}.{log_name}")
        _required(log, {"returncode", "seconds", "stdout", "stderr"}, f"{label}.{log_name}")
        if _integer(log["returncode"], f"{label}.{log_name}.returncode") != 0:
            raise RuntimeError(f"{label}.{log_name} did not succeed")
        _number(log["seconds"], f"{label}.{log_name}.seconds", positive=True)
    _artifact(build["compile_commands"], f"{label}.compile_commands", revision=False)
    _artifact(build["corpus_manifest"], f"{label}.corpus_manifest", revision=False)
    targets = _object(build["targets"], f"{label}.targets")
    expected_targets = {"csv2_benchmark", "csv2_benchmark_allocations"}
    _required(targets, expected_targets, f"{label}.targets")
    _closed(targets, expected_targets, f"{label}.targets")
    for name in expected_targets:
        artifact = _artifact(targets[name], f"{label}.targets.{name}", revision=True)
        if artifact["revision"] != revision:
            raise RuntimeError(f"{label}.targets.{name} revision is inconsistent")
    api = _object(build["file_api"], f"{label}.file_api")
    _required(api, {"compiler", "targets", "link_commands"}, f"{label}.file_api")
    api_targets = _object(api["targets"], f"{label}.file_api.targets")
    links = _object(api["link_commands"], f"{label}.file_api.link_commands")
    for name in expected_targets:
        target = _object(api_targets.get(name), f"{label}.file_api.targets.{name}")
        sources = set(_array(target.get("sources"), f"{label}.file_api.targets.{name}.sources"))
        if sources != audited_builds.CURRENT_SOURCES:
            raise RuntimeError(f"{label}.file_api.targets.{name} source set is incomplete")
        commands = _array(links.get(name), f"{label}.file_api.link_commands.{name}")
        if not commands or not all(isinstance(command, str) and command for command in commands):
            raise RuntimeError(f"{label}.file_api lacks a link command for {name}")
    identity = _hex_digest(build["identity_digest"], f"{label}.identity_digest", (64,))
    if identity != audited_builds.current_build_identity_digest(build):
        raise RuntimeError(f"{label}.identity_digest is inconsistent")
    digest = _hex_digest(build["digest"], f"{label}.digest", (64,))
    unsigned = dict(build)
    unsigned.pop("digest")
    if digest != audited_builds.document_digest(unsigned):
        raise RuntimeError(f"{label}.digest is inconsistent")
    return build


def validate_comparison_report(report: object) -> None:
    document = _object(report, "comparison report")
    allowed = {
        "schema", "artifact_mode", "mode", "status", "evidence_level",
        "controlled_complete", "decision_eligible",
        "generated_at_utc", "completed_at_utc", "error", "runs", "warmups",
        "iterations_per_run", "compiler", "compiler_flags", "host", "runner",
        "adapter_source", "baseline", "candidate", "datasets", "calibration",
        "cases", "machine_profile",
    }
    required = allowed - {"completed_at_utc", "error"}
    _required(document, required, "comparison report")
    _closed(document, allowed, "comparison report")
    if document["schema"] != COMPARISON_SCHEMA:
        raise RuntimeError("comparison report has an unsupported schema")
    artifact_mode = document["artifact_mode"]
    if artifact_mode not in {"owned", "external"}:
        raise RuntimeError("comparison report artifact mode is invalid")
    if artifact_mode == "external" and document["evidence_level"] != "exploratory":
        raise RuntimeError("external artifacts are restricted to exploratory evidence")
    if document["mode"] not in {"aa", "compare"}:
        raise RuntimeError("comparison report mode is invalid")
    if document["status"] not in {"running", "completed", "failed"}:
        raise RuntimeError("comparison report status is invalid")
    if document["evidence_level"] not in {"exploratory", "controlled"}:
        raise RuntimeError("comparison report evidence level is invalid")
    if document["evidence_level"] == "controlled":
        _machine_profile(document["machine_profile"], "comparison report.machine_profile")
    elif document["machine_profile"] is not None:
        raise RuntimeError("exploratory comparison report must not bind a machine profile")
    expected_complete = controlled_complete(
        str(document["evidence_level"]),
        str(document["status"]),
        owned_build=artifact_mode == "owned",
    )
    if type(document["controlled_complete"]) is not bool or document[
        "controlled_complete"
    ] != expected_complete:
        raise RuntimeError("comparison report controlled completion is inconsistent")
    if document["decision_eligible"] is not False:
        raise RuntimeError("comparison reports cannot claim final decision eligibility")

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
    capabilities: list[
        dict[str, tuple[str, frozenset[str], str, str]]
    ] = []
    build_documents: list[dict[str, object]] = []
    for side in ("baseline", "candidate"):
        side_document = _object(document[side], f"comparison report.{side}")
        _required(
            side_document,
            {"artifact", "build", "description", "description_invocation"},
            f"comparison report.{side}",
        )
        artifact = _artifact(
            side_document["artifact"], f"comparison report.{side}.artifact", revision=True
        )
        if artifact_mode == "owned":
            build = _common_build(
                side_document["build"], f"comparison report.{side}.build"
            )
            output = build["output"]
            if any(
                artifact[field] != output[field]
                for field in ("path", "size", "sha256", "mtime_ns", "revision")
            ):
                raise RuntimeError(
                    f"comparison report.{side} artifact differs from its build"
                )
            build_documents.append(build)
        elif side_document["build"] is not None:
            raise RuntimeError(f"comparison report.{side}.build must be null")
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
            for _, supported_sources, _, _ in contracts.values()
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

    if artifact_mode == "owned":
        baseline_build, candidate_build = build_documents
        if (
            baseline_build["adapter_export"]["digest"]
            != candidate_build["adapter_export"]["digest"]
            or baseline_build["compiler"]["artifact"]["sha256"]
            != candidate_build["compiler"]["artifact"]["sha256"]
            or baseline_build["normalized_argv"] != candidate_build["normalized_argv"]
        ):
            raise RuntimeError("comparison owned builds are not compatible")
        expected_flags = " ".join(candidate_build["compiler_flags"])
        if document["compiler_flags"] != expected_flags:
            raise RuntimeError("comparison compiler_flags differ from the owned build")

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
                "dataset", "operation", "source", "semantic_case_id", "scope",
                "byte_basis", "semantic_signature",
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
        expected_semantic_ids = {
            contract[2] for contract in operation_capabilities if contract
        }
        if len(expected_semantic_ids) != 1:
            raise RuntimeError(f"{label} semantic case ID differs between artifacts")
        expected_semantic_case_id = next(iter(expected_semantic_ids))
        expected_byte_bases = {
            contract[3] for contract in operation_capabilities if contract
        }
        if len(expected_byte_bases) != 1:
            raise RuntimeError(f"{label} byte basis differs between artifacts")
        expected_byte_basis = next(iter(expected_byte_bases))
        if case["scope"] != expected_scope:
            raise RuntimeError(f"{label}.scope differs from its operation contract")
        if case["semantic_case_id"] != expected_semantic_case_id:
            raise RuntimeError(
                f"{label}.semantic_case_id differs from its operation contract"
            )
        if case["byte_basis"] != expected_byte_basis:
            raise RuntimeError(f"{label}.byte_basis differs from its operation contract")
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
                "protocol", "revision", "operation", "scope", "source",
                "semantic_case_id", "byte_basis", "bytes",
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
            if result["semantic_case_id"] != expected_semantic_case_id:
                raise RuntimeError(
                    f"{launch_label}.result semantic case ID is inconsistent"
                )
            if result["byte_basis"] != expected_byte_basis:
                raise RuntimeError(f"{launch_label}.result byte basis is inconsistent")
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
        derivation.validate_comparison_case(
            case,
            runs=runs,
            warmups=warmups,
            iterations=iterations,
            common_protocol=COMMON_PROTOCOL,
            label=label,
        )

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
        if calibration["schema"] != COMPARISON_SCHEMA:
            raise RuntimeError("comparison report calibration schema is invalid")
    if document["mode"] == "aa" and document["calibration"] is not None:
        raise RuntimeError("A/A comparison must not reference another calibration")
    if document["mode"] == "aa" and revisions[0] != revisions[1]:
        raise RuntimeError("A/A comparison revisions must match")
    if document["mode"] == "compare" and revisions[0] == revisions[1]:
        raise RuntimeError("A/B comparison requires different revisions")
    if document["mode"] == "aa":
        baseline_hash = document["baseline"]["artifact"]["sha256"]
        candidate_hash = document["candidate"]["artifact"]["sha256"]
        if baseline_hash != candidate_hash:
            raise RuntimeError("A/A comparison artifacts must be byte-identical")
        if artifact_mode == "owned" and (
            document["baseline"]["build"]["identity_digest"]
            != document["candidate"]["build"]["identity_digest"]
        ):
            raise RuntimeError("A/A comparison owned build identities must match")
    if artifact_mode == "owned":
        candidate_build = document["candidate"]["build"]
        adapter_export = candidate_build["adapter_export"]
        adapter_file = adapter_export["files"][0]
        if (
            adapter["revision"] != adapter_export["commit"]
            or adapter["sha256"] != adapter_file["sha256"]
        ):
            raise RuntimeError("comparison report adapter differs from the owned build")
    elif adapter["revision"] != "shared-source":
        raise RuntimeError("comparison report external adapter revision is invalid")


def validate_fixed_metrics_report(report: object) -> None:
    document = _object(report, "fixed-machine report")
    allowed = {
        "schema", "artifact_mode", "build", "status", "evidence_level",
        "controlled_complete", "decision_eligible",
        "generated_at_utc", "completed_at_utc", "error", "machine", "compiler",
        "compiler_identity", "compiler_flags", "operation", "source", "runs",
        "artifacts", "clean_build", "post_build", "verification", "allocations", "timing",
        "timing_invocation", "pmu", "pmu_invocation", "peak_rss", "code_size",
        "comparison_binding", "machine_profile",
    }
    required = {
        "schema", "artifact_mode", "build", "status", "evidence_level",
        "controlled_complete", "decision_eligible",
        "generated_at_utc", "machine", "compiler", "compiler_identity",
        "compiler_flags", "operation", "source", "runs", "artifacts", "clean_build",
        "post_build", "machine_profile",
    }
    _required(document, required, "fixed-machine report")
    _closed(document, allowed, "fixed-machine report")
    if document["schema"] != METRICS_SCHEMA:
        raise RuntimeError("fixed-machine report has an unsupported schema")
    artifact_mode = document["artifact_mode"]
    if artifact_mode not in {"owned", "external"}:
        raise RuntimeError("fixed-machine report artifact mode is invalid")
    if artifact_mode == "owned":
        current_build = _current_build(document["build"], "fixed-machine report.build")
    elif document["build"] is not None:
        raise RuntimeError("external fixed-machine report build must be null")
    else:
        current_build = None
    status = document["status"]
    evidence = document["evidence_level"]
    if status not in {"running", "completed", "failed"}:
        raise RuntimeError("fixed-machine report status is invalid")
    if evidence not in {"exploratory", "controlled"}:
        raise RuntimeError("fixed-machine report evidence level is invalid")
    if artifact_mode == "external" and evidence != "exploratory":
        raise RuntimeError("external fixed-machine artifacts are exploratory only")
    if evidence == "controlled":
        _machine_profile(document["machine_profile"], "fixed-machine report.machine_profile")
    elif document["machine_profile"] is not None:
        raise RuntimeError("exploratory fixed-machine report must not bind a machine profile")
    expected_complete = controlled_complete(
        str(evidence), str(status), owned_build=artifact_mode == "owned"
    )
    if type(document["controlled_complete"]) is not bool or document[
        "controlled_complete"
    ] != expected_complete:
        raise RuntimeError("fixed-machine report controlled completion is inconsistent")
    if document["decision_eligible"] is not False:
        raise RuntimeError("fixed-machine reports cannot claim final decision eligibility")
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
    if current_build is not None:
        expected_flags = " ".join(current_build["compiler_flags"])
        if document["compiler_flags"] != expected_flags:
            raise RuntimeError("fixed-machine compiler_flags differ from the owned build")
        for name, artifact in (
            ("csv2_benchmark", executable),
            ("csv2_benchmark_allocations", allocation),
        ):
            built = current_build["targets"][name]
            if any(
                artifact[field] != built[field]
                for field in ("path", "size", "sha256", "mtime_ns", "revision")
            ):
                raise RuntimeError(f"fixed-machine {name} differs from the owned build")

    if status == "completed":
        _required(
            document,
            {
                "completed_at_utc", "verification", "allocations", "timing",
                "timing_invocation", "comparison_binding",
            },
            "completed fixed-machine report",
        )
        _string(document["completed_at_utc"], "fixed-machine report.completed_at_utc")
        verification = _object(document["verification"], "fixed-machine report.verification")
        _required(verification, {"result", "invocation"}, "fixed-machine report.verification")
        result = _object(verification["result"], "fixed-machine report.verification.result")
        current_fields = {
            "protocol", "revision", "operation", "source", "dataset",
            "semantic_case_id", "scope", "byte_basis", "checksum", "bytes",
            "rows", "cells", "allocations", "allocated_bytes",
        }
        _required(result, current_fields, "fixed-machine report.verification.result")
        if result["protocol"] != CURRENT_PROTOCOL:
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
        _string(
            result["semantic_case_id"],
            "fixed-machine report.verification.result.semantic_case_id",
        )
        _string(result["scope"], "fixed-machine report.verification.result.scope")
        if result["byte_basis"] != "input_corpus":
            raise RuntimeError("fixed-machine verification byte basis is invalid")
        binding = _object(
            document["comparison_binding"],
            "fixed-machine report.comparison_binding",
        )
        binding_fields = {
            "dataset", "semantic_case_id", "scope", "source", "byte_basis"
        }
        _required(binding, binding_fields, "fixed-machine report.comparison_binding")
        _closed(binding, binding_fields, "fixed-machine report.comparison_binding")
        for field in binding_fields:
            if binding[field] != result[field]:
                raise RuntimeError(
                    f"fixed-machine comparison binding differs for {field}"
                )
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
        if artifact_mode != "owned":
            raise RuntimeError("controlled fixed-machine report requires an owned build")
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
        recorded_commands = _artifact(
            identities["compile_commands"], "controlled compile commands", revision=False
        )
        if current_build is not None:
            if compiler_artifact["sha256"] != current_build["compiler"]["artifact"]["sha256"]:
                raise RuntimeError("fixed-machine compiler differs from the owned build")
            if recorded_commands["sha256"] != current_build["compile_commands"]["sha256"]:
                raise RuntimeError("fixed-machine compile commands differ from the owned build")
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


def validate_evidence_bundle(bundle: object) -> None:
    document = _object(bundle, "performance evidence bundle")
    fields = {
        "schema", "status", "evidence_level", "decision_eligible",
        "generated_at_utc", "completed_at_utc", "baseline_revision",
        "candidate_revision", "source_tree", "compiler_sha256", "machine",
        "machine_profile",
        "datasets", "comparison_binding", "components", "checks", "artifacts",
        "finalizer",
    }
    _required(document, fields, "performance evidence bundle")
    _closed(document, fields, "performance evidence bundle")
    if document["schema"] != EVIDENCE_SCHEMA:
        raise RuntimeError("performance evidence bundle has an unsupported schema")
    if document["status"] != "completed":
        raise RuntimeError("performance evidence bundle must be completed")
    evidence = document["evidence_level"]
    if evidence not in {"exploratory", "controlled"}:
        raise RuntimeError("performance evidence bundle evidence level is invalid")
    if type(document["decision_eligible"]) is not bool or document[
        "decision_eligible"
    ] != (evidence == "controlled"):
        raise RuntimeError("performance evidence bundle decision eligibility is inconsistent")
    if evidence == "controlled":
        _machine_profile(
            document["machine_profile"],
            "performance evidence bundle.machine_profile",
        )
    elif document["machine_profile"] is not None:
        raise RuntimeError("exploratory evidence must not bind a machine profile")
    _string(document["generated_at_utc"], "performance evidence bundle.generated_at_utc")
    _string(document["completed_at_utc"], "performance evidence bundle.completed_at_utc")
    for field in ("baseline_revision", "candidate_revision", "source_tree"):
        _hex_digest(document[field], f"performance evidence bundle.{field}", (40, 64))
    _hex_digest(
        document["compiler_sha256"],
        "performance evidence bundle.compiler_sha256",
        (64,),
    )

    machine = _object(document["machine"], "performance evidence bundle.machine")
    machine_fields = {
        "node", "machine", "cpu_model", "logical_cpus", "process_affinity", "python"
    }
    _required(machine, machine_fields, "performance evidence bundle.machine")
    _closed(machine, machine_fields, "performance evidence bundle.machine")
    for field in ("node", "machine", "cpu_model", "python"):
        _string(machine[field], f"performance evidence bundle.machine.{field}")
    _integer(machine["logical_cpus"], "performance evidence bundle.machine.logical_cpus", 1)
    affinity = _array(
        machine["process_affinity"],
        "performance evidence bundle.machine.process_affinity",
    )
    if not affinity:
        raise RuntimeError("performance evidence bundle process affinity must not be empty")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in affinity
    ):
        raise RuntimeError("performance evidence bundle process affinity is invalid")

    datasets = _array(document["datasets"], "performance evidence bundle.datasets")
    if not datasets:
        raise RuntimeError("performance evidence bundle datasets must not be empty")
    names: set[str] = set()
    for index, value in enumerate(datasets):
        label = f"performance evidence bundle.datasets[{index}]"
        dataset = _object(value, label)
        dataset_fields = {"name", "size", "sha256"}
        _required(dataset, dataset_fields, label)
        _closed(dataset, dataset_fields, label)
        name = _string(dataset["name"], f"{label}.name")
        if name in names:
            raise RuntimeError("performance evidence bundle contains duplicate datasets")
        names.add(name)
        _integer(dataset["size"], f"{label}.size", 1)
        _hex_digest(dataset["sha256"], f"{label}.sha256", (64,))

    binding = _object(
        document["comparison_binding"],
        "performance evidence bundle.comparison_binding",
    )
    binding_fields = {
        "dataset", "semantic_case_id", "scope", "source", "byte_basis"
    }
    _required(binding, binding_fields, "performance evidence bundle.comparison_binding")
    _closed(binding, binding_fields, "performance evidence bundle.comparison_binding")
    for field in binding_fields:
        _string(binding[field], f"performance evidence bundle.comparison_binding.{field}")
    if binding["byte_basis"] != "input_corpus":
        raise RuntimeError("performance evidence bundle byte basis is invalid")

    components = _object(
        document["components"], "performance evidence bundle.components"
    )
    component_names = {"calibration", "comparison", "fixed_metrics"}
    _required(components, component_names, "performance evidence bundle.components")
    _closed(components, component_names, "performance evidence bundle.components")
    expected_schemas = {
        "calibration": COMPARISON_SCHEMA,
        "comparison": COMPARISON_SCHEMA,
        "fixed_metrics": METRICS_SCHEMA,
    }
    expected_complete = evidence == "controlled"
    for name, expected_schema in expected_schemas.items():
        label = f"performance evidence bundle.components.{name}"
        component = _object(components[name], label)
        component_fields = {"schema", "revision", "build_digest", "controlled_complete"}
        _required(component, component_fields, label)
        _closed(component, component_fields, label)
        if component["schema"] != expected_schema:
            raise RuntimeError(f"{label}.schema is invalid")
        _hex_digest(component["revision"], f"{label}.revision", (40, 64))
        _hex_digest(component["build_digest"], f"{label}.build_digest", (64,))
        if type(component["controlled_complete"]) is not bool or component[
            "controlled_complete"
        ] != expected_complete:
            raise RuntimeError(f"{label}.controlled_complete is inconsistent")
        if component["revision"] != document["candidate_revision"]:
            raise RuntimeError(f"{label}.revision differs from the candidate")
    if (
        components["calibration"]["build_digest"]
        != components["comparison"]["build_digest"]
    ):
        raise RuntimeError(
            "performance evidence bundle A/A and A/B candidate builds differ"
        )

    check_names = {
        "artifact_manifests", "calibration", "revisions", "source_tree",
        "compiler", "machine", "machine_profile", "datasets", "corpus",
        "semantic_binding",
    }
    checks = _object(document["checks"], "performance evidence bundle.checks")
    _required(checks, check_names, "performance evidence bundle.checks")
    _closed(checks, check_names, "performance evidence bundle.checks")
    if any(checks[name] is not True for name in check_names):
        raise RuntimeError("performance evidence bundle contains an incomplete cross-check")

    artifact_names = {
        "calibration_report", "calibration_manifest", "comparison_report",
        "comparison_manifest", "fixed_metrics_report", "fixed_metrics_manifest",
        "corpus_manifest",
    }
    evidence_artifacts = _object(
        document["artifacts"], "performance evidence bundle.artifacts"
    )
    _required(evidence_artifacts, artifact_names, "performance evidence bundle.artifacts")
    _closed(evidence_artifacts, artifact_names, "performance evidence bundle.artifacts")
    for name in artifact_names:
        _manifest_artifact(
            evidence_artifacts[name],
            f"performance evidence bundle.artifacts.{name}",
            revision=False,
        )
    _source_bundle(document["finalizer"], "performance evidence bundle.finalizer")


def validate_artifact_manifest(manifest: object) -> None:
    from . import ARTIFACT_MANIFEST_SCHEMA

    document = _object(manifest, "artifact manifest")
    fields = {"schema", "kind", "report", "inputs"}
    _required(document, fields, "artifact manifest")
    _closed(document, fields, "artifact manifest")
    if document["schema"] != ARTIFACT_MANIFEST_SCHEMA:
        raise RuntimeError("artifact manifest has an unsupported schema")
    kind = document["kind"]
    if kind not in {"comparison", "fixed-metrics", "evidence-bundle"}:
        raise RuntimeError("artifact manifest kind is invalid")
    _manifest_artifact(document["report"], "artifact manifest.report", revision=False)
    inputs = _object(document["inputs"], "artifact manifest.inputs")
    if kind == "comparison":
        required = {"baseline", "candidate", "datasets", "builds", "machine_profile"}
        _required(inputs, required, "artifact manifest.inputs")
        _closed(inputs, required, "artifact manifest.inputs")
        _manifest_artifact(
            inputs["baseline"], "artifact manifest.inputs.baseline", revision=True
        )
        _manifest_artifact(
            inputs["candidate"], "artifact manifest.inputs.candidate", revision=True
        )
        datasets = _array(inputs["datasets"], "artifact manifest.inputs.datasets")
        if not datasets:
            raise RuntimeError("artifact manifest datasets must not be empty")
        for index, dataset in enumerate(datasets):
            _manifest_artifact(
                dataset,
                f"artifact manifest.inputs.datasets[{index}]",
                revision=False,
            )
        digests = _object(inputs["builds"], "artifact manifest.inputs.builds")
        _required(digests, {"baseline", "candidate"}, "artifact manifest.inputs.builds")
        _closed(digests, {"baseline", "candidate"}, "artifact manifest.inputs.builds")
        for side in ("baseline", "candidate"):
            value = digests[side]
            if value is not None:
                _hex_digest(value, f"artifact manifest.inputs.builds.{side}", (64,))
        if inputs["machine_profile"] is not None:
            _manifest_artifact(
                inputs["machine_profile"],
                "artifact manifest.inputs.machine_profile",
                revision=False,
            )
    elif kind == "fixed-metrics":
        input_fields = {"artifacts", "build", "machine_profile"}
        _required(inputs, input_fields, "artifact manifest.inputs")
        _closed(inputs, input_fields, "artifact manifest.inputs")

        artifacts_document = _object(
            inputs["artifacts"], "artifact manifest.inputs.artifacts"
        )
        required_artifacts = {
            "collector",
            "executable",
            "allocation_executable",
            "dataset",
        }
        optional_artifacts = {"compiler_executable", "compile_commands"}
        _required(
            artifacts_document,
            required_artifacts,
            "artifact manifest.inputs.artifacts",
        )
        _closed(
            artifacts_document,
            required_artifacts | optional_artifacts,
            "artifact manifest.inputs.artifacts",
        )
        _source_bundle(
            artifacts_document["collector"],
            "artifact manifest.inputs.artifacts.collector",
        )
        executable = _manifest_artifact(
            artifacts_document["executable"],
            "artifact manifest.inputs.artifacts.executable",
            revision=True,
        )
        allocation = _manifest_artifact(
            artifacts_document["allocation_executable"],
            "artifact manifest.inputs.artifacts.allocation_executable",
            revision=True,
        )
        _manifest_artifact(
            artifacts_document["dataset"],
            "artifact manifest.inputs.artifacts.dataset",
            revision=False,
        )
        if executable["revision"] != allocation["revision"]:
            raise RuntimeError("artifact manifest executable revisions are inconsistent")

        has_compiler = "compiler_executable" in artifacts_document
        has_commands = "compile_commands" in artifacts_document
        if has_compiler != has_commands:
            raise RuntimeError(
                "artifact manifest compiler artifacts must be present as a pair"
            )
        if has_compiler:
            _manifest_artifact(
                artifacts_document["compiler_executable"],
                "artifact manifest.inputs.artifacts.compiler_executable",
                revision=False,
            )
            _manifest_artifact(
                artifacts_document["compile_commands"],
                "artifact manifest.inputs.artifacts.compile_commands",
                revision=False,
            )

        build = inputs["build"]
        if build is not None:
            _hex_digest(build, "artifact manifest.inputs.build", (64,))
            if not has_compiler:
                raise RuntimeError(
                    "artifact manifest owned build requires compiler artifacts"
                )
        if inputs["machine_profile"] is not None:
            _manifest_artifact(
                inputs["machine_profile"],
                "artifact manifest.inputs.machine_profile",
                revision=False,
            )
    else:
        input_fields = {
            "calibration_report", "calibration_manifest", "comparison_report",
            "comparison_manifest", "fixed_metrics_report", "fixed_metrics_manifest",
            "corpus_manifest", "finalizer",
        }
        _required(inputs, input_fields, "artifact manifest.inputs")
        _closed(inputs, input_fields, "artifact manifest.inputs")
        for name in input_fields - {"finalizer"}:
            _manifest_artifact(
                inputs[name],
                f"artifact manifest.inputs.{name}",
                revision=False,
            )
        _source_bundle(inputs["finalizer"], "artifact manifest.inputs.finalizer")
