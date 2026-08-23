from __future__ import annotations

import json
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
