"""Controlled caller flags and same-compilation dependency provenance.

The compiler and its SDK are trusted; caller-selected inputs are not.
"""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence

POLICY = "csv2-owned-input-policy-v2"
REMOVED_ENV = frozenset({
    "LD_PRELOAD", "LD_RUN_PATH", "DYLD_INSERT_LIBRARIES",
    "CC", "CXX", "GCC_COMPARE_DEBUG",
    "CMAKE_CXX_COMPILER_LAUNCHER", "CMAKE_C_COMPILER_LAUNCHER",
    "CMAKE_PREFIX_PATH", "CMAKE_MODULE_PATH", "CMAKE_FIND_ROOT_PATH",
    "CMAKE_PROJECT_TOP_LEVEL_INCLUDES",
    "CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
    "COMPILER_PATH", "GCC_EXEC_PREFIX", "LIBRARY_PATH", "CL", "_CL_", "LINK",
    "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "CMAKE_TOOLCHAIN_FILE",
    "CMAKE_PROJECT_INCLUDE", "CMAKE_PROJECT_INCLUDE_BEFORE",
    "CCC_OVERRIDE_OPTIONS", "CCC_ADD_ARGS", "CLANG_CONFIG_FILE_SYSTEM_DIR",
    "CLANG_CONFIG_FILE_USER_DIR", "DEPENDENCIES_OUTPUT", "SUNPRO_DEPENDENCIES",
})
BOUND_ENV = ("PATH", "INCLUDE", "LIB", "LIBPATH", "SDKROOT", "SYSTEMROOT",
             "WINDOWSSDKDIR", "WINDOWSSDKVERSION", "VCTOOLSINSTALLDIR",
             "SOURCE_DATE_EPOCH", "MACOSX_DEPLOYMENT_TARGET", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")


def environment() -> tuple[dict[str, str], dict[str, Any]]:
    env = {key: value for key, value in os.environ.items() if key.upper() not in REMOVED_ENV}
    env["LC_ALL"] = "C"
    binding = {key: value for key, value in env.items() if key.upper() in BOUND_ENV}
    return env, {"policy": POLICY, "removed": sorted(REMOVED_ENV), "bound": binding}


def flags(arguments: Sequence[object], family: str | None = None) -> None:
    """Allow only explicit code-generation options; no paths or opaque payloads."""
    index = 0
    while index < len(arguments):
        flag = arguments[index]
        if not isinstance(flag, str):
            raise RuntimeError("compiler flags contain a non-string argument")
        if "CSV2_" in flag:
            raise RuntimeError("compiler flags override a reserved definition")
        if "@" in flag:
            raise RuntimeError("compiler flags cannot use response files")
        if flag.lower().startswith(("-wp,", "-xclang", "-xpreprocessor")):
            raise RuntimeError("compiler flags cannot use preprocessor pass-through")
        if flag.lower().startswith(("-include", "-imacros", "/fi")):
            raise RuntimeError("compiler flags cannot force preprocessor input")
        if flag in ("-D", "-U", "/D", "/U"):
            index += 1
            if index == len(arguments) or not isinstance(arguments[index], str):
                raise RuntimeError("incomplete compiler definition")
            flag += arguments[index]
        if "CSV2_" in flag:
            raise RuntimeError("compiler flags override a reserved definition")
        gnu = re.fullmatch(
            r"(?:-O[0-3sgz]|-Ofast|-UNDEBUG|-DNDEBUG(?:=[01])?|"
            r"-std=(?:c|gnu)\+\+(?:98|03|11|14|17|20|23|26|2a|2b|2c)|"
            r"-stdlib=(?:libc\+\+|libstdc\+\+)|-m(?:arch|tune|cpu)=[A-Za-z0-9_.+-]+|"
            r"-m(?:32|64|sse[234]?(?:\.[12])?|avx2?|avx512[a-z0-9]+|fma|no-avx2?)|"
            r"-f(?:no-)?(?:exceptions|rtti|omit-frame-pointer|strict-aliasing|fast-math)|"
            r"-flto(?:=(?:auto|thin|full|[0-9]+))?|-g[0-3]?|-pthread|"
            r"-W(?:all|extra|pedantic|error)|-pedantic)", flag)
        msvc = re.fullmatch(
            r"/(?:O[12dx]|DNDEBUG(?:=[01])?|UNDEBUG|std:c\+\+(?:14|17|20|latest)|"
            r"arch:(?:IA32|SSE|SSE2|AVX|AVX2|AVX512)|EHsc|GR-?|M[DT]d?|"
            r"fp:(?:precise|strict|fast)|W[0-4]|WX|nologo|Brepro|experimental:deterministic)",
            flag)
        if not ((gnu and family != "msvc") or (msvc and family != "gnu")):
            raise RuntimeError(f"unsupported controlled compiler flag: {flag!r}")
        index += 1


def depfile_paths(text: str) -> list[str]:
    # GCC/Clang make escaping: escaped spaces, hashes and backslashes, continuations.
    text = text.replace("\\\n", "")
    if ": " not in text:
        raise RuntimeError("compiler dependency file is missing its target")
    payload = text.split(": ", 1)[1]
    tokens = re.findall(r"(?:\\.|[^\s])+", payload)
    return [re.sub(r"\\(.)", r"\1", token).replace("$$", "$") for token in tokens]


def bind_dependencies(
    paths: Iterable[str],
    exports: Mapping[str, dict[str, Any]],
    *,
    cwd: Path,
    required_sources: Iterable[tuple[str, str]],
    trusted_roots: Sequence[Path] = (),
) -> dict[str, Any]:
    known = {}
    for label, export in exports.items():
        root = Path(export["root"]).resolve(strict=True)
        for entry in export["files"]:
            known[(root / entry["path"]).resolve(strict=True)] = {
                "export": label, "path": entry["path"], "sha256": entry["sha256"]}
    first_party_suffixes = {
        "/" + record["path"].removeprefix("include/")
        for record in known.values()
        if record["path"].startswith("include/csv2/")
    }
    records = {}
    external = set()
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = cwd / path
        try:
            path = path.resolve(strict=True)
        except OSError as error:
            raise RuntimeError(f"compiler dependency input is unavailable: {path}") from error
        if path in known:
            record = known[path]
            records[(record["export"], record["path"])] = record
        elif any(path.as_posix().endswith(suffix) for suffix in first_party_suffixes):
            raise RuntimeError(f"compiler consumed a shadowed first-party header: {path}")
        elif any(path.is_relative_to(root) for root in trusted_roots):
            external.add(str(path))
        else:
            raise RuntimeError(f"compiler consumed an input outside immutable exports: {path}")
    if not set(required_sources).issubset(records):
        raise RuntimeError("compiler dependency evidence lacks owned source closure")
    if not any(record["path"].startswith("include/csv2/") for record in records.values()):
        raise RuntimeError("compiler dependency evidence lacks consumed csv2 headers")
    return {"schema": "csv2-compile-dependencies-v2",
            "files": [records[key] for key in sorted(records)],
            "trusted_system_inputs": sorted(external)}


def recorded_path(value: str) -> PurePath:
    """Interpret persisted Windows paths even when reports are read on POSIX."""
    path_type = PureWindowsPath if re.match(r"^(?:[A-Za-z]:|\\\\)", value) else PurePosixPath
    result = path_type(value)
    if not result.is_absolute() or ".." in result.parts:
        raise RuntimeError("owned dependency path is not absolute and normalized")
    return result


def verify_dependencies(
    evidence: object,
    exports: Mapping[str, dict[str, Any]],
    required_sources: Iterable[tuple[str, str]],
) -> None:
    from .builds import safe_git_path

    if not isinstance(evidence, dict) or evidence.get("schema") != "csv2-compile-dependencies-v2":
        raise RuntimeError("owned dependency evidence has the wrong schema")
    required = {"schema", "files", "trusted_system_inputs", "trusted_system_roots"}
    if not required.issubset(evidence) or set(evidence) - required - {"units"}:
        raise RuntimeError("owned dependency evidence fields are incomplete or unknown")
    for field in ("trusted_system_inputs", "trusted_system_roots"):
        values = evidence.get(field)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            raise RuntimeError("owned dependency system boundary is malformed")
    roots = [recorded_path(value) for value in evidence["trusted_system_roots"]]
    if any(not root.is_absolute() for root in roots):
        raise RuntimeError("owned dependency system root is not absolute")
    for value in evidence["trusted_system_inputs"]:
        if not any(recorded_path(value).is_relative_to(root) for root in roots):
            raise RuntimeError("owned dependency evidence has an outside system input")
    files = evidence.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError("owned dependency evidence is missing")
    known = {
        (label, entry["path"]): entry["sha256"]
        for label, export in exports.items()
        for entry in export["files"]
    }
    seen = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"export", "path", "sha256"}:
            raise RuntimeError("owned dependency entry is malformed")
        if not all(isinstance(value, str) for value in entry.values()):
            raise RuntimeError("owned dependency entry values are malformed")
        safe_git_path(entry["path"])
        key = (entry["export"], entry["path"])
        if key in seen or known.get(key) != entry["sha256"]:
            raise RuntimeError("owned dependency evidence differs from immutable exports")
        seen.add(key)
    if not set(required_sources).issubset(seen) or not any(
        path.startswith("include/csv2/") for _, path in seen
    ):
        raise RuntimeError("owned dependency evidence lacks consumed input closure")
    suffixes = {
        "/" + path.removeprefix("include/")
        for _, path in known if path.startswith("include/csv2/")
    }
    if any(
        recorded_path(value).as_posix().endswith(suffix)
        for value in evidence["trusted_system_inputs"] for suffix in suffixes
    ):
        raise RuntimeError("owned dependency evidence contains a shadowed first-party header")
