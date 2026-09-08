from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
from csv2bench import machine


def profile() -> dict[str, object]:
    return {
        "schema": "csv2-machine-profile-v1",
        "id": "fixed-test-host",
        "system": "Linux",
        "architecture": "x86_64",
        "cpu_model": "Example CPU",
        "logical_cpus": 8,
        "allowed_affinity": [2, 3],
        "kernel_release": "6.8.0",
        "governor": "performance",
        "turbo_boost": "disabled",
    }


def observation() -> dict[str, object]:
    value = profile()
    del value["schema"]
    del value["id"]
    value["process_affinity"] = [2]
    del value["allowed_affinity"]
    return value


class MachineProfileTests(unittest.TestCase):
    def test_profile_binds_bytes_and_matching_runtime_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "machine.json"
            path.write_text(json.dumps(profile()), encoding="utf-8")
            with mock.patch.object(machine, "observe", return_value=observation()):
                binding = machine.load(path)
            machine.verify_binding(binding)
        self.assertEqual(binding["profile"]["id"], "fixed-test-host")
        self.assertEqual(binding["digest"], binding["artifact"]["sha256"])

    def test_runtime_checks_live_state_but_binding_is_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "machine.json"
            path.write_text(json.dumps(profile()), encoding="utf-8")
            with mock.patch.object(machine, "observe", return_value=observation()):
                binding = machine.load(path)
                machine.verify_runtime(binding)
            for field, value in (
                ("governor", "powersave"),
                ("turbo_boost", "enabled"),
                ("process_affinity", [3]),
            ):
                with self.subTest(field=field):
                    changed = observation()
                    changed[field] = value
                    with mock.patch.object(machine, "observe", return_value=changed) as observe:
                        machine.verify_binding(binding)
                        observe.assert_not_called()
                        with self.assertRaisesRegex(RuntimeError, field):
                            machine.verify_runtime(binding)
            with mock.patch.object(machine, "observe") as observe:
                invalid = dict(binding, digest="invalid")
                with self.assertRaisesRegex(RuntimeError, "digest"):
                    machine.verify_runtime(invalid)
                observe.assert_not_called()

    def test_governor_requires_complete_or_unavailable_observation(self) -> None:
        for states, expected in (
            (["performance", "performance"], "performance"),
            (["powersave", "performance"], "mixed:performance,powersave"),
            ([None, None], "unavailable"),
        ):
            with self.subTest(states=states):
                with mock.patch.object(machine, "_read_state", side_effect=states):
                    self.assertEqual(machine.governor([2, 3]), expected)
        with mock.patch.object(machine, "_read_state", side_effect=["performance", None]):
            with self.assertRaisesRegex(RuntimeError, "partial"):
                machine.governor([2, 3])

    def test_affinity_parsing_is_strict_and_canonical(self) -> None:
        self.assertEqual(machine.parse_affinity(" 3, 2,3 , 00 "), [0, 2, 3])
        for value in ("", " ", ",2", "2,", "2,,3", "-1", "+1", "1-3", "١", "1 2"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "CPU affinity"):
                    machine.parse_affinity(value)

    def test_cpu_identity_platform_sources_and_fallback(self) -> None:
        with mock.patch.object(machine.platform, "system", return_value="Linux"):
            with mock.patch.object(Path, "open", mock.mock_open(read_data="model name : Example CPU\n")):
                self.assertEqual(machine.cpu_identity(), ("Example CPU", "/proc/cpuinfo:model name"))
            with mock.patch.object(Path, "open", side_effect=OSError):
                with mock.patch.object(machine.platform, "processor", return_value="fallback CPU"):
                    self.assertEqual(machine.cpu_identity(), ("fallback CPU", "platform.processor"))
        with mock.patch.object(machine.platform, "system", return_value="Darwin"):
            with mock.patch.object(Path, "is_file", return_value=True):
                with mock.patch.object(machine.subprocess, "run", side_effect=[
                    subprocess.CompletedProcess([], 1, ""),
                    subprocess.CompletedProcess([], 0, "Mac model\n"),
                ]):
                    self.assertEqual(machine.cpu_identity(), ("Mac model", "sysctl:hw.model"))
        with mock.patch.object(machine.platform, "system", return_value="Windows"):
            with mock.patch.dict(machine.os.environ, {"PROCESSOR_IDENTIFIER": " Windows CPU "}):
                self.assertEqual(machine.cpu_identity(), ("Windows CPU", "environment:PROCESSOR_IDENTIFIER"))
        with mock.patch.object(machine.platform, "system", return_value="Other"):
            with mock.patch.object(machine.platform, "processor", return_value=""), mock.patch.object(
                machine.platform, "uname", return_value=mock.Mock(processor="")
            ):
                self.assertEqual(machine.cpu_identity(), ("unknown", "unavailable"))

    def test_binding_rejects_embedded_profile_not_backed_by_the_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "machine.json"
            path.write_text(json.dumps(profile()), encoding="utf-8")
            with mock.patch.object(machine, "observe", return_value=observation()):
                binding = machine.load(path)
            changed = json.loads(json.dumps(binding))
            changed["profile"]["governor"] = "powersave"
            changed["observation"]["governor"] = "powersave"
            with self.assertRaisesRegex(RuntimeError, "content differs"):
                machine.verify_binding(changed)

    def test_profile_rejects_runtime_or_affinity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "machine.json"
            path.write_text(json.dumps(profile()), encoding="utf-8")
            changed = observation()
            changed["governor"] = "powersave"
            with mock.patch.object(machine, "observe", return_value=changed):
                with self.assertRaisesRegex(RuntimeError, "governor"):
                    machine.load(path)
            changed = observation()
            changed["process_affinity"] = [4]
            with mock.patch.object(machine, "observe", return_value=changed):
                with self.assertRaisesRegex(RuntimeError, "outside"):
                    machine.load(path)

    def test_profile_is_closed_and_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "machine.json"
            invalid = profile()
            invalid["extra"] = True
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unsupported or incomplete"):
                machine.load(path)
            path.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unique-key"):
                machine.load(path)


if __name__ == "__main__":
    unittest.main()
