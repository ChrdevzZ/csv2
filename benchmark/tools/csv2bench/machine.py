"""Verified fixed-machine profiles for controlled benchmark evidence."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from collections.abc import Mapping
from pathlib import Path

from . import artifacts


MACHINE_PROFILE_SCHEMA = "csv2-machine-profile-v1"


def reject_runtime_injection(environment: Mapping[str, str]) -> None:
    """Reject caller-supplied libraries; filtering children cannot clean this process."""
    active = sorted(
        name for name, value in environment.items()
        if name.upper() in {"LD_PRELOAD", "LD_AUDIT"} and value
    )
    if active:
        raise RuntimeError(
            "controlled measurement rejects runtime injection: " + ", ".join(active)
            + "; restart collection from a clean environment"
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate machine-profile key: {key}")
        result[key] = value
    return result


def parse_affinity(value: str) -> list[int]:
    """Parse an explicit CPU list without silently discarding malformed entries."""
    tokens = [token.strip() for token in value.split(",")]
    if any(not token or not token.isascii() or not token.isdecimal() for token in tokens):
        raise RuntimeError("CPU affinity must be a comma-separated list of nonnegative integers")
    try:
        return sorted({int(token) for token in tokens})
    except ValueError as error:
        raise RuntimeError("CPU affinity contains an invalid integer") from error


def cpu_identity() -> tuple[str, str]:
    if platform.system() == "Linux":
        try:
            with Path("/proc/cpuinfo").open(
                "r", encoding="utf-8", errors="replace"
            ) as cpuinfo:
                for line in cpuinfo:
                    name, separator, value = line.partition(":")
                    if (
                        separator
                        and name.strip() in {"model name", "Hardware", "Processor"}
                        and value.strip()
                    ):
                        return value.strip(), f"/proc/cpuinfo:{name.strip()}"
        except OSError:
            pass
    elif platform.system() == "Darwin":
        sysctl = Path("/usr/sbin/sysctl")
        if sysctl.is_file():
            for name in ("machdep.cpu.brand_string", "hw.model"):
                try:
                    completed = subprocess.run(
                        [str(sysctl), "-n", name],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    continue
                value = completed.stdout.strip()
                if completed.returncode == 0 and value:
                    return value, f"sysctl:{name}"
    elif platform.system() == "Windows":
        value = os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
        if value:
            return value, "environment:PROCESSOR_IDENTIFIER"

    for source, value in (
        ("platform.processor", platform.processor()),
        ("platform.uname.processor", platform.uname().processor),
    ):
        if value.strip():
            return value.strip(), source
    return "unknown", "unavailable"


def _read_state(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="ascii").strip()
    except OSError:
        return None
    return value or None


def governor(affinity: list[int]) -> str:
    states = [
        _read_state(Path(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"))
        for cpu in affinity
    ]
    values = {state for state in states if state is not None}
    if not values:
        return "unavailable"
    if None in states:
        raise RuntimeError("CPU governor observation is partially unavailable")
    if len(values) == 1:
        return next(iter(values))
    return "mixed:" + ",".join(
        f"{cpu}={state}" for cpu, state in sorted(zip(affinity, states))
    )


def turbo_boost() -> str:
    no_turbo = _read_state(Path("/sys/devices/system/cpu/intel_pstate/no_turbo"))
    if no_turbo in {"0", "1"}:
        return "enabled" if no_turbo == "0" else "disabled"
    boost = _read_state(Path("/sys/devices/system/cpu/cpufreq/boost"))
    if boost in {"0", "1"}:
        return "enabled" if boost == "1" else "disabled"
    return "unavailable"


def observe() -> dict[str, object]:
    if not hasattr(os, "sched_getaffinity"):
        raise RuntimeError("controlled machine observation requires sched_getaffinity")
    affinity = sorted(os.sched_getaffinity(0))
    if not affinity:
        raise RuntimeError("controlled machine observation found empty CPU affinity")
    return {
        "system": platform.system(),
        "architecture": platform.machine(),
        "cpu_model": cpu_identity()[0],
        "logical_cpus": os.cpu_count() or 1,
        "process_affinity": affinity,
        "kernel_release": platform.release(),
        "governor": governor(affinity),
        "turbo_boost": turbo_boost(),
    }


def _validate_profile(document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        raise RuntimeError("machine profile must contain a JSON object")
    fields = {
        "schema",
        "id",
        "system",
        "architecture",
        "cpu_model",
        "logical_cpus",
        "allowed_affinity",
        "kernel_release",
        "governor",
        "turbo_boost",
    }
    if set(document) != fields or document.get("schema") != MACHINE_PROFILE_SCHEMA:
        raise RuntimeError("machine profile has an unsupported or incomplete schema")
    for field in fields - {"logical_cpus", "allowed_affinity"}:
        if not isinstance(document[field], str) or not document[field]:
            raise RuntimeError(f"machine profile {field} must be a non-empty string")
    logical_cpus = document["logical_cpus"]
    if isinstance(logical_cpus, bool) or not isinstance(logical_cpus, int) or logical_cpus < 1:
        raise RuntimeError("machine profile logical_cpus must be positive")
    allowed = document["allowed_affinity"]
    if (
        not isinstance(allowed, list)
        or not allowed
        or any(isinstance(cpu, bool) or not isinstance(cpu, int) or cpu < 0 for cpu in allowed)
        or allowed != sorted(set(allowed))
    ):
        raise RuntimeError("machine profile allowed_affinity is invalid")
    if document["system"] != "Linux":
        raise RuntimeError("controlled machine profiles currently require Linux")
    if document["turbo_boost"] not in {"enabled", "disabled", "unavailable"}:
        raise RuntimeError("machine profile turbo_boost is invalid")
    return document


def _read_profile(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    canonical = artifacts.canonical_existing(path, "machine profile")
    if not canonical.is_file():
        raise RuntimeError("machine profile is not a regular file")
    before = artifacts.metadata(canonical)
    try:
        document = json.loads(
            canonical.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError("machine profile is not valid unique-key UTF-8 JSON") from error
    profile = _validate_profile(document)
    after = artifacts.metadata(canonical)
    if before != after:
        raise RuntimeError("machine profile changed while it was read")
    return profile, before


def load(path: Path) -> dict[str, object]:
    reject_runtime_injection(os.environ)
    profile, artifact = _read_profile(path)
    observation = observe()
    for field in (
        "system",
        "architecture",
        "cpu_model",
        "logical_cpus",
        "kernel_release",
        "governor",
        "turbo_boost",
    ):
        if profile[field] != observation[field]:
            raise RuntimeError(f"machine profile differs from runtime observation: {field}")
    affinity = observation["process_affinity"]
    if not set(affinity) <= set(profile["allowed_affinity"]):
        raise RuntimeError("runtime CPU affinity is outside the machine profile")
    return {
        "artifact": artifact,
        "profile": profile,
        "digest": artifact["sha256"],
        "observation": observation,
    }


def verify_binding(binding: object, label: str = "machine profile") -> None:
    if not isinstance(binding, dict):
        raise RuntimeError(f"{label} binding must be an object")
    artifact = binding.get("artifact")
    if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
        raise RuntimeError(f"{label} binding lacks its source artifact")
    profile, actual_artifact = _read_profile(Path(artifact["path"]))
    if actual_artifact != artifact:
        raise RuntimeError(f"{label} artifact differs from its recorded identity")
    if binding.get("digest") != actual_artifact["sha256"]:
        raise RuntimeError(f"{label} digest differs from its source artifact")
    if binding.get("profile") != profile:
        raise RuntimeError(f"{label} content differs from its source artifact")


def verify_runtime(binding: object, label: str = "machine profile") -> None:
    """Verify recorded profile bytes and the live state at a measurement boundary."""
    reject_runtime_injection(os.environ)
    verify_binding(binding, label)
    if not isinstance(binding, dict):
        raise RuntimeError(f"{label} binding must be an object")
    expected = binding.get("observation")
    if not isinstance(expected, dict):
        raise RuntimeError(f"{label} lacks a runtime observation")
    actual = observe()
    changed = sorted(
        field
        for field in expected.keys() | actual.keys()
        if expected.get(field) != actual.get(field)
    )
    if changed:
        raise RuntimeError(f"{label} runtime state changed: {', '.join(changed)}")
