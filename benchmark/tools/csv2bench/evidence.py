"""Finalize comparison and fixed-machine reports into one decision gate."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import ARTIFACT_MANIFEST_SCHEMA, EVIDENCE_SCHEMA
from . import artifacts, atomic, builds, machine as machine_profile_tool, protocol


Document = dict[str, object]


def _unique_object(pairs: list[tuple[str, object]]) -> Document:
    result: Document = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_document(path: Path, label: str) -> tuple[Document, Path, Document]:
    canonical = artifacts.canonical_existing(path, label)
    if not canonical.is_file():
        raise RuntimeError(f"{label} is not a regular file: {canonical}")
    before = artifacts.metadata(canonical)
    try:
        contents = canonical.read_bytes()
        document = json.loads(
            contents.decode("utf-8"), object_pairs_hook=_unique_object
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"{label} is not valid unique-key UTF-8 JSON") from error
    after = artifacts.metadata(canonical)
    if before != after:
        raise RuntimeError(f"{label} changed while it was read")
    if not isinstance(document, dict):
        raise RuntimeError(f"{label} must contain a JSON object")
    return document, canonical, before


def finalizer_source_paths() -> list[Path]:
    benchmark_root = Path(__file__).resolve().parents[2]
    package_root = Path(__file__).resolve().parent
    return artifacts.python_source_paths(
        benchmark_root / "finalize_evidence.py", package_root
    )


def _verify_artifact(record: Document, label: str) -> None:
    artifacts.verify_unchanged(record, label)


def _identity_paths(value: object, label: str):
    """Yield every filesystem object embedded in a manifest input."""
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _identity_paths(item, f"{label}[{index}]")
        return
    if not isinstance(value, dict):
        return
    if value.get("kind") == "source-bundle":
        root = Path(str(value["root"]))
        for member in value["files"]:
            yield f"{label} source", root / str(member["path"])
        return
    if value.get("schema") == "csv2-git-export-v1":
        root = Path(str(value["root"])).resolve(strict=False)
        for member in value["files"]:
            relative = builds.safe_git_path(str(member["path"]))
            target = root.joinpath(*relative.parts).resolve(strict=False)
            try:
                common = Path(os.path.commonpath((str(root), str(target))))
            except ValueError as error:
                raise RuntimeError(f"{label} Git export path escapes its root") from error
            if os.path.normcase(str(common)) != os.path.normcase(str(root)):
                raise RuntimeError(f"{label} Git export path escapes its root")
            yield f"{label} Git export", target
        return
    if "path" in value and {"size", "sha256"}.issubset(value):
        yield label, Path(str(value["path"]))
        return
    for name, item in value.items():
        yield from _identity_paths(item, f"{label}.{name}")


def _verify_report_identity(
    manifest: Document, report_identity: Document, label: str
) -> None:
    if manifest["report"] != report_identity:
        raise RuntimeError(f"{label} does not bind the supplied report")
    _verify_artifact(manifest["report"], f"{label} report")


def _verify_comparison_manifest(
    report: Document, manifest: Document, report_identity: Document, label: str
) -> None:
    protocol.validate_artifact_manifest(manifest)
    if manifest["kind"] != "comparison":
        raise RuntimeError(f"{label} has the wrong artifact-manifest kind")
    _verify_report_identity(manifest, report_identity, label)
    inputs = manifest["inputs"]
    for side in ("baseline", "candidate"):
        recorded = inputs[side]
        if recorded != report[side]["artifact"]:
            raise RuntimeError(f"{label} {side} artifact differs from the report")
        _verify_artifact(recorded, f"{label} {side} artifact")
        build = report[side]["build"]
        expected_digest = build["digest"] if isinstance(build, dict) else None
        if inputs["builds"][side] != expected_digest:
            raise RuntimeError(f"{label} {side} build digest differs from the report")

    manifest_datasets = {str(item["path"]): item for item in inputs["datasets"]}
    if len(manifest_datasets) != len(inputs["datasets"]):
        raise RuntimeError(f"{label} contains duplicate dataset artifacts")
    if len(manifest_datasets) != len(report["datasets"]):
        raise RuntimeError(f"{label} dataset count differs from the report")
    for dataset in report["datasets"]:
        recorded = manifest_datasets.get(str(dataset["path"]))
        if recorded is None or any(
            recorded[field] != dataset[field] for field in ("path", "size", "sha256")
        ):
            raise RuntimeError(f"{label} dataset artifacts differ from the report")
        _verify_artifact(recorded, f"{label} dataset {dataset['name']}")
    expected_profile = report["machine_profile"]
    expected_artifact = (
        expected_profile["artifact"] if isinstance(expected_profile, dict) else None
    )
    if inputs["machine_profile"] != expected_artifact:
        raise RuntimeError(f"{label} machine profile differs from the report")
    if expected_artifact is not None:
        _verify_artifact(expected_artifact, f"{label} machine profile")


def _verify_fixed_manifest(
    report: Document, manifest: Document, report_identity: Document
) -> None:
    label = "fixed-metrics artifact manifest"
    protocol.validate_artifact_manifest(manifest)
    if manifest["kind"] != "fixed-metrics":
        raise RuntimeError(f"{label} has the wrong kind")
    _verify_report_identity(manifest, report_identity, label)
    inputs = manifest["inputs"]
    if inputs["artifacts"] != report["artifacts"]:
        raise RuntimeError("fixed-metrics manifest artifacts differ from the report")
    expected_build = report["build"]["identity_digest"]
    if inputs["build"] != expected_build:
        raise RuntimeError("fixed-metrics manifest build differs from the report")
    expected_profile = report["machine_profile"]
    expected_artifact = (
        expected_profile["artifact"] if isinstance(expected_profile, dict) else None
    )
    if inputs["machine_profile"] != expected_artifact:
        raise RuntimeError("fixed-metrics manifest machine profile differs from the report")
    if expected_artifact is not None:
        _verify_artifact(expected_artifact, "fixed-metrics machine profile")
    for name, identity in inputs["artifacts"].items():
        _verify_artifact(identity, f"fixed-metrics {name}")


def _safe_corpus_member(root: Path, encoded: object) -> Path:
    if not isinstance(encoded, str) or not encoded or "\\" in encoded:
        raise RuntimeError("corpus dataset path is invalid")
    relative = PurePosixPath(encoded)
    if (
        relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
        or (relative.parts and ":" in relative.parts[0])
    ):
        raise RuntimeError(f"corpus dataset path is unsafe: {encoded}")
    target = root.joinpath(*relative.parts).resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as error:
        raise RuntimeError(f"corpus dataset escapes its root: {encoded}") from error
    if not target.is_file():
        raise RuntimeError(f"corpus dataset is not a regular file: {target}")
    return target


def _corpus_index(
    document: Document,
    manifest_path: Path,
    *,
    verify_contents: bool = True,
) -> dict[str, Document]:
    required = {"schema", "generator_version", "prng", "scale", "datasets"}
    if set(document) != required or document.get("schema") != "csv2-benchmark-corpus-v2":
        raise RuntimeError("corpus manifest has an unsupported or incomplete schema")
    datasets = document["datasets"]
    if not isinstance(datasets, list) or not datasets:
        raise RuntimeError("corpus manifest contains no datasets")
    root = manifest_path.parent.resolve(strict=True)
    result: dict[str, Document] = {}
    required_dataset = {
        "name", "path", "parameters", "size", "sha256", "rows", "cells",
        "raw_checksum", "content_checksum", "strict_valid", "strict_error",
    }
    error_codes = {
        "none",
        "unexpected_quote",
        "unclosed_quote",
        "invalid_doubled_quote",
        "characters_after_closing_quote",
        "bare_carriage_return",
    }
    for value in datasets:
        if not isinstance(value, dict) or set(value) != required_dataset:
            raise RuntimeError("corpus manifest contains an incomplete dataset")
        name = value["name"]
        if not isinstance(name, str) or not name or name in result:
            raise RuntimeError("corpus manifest contains an invalid or duplicate dataset name")
        size = value["size"]
        digest = value["sha256"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise RuntimeError(f"corpus dataset {name} has an invalid size")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RuntimeError(f"corpus dataset {name} has an invalid SHA-256")
        path = _safe_corpus_member(root, value["path"])
        if path.name != name:
            raise RuntimeError(f"corpus dataset path/name mismatch for {name}")
        if path.stat().st_size != size or (
            verify_contents and artifacts.sha256_file(path) != digest
        ):
            raise RuntimeError(f"corpus dataset {name} differs from its manifest")
        strict_valid = value["strict_valid"]
        if type(strict_valid) is not bool:
            raise RuntimeError(f"corpus dataset {name} has an invalid strict-valid flag")
        strict_error = value["strict_error"]
        error_fields = {"code", "byte_offset", "row", "column"}
        if not isinstance(strict_error, dict) or set(strict_error) != error_fields:
            raise RuntimeError(f"corpus dataset {name} has an invalid strict diagnostic")
        code = strict_error["code"]
        locations = tuple(strict_error[field] for field in ("byte_offset", "row", "column"))
        if code not in error_codes or any(
            isinstance(location, bool) or not isinstance(location, int) or location < 0
            for location in locations
        ):
            raise RuntimeError(f"corpus dataset {name} has an invalid strict diagnostic")
        if strict_valid:
            if code != "none" or locations != (0, 0, 0) or value["content_checksum"] is None:
                raise RuntimeError(f"corpus dataset {name} has inconsistent valid diagnostics")
        elif (
            code == "none"
            or locations[0] >= size
            or locations[1] == 0
            or locations[2] == 0
            or value["content_checksum"] is not None
        ):
            raise RuntimeError(f"corpus dataset {name} has inconsistent invalid diagnostics")
        result[name] = value
    return result


def _dataset_index(report: Document, label: str) -> dict[str, Document]:
    result: dict[str, Document] = {}
    for value in report["datasets"]:
        name = str(value["name"])
        if name in result:
            raise RuntimeError(f"{label} contains duplicate datasets")
        result[name] = value
    return result


def _machine_identity(host: Document, machine: Document) -> Document:
    fields = ("node", "machine", "cpu_model", "logical_cpus", "process_affinity", "python")
    for field in fields:
        if host.get(field) != machine.get(field):
            raise RuntimeError(f"comparison and fixed-metrics machine differ: {field}")
    affinity = host.get("process_affinity")
    if not isinstance(affinity, list) or not affinity:
        raise RuntimeError("complete evidence requires a non-empty process affinity")
    return {field: host[field] for field in fields}


def _same_revision_artifact(left: Document, right: Document) -> bool:
    return all(
        left.get(field) == right.get(field)
        for field in ("revision", "size", "sha256")
    )


def assemble_evidence(
    calibration: Document,
    comparison: Document,
    fixed_metrics: Document,
    corpus: Document,
    corpus_path: Path,
    identities: dict[str, Document],
    finalizer: Document,
) -> Document:
    protocol.validate_comparison_report(calibration)
    protocol.validate_comparison_report(comparison)
    protocol.validate_fixed_metrics_report(fixed_metrics)
    for name, report in (
        ("calibration", calibration),
        ("comparison", comparison),
        ("fixed metrics", fixed_metrics),
    ):
        if report["artifact_mode"] != "owned" or report["status"] != "completed":
            raise RuntimeError(f"{name} must be a completed owned report")
        if report["decision_eligible"] is not False:
            raise RuntimeError(f"{name} cannot already claim final decision eligibility")
    levels = {
        str(calibration["evidence_level"]),
        str(comparison["evidence_level"]),
        str(fixed_metrics["evidence_level"]),
    }
    if len(levels) != 1:
        raise RuntimeError("evidence components have different evidence levels")
    evidence_level = next(iter(levels))
    expected_complete = evidence_level == "controlled"
    for name, report in (
        ("calibration", calibration),
        ("comparison", comparison),
        ("fixed metrics", fixed_metrics),
    ):
        if report["controlled_complete"] is not expected_complete:
            raise RuntimeError(f"{name} controlled completion is inconsistent")
    profiles = [
        calibration["machine_profile"],
        comparison["machine_profile"],
        fixed_metrics["machine_profile"],
    ]
    if expected_complete:
        if any(not isinstance(profile, dict) for profile in profiles):
            raise RuntimeError("controlled evidence requires machine profiles")
        if len({profile["digest"] for profile in profiles}) != 1:
            raise RuntimeError("evidence components use different machine profiles")
        if any(profile != profiles[0] for profile in profiles[1:]):
            raise RuntimeError("machine profile observations differ across components")
        machine_profile = profiles[0]
        machine_profile_tool.verify_binding(machine_profile, "controlled machine profile")
    else:
        if any(profile is not None for profile in profiles):
            raise RuntimeError("exploratory evidence must not bind a machine profile")
        machine_profile = None

    if calibration["mode"] != "aa" or comparison["mode"] != "compare":
        raise RuntimeError("complete evidence requires one A/A and one A/B report")
    calibration_noise = {
        (case["dataset"], case["operation"], case["source"]): case["observed_noise"]
        for case in calibration["cases"]
    }
    for case in comparison["cases"]:
        key = (case["dataset"], case["operation"], case["source"])
        if key not in calibration_noise:
            raise RuntimeError("A/B case has no corresponding A/A calibration case")
        if case["calibration_noise"] != calibration_noise[key]:
            raise RuntimeError("A/B case calibration noise differs from derived A/A noise")
    calibration_identity = identities["calibration_report"]
    calibration_reference = comparison["calibration"]
    if not isinstance(calibration_reference, dict) or any(
        calibration_reference.get(field) != calibration_identity[field]
        for field in ("path", "size", "sha256")
    ) or calibration_reference.get("schema") != calibration["schema"]:
        raise RuntimeError("A/B report does not bind the supplied A/A calibration")

    calibration_build = calibration["candidate"]["build"]
    calibration_baseline_build = calibration["baseline"]["build"]
    comparison_build = comparison["candidate"]["build"]
    baseline_build = comparison["baseline"]["build"]
    current_build = fixed_metrics["build"]
    for build, label in (
        (calibration_baseline_build, "calibration baseline build"),
        (calibration_build, "calibration candidate build"),
        (comparison_build, "comparison candidate build"),
        (baseline_build, "comparison baseline build"),
    ):
        builds.validate_build_manifest(build)
    builds.verify_current_build_manifest(current_build)
    if (
        calibration_baseline_build["identity_digest"]
        != calibration_build["identity_digest"]
    ):
        raise RuntimeError("A/A baseline and candidate build identities differ")
    if calibration_build["identity_digest"] != comparison_build["identity_digest"]:
        raise RuntimeError("A/A and A/B candidate build identities differ")

    candidate_revision = str(comparison_build["revision"])
    baseline_revision = str(baseline_build["revision"])
    if (
        calibration_build["revision"] != candidate_revision
        or current_build["revision"] != candidate_revision
    ):
        raise RuntimeError("candidate revisions differ across evidence components")
    source_tree = str(comparison_build["header_export"]["tree"])
    if (
        calibration_build["header_export"]["tree"] != source_tree
        or current_build["source_export"]["tree"] != source_tree
    ):
        raise RuntimeError("candidate source trees differ across evidence components")
    compiler_sha256 = str(comparison_build["compiler"]["artifact"]["sha256"])
    if (
        calibration_build["compiler"]["artifact"]["sha256"] != compiler_sha256
        or current_build["compiler"]["artifact"]["sha256"] != compiler_sha256
    ):
        raise RuntimeError("compiler artifacts differ across evidence components")
    if calibration["host"] != comparison["host"]:
        raise RuntimeError("A/A and A/B host identities differ")
    machine = _machine_identity(comparison["host"], fixed_metrics["machine"])
    if calibration["runner"] != comparison["runner"]:
        raise RuntimeError("A/A and A/B runner bundles differ")
    _verify_artifact(comparison["runner"], "comparison runner bundle")
    if not _same_revision_artifact(
        calibration["adapter_source"], comparison["adapter_source"]
    ):
        raise RuntimeError("A/A and A/B adapter artifacts differ")

    calibration_datasets = _dataset_index(calibration, "A/A report")
    comparison_datasets = _dataset_index(comparison, "A/B report")
    if calibration_datasets != comparison_datasets:
        raise RuntimeError("A/A and A/B dataset identities differ")
    corpus_datasets = _corpus_index(corpus, corpus_path)
    for name, dataset in comparison_datasets.items():
        corpus_dataset = corpus_datasets.get(name)
        if corpus_dataset is None or any(
            dataset[field] != corpus_dataset[field] for field in ("size", "sha256")
        ):
            raise RuntimeError(f"comparison dataset is not bound to the corpus: {name}")
        corpus_dataset_path = _safe_corpus_member(
            corpus_path.parent.resolve(strict=True), corpus_dataset["path"]
        )
        if Path(str(dataset["path"])).resolve(strict=True) != corpus_dataset_path:
            raise RuntimeError(
                f"comparison dataset path is not bound to the corpus: {name}"
            )
    metrics_dataset = fixed_metrics["artifacts"]["dataset"]
    metrics_name = Path(str(metrics_dataset["path"])).name
    corpus_metrics = corpus_datasets.get(metrics_name)
    if corpus_metrics is None or any(
        metrics_dataset[field] != corpus_metrics[field] for field in ("size", "sha256")
    ):
        raise RuntimeError("fixed-metrics dataset is not bound to the corpus")
    corpus_metrics_path = _safe_corpus_member(
        corpus_path.parent.resolve(strict=True), corpus_metrics["path"]
    )
    if Path(str(metrics_dataset["path"])).resolve(strict=True) != corpus_metrics_path:
        raise RuntimeError("fixed-metrics dataset path is not bound to the corpus")
    if metrics_name not in comparison_datasets:
        raise RuntimeError("fixed-metrics dataset is not present in the comparison")
    comparison_binding = fixed_metrics["comparison_binding"]
    matching_cases = [
        case
        for case in comparison["cases"]
        if case["dataset"] == comparison_binding["dataset"]
        and case["semantic_case_id"] == comparison_binding["semantic_case_id"]
        and case["scope"] == comparison_binding["scope"]
        and case["source"] == comparison_binding["source"]
        and case["byte_basis"] == comparison_binding["byte_basis"]
    ]
    if len(matching_cases) != 1:
        raise RuntimeError(
            "fixed metrics must bind exactly one A/B semantic comparison case"
        )
    if current_build["corpus_manifest"] != identities["corpus_manifest"]:
        raise RuntimeError("current-tree build does not bind the supplied corpus manifest")

    timestamp = datetime.now(timezone.utc).isoformat()
    component_data = {
        "calibration": {
            "schema": calibration["schema"],
            "revision": candidate_revision,
            "build_digest": calibration_build["identity_digest"],
            "controlled_complete": calibration["controlled_complete"],
        },
        "comparison": {
            "schema": comparison["schema"],
            "revision": candidate_revision,
            "build_digest": comparison_build["identity_digest"],
            "controlled_complete": comparison["controlled_complete"],
        },
        "fixed_metrics": {
            "schema": fixed_metrics["schema"],
            "revision": candidate_revision,
            "build_digest": current_build["identity_digest"],
            "controlled_complete": fixed_metrics["controlled_complete"],
        },
    }
    bundle: Document = {
        "schema": EVIDENCE_SCHEMA,
        "status": "completed",
        "evidence_level": evidence_level,
        "decision_eligible": evidence_level == "controlled",
        "generated_at_utc": timestamp,
        "completed_at_utc": timestamp,
        "baseline_revision": baseline_revision,
        "candidate_revision": candidate_revision,
        "source_tree": source_tree,
        "compiler_sha256": compiler_sha256,
        "machine": machine,
        "machine_profile": machine_profile,
        "datasets": [
            {"name": name, "size": value["size"], "sha256": value["sha256"]}
            for name, value in sorted(comparison_datasets.items())
        ],
        "comparison_binding": comparison_binding,
        "components": component_data,
        "checks": {
            "artifact_manifests": True,
            "calibration": True,
            "revisions": True,
            "source_tree": True,
            "compiler": True,
            "machine": True,
            "machine_profile": True,
            "datasets": True,
            "corpus": True,
            "semantic_binding": True,
        },
        "artifacts": identities,
        "finalizer": finalizer,
    }
    protocol.validate_evidence_bundle(bundle)
    return bundle


def finalize(
    *,
    calibration_path: Path,
    calibration_manifest_path: Path,
    comparison_path: Path,
    comparison_manifest_path: Path,
    fixed_metrics_path: Path,
    fixed_metrics_manifest_path: Path,
    corpus_manifest_path: Path,
    output: Path,
    output_manifest: Path,
) -> Document:
    loaded: dict[str, Document] = {}
    paths: dict[str, Path] = {}
    identities: dict[str, Document] = {}
    for name, path in (
        ("calibration_report", calibration_path),
        ("calibration_manifest", calibration_manifest_path),
        ("comparison_report", comparison_path),
        ("comparison_manifest", comparison_manifest_path),
        ("fixed_metrics_report", fixed_metrics_path),
        ("fixed_metrics_manifest", fixed_metrics_manifest_path),
        ("corpus_manifest", corpus_manifest_path),
    ):
        loaded[name], paths[name], identities[name] = load_document(path, name)

    protocol.validate_comparison_report(loaded["calibration_report"])
    protocol.validate_comparison_report(loaded["comparison_report"])
    protocol.validate_fixed_metrics_report(loaded["fixed_metrics_report"])
    _verify_comparison_manifest(
        loaded["calibration_report"],
        loaded["calibration_manifest"],
        identities["calibration_report"],
        "calibration artifact manifest",
    )
    _verify_comparison_manifest(
        loaded["comparison_report"],
        loaded["comparison_manifest"],
        identities["comparison_report"],
        "comparison artifact manifest",
    )
    _verify_fixed_manifest(
        loaded["fixed_metrics_report"],
        loaded["fixed_metrics_manifest"],
        identities["fixed_metrics_report"],
    )

    benchmark_root = Path(__file__).resolve().parents[2]
    finalizer = artifacts.bundle_metadata(
        benchmark_root, finalizer_source_paths(), EVIDENCE_SCHEMA
    )
    output = artifacts.canonical_output(output)
    output_manifest = artifacts.canonical_output(output_manifest)
    protected = [(name, path) for name, path in paths.items()]
    protected.extend(("finalizer source", path) for path in finalizer_source_paths())
    for report_name in (
        "calibration_report",
        "comparison_report",
        "fixed_metrics_report",
    ):
        protected.extend(_identity_paths(loaded[report_name], report_name))
    for manifest_name in (
        "calibration_manifest",
        "comparison_manifest",
        "fixed_metrics_manifest",
    ):
        manifest = loaded[manifest_name]
        protected.extend(
            _identity_paths(manifest["inputs"], f"{manifest_name} input")
        )
    corpus_root = paths["corpus_manifest"].parent.resolve(strict=True)
    corpus_datasets = _corpus_index(
        loaded["corpus_manifest"],
        paths["corpus_manifest"],
        verify_contents=False,
    )
    protected.extend(
        (
            f"corpus dataset {name}",
            _safe_corpus_member(corpus_root, dataset["path"]),
        )
        for name, dataset in corpus_datasets.items()
    )
    artifacts.reject_output_alias(output, protected)
    artifacts.reject_output_alias(output_manifest, protected)
    if artifacts.paths_alias(output, output_manifest):
        raise RuntimeError("evidence bundle and artifact manifest paths must be distinct")
    for label, destination in (
        ("evidence bundle", output),
        ("evidence artifact manifest", output_manifest),
    ):
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(f"{label} output already exists: {destination}")

    bundle = assemble_evidence(
        loaded["calibration_report"],
        loaded["comparison_report"],
        loaded["fixed_metrics_report"],
        loaded["corpus_manifest"],
        paths["corpus_manifest"],
        identities,
        finalizer,
    )
    for name, identity in identities.items():
        _verify_artifact(identity, name)
    _verify_artifact(finalizer, "evidence finalizer")
    # Repeat the nested artifact/build/corpus checks after assembly so a file
    # changed during cross-document validation cannot be published as complete.
    _verify_comparison_manifest(
        loaded["calibration_report"],
        loaded["calibration_manifest"],
        identities["calibration_report"],
        "calibration artifact manifest",
    )
    _verify_comparison_manifest(
        loaded["comparison_report"],
        loaded["comparison_manifest"],
        identities["comparison_report"],
        "comparison artifact manifest",
    )
    _verify_fixed_manifest(
        loaded["fixed_metrics_report"],
        loaded["fixed_metrics_manifest"],
        identities["fixed_metrics_report"],
    )
    bundle = assemble_evidence(
        loaded["calibration_report"],
        loaded["comparison_report"],
        loaded["fixed_metrics_report"],
        loaded["corpus_manifest"],
        paths["corpus_manifest"],
        identities,
        finalizer,
    )
    for name, identity in identities.items():
        _verify_artifact(identity, name)
    _verify_artifact(finalizer, "evidence finalizer")
    staged_output = atomic.stage_json(output, bundle)
    try:
        if artifacts.paths_alias(staged_output, output_manifest):
            raise RuntimeError("artifact manifest path aliases the staged evidence bundle")
        staged_identity = artifacts.metadata(staged_output)
        report_identity = {**staged_identity, "path": str(output)}
        manifest: Document = {
            "schema": ARTIFACT_MANIFEST_SCHEMA,
            "kind": "evidence-bundle",
            "report": report_identity,
            "inputs": {**identities, "finalizer": finalizer},
        }
        protocol.validate_artifact_manifest(manifest)
        # The manifest is the prerequisite; the eligible bundle is the final
        # atomic publication, so an interruption cannot leave it unbound.
        atomic.write_json(output_manifest, manifest)
        atomic.publish_staged(staged_output, output)
        _verify_artifact(report_identity, "published evidence bundle")
    except BaseException:
        atomic.discard_staged(staged_output)
        raise
    return bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--calibration-manifest", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--comparison-manifest", type=Path, required=True)
    parser.add_argument("--fixed-metrics", type=Path, required=True)
    parser.add_argument("--fixed-metrics-manifest", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output_manifest = args.manifest or args.output.with_suffix(
        args.output.suffix + ".sha256.json"
    )
    try:
        finalize(
            calibration_path=args.calibration,
            calibration_manifest_path=args.calibration_manifest,
            comparison_path=args.comparison,
            comparison_manifest_path=args.comparison_manifest,
            fixed_metrics_path=args.fixed_metrics,
            fixed_metrics_manifest_path=args.fixed_metrics_manifest,
            corpus_manifest_path=args.corpus_manifest,
            output=args.output,
            output_manifest=output_manifest,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
