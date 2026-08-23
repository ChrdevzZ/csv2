# CSV2 benchmark and performance evidence

The benchmark tree separates current-tree microbenchmarks from cross-revision
comparisons. A checksum or allocation result may be a CI gate; hosted timing
never is. This verification code does not change CSV2's installed headers or
its C++11 consumer requirement.

## Layout and build boundary

```text
benchmark/
├── current/    Google Benchmark registry, kernels, and measurement support
├── compare/    self-contained C++11 common driver
├── datasets/   deterministic generator, committed smoke corpus, manifest
├── checks/     CTest protocol, checksum, CLI, and allocation contracts
├── protocol/   versioned report documentation and JSON schemas
├── tools/      standard-library-only Python evidence pipeline and tests
├── finalize_evidence.py  cross-report final decision gate
└── legacy/     historical csv-game sources, excluded from new reports
```

`benchmark/CMakeLists.txt` requires CMake 3.16 and is parsed only when
`CSV2_BUILD_BENCHMARKS=ON`. Benchmarks build independently of runtime tests.
Google Benchmark is used only by `current/`; `compare/common_driver.cpp` links
only `csv2::csv2` and remains C++11.

```bash
cmake -S . -B build-benchmark -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCSV2_BUILD_BENCHMARK_CHECKS=ON \
  -DCSV2_REQUIRE_PYTHON_AUDITS=ON \
  -DCSV2_VERIFICATION_PROFILE=quick \
  -DCSV2_BENCHMARK_REVISION="$(git rev-parse HEAD)"
cmake --build build-benchmark --parallel
ctest --test-dir build-benchmark -L benchmark-checksum \
  --no-tests=error --output-on-failure
```

`CSV2_BUILD_BENCHMARK_CHECKS` controls CTest registration and requires
benchmarks to be enabled. With checks off, the benchmark executables and common
driver still build. A quick local configuration may proceed without Python but
prints every skipped Python audit; full/perf and
`CSV2_REQUIRE_PYTHON_AUDITS=ON` require Python 3.10+. The current benchmark
uses C++23 when available and otherwise C++20. Google Benchmark itself is built
as C++17 and is never installed or exported.

## Current-tree operation registry

Names follow `csv2/<operation>/<source>/<dataset>`. Use `--csv2-list` to see
the exact operations available with the selected standard library and mmap
configuration.

| Group | Operations |
| --- | --- |
| source | `file-read-cached`, `mmap-open`, `mmap-touch-resident`, `parse-borrowed`, `parse-owned`, conditional `parse-span` |
| traversal | `rows`, `rows-cells` |
| extraction | row raw; cell raw/decoded/content with fresh or reused string; decoded fresh/reused vector |
| validation | `valid`, `invalid-early`, `invalid-middle`, `invalid-late` |
| conversion | `integer-bool-error`, conditional `integer-expected` |
| ranges | `pipeline`, conditional `to-container` |
| index | `build`, `sequential-lookup`, deterministic `random-lookup` |
| writer | raw/escaped × direct/streamable, plus `always-direct` |

`file-read-cached` opens and reads a file repeatedly; it describes a cached
filesystem path, not cold storage. `mmap-open` creates a fresh mapping without
pre-mapping the input. `mmap-touch-resident` touches one byte per page and the
final byte of a mapping prepared before timing; it describes resident-page
access, not first page faults. Each operation declares source compatibility and
a preparation bitmask. `Context` materializes only that state: source/traversal
kernels do not decode Writer rows or allocate Writer buffers. Reused extraction
buffers and Writer output capacity are reserved before timing only for
operations that need them.

Index construction and lookup are separate measurements. `index/build` owns
the construction and allocation cost. The two lookup operations consume a
prepared `RowIndex` and precomputed deterministic positions; their timed paths
perform only lookup, row-boundary access, and result observation and must not
allocate.

Validation names are input contracts rather than labels for the same kernel.
`validation/valid` requires successful strict validation. Each invalid case
requires the manifest's exact diagnostic and an offset in its declared early,
middle, or late region before timing begins.

Writer direct kernels pass contiguous strings; streamable kernels use a
non-owning wrapper with an explicit inserter. Both escaped paths consume the
same predecoded rows, so CSV decoding is measured only by extraction kernels.
Writer checksum calculation happens after timing. The current-tree registry
uses distinct timed and verification function pointers, so checksum branches
and row/cell metadata traversal cannot enter timed kernels. Every timed kernel
also passes its live local result through an inline `TimedObserver`: scalars
use `DoNotOptimize`, while live contiguous memory escapes its pointer/size
before `ClobberMemory`. A dedicated Release IPO/LTO audit proves that each
affected kernel observes a value or memory. The common driver likewise writes
into a preallocated fixed buffer and asserts that its checksum mixer is never
called while the timer is active.

Kernel failures are explicit. Input open/read/change, mmap, parse, output
overflow, and output-stream errors carry a `KernelStatus` plus native error
code. Verify/list/timing fail when no operation/source pair matches; verify
never emits a success wire for a failed kernel, timing uses `SkipWithError`,
and the metrics parser rejects skipped/error Google Benchmark records.

Google Benchmark reports input-corpus bytes through `SetBytesProcessed` for
all operations. Exact operation/output bytes are a separate counter. This
makes GiB/s comparable across traversal, extraction, and Writer kernels and
does not mislabel Writer output bandwidth as input throughput.

### Semantic verification

Checksums and allocation counts are transported by a separate exact integer
wire, never by floating-point benchmark counters:

```bash
./build-benchmark/benchmark/current/csv2_benchmark \
  --csv2-input benchmark/datasets/fixtures/quote_heavy.csv \
  --csv2-source buffer \
  --csv2-operation writer/escaped-direct \
  --csv2-verify
```

The line begins with `protocol=csv2-current-v3` and includes a stable semantic
case ID, scope, source, byte basis, decimal `uint64_t` checksum, bytes, rows,
cells, allocations, and allocated bytes. The
instrumented `csv2_benchmark_allocations` executable replaces ordinary and
C++17 aligned `new`/`new[]`. Verification fails when an operation marked
zero-allocation allocates. CI currently gates zero allocation for traversal,
borrowed parsing, reused extraction, strict validation/conversion/ranges, and
direct Writer paths. `checks/expected_checksums.json` is executable test data:
CI runs every listed operation and compares complete wire fields and the full
decimal checksum; prefix matches are rejected.

### Timing

After a successful verify call, pass ordinary Google Benchmark options. A
timing process accepts exactly one operation and one concrete compatible
source; `all` is available only to list, verify, and audit modes. The suite
runner starts one process for each requested operation/source/dataset case.

```bash
./build-benchmark/benchmark/current/csv2_benchmark \
  --csv2-input benchmark/datasets/fixtures/short_unquoted.csv \
  --csv2-source buffer \
  --csv2-operation traversal/rows-cells \
  --benchmark_min_time=0.5s \
  --benchmark_min_warmup_time=0.2 \
  --benchmark_repetitions=20 \
  --benchmark_enable_random_interleaving=true \
  --benchmark_out=build-benchmark/rows-cells.json \
  --benchmark_out_format=json
```

The executable uses real time. Mmap operations disappear completely from an
explicit `-DCSV2_HAS_MMAP=0` build. `checks/case_manifest.json` assigns every
registered operation at least one stable verify and dry-run case; CI rejects
missing registrations, unsupported sources, and unknown non-conditional
entries.

## Deterministic corpus

`datasets/manifest.json` records generator version, specified LCG32 seed,
scale, parameters, byte size, SHA-256, rows, cells, raw/content checksums, and
strict-valid status. Committed fixtures are deliberately small and cover:

- startup, tall/narrow, short unquoted, and wide rows;
- quote-heavy, doubled quotes, quoted LF, and CRLF;
- empty/trailing fields, a long field, numeric fields, and header/empty lines;
- UTF-8 byte payloads and 15/16, 31/32, 63/64, 255/256, 4095/4096 boundaries;
- strict-invalid input at early, middle, and late positions.

Generate a larger corpus only under an ignored build tree:

```bash
python3 benchmark/generate_datasets.py \
  --output build-benchmark/corpus/fixtures \
  --manifest build-benchmark/corpus/manifest.json \
  --scale 100
```

With `CSV2_VERIFICATION_PROFILE=perf`, CMake exposes the equivalent explicit
target `csv2_benchmark_corpus`; its multiplier is controlled by
`CSV2_BENCHMARK_CORPUS_SCALE` and defaults to 100. The target is not part of
the default build and does not start a timing run.

## Cross-revision common driver

Never compare two revisions' historical benchmark programs. The owned-build
pipeline exports the same candidate `benchmark/compare/common_driver.cpp` and
each exact header tree directly from immutable Git blobs, then compiles both
with one audited compiler and normalized command. It rejects links, unsafe
paths, dirty-worktree substitution, mismatched flags, and output drift.

The driver emits `csv2-common-v4`. Its `--describe` wire assigns every
operation an explicit semantic case ID, scope, byte basis, and supported source
set. `rows_cells` is
`traversal_only`; Writer operations are `writer_only` and consume pointer/length
row views prepared before timing; `legacy_mmap_rows_cells` is explicitly
`mmap_and_traversal`. Direct and streamable Writer variants must agree on
checksum, rows, and cells. Each operation performs an untimed semantic
checksum; a mismatch prevents a performance decision.

## Comparison pipeline

`run_suite.py` is a compatibility wrapper around `tools/csv2bench/runner.py`.
Owned mode is the default: the tool resolves commits, exports and builds both
drivers, embeds `csv2-benchmark-build-v1` manifests, revalidates all Git/build/
dataset/tool inputs, rejects output aliases, and atomically publishes a v5
report plus its v3 artifact manifest. External executables require
`--external-artifacts` and are restricted to exploratory evidence.

First generate the owned current-tree corpus with the fixed-metrics command
below. Then run A/A and A/B against that exact generated fixture directory:

```bash
BASE="$(git merge-base master HEAD)"
CANDIDATE="$(git rev-parse HEAD)"
CXX="$(command -v c++)"

python3 benchmark/run_suite.py \
  --repository . \
  --baseline-ref "$CANDIDATE" --candidate-ref "$CANDIDATE" \
  --build-root build-benchmark/owned-aa \
  --compiler-executable "$CXX" \
  --compiler-flags='-std=c++11 -O3 -DNDEBUG' \
  --datasets build-benchmark/current-owned/build/benchmark-corpus/fixtures \
  --operations rows_cells,legacy_writer_raw \
  --sources buffer,mmap \
  --files short_unquoted.csv,quote_heavy.csv,multiline.csv,crlf.csv \
  --runs 20 --warmups 3 --iterations 10 --mode aa \
  --evidence-level controlled --cpu-affinity 0 \
  --machine-profile /etc/csv2/perf-machine.json \
  --output build-benchmark/aa.json

python3 benchmark/run_suite.py \
  --repository . \
  --baseline-ref "$BASE" --candidate-ref "$CANDIDATE" \
  --build-root build-benchmark/owned-ab \
  --compiler-executable "$CXX" \
  --compiler-flags='-std=c++11 -O3 -DNDEBUG' \
  --datasets build-benchmark/current-owned/build/benchmark-corpus/fixtures \
  --operations rows_cells,legacy_writer_raw \
  --sources buffer,mmap \
  --files short_unquoted.csv,quote_heavy.csv,multiline.csv,crlf.csv \
  --runs 20 --warmups 3 --iterations 10 --mode compare \
  --calibration build-benchmark/aa.json \
  --evidence-level controlled --cpu-affinity 0 \
  --machine-profile /etc/csv2/perf-machine.json \
  --output build-benchmark/ab.json
```

Run the process itself under the declared affinity, for example
`taskset -c 0 python3 ...`; controlled mode rejects an affinity mismatch.
Numeric CLI fields accept unsigned ASCII decimal only. Signs, whitespace,
zero iterations, and overflow are rejected before measurement.

The report retains launch order, raw output, every sample, provenance, median,
MAD, and deterministic paired-bootstrap 95% interval. Validation reparses every
saved launch wire, reconstructs the `(phase, round, order)` schedule, and
recomputes throughput, medians, MADs, confidence intervals, noise, thresholds,
and verdicts. A/B requires distinct commits; A/A requires identical revisions,
owned build identities, and executable hashes. A regression is reported only
when candidate median throughput drops beyond
`max(5%, comparison noise, A/A noise)` and the complete interval lies below
parity. Comparison noise is the larger of the baseline and candidate relative
MAD bounds, not a baseline-only estimate.

## Fixed-machine metrics

`collect_metrics.py` exports the full candidate Git tree, configures an
isolated CMake/Ninja Release build, and audits its File API codemodel,
target-specific compile commands, include roots, revision definition,
caller-supplied compiler flags, link commands, executables, and corpus before
accepting timing JSON. Owned metrics require a non-empty native
`--compiler-flags` value; those flags are applied to both Release targets and
are not descriptive metadata. It records
allocations, Google Benchmark real-time samples, Linux PMU counters, peak RSS,
text/data/BSS sizes, and clean owned-build duration:

```bash
taskset -c 0 python3 benchmark/collect_metrics.py \
  --repository . --candidate-ref "$CANDIDATE" \
  --build-root build-benchmark/current-owned --corpus-scale 100 \
  --compiler-executable "$(command -v c++)" \
  --compiler-flags='-O3 -DNDEBUG' \
  --operation traversal/rows-cells \
  --input short_unquoted.csv \
  --source buffer --runs 20 \
  --minimum-time 0.5s --warmup-seconds 0.5 \
  --evidence-level controlled --cpu-affinity 0 \
  --machine-profile /etc/csv2/perf-machine.json \
  --output build-benchmark/fixed-machine.json
```

Controlled metrics currently require Linux, a verified
`csv2-machine-profile-v1`, at least 20 repetitions, matching CPU affinity,
positive warmup, a libpfm-enabled Google Benchmark build, and complete
cycles/instructions/branch-misses plus RSS/size and clean-build timing
collection. Corpus generation is untimed and its checked manifest remains part
of the owned build identity. The current wire revision, source Git commit,
codemodel, compile/link commands, compiler executable, and output hashes must
all agree. Both pipelines hash their entry point and complete imported Python
helper closure as one deterministic source bundle; A/B rejects an A/A
calibration produced by a different bundle. `--skip-pmu`, `--skip-rss`, and
`--skip-size` are exploratory smoke-only relaxations.

Finalize the three component reports only after all measurements complete:

```bash
python3 benchmark/finalize_evidence.py \
  --calibration build-benchmark/aa.json \
  --calibration-manifest build-benchmark/aa.json.sha256.json \
  --comparison build-benchmark/ab.json \
  --comparison-manifest build-benchmark/ab.json.sha256.json \
  --fixed-metrics build-benchmark/fixed-machine.json \
  --fixed-metrics-manifest build-benchmark/fixed-machine.json.sha256.json \
  --corpus-manifest build-benchmark/current-owned/build/benchmark-corpus/manifest.json \
  --output build-benchmark/evidence.json
```

The finalizer revalidates the reports, manifests, exact corpus files, source
trees, compiler, machine profile/affinity, candidate build, and A/A calibration
link. It also requires exactly one A/B case whose dataset, semantic case ID,
scope, source, and byte basis match the fixed-metrics `comparison_binding`.
Its output and sibling manifest paths must not already exist.
Individual comparison and fixed-metrics reports expose
`controlled_complete`, but always keep `decision_eligible=false`. Only the
resulting `csv2-performance-evidence-bundle-v2` can be decision-eligible.

## Evidence classes and protocols

- `exploratory` is suitable for GitHub-hosted runners and local smoke tests.
  Reports are reviewable artifacts but cannot support a regression verdict.
- `controlled` requires a stable Linux machine, fixed affinity, a reviewed
  `csv2-machine-profile-v1`, A/A noise calibration, three or more warmups, and
  at least 20 paired runs. Runtime CPU model, architecture, logical CPU count,
  affinity, kernel, governor, and turbo/boost observations must match the
  profile, whose digest is shared by A/A, A/B, and fixed metrics. Only a
  finalized bundle containing all controlled-complete components is
  decision-eligible. Finalization reparses the profile artifact and compares its
  content with all embedded bindings.

The fixed contracts are `csv2-common-v4`, `csv2-current-v3`,
`csv2-benchmark-build-v1`, `csv2-benchmark-report-v5`,
`csv2-fixed-machine-metrics-v5`, `csv2-performance-evidence-bundle-v2`,
`csv2-artifact-manifest-v3`, and `csv2-machine-profile-v1`. Older or unknown
versions are rejected rather than converted. Every completed component and
evidence JSON has a sibling v3 SHA-256 artifact manifest. See
[`protocol/README.md`](protocol/README.md) for the wire boundary and schemas.

The manual `Performance evidence` workflow produces and finalizes exploratory
artifacts on a hosted runner or controlled artifacts only on a self-hosted
runner carrying the `csv2-perf` label. It checks out the exact candidate,
verifies `HEAD`, loads the preconfigured `CSV2_PERF_MACHINE_PROFILE` on a
controlled runner, then uses only the owned-build APIs for common drivers and
current-tree metrics; no
workflow-local archive/compile path can stamp unrelated sources as that
revision. For an explicit `files` subset, fixed metrics uses its first dataset
so that the cross-report evidence overlaps. The workflow fails before evidence
upload unless the final bundle and its artifact manifest are both produced;
failed runs upload a separate diagnostics artifact, never an evidence artifact.
This Stage B infrastructure change makes no library performance claim.
