from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import _support


MODULE_PATH = _support.BENCHMARK_DIR / "datasets" / "generate.py"
SPEC = importlib.util.spec_from_file_location("generate_datasets", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class DatasetGeneratorTests(unittest.TestCase):
    @staticmethod
    def write_generated(fixtures: Path, *, omit: str | None = None) -> None:
        for name, (contents, _parameters) in generator.generated_datasets().items():
            if name != omit:
                (fixtures / name).write_bytes(contents)

    def test_manifest_rejects_unregistered_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = Path(directory)
            self.write_generated(fixtures)
            (fixtures / "stale.csv").write_bytes(b"stale\n")

            with self.assertRaisesRegex(
                RuntimeError, "unexpected benchmark datasets: stale.csv"
            ):
                generator.build_manifest(fixtures, scale=1)

    def test_manifest_rejects_missing_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = Path(directory)
            self.write_generated(fixtures, omit="small_startup.csv")

            with self.assertRaisesRegex(
                RuntimeError, "missing benchmark datasets: small_startup.csv"
            ):
                generator.build_manifest(fixtures, scale=1)


if __name__ == "__main__":
    unittest.main()
