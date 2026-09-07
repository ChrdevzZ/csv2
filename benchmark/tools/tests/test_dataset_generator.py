from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import _support


MODULE_PATH = _support.BENCHMARK_DIR / "datasets" / "generate.py"
SPEC = importlib.util.spec_from_file_location("generate_datasets", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class DatasetGeneratorTests(unittest.TestCase):
    @staticmethod
    def write_generated(
        fixtures: Path, *, omit: str | None = None
    ) -> dict[str, dict[str, object]]:
        generated = generator.generated_datasets()
        for name, (contents, _parameters) in generated.items():
            if name != omit:
                (fixtures / name).write_bytes(contents)
        return {name: parameters for name, (_, parameters) in generated.items()}

    def test_manifest_rejects_unregistered_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = Path(directory)
            parameters = self.write_generated(fixtures)
            (fixtures / "stale.csv").write_bytes(b"stale\n")
            with self.assertRaisesRegex(RuntimeError, "unexpected benchmark datasets: stale.csv"):
                generator.build_manifest(fixtures, 1, parameters)

    def test_manifest_rejects_missing_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixtures = Path(directory)
            parameters = self.write_generated(fixtures, omit="small_startup.csv")
            with self.assertRaisesRegex(RuntimeError, "missing benchmark datasets: small_startup.csv"):
                generator.build_manifest(fixtures, 1, parameters)

    def test_generation_once_and_manifest_reads_written_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(generator, "generated_datasets", wraps=generator.generated_datasets) as generate:
                with mock.patch.object(sys, "argv", [str(MODULE_PATH), "--output", str(root / "fixtures")]):
                    self.assertEqual(generator.main(), 0)
                generate.assert_called_once_with(1)
            self.assertEqual((root / "manifest.json").read_bytes(), (MODULE_PATH.parent / "manifest.json").read_bytes())
            parameters = {name: values for name, (_, values) in generator.generated_datasets().items()}
            changed = b"changed,on,disk\n"
            (root / "fixtures" / "small_startup.csv").write_bytes(changed)
            with mock.patch.object(generator, "generated_datasets", side_effect=AssertionError("must not regenerate")):
                manifest = generator.build_manifest(root / "fixtures", 1, parameters)
            record = next(item for item in manifest["datasets"] if item["name"] == "small_startup.csv")
            self.assertEqual(record["sha256"], hashlib.sha256(changed).hexdigest())
            self.assertEqual(record["size"], len(changed))
            self.assertEqual(record["raw_checksum"], str(generator.stable_checksum([changed])))

    def test_generation_rejects_committed_inventory_drift_before_writing(self) -> None:
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixtures = root / "fixtures"
                fixtures.mkdir()
                self.write_generated(fixtures)
                if missing:
                    (fixtures / "small_startup.csv").unlink()
                else:
                    (fixtures / "stale.csv").write_bytes(b"stale\n")
                with mock.patch.object(generator, "__file__", str(root / "generate.py")):
                    with mock.patch.object(sys, "argv", [str(MODULE_PATH), "--output", str(root / "output")]):
                        with self.assertRaisesRegex(RuntimeError, "committed benchmark fixture inventory differs"):
                            generator.main()
                self.assertFalse((root / "output").exists())

    def test_cmake_incremental_corpus(self) -> None:
        cmake = shutil.which("cmake")
        available = [(name, tool) for name, tool in (("Ninja", "ninja"), ("Unix Makefiles", "make")) if shutil.which(tool)]
        if not cmake or not available:
            self.skipTest("CMake and Ninja or Make are required")
        for backend, _tool in available:
            with self.subTest(generator=backend), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, build = root / "source", root / "build"
                shutil.copytree(MODULE_PATH.parent, source / "datasets")
                (source / "CMakeLists.txt").write_text(
                    'cmake_minimum_required(VERSION 3.16)\nproject(corpus NONE)\n'
                    'set(csv2_benchmark_enable_generated_corpus ON)\n'
                    'set(CSV2_PYTHON_AUDITS_AVAILABLE ON)\n'
                    f'set(CSV2_PYTHON_EXECUTABLE "{Path(sys.executable).as_posix()}")\n'
                    'add_subdirectory(datasets)\n', encoding="utf-8")
                def run(*args: str) -> None:
                    result = subprocess.run([cmake, *args], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                def compile_corpus() -> None:
                    run("--build", str(build), "--target", "csv2_benchmark_corpus")
                run("-S", str(source), "-B", str(build), "-G", backend, "-DCSV2_BENCHMARK_CORPUS_SCALE=1")
                compile_corpus()
                corpus = build / "benchmark-corpus"
                outputs = sorted((corpus / "fixtures").glob("*.csv")) + [corpus / "manifest.json"]
                self.assertEqual({path.name for path in outputs[:-1]}, set(generator.generated_datasets()))
                contents = {path: path.read_bytes() for path in outputs}
                identities = {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in outputs}
                compile_corpus()
                self.assertEqual(identities, {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in outputs})
                self.assertEqual(contents, {path: path.read_bytes() for path in outputs})
                fixture = source / "datasets" / "fixtures" / "small_startup.csv"
                fixture_contents = fixture.read_bytes()
                fixture.unlink()
                result = subprocess.run(
                    [cmake, "--build", str(build), "--target", "csv2_benchmark_corpus"],
                    text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("committed benchmark fixture inventory differs", result.stdout + result.stderr)
                self.assertEqual(identities, {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in outputs})
                self.assertEqual(contents, {path: path.read_bytes() for path in outputs})
                fixture.write_bytes(fixture_contents)
                outputs[0].unlink()
                compile_corpus()
                self.assertEqual(contents, {path: path.read_bytes() for path in outputs})
                for path in (outputs[-2], outputs[-1]):
                    path.unlink()
                    compile_corpus()
                    self.assertEqual(path.read_bytes(), contents[path])
                run("-S", str(source), "-B", str(build), "-DCSV2_BENCHMARK_CORPUS_SCALE=2")
                compile_corpus()
                self.assertEqual(json.loads((corpus / "manifest.json").read_text())["scale"], 2)
                contents = {path: path.read_bytes() for path in outputs}
                script = source / "datasets" / "generate.py"
                with script.open("a", encoding="utf-8") as stream:
                    stream.write("\n# Incremental dependency probe.\n")
                # Only the script is newer than outputs; parameters cannot trigger this build.
                stamp = time.time_ns()
                os.utime(build / "datasets" / "corpus-inputs.txt", ns=(stamp - 4_000_000_000,) * 2)
                for path in outputs:
                    os.utime(path, ns=(stamp - 2_000_000_000,) * 2)
                os.utime(script, ns=(stamp,) * 2)
                identities = {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in outputs}
                compile_corpus()
                for path in outputs:
                    self.assertNotEqual(identities[path], (path.stat().st_mtime_ns, path.stat().st_ino))
                self.assertEqual(contents, {path: path.read_bytes() for path in outputs})
                (source / "datasets" / "fixtures" / "stale.csv").write_bytes(b"stale\n")
                result = subprocess.run(
                    [cmake, "--build", str(build), "--target", "csv2_benchmark_corpus"],
                    text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("committed benchmark fixture inventory differs", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
