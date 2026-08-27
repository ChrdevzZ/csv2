from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).with_name("verify_ctest_inventory.py")
SPEC = importlib.util.spec_from_file_location("verify_ctest_inventory", MODULE)
assert SPEC and SPEC.loader
verify_ctest_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_ctest_inventory)


def test_entry(name: str, target: str, labels: list[str]) -> dict[str, object]:
    return {
        "command": [f"/tmp/build/{target}"],
        "name": name,
        "properties": [{"name": "LABELS", "value": labels}],
    }


class VerifyCTestInventoryTests(unittest.TestCase):
    def test_accepts_exact_unique_labeled_inventory(self) -> None:
        names = verify_ctest_inventory.verify_inventory(
            {
                "tests": [
                    test_entry(
                        "csv2.reader.first",
                        "csv2_reader",
                        ["sanitizer-smoke", "reader"],
                    ),
                    test_entry(
                        "csv2.reader.second",
                        "csv2_reader",
                        ["sanitizer-smoke", "reader"],
                    ),
                    test_entry(
                        "csv2.writer",
                        "csv2_writer",
                        ["sanitizer-smoke", "writer"],
                    ),
                ]
            },
            label="sanitizer-smoke",
            expected_targets={"csv2_reader", "csv2_writer"},
            expected_tests={
                "csv2.reader.first": "csv2_reader",
                "csv2.reader.second": "csv2_reader",
                "csv2.writer": "csv2_writer",
            },
        )
        self.assertEqual(
            names,
            ["csv2.reader.first", "csv2.reader.second", "csv2.writer"],
        )

    def test_rejects_missing_manifest_target(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "missing labeled CTest names.*writer"
        ):
            verify_ctest_inventory.verify_inventory(
                {
                    "tests": [
                        test_entry("csv2.reader", "csv2_reader", ["sanitizer-smoke"])
                    ]
                },
                label="sanitizer-smoke",
                expected_targets={"csv2_reader", "csv2_writer"},
                expected_tests={
                    "csv2.reader": "csv2_reader",
                    "csv2.writer": "csv2_writer",
                },
            )

    def test_rejects_target_without_expected_ctest(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "no test for target.*csv2_writer"
        ):
            verify_ctest_inventory.verify_inventory(
                {
                    "tests": [
                        test_entry("csv2.reader", "csv2_reader", ["sanitizer-smoke"])
                    ]
                },
                label="sanitizer-smoke",
                expected_targets={"csv2_reader", "csv2_writer"},
                expected_tests={"csv2.reader": "csv2_reader"},
            )

    def test_rejects_expected_ctest_for_unknown_target(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "references unknown target.*csv2_extra"
        ):
            verify_ctest_inventory.verify_inventory(
                {
                    "tests": [
                        test_entry("csv2.reader", "csv2_reader", ["sanitizer-smoke"])
                    ]
                },
                label="sanitizer-smoke",
                expected_targets={"csv2_reader"},
                expected_tests={
                    "csv2.reader": "csv2_reader",
                    "csv2.extra": "csv2_extra",
                },
            )

    def test_rejects_test_count_drift_within_an_existing_target(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "missing labeled CTest names.*second"
        ):
            verify_ctest_inventory.verify_inventory(
                {
                    "tests": [
                        test_entry(
                            "csv2.reader.first",
                            "csv2_reader",
                            ["sanitizer-smoke"],
                        )
                    ]
                },
                label="sanitizer-smoke",
                expected_targets={"csv2_reader"},
                expected_tests={
                    "csv2.reader.first": "csv2_reader",
                    "csv2.reader.second": "csv2_reader",
                },
            )

    def test_rejects_labeled_target_outside_manifest(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "unexpected labeled CTest names.*extra"
        ):
            verify_ctest_inventory.verify_inventory(
                {
                    "tests": [
                        test_entry("csv2.reader", "csv2_reader", ["sanitizer-smoke"]),
                        test_entry("csv2.extra", "csv2_extra", ["sanitizer-smoke"]),
                    ]
                },
                label="sanitizer-smoke",
                expected_targets={"csv2_reader"},
                expected_tests={"csv2.reader": "csv2_reader"},
            )

    def test_rejects_duplicate_test_names(self) -> None:
        payload = {
            "tests": [
                test_entry("csv2.reader", "csv2_reader", ["sanitizer-smoke"]),
                test_entry("csv2.reader", "csv2_reader", ["sanitizer-smoke"]),
            ]
        }
        with self.assertRaisesRegex(RuntimeError, "duplicate CTest name"):
            verify_ctest_inventory.verify_inventory(
                payload,
                label="sanitizer-smoke",
                expected_targets={"csv2_reader"},
                expected_tests={"csv2.reader": "csv2_reader"},
            )

    def test_rejects_test_without_requested_label(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "does not carry label"):
            verify_ctest_inventory.verify_inventory(
                {
                    "tests": [test_entry("csv2.reader", "csv2_reader", ["runtime"])]
                },
                label="sanitizer-smoke",
                expected_targets={"csv2_reader"},
                expected_tests={"csv2.reader": "csv2_reader"},
            )

    def test_rejects_expected_test_bound_to_wrong_target(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "target mismatch"):
            verify_ctest_inventory.verify_inventory(
                {
                    "tests": [
                        test_entry(
                            "csv2.reader", "csv2_writer", ["sanitizer-smoke"]
                        )
                    ]
                },
                label="sanitizer-smoke",
                expected_targets={"csv2_reader", "csv2_writer"},
                expected_tests={
                    "csv2.reader": "csv2_reader",
                    "csv2.writer": "csv2_writer",
                },
            )


if __name__ == "__main__":
    unittest.main()
