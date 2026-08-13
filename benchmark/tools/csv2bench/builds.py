"""Immutable Git export and owned common-driver build support."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Sequence

from . import BUILD_SCHEMA
from . import artifacts


OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
DRIVE_PREFIX = re.compile(r"[A-Za-z]:")
Run = Callable[..., subprocess.CompletedProcess]


def _canonical_json(document: object) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def document_digest(document: object) -> str:
    return hashlib.sha256(_canonical_json(document)).hexdigest()


def safe_git_path(value: str) -> PurePosixPath:
    """Validate a Git path before materializing it on any host platform."""
    if not value or "\\" in value or value.startswith("/") or value.startswith("//"):
        raise RuntimeError(f"unsafe Git path: {value!r}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise RuntimeError(f"unsafe Git path: {value!r}")
    components = value.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise RuntimeError(f"unsafe Git path: {value!r}")
    if DRIVE_PREFIX.match(components[0]) or any(":" in component for component in components):
        raise RuntimeError(f"unsafe Git path: {value!r}")
    result = PurePosixPath(*components)
    if result.is_absolute():
        raise RuntimeError(f"unsafe Git path: {value!r}")
    return result


def _object_id(value: str, label: str) -> str:
    if not OBJECT_ID.fullmatch(value):
        raise RuntimeError(f"{label} is not a Git object ID: {value!r}")
    return value


def _git(
    repository: Path,
    arguments: Sequence[str],
    *,
    run_fn: Run = subprocess.run,
) -> bytes:
    command = ["git", "-C", str(repository), *arguments]
    completed = run_fn(command, capture_output=True, timeout=30)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Git command failed ({completed.returncode}): {json.dumps(command)}\n{stderr}"
        )
    return bytes(completed.stdout)


def resolve_commit(repository: Path, reference: str, *, run_fn: Run = subprocess.run) -> str:
    repository = artifacts.canonical_existing(repository, "Git repository")
    output = _git(
        repository,
        ["rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}"],
        run_fn=run_fn,
    )
    lines = output.decode("ascii", errors="strict").splitlines()
    if len(lines) != 1:
        raise RuntimeError("git rev-parse returned an ambiguous commit")
    return _object_id(lines[0], "resolved commit")


def commit_tree(repository: Path, commit: str, *, run_fn: Run = subprocess.run) -> str:
    commit = _object_id(commit, "commit")
    output = _git(
        repository,
        ["rev-parse", "--verify", "--end-of-options", f"{commit}^{{tree}}"],
        run_fn=run_fn,
    )
    lines = output.decode("ascii", errors="strict").splitlines()
    if len(lines) != 1:
        raise RuntimeError("git rev-parse returned an ambiguous tree")
    return _object_id(lines[0], "commit tree")


def parse_ls_tree(output: bytes) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, separator, encoded_path = record.partition(b"\t")
        fields = metadata.split(b" ")
        if not separator or len(fields) != 3:
            raise RuntimeError("malformed git ls-tree record")
        try:
            mode, kind, object_id = (field.decode("ascii") for field in fields)
            path = encoded_path.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise RuntimeError("Git tree metadata is not valid UTF-8") from error
        safe_git_path(path)
        if path in seen:
            raise RuntimeError(f"duplicate Git tree path: {path}")
        seen.add(path)
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise RuntimeError(
                f"unsupported Git tree entry {path!r}: mode={mode} type={kind}"
            )
        entries.append(
            {
                "mode": mode,
                "type": kind,
                "oid": _object_id(object_id, f"Git object for {path}"),
                "path": path,
            }
        )
    if not entries:
        raise RuntimeError("Git tree contains no regular files")
    return entries


def list_regular_files(
    repository: Path, commit: str, *, run_fn: Run = subprocess.run
) -> list[dict[str, str]]:
    commit = _object_id(commit, "commit")
    return parse_ls_tree(
        _git(repository, ["ls-tree", "-rz", "--full-tree", "-r", commit], run_fn=run_fn)
    )


def _selected_entries(
    entries: Sequence[dict[str, str]], selections: Sequence[str] | None
) -> tuple[list[dict[str, str]], list[str]]:
    if selections is None:
        return list(entries), ["<full-tree>"]
    if not selections:
        raise RuntimeError("Git export selection must not be empty")
    normalized: list[str] = []
    for selection in selections:
        path = safe_git_path(selection).as_posix()
        if path in normalized:
            raise RuntimeError(f"duplicate Git export selection: {path}")
        normalized.append(path)
    selected: list[dict[str, str]] = []
    matched = {selection: False for selection in normalized}
    for entry in entries:
        path = entry["path"]
        for selection in normalized:
            if path == selection or path.startswith(selection + "/"):
                matched[selection] = True
                selected.append(entry)
                break
    missing = [selection for selection, present in matched.items() if not present]
    if missing:
        raise RuntimeError(f"Git export selection is missing: {', '.join(missing)}")
    return selected, normalized


def export_target(root: Path, git_path: str) -> Path:
    relative = safe_git_path(git_path)
    root = root.resolve(strict=True)
    target = root.joinpath(*relative.parts)
    resolved = target.resolve(strict=False)
    try:
        common = Path(os.path.commonpath((str(root), str(resolved))))
    except ValueError as error:
        raise RuntimeError(f"Git export path escapes staging root: {git_path}") from error
    if os.path.normcase(str(common)) != os.path.normcase(str(root)):
        raise RuntimeError(f"Git export path escapes staging root: {git_path}")
    return target


def export_git_tree(
    repository: Path,
    reference: str,
    destination: Path,
    selections: Sequence[str] | None = None,
    *,
    run_fn: Run = subprocess.run,
) -> dict[str, object]:
    """Export selected regular blobs without consulting the working tree."""
    repository = artifacts.canonical_existing(repository, "Git repository")
    if not repository.is_dir():
        raise RuntimeError(f"Git repository is not a directory: {repository}")
    commit = resolve_commit(repository, reference, run_fn=run_fn)
    tree = commit_tree(repository, commit, run_fn=run_fn)
    entries, normalized_selections = _selected_entries(
        list_regular_files(repository, commit, run_fn=run_fn), selections
    )

    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(f"Git export destination already exists: {destination}")
    destination.mkdir()
    root = destination.resolve(strict=True)
    files: list[dict[str, object]] = []
    target_keys: set[str] = set()
    try:
        for entry in entries:
            target = export_target(root, entry["path"])
            target_key = os.path.normcase(str(target.resolve(strict=False)))
            if target_key in target_keys:
                raise RuntimeError(f"Git paths collide on this filesystem: {entry['path']}")
            target_keys.add(target_key)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.parent.resolve(strict=True).is_relative_to(root):
                raise RuntimeError(f"Git export parent escapes staging root: {entry['path']}")
            blob = _git(repository, ["cat-file", "blob", entry["oid"]], run_fn=run_fn)
            with target.open("xb") as output:
                output.write(blob)
                output.flush()
                os.fsync(output.fileno())
            if os.name != "nt" and entry["mode"] == "100755":
                target.chmod(target.stat().st_mode | stat.S_IXUSR)
            files.append(
                {
                    **entry,
                    "size": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest(),
                }
            )
    except BaseException:
        shutil.rmtree(root)
        raise

    manifest: dict[str, object] = {
        "schema": "csv2-git-export-v1",
        "repository": str(repository),
        "reference": reference,
        "commit": commit,
        "tree": tree,
        "selections": normalized_selections,
        "root": str(root),
        "files": files,
    }
    manifest["digest"] = document_digest(manifest)
    return manifest


def verify_git_export(manifest: dict[str, object]) -> None:
    if manifest.get("schema") != "csv2-git-export-v1":
        raise RuntimeError("Git export manifest has the wrong schema")
    expected_digest = str(manifest.get("digest", ""))
    unsigned = dict(manifest)
    unsigned.pop("digest", None)
    if not SHA256.fullmatch(expected_digest) or document_digest(unsigned) != expected_digest:
        raise RuntimeError("Git export manifest digest is inconsistent")
    repository = artifacts.canonical_existing(
        Path(str(manifest.get("repository", ""))), "Git repository"
    )
    root = artifacts.canonical_existing(
        Path(str(manifest.get("root", ""))), "Git export root"
    )
    commit = _object_id(str(manifest.get("commit", "")), "Git export commit")
    tree = _object_id(str(manifest.get("tree", "")), "Git export tree")
    if commit_tree(repository, commit) != tree:
        raise RuntimeError("Git export tree does not belong to its commit")
    source_entries = {
        entry["path"]: entry for entry in list_regular_files(repository, commit)
    }
    values = manifest.get("files")
    if not isinstance(values, list) or not values:
        raise RuntimeError("Git export manifest has no files")
    expected_files: set[Path] = set()
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            raise RuntimeError(f"Git export file {index} is not an object")
        path = str(value.get("path", ""))
        source = source_entries.get(path)
        if source is None or any(value.get(field) != source[field] for field in ("mode", "type", "oid")):
            raise RuntimeError(f"Git export file is not bound to the commit tree: {path}")
        target = export_target(root, path)
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f"Git export file is missing or not regular: {path}")
        size = target.stat().st_size
        digest = artifacts.sha256_file(target)
        if value.get("size") != size or value.get("sha256") != digest:
            raise RuntimeError(f"Git export file changed after extraction: {path}")
        blob = _git(repository, ["cat-file", "blob", str(value["oid"])])
        if len(blob) != size or hashlib.sha256(blob).hexdigest() != digest:
            raise RuntimeError(f"Git export file differs from its Git blob: {path}")
        expected_files.add(target.resolve(strict=True))
    actual_files: set[Path] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Git export contains a symlink: {path}")
        if path.is_file():
            actual_files.add(path.resolve(strict=True))
    if actual_files != expected_files:
        raise RuntimeError("Git export contains missing or unmanifested files")


def _compiler_path(value: Path) -> Path:
    candidate = value.expanduser()
    if not candidate.is_absolute():
        located = shutil.which(str(candidate))
        if located is None:
            raise RuntimeError(f"compiler executable was not found: {value}")
        candidate = Path(located)
    compiler = artifacts.canonical_existing(candidate, "compiler executable")
    if not compiler.is_file():
        raise RuntimeError(f"compiler executable is not a file: {compiler}")
    return compiler


def normalize_build_argv(
    argv: Sequence[str], replacements: Iterable[tuple[str, str]]
) -> list[str]:
    normalized = list(argv)
    ordered = sorted(replacements, key=lambda replacement: len(replacement[0]), reverse=True)
    for index, argument in enumerate(normalized):
        for value, placeholder in ordered:
            if value:
                argument = argument.replace(value, placeholder)
        normalized[index] = argument
    return normalized


def _artifact(path: Path, revision: str) -> dict[str, object]:
    return artifacts.metadata(path, revision)


def compile_common_driver(
    *,
    header_export: dict[str, object],
    adapter_export: dict[str, object],
    compiler: Path,
    compiler_flags: Sequence[str],
    output: Path,
    enable_modern_writer_operations: bool = True,
    run_fn: Run = subprocess.run,
) -> dict[str, object]:
    """Compile one common driver and return its complete audited build manifest."""
    verify_git_export(header_export)
    verify_git_export(adapter_export)
    revision = str(header_export.get("commit", ""))
    _object_id(revision, "header export commit")
    header_root = artifacts.canonical_existing(
        Path(str(header_export.get("root", ""))), "header export root"
    )
    adapter_root = artifacts.canonical_existing(
        Path(str(adapter_export.get("root", ""))), "adapter export root"
    )
    include_root = artifacts.canonical_existing(header_root / "include", "include root")
    adapter_source = artifacts.canonical_existing(
        adapter_root / "benchmark" / "compare" / "common_driver.cpp",
        "common driver source",
    )
    compiler = _compiler_path(compiler)
    compiler_artifact = _artifact(compiler, "compiler")

    compiler_name = compiler.name.lower()
    msvc = compiler_name in {"cl", "cl.exe"}
    version_command = (
        [str(compiler), "/Bv", "/?"] if msvc else [str(compiler), "--version"]
    )
    version = run_fn(version_command, capture_output=True, text=True, timeout=30)
    if version.returncode != 0 or not (version.stdout.strip() or version.stderr.strip()):
        raise RuntimeError("compiler version command failed or returned no identity")

    output = output.expanduser().resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    protected_paths = [("compiler executable", compiler)]
    for label, export in (("header", header_export), ("adapter", adapter_export)):
        export_root = Path(str(export["root"]))
        protected_paths.extend(
            (f"{label} source {entry['path']}", export_root.joinpath(*PurePosixPath(entry["path"]).parts))
            for entry in export["files"]
        )
    artifacts.reject_output_alias(output, protected_paths)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".build", dir=output.parent
    )
    os.close(handle)
    temporary_output = Path(temporary_name)
    temporary_output.unlink()
    temporary_object = temporary_output.with_suffix(temporary_output.suffix + ".obj")
    revision_definition = f'CSV2_BENCHMARK_REVISION="{revision}"'
    modern_definition = "CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1"
    if msvc:
        command = [
            str(compiler),
            *compiler_flags,
            f"/D{revision_definition}",
            *([f"/D{modern_definition}"] if enable_modern_writer_operations else []),
            f"/I{include_root}",
            str(adapter_source),
            f"/Fe:{temporary_output}",
            f"/Fo:{temporary_object}",
        ]
    else:
        command = [
            str(compiler),
            *compiler_flags,
            f"-D{revision_definition}",
            *([f"-D{modern_definition}"] if enable_modern_writer_operations else []),
            f"-I{include_root}",
            str(adapter_source),
            "-o",
            str(temporary_output),
        ]
    try:
        completed = run_fn(command, capture_output=True, text=True, timeout=600)
        if completed.returncode != 0:
            raise RuntimeError(
                "common driver compilation failed\n"
                f"command: {json.dumps(command)}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        if (
            not temporary_output.is_file()
            or temporary_output.is_symlink()
            or temporary_output.stat().st_size == 0
        ):
            raise RuntimeError("compiler did not create a regular non-empty executable")
        verify_git_export(header_export)
        verify_git_export(adapter_export)
        artifacts.verify_unchanged(compiler_artifact, "compiler executable")
        os.replace(temporary_output, output)
    finally:
        if temporary_output.exists() or temporary_output.is_symlink():
            temporary_output.unlink()
        if temporary_object.exists() or temporary_object.is_symlink():
            temporary_object.unlink()

    normalized_argv = normalize_build_argv(
        command,
        (
            (str(include_root), "{include_root}"),
            (str(adapter_source), "{adapter_source}"),
            (str(temporary_output), "{output}"),
            (revision, "{revision}"),
        ),
    )
    manifest: dict[str, object] = {
        "schema": BUILD_SCHEMA,
        "kind": "common-driver",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "revision": revision,
        "header_export": header_export,
        "adapter_export": adapter_export,
        "compiler": {
            "artifact": compiler_artifact,
            "version": {
                "command": version_command,
                "returncode": version.returncode,
                "stdout": version.stdout,
                "stderr": version.stderr,
            },
        },
        "compiler_flags": list(compiler_flags),
        "argv": command,
        "normalized_argv": normalized_argv,
        "build_log": {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
        "output": _artifact(output, revision),
    }
    manifest["digest"] = document_digest(manifest)
    validate_build_manifest(manifest)
    return manifest


def validate_build_manifest(manifest: dict[str, object]) -> None:
    required = {
        "schema",
        "kind",
        "generated_at_utc",
        "revision",
        "header_export",
        "adapter_export",
        "compiler",
        "compiler_flags",
        "argv",
        "normalized_argv",
        "build_log",
        "output",
        "digest",
    }
    if set(manifest) != required:
        raise RuntimeError("build manifest fields are incomplete or unknown")
    if manifest["schema"] != BUILD_SCHEMA or manifest["kind"] != "common-driver":
        raise RuntimeError("build manifest has the wrong schema or kind")
    expected_digest = str(manifest["digest"])
    unsigned = dict(manifest)
    unsigned.pop("digest")
    if not SHA256.fullmatch(expected_digest) or document_digest(unsigned) != expected_digest:
        raise RuntimeError("build manifest digest is inconsistent")
    revision = _object_id(str(manifest["revision"]), "build revision")
    header_export = manifest["header_export"]
    adapter_export = manifest["adapter_export"]
    if not isinstance(header_export, dict) or not isinstance(adapter_export, dict):
        raise RuntimeError("build source exports are malformed")
    verify_git_export(header_export)
    verify_git_export(adapter_export)
    if header_export.get("commit") != revision:
        raise RuntimeError("build revision differs from the header export")
    header_paths = {str(entry["path"]) for entry in header_export["files"]}
    if not header_paths or any(
        path != "include" and not path.startswith("include/") for path in header_paths
    ):
        raise RuntimeError("build header export contains an unexpected path")
    adapter_paths = [str(entry["path"]) for entry in adapter_export["files"]]
    if adapter_paths != ["benchmark/compare/common_driver.cpp"]:
        raise RuntimeError("build adapter export is not the common driver")

    compiler = manifest["compiler"]
    if not isinstance(compiler, dict) or set(compiler) != {"artifact", "version"}:
        raise RuntimeError("build compiler identity is malformed")
    compiler_artifact = compiler["artifact"]
    version = compiler["version"]
    if not isinstance(compiler_artifact, dict) or not isinstance(version, dict):
        raise RuntimeError("build compiler identity is malformed")
    if set(version) != {"command", "returncode", "stdout", "stderr"}:
        raise RuntimeError("build compiler version record is malformed")
    if version["returncode"] != 0 or not isinstance(version["command"], list):
        raise RuntimeError("build compiler version command did not succeed")
    artifacts.verify_unchanged(compiler_artifact, "build compiler")

    argv = manifest["argv"]
    normalized_argv = manifest["normalized_argv"]
    compiler_flags = manifest["compiler_flags"]
    if not all(isinstance(value, list) for value in (argv, normalized_argv, compiler_flags)):
        raise RuntimeError("build command fields are malformed")
    if not argv or len(argv) != len(normalized_argv):
        raise RuntimeError("build command normalization is inconsistent")
    compiler_path = artifacts.canonical_existing(
        Path(str(compiler_artifact.get("path", ""))), "build compiler"
    )
    if Path(str(argv[0])).resolve(strict=True) != compiler_path:
        raise RuntimeError("build command did not invoke the recorded compiler")
    normalized_text = "\n".join(str(value) for value in normalized_argv)
    for placeholder in ("{revision}", "{include_root}", "{adapter_source}", "{output}"):
        if placeholder not in normalized_text:
            raise RuntimeError(f"build command is missing normalized {placeholder}")
    build_log = manifest["build_log"]
    if (
        not isinstance(build_log, dict)
        or set(build_log) != {"returncode", "stdout", "stderr"}
        or build_log["returncode"] != 0
    ):
        raise RuntimeError("build log does not record a successful compile")
    output = manifest["output"]
    if not isinstance(output, dict) or output.get("revision") != revision:
        raise RuntimeError("build output identity is malformed")
    artifacts.verify_unchanged(output, "build output")


def assert_compatible_builds(
    baseline: dict[str, object], candidate: dict[str, object]
) -> None:
    validate_build_manifest(baseline)
    validate_build_manifest(candidate)
    baseline_compiler = baseline["compiler"]["artifact"]["sha256"]
    candidate_compiler = candidate["compiler"]["artifact"]["sha256"]
    if baseline_compiler != candidate_compiler:
        raise RuntimeError("baseline and candidate compiler artifacts differ")
    if baseline["adapter_export"]["digest"] != candidate["adapter_export"]["digest"]:
        raise RuntimeError("baseline and candidate adapter exports differ")
    if baseline["normalized_argv"] != candidate["normalized_argv"]:
        raise RuntimeError("baseline and candidate normalized build commands differ")


def build_common_pair(
    *,
    repository: Path,
    baseline_reference: str,
    candidate_reference: str,
    compiler: Path,
    compiler_flags: Sequence[str],
    workspace: Path,
    enable_modern_writer_operations: bool = True,
    run_fn: Run = subprocess.run,
) -> dict[str, object]:
    """Build both comparison artifacts from immutable objects and one shared adapter."""
    repository = artifacts.canonical_existing(repository, "Git repository")
    workspace = workspace.expanduser().resolve(strict=False)
    workspace.mkdir(parents=True, exist_ok=False)
    adapter = export_git_tree(
        repository,
        candidate_reference,
        workspace / "adapter",
        ("benchmark/compare/common_driver.cpp",),
        run_fn=run_fn,
    )
    headers = {
        "baseline": export_git_tree(
            repository,
            baseline_reference,
            workspace / "baseline-source",
            ("include",),
            run_fn=run_fn,
        ),
        "candidate": export_git_tree(
            repository,
            candidate_reference,
            workspace / "candidate-source",
            ("include",),
            run_fn=run_fn,
        ),
    }
    suffix = ".exe" if os.name == "nt" else ""
    manifests: dict[str, dict[str, object]] = {}
    for side in ("baseline", "candidate"):
        manifests[side] = compile_common_driver(
            header_export=headers[side],
            adapter_export=adapter,
            compiler=compiler,
            compiler_flags=compiler_flags,
            output=workspace / f"csv2-common-{side}{suffix}",
            enable_modern_writer_operations=enable_modern_writer_operations,
            run_fn=run_fn,
        )
    assert_compatible_builds(manifests["baseline"], manifests["candidate"])
    if (
        manifests["baseline"]["revision"] == manifests["candidate"]["revision"]
        and manifests["baseline"]["output"]["sha256"]
        != manifests["candidate"]["output"]["sha256"]
    ):
        raise RuntimeError("A/A owned builds are not byte-identical")
    return {
        "baseline": manifests["baseline"],
        "candidate": manifests["candidate"],
        "adapter": adapter,
    }
