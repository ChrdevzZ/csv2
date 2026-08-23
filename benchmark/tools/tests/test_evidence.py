from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import test_protocol
from csv2bench import artifacts, evidence, protocol


class EvidenceBundleTests(unittest.TestCase):
    def test_finalizer_bundle_covers_entry_point_and_imported_helpers(self) -> None:
        benchmark_root = Path(evidence.__file__).resolve().parents[2]
        members = {
            path.resolve().relative_to(benchmark_root).as_posix()
            for path in evidence.finalizer_source_paths()
        }
        self.assertEqual(
            members,
            {
                "finalize_evidence.py",
                "tools/csv2bench/__init__.py",
                "tools/csv2bench/artifacts.py",
                "tools/csv2bench/atomic.py",
                "tools/csv2bench/builds.py",
                "tools/csv2bench/derivation.py",
                "tools/csv2bench/evidence.py",
                "tools/csv2bench/protocol.py",
            },
        )

    def components(self, root: Path):
        fixture_root = root / "fixtures"
        fixture_root.mkdir()
        dataset_path = fixture_root / "input.csv"
        dataset_path.write_bytes(b"x")
        dataset_hash = hashlib.sha256(b"x").hexdigest()
        corpus = {
            "schema": "csv2-benchmark-corpus-v2",
            "generator_version": 2,
            "prng": {"algorithm": "lcg32", "seed": 1},
            "scale": 1,
            "datasets": [
                {
                    "name": "input.csv",
                    "path": "fixtures/input.csv",
                    "parameters": {"kind": "test"},
                    "size": 1,
                    "sha256": dataset_hash,
                    "rows": 1,
                    "cells": 1,
                    "raw_checksum": "1",
                    "content_checksum": "1",
                    "strict_valid": True,
                }
            ],
        }
        corpus_path = root / "manifest.json"
        corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
        corpus_identity = artifacts.metadata(corpus_path)

        calibration = test_protocol.controlled_comparison_report()
        comparison = copy.deepcopy(calibration)
        runner_source = root / "runner.py"
        runner_source.write_text("# test runner\n", encoding="utf-8")
        runner_bundle = artifacts.bundle_metadata(
            root, [runner_source], "runner-tool-bundle"
        )
        calibration["runner"] = copy.deepcopy(runner_bundle)
        comparison["runner"] = copy.deepcopy(runner_bundle)
        comparison["mode"] = "compare"
        comparison["datasets"][0].update(
            path=str(dataset_path.resolve()), size=1, sha256=dataset_hash
        )
        calibration["datasets"] = copy.deepcopy(comparison["datasets"])

        calibration_file = root / "aa.json"
        calibration_file.write_text("{}", encoding="utf-8")
        calibration_identity = artifacts.metadata(calibration_file)
        comparison["calibration"] = {
            "path": calibration_identity["path"],
            "size": calibration_identity["size"],
            "sha256": calibration_identity["sha256"],
            "schema": calibration["schema"],
        }

        fixed = test_protocol.controlled_metrics_report()
        fixed["artifacts"]["dataset"] = artifacts.metadata(dataset_path)
        fixed["build"]["corpus_manifest"] = corpus_identity
        fixed["build"]["identity_digest"] = test_protocol.builds.current_build_identity_digest(
            fixed["build"]
        )
        unsigned_build = dict(fixed["build"])
        unsigned_build.pop("digest")
        fixed["build"]["digest"] = test_protocol.builds.document_digest(unsigned_build)

        identities = {
            "calibration_report": calibration_identity,
            "calibration_manifest": test_protocol.artifact(),
            "comparison_report": test_protocol.artifact(),
            "comparison_manifest": test_protocol.artifact(),
            "fixed_metrics_report": test_protocol.artifact(),
            "fixed_metrics_manifest": test_protocol.artifact(),
            "corpus_manifest": corpus_identity,
        }
        return calibration, comparison, fixed, corpus, corpus_path, identities

    def assemble(self, root: Path):
        values = self.components(root)
        with mock.patch.object(evidence.builds, "validate_build_manifest"), mock.patch.object(
            evidence.builds, "verify_current_build_manifest"
        ):
            bundle = evidence.assemble_evidence(
                *values[:4], values[4], values[5], test_protocol.bundle()
            )
        return bundle, values

    def persisted_inputs(self, root: Path) -> dict[str, Path]:
        calibration, comparison, fixed, _corpus, corpus_path, _identities = (
            self.components(root)
        )
        calibration_path = root / "aa.json"
        calibration_path.write_text(json.dumps(calibration), encoding="utf-8")
        calibration_identity = artifacts.metadata(calibration_path)
        comparison["calibration"] = {
            key: calibration_identity[key] for key in ("path", "size", "sha256")
        }
        comparison["calibration"]["schema"] = calibration["schema"]

        comparison_path = root / "ab.json"
        fixed_path = root / "fixed.json"
        comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
        fixed_path.write_text(json.dumps(fixed), encoding="utf-8")
        paths = {
            "calibration_path": calibration_path,
            "comparison_path": comparison_path,
            "fixed_metrics_path": fixed_path,
            "corpus_manifest_path": corpus_path,
        }
        for name in ("calibration", "comparison", "fixed_metrics"):
            manifest_path = root / f"{name}.manifest.json"
            manifest_path.write_text('{"inputs": {}}', encoding="utf-8")
            paths[f"{name}_manifest_path"] = manifest_path
        return paths

    def finalize_with_isolated_manifest_checks(
        self, paths: dict[str, Path], output: Path, output_manifest: Path
    ):
        with mock.patch.object(
            evidence, "_verify_comparison_manifest"
        ), mock.patch.object(evidence, "_verify_fixed_manifest"), mock.patch.object(
            evidence.builds, "validate_build_manifest"
        ), mock.patch.object(evidence.builds, "verify_current_build_manifest"):
            return evidence.finalize(
                **paths,
                output=output,
                output_manifest=output_manifest,
            )

    def test_controlled_components_only_become_decision_eligible_as_a_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle, values = self.assemble(Path(directory))
        self.assertTrue(bundle["decision_eligible"])
        self.assertTrue(all(bundle["checks"].values()))
        self.assertTrue(
            all(
                component["controlled_complete"]
                for component in bundle["components"].values()
            )
        )
        for report in values[:3]:
            self.assertFalse(report["decision_eligible"])
        protocol.validate_evidence_bundle(bundle)

    def test_exploratory_bundle_is_never_decision_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = self.components(Path(directory))
            for report in values[:3]:
                report["evidence_level"] = "exploratory"
                report["controlled_complete"] = False
            with mock.patch.object(evidence.builds, "validate_build_manifest"), mock.patch.object(
                evidence.builds, "verify_current_build_manifest"
            ):
                bundle = evidence.assemble_evidence(
                    *values[:4], values[4], values[5], test_protocol.bundle()
                )
        self.assertFalse(bundle["decision_eligible"])

    def test_finalizer_rejects_calibration_noise_not_derived_from_aa_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = self.components(Path(directory))
            values[1]["cases"][0]["calibration_noise"] = 0.01
            with mock.patch.object(
                evidence.builds, "validate_build_manifest"
            ), mock.patch.object(evidence.builds, "verify_current_build_manifest"):
                with self.assertRaisesRegex(RuntimeError, "calibration noise"):
                    evidence.assemble_evidence(
                        *values[:4], values[4], values[5], test_protocol.bundle()
                    )

    def test_adapter_identity_ignores_workspace_path_and_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = self.components(Path(directory))
            adapter = values[1]["adapter_source"]
            adapter["path"] = str(Path(directory) / "other-workspace" / "adapter.cpp")
            adapter["mtime_ns"] += 1
            with mock.patch.object(
                evidence.builds, "validate_build_manifest"
            ), mock.patch.object(evidence.builds, "verify_current_build_manifest"):
                bundle = evidence.assemble_evidence(
                    *values[:4], values[4], values[5], test_protocol.bundle()
                )

        self.assertTrue(bundle["decision_eligible"])

    def test_finalizer_atomically_publishes_bundle_and_bound_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.persisted_inputs(root)
            output = root / "evidence.json"
            output_manifest = root / "evidence.manifest.json"
            bundle = self.finalize_with_isolated_manifest_checks(
                paths, output, output_manifest
            )
            published = json.loads(output.read_text(encoding="utf-8"))
            manifest = json.loads(output_manifest.read_text(encoding="utf-8"))
            output_identity = artifacts.metadata(output)

        self.assertEqual(published, bundle)
        self.assertTrue(bundle["decision_eligible"])
        self.assertEqual(manifest["kind"], "evidence-bundle")
        self.assertEqual(manifest["report"], output_identity)
        protocol.validate_artifact_manifest(manifest)

    def test_finalizer_never_publishes_bundle_before_its_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.persisted_inputs(root)
            output = root / "evidence.json"
            output_manifest = root / "evidence.manifest.json"
            real_publish = evidence.atomic.publish_staged

            def fail_final_publication(temporary: Path, destination: Path) -> None:
                if destination == output.resolve(strict=False):
                    raise OSError("simulated final publication failure")
                real_publish(temporary, destination)

            with mock.patch.object(
                evidence.atomic,
                "publish_staged",
                side_effect=fail_final_publication,
            ):
                with self.assertRaisesRegex(OSError, "final publication failure"):
                    self.finalize_with_isolated_manifest_checks(
                        paths, output, output_manifest
                    )

            self.assertFalse(output.exists())
            self.assertTrue(output_manifest.is_file())
            manifest = json.loads(output_manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "evidence-bundle")
            self.assertEqual(manifest["report"]["path"], str(output.resolve()))

    def test_finalizer_rejects_output_aliasing_an_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.persisted_inputs(root)
            calibration = paths["calibration_path"]
            original = calibration.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "output path aliases"):
                self.finalize_with_isolated_manifest_checks(
                    paths, calibration, root / "evidence.manifest.json"
                )
            self.assertEqual(calibration.read_bytes(), original)

    def test_finalizer_rejects_preexisting_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.persisted_inputs(root)
            output = root / "evidence.json"
            output.write_text("old evidence", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "output already exists"):
                self.finalize_with_isolated_manifest_checks(
                    paths, output, root / "evidence.manifest.json"
                )
            self.assertEqual(output.read_text(encoding="utf-8"), "old evidence")

    def test_finalizer_rejects_output_aliasing_an_unselected_corpus_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.persisted_inputs(root)
            corpus_path = paths["corpus_manifest_path"]
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
            extra = corpus_path.parent / "fixtures" / "unselected.csv"
            extra.write_bytes(b"unselected")
            corpus["datasets"].append(
                {
                    "name": extra.name,
                    "path": f"fixtures/{extra.name}",
                    "parameters": {"kind": "test"},
                    "size": extra.stat().st_size,
                    "sha256": artifacts.sha256_file(extra),
                    "rows": 1,
                    "cells": 1,
                    "raw_checksum": "1",
                    "content_checksum": "1",
                    "strict_valid": True,
                }
            )
            corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

            fixed_path = paths["fixed_metrics_path"]
            fixed = json.loads(fixed_path.read_text(encoding="utf-8"))
            fixed["build"]["corpus_manifest"] = artifacts.metadata(corpus_path)
            fixed["build"]["identity_digest"] = (
                test_protocol.builds.current_build_identity_digest(fixed["build"])
            )
            unsigned_build = dict(fixed["build"])
            unsigned_build.pop("digest")
            fixed["build"]["digest"] = test_protocol.builds.document_digest(
                unsigned_build
            )
            fixed_path.write_text(json.dumps(fixed), encoding="utf-8")

            original = extra.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "output path aliases"):
                self.finalize_with_isolated_manifest_checks(
                    paths, extra, root / "evidence.manifest.json"
                )
            self.assertEqual(extra.read_bytes(), original)

    def test_cross_document_revision_machine_and_corpus_mismatches_fail(self) -> None:
        mutations = {
            "revision": lambda values: values[2]["build"].update(revision="e" * 40),
            "A/A build": lambda values: values[0]["baseline"]["build"].update(
                identity_digest="0" * 64
            ),
            "machine": lambda values: values[2]["machine"].update(process_affinity=[1]),
            "corpus": lambda values: values[3]["datasets"][0].update(sha256="0" * 64),
            "dataset membership": lambda values: values[1]["datasets"][0].update(
                name="other.csv"
            ),
            "calibration": lambda values: values[1]["calibration"].update(
                sha256="0" * 64
            ),
            "adapter hash": lambda values: values[1]["adapter_source"].update(
                sha256="0" * 64
            ),
            "adapter revision": lambda values: values[1]["adapter_source"].update(
                revision="0" * 40
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                values = self.components(Path(directory))
                mutate(values)
                with mock.patch.object(
                    evidence.builds, "validate_build_manifest"
                ), mock.patch.object(evidence.builds, "verify_current_build_manifest"):
                    with self.assertRaises(RuntimeError):
                        evidence.assemble_evidence(
                            *values[:4], values[4], values[5], test_protocol.bundle()
                        )

    def test_runner_bundle_drift_fails_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = self.components(Path(directory))
            runner = values[0]["runner"]
            runner_path = Path(str(runner["root"])) / str(runner["files"][0]["path"])
            runner_path.write_text("# changed runner\n", encoding="utf-8")
            with mock.patch.object(
                evidence.builds, "validate_build_manifest"
            ), mock.patch.object(evidence.builds, "verify_current_build_manifest"):
                with self.assertRaisesRegex(RuntimeError, "source bundle"):
                    evidence.assemble_evidence(
                        *values[:4], values[4], values[5], test_protocol.bundle()
                    )

    def test_manifest_identity_walk_includes_nested_datasets_and_sources(self) -> None:
        source = test_protocol.bundle()
        export = test_protocol.controlled_comparison_report()["baseline"]["build"][
            "header_export"
        ]
        identities = {
            "datasets": [test_protocol.artifact()],
            "tools": {"runner": source},
            "headers": export,
            "builds": {"baseline": "a" * 64},
        }
        paths = list(evidence._identity_paths(identities, "inputs"))
        self.assertIn(("inputs.datasets[0]", Path("/artifact")), paths)
        self.assertIn(
            ("inputs.tools.runner source", Path("/source") / "artifact"), paths
        )
        self.assertIn(
            (
                "inputs.headers Git export",
                Path(str(export["root"])).resolve(strict=False)
                / "include/csv2/reader.hpp",
            ),
            paths,
        )

    def test_load_document_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema": 1, "schema": 2}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unique-key"):
                evidence.load_document(path, "duplicate report")


if __name__ == "__main__":
    unittest.main()
