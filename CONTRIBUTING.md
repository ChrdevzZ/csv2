# Contributing

Contributions are welcome through issues and pull requests. Keep generated and
temporary output in an out-of-source directory (`build/`, `build-*`,
`cmake-build-*`, or `out/` are ignored).

## Public source and generated header

The modular headers in `include/csv2/` are the source of truth. The public
target must continue to require only `cxx_std_11`. Regenerate the distribution
header after every public-header change:

```bash
python3 utils/amalgamate/amalgamate.py -c single_include.json -s .
git diff --exit-code -- single_include/csv2/csv2.hpp
```

Commit modular and generated forms together. A test/benchmark-only change must
leave both trees untouched.

## Verification components

All components are disabled by default and may be selected independently:

```text
CSV2_BUILD_TESTS
CSV2_BUILD_BENCHMARKS
CSV2_BUILD_BENCHMARK_CHECKS  # requires benchmarks
CSV2_BUILD_FUZZERS
```

The real libFuzzer targets require Clang's GNU frontend on a non-Windows
platform. Windows verification uses the deterministic reader and writer fuzz
smoke executables built with `CSV2_BUILD_TESTS=ON`.

`CSV2_VERIFICATION_PROFILE=quick|full|perf` chooses depth but never enables a
component. A normal pre-push run is:

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_COMPILE_WARNING_AS_ERROR=ON \
  -DCSV2_BUILD_TESTS=ON \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCSV2_BUILD_BENCHMARK_CHECKS=ON \
  -DCSV2_REQUIRE_PYTHON_AUDITS=ON \
  -DCSV2_VERIFICATION_PROFILE=quick
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Use `full` before changing standards, feature detection, iterators/ranges,
ownership, no-mmap/no-exceptions behavior, or platform mapping. Use `perf` only
with the benchmark evidence process; profile selection is not itself a claim
that a machine is controlled.

Full/perf profiles and every CI job require Python 3.10 audits. A quick local
configuration may continue without Python only after printing the skipped
audit categories; do not report that run as the complete quick gate.

`CSV2_ENABLE_SANITIZERS=ON` applies supported sanitizers only to first-party
verification targets. GNU-style GCC/Clang and AppleClang use ASan+UBSan; MSVC
uses ASan; x64 Clang-CL uses ASan+UBSan in a non-Debug CRT configuration.

## Runtime tests

Do not add behavior to a monolithic main file. Put it under the owning one of
the 13 domains in `test/runtime/` and use a stable ID:

```cpp
CSV2_TEST_CASE("reader.scan.trailing-empty", "reader.scan") {
  // ...
}
```

Runtime sources use the backend-independent macros from
`csv2_test/assertions.hpp`. C++14–23 normal variants use Catch2; C++11 and all
no-exceptions variants use the non-throwing CSV2 runner. Keep one semantic
source unless a language feature genuinely requires a compile-only contract.

When adding a source or capability, update the declaration in
`test/runtime/CMakeLists.txt`. The manifest rejects duplicate/unknown domains,
missing files, invalid profiles, and impossible capability combinations.
CTest names are stable:

```text
csv2.runtime.<domain>.<modular|single>.cxx<standard>.<normal|no_mmap|no_exceptions>
```

Select focused work by name or label rather than a test count. Shared support
types belong in the focused headers under `test/support/include/csv2_test/`;
avoid expanding the compatibility umbrella `test_support.hpp`.

Compile-only public-header, config, standard-library-feature, and mmap path
contracts belong in `test/contracts/`. Platform injection and emulation belong
in `test/platform/`.

See [`test/README.md`](test/README.md) for the complete domain and matrix
contract.

## Fixtures, properties, and fuzzing

Use inline bytes for small cases. If a fixture improves clarity:

1. add it under `test/fixtures/upstream`, `regression`, or `property`;
2. update `test/fixtures/SHA256SUMS`;
3. preserve exact LF/CRLF/quoted-LF bytes;
4. never normalize the file through a text-mode rewrite.

The fixture CMake layer rejects missing, extra, or hash-mismatched CSV files.
`.gitattributes` disables checkout conversion for fixtures and fuzz seeds.

For a regression inherited from the retired doctest suite, retain its mapping
in `test/migration/legacy_case_map.tsv`. The parity checker requires its old
title to appear in the immutable `legacy_doctest_inventory.json` captured from
base commit `635e59a`, then validates the new stable ID and domain. When the
pinned Git objects are available it also re-reads the original source blob;
shallow clones and source packages still verify the fixed inventory metadata
and digests.

Changes to parsing or escaping should extend the deterministic round-trip
property and, when appropriate, both libFuzzer targets. Replay the committed
corpora, minimize crashes, and use libFuzzer `-merge=1` before proposing a new
seed. Raw corpora, profiles, and crash artifacts stay in ignored build trees;
commit only a small stable reproducer.

## Benchmarks and performance claims

Current-tree kernels live in `benchmark/current/kernels/` and are registered
by operation, source, and dataset. Every kernel must define:

- preparation outside timing;
- the exact timed action;
- a live local value/memory observation before clear or destruction;
- untimed checksum verification;
- input bytes, rows, cells, and operation bytes;
- whether the timed path must allocate zero times;
- supported sources, preparation requirements, and explicit failure status.

Add one stable entry to `benchmark/checks/case_manifest.json` for every new
operation. The manifest gate lists the compiled registry, verifies the exact
semantic wire, and starts a short dry run for each available operation; feature-
conditional entries may remain absent from builds that lack the capability.
Actual timing must select exactly one operation and one concrete compatible
source per process.

Operation names must describe their cache and preparation boundary. Do not call
repeated filesystem reads cold I/O or prepared page touches first-fault work.
Separate index construction from prepared lookup, and bind validation scenario
names to preflight-checked corpus diagnostics.

Timing never replaces correctness tests. Do not compare historical benchmark
executables or hand-built artifacts across revisions. Use the owned pipeline,
which exports immutable Git objects and compiles the same C++11
`benchmark/compare/common_driver.cpp` against both exact header trees with an
audited compiler and normalized command. `--external-artifacts` is for
exploratory diagnostics only.

Performance statements require the versioned pipeline, retained JSON, A/A
noise calibration, alternating A/B runs, matching checksums, and the threshold
documented in [`benchmark/README.md`](benchmark/README.md). GitHub-hosted
results are `exploratory` and cannot establish “no regression”. Only a
completed `controlled` evidence bundle produced by the cross-report finalizer
is decision-eligible. Controlled work also requires a reviewed machine profile
whose digest and runtime observation match A/A, A/B, and fixed metrics. Do not
edit derived statistics or verdicts: validators rebuild them from launch wires,
samples, and the recorded schedule.

## Verification dependencies

Catch2 and Google Benchmark are test-only, offline snapshots under
`third_party/verification`. Do not add `FetchContent`, submodules, system-package
fallbacks, or configure-time network access. Before changing a snapshot:

1. update exact tag/commit, archive SHA-256, SPDX license, whitelist,
   per-file SHA-256 list, and snapshot hash in `manifest.json`;
2. fetch and stage only through the maintainer tool's explicit network mode;
3. keep patches as separate files under `patches/` with rationale and upstream
   issue; never edit a snapshot silently;
4. run both the integrity and tooling-contract tests;
5. install with all verification components enabled and confirm that no
   dependency target or file enters the CSV2 package.

```bash
python3 tools/vendor/update_verification_dependencies.py check
python3 tools/vendor/test_update_verification_dependencies.py -v
```

Third-party sources are excluded from CSV2 formatting, Werror, sanitizers, and
coverage. Dependency loaders must also override `COMPILE_WARNING_AS_ERROR` at
target scope because CMake's global initializer crosses subdirectory policy
scopes. Loaders must reject target collisions and restore the parent Cache
value/type/help/advanced/strings state exactly; CMake validates every vendored
file hash even when Python is unavailable. See
[`third_party/verification/README.md`](third_party/verification/README.md).

## CI and documentation

The existing Linux, Windows, macOS, and fuzz/benchmark workflow identities are
the automatic quick checks. `full.yml` and `perf.yml` are manually dispatched.
Keep matrices `fail-fast: false`, upload JUnit/evidence artifacts, and select
CTest by stable names or labels rather than hard-coded totals.

Performance jobs must finish with `benchmark/finalize_evidence.py`; checking
that component files merely exist is not an evidence gate. Comparison and
fixed-metrics reports can declare only `controlled_complete`. Do not set or
infer final `decision_eligible` outside the cross-report evidence bundle.
Fixed metrics must bind exactly one A/B case by dataset, semantic case ID,
scope, source, and byte basis.

Update the root README for public behavior, `test/README.md` for verification
topology, `benchmark/README.md` and `benchmark/protocol/README.md` for timing or
wire changes, and the verification dependency README for supply-chain changes.
Temporary research and one-off reports belong in ignored local directories,
not a tracked top-level `docs/` tree.

## Code of conduct

This project follows the [Open Code of Conduct][code-of-conduct].

[code-of-conduct]: https://github.com/spotify/code-of-conduct/blob/master/code-of-conduct.md
