from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import check_legacy_case_map as checker


class LegacyParityTests(unittest.TestCase):
    def test_inventory_and_mapping_match_without_git_history(self) -> None:
        mappings, stable_cases, git_verified = checker.verify(check_git=False)

        self.assertEqual(mappings, checker.EXPECTED_TITLE_COUNT)
        self.assertGreaterEqual(stable_cases, mappings)
        self.assertFalse(git_verified)

    def test_missing_git_objects_fall_back_to_pinned_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mappings, stable_cases, git_verified = checker.verify(
                repository=Path(directory)
            )

        self.assertEqual(mappings, checker.EXPECTED_TITLE_COUNT)
        self.assertGreaterEqual(stable_cases, mappings)
        self.assertFalse(git_verified)

    def test_unique_replacement_legacy_title_is_rejected(self) -> None:
        mapping = checker.MAPPING.read_text(encoding="utf-8")
        original = "Read a file, its header, rows, columns, and cells"
        replacement = "Invented unique title that never existed in the base suite"
        mutated = mapping.replace(original, replacement, 1)
        self.assertNotEqual(mutated, mapping)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / checker.MAPPING.name
            path.write_text(mutated, encoding="utf-8", newline="")
            with self.assertRaisesRegex(ValueError, "legacy title inventory mismatch"):
                checker.verify(mapping=path, check_git=False)

    def test_pinned_blob_provenance_when_git_object_is_available(self) -> None:
        inventory_titles = checker.load_inventory()
        if checker.git_object_type(
            checker.REPOSITORY, checker.EXPECTED_BASE["blob"]
        ) is None:
            self.skipTest("pinned base blob is unavailable in this checkout")

        self.assertTrue(checker.verify_git_provenance(inventory_titles))


if __name__ == "__main__":
    unittest.main()
