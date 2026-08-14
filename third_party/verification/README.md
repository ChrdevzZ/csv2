# Offline verification dependencies

This directory contains immutable source snapshots used only by CSV2 tests and
benchmarks. A normal library configure does not parse them. Their targets are
never installed, exported, linked by `csv2::csv2`, or exposed to consumers.

## Locked sources

| Dependency | Version and source | Archive SHA-256 | Snapshot SHA-256 | License | Consumer |
| --- | --- | --- | --- | --- | --- |
| Catch2 | signed tag object `95d8a61b089317bec800c7cc4c64064cbcb3802d`, peeled commit `8b08d4d79514f45f7e4ce2a607ac9c94e920d1bb` (`v3.15.3`) | `b0299ae552918220a7a6e21e7de5b714777f4e8c883fb70c4bb23fe01df8c6e3` | `30a95651c113d1d7e7fee94504319312f9854f0c895e88da98d2233481d08925` | BSL-1.0 | C++14–23 normal runtime tests |
| Google Benchmark | commit/tag `192ef10025eb2c4cdd392bc502f0c852196baa48` (`v1.9.5`) | `f82705a2726d8f6cdcda274b841f6314dbfc6f731cdda06c946f310ec1cc3ad9` | `e5ed0f09089472e1ea729869600ae03a8aef75fc521952dcfd30c4904481d789` | Apache-2.0 | current-tree benchmark only |

`manifest.json` is the machine-readable authority. `*.files` are sorted,
duplicate-free path allowlists and `*.sha256` bind every allowed path to its
content. The aggregate snapshot hash additionally covers each relative path,
byte count, and file content, so an added, removed, renamed, or changed file
fails integrity validation.

The curated snapshots retain licenses, the upstream build modules needed to
configure the isolated projects, public headers, and split library sources.
Upstream tests, examples, documentation, CI configuration, and unrelated
development files are excluded. Catch2's split library avoids the compile-memory
concentration of its amalgamated test header. Google Benchmark builds itself as
C++17; the independent CSV2 common driver does not link it and remains C++11.

## Dependency boundary

```text
C++11 normal runtime tests       -> csv2_minitest
all no-exceptions runtime tests  -> csv2_minitest
C++14–23 normal runtime tests    -> Catch2::Catch2WithMain
current-tree benchmark           -> benchmark::benchmark
C++11 common comparison driver   -> csv2::csv2 only
Python evidence tools            -> Python 3.10+ standard library only
```

The loaders call `add_subdirectory(... EXCLUDE_FROM_ALL)` only when the owning
component is enabled. Catch2 docs, extras, self-tests, examples, fuzzers,
benchmarks, installation, and Werror are disabled. Google Benchmark tests,
GTest, dependency downloads, installation, docs/tools, assembly tests, and
Werror are disabled. Google Benchmark's libpfm integration remains off for
quick/full builds and is enabled for perf builds only when its headers and
library are available. CSV2 warning-as-error, sanitizer, coverage, and format
rules apply only to first-party targets; the dependency loaders explicitly set
`COMPILE_WARNING_AS_ERROR=OFF` even when the parent build enables it globally.
Each loader rejects pre-existing target names, snapshots the complete parent
CMake Cache before entering the vendored project, and restores its values and
metadata while deleting entries introduced by the dependency.

CI installs CSV2 after configuring all verification components and fails if an
installed path contains Catch2 or Google Benchmark names. This supplements the
target configuration and prevents future loader changes from leaking a
dependency into package exports.

## Offline integrity check

Run from the repository root:

```bash
python3 tools/vendor/update_verification_dependencies.py check
python3 tools/vendor/test_update_verification_dependencies.py -v
```

`check` performs no network access. It validates schema, allowlists, licenses,
directory contents, per-file hashes, and both snapshot hashes. CMake performs
the same path, directory, symlink, and per-file SHA-256 checks without Python
before loading either dependency. Ordinary configuration and all CI jobs are
offline: there is no `FetchContent`, submodule update, package-manager fallback,
or automatic fetch.

Python 3.10 additionally runs the aggregate snapshot and maintenance-tool
contracts. Full/perf profiles and `CSV2_REQUIRE_PYTHON_AUDITS=ON` fail when it
is unavailable; a quick local build may continue only with an explicit warning
listing those skipped audits. The CMake per-file gate is never skipped.

## Maintainer update procedure

Dependency updates are explicit review operations. First edit a proposed
manifest entry with the exact upstream archive URL and independently verified
archive SHA-256. Then download only with the opt-in flag and stage only into a
new empty directory:

```bash
python3 tools/vendor/update_verification_dependencies.py \
  fetch catch2 build-vendor/catch2.tar.gz --allow-network
python3 tools/vendor/update_verification_dependencies.py \
  stage catch2 build-vendor/catch2.tar.gz build-vendor/catch2-stage
```

The downloader refuses an existing output, verifies the archive before use,
and deletes a mismatched download. Extraction rejects absolute paths, `..`,
links, special entries, multiple archive roots, and files absent from the
allowlist. Staging refuses a non-empty destination and verifies the resulting
snapshot hash.

After reviewing the staged diff:

1. update the allowlist to the minimal required files;
2. regenerate the per-file hashes with `write-hashes <dependency>`;
3. update tag object, peeled commit, version, archive and snapshot hashes,
   license metadata, and license path;
4. replace the snapshot without modifying its bytes;
5. run integrity/tooling tests and all dependent builds;
6. configure every verification component, install CSV2, and audit the install
   manifest for dependency leakage.

The current `patches` arrays are empty. If a local patch becomes unavoidable,
store it as a separate file under `patches/` and record its ordered path,
rationale, and upstream issue in the manifest. Direct unrecorded edits to a
snapshot are prohibited.
