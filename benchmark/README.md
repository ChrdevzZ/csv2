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
  -DCSV2_VERIFICATION_PROFILE=quick \
  -DCSV2_BENCHMARK_REVISION="$(git rev-parse HEAD)"
cmake --build build-benchmark --parallel
ctest --test-dir build-benchmark -L benchmark-checksum \
  --no-tests=error --output-on-failure
```

`CSV2_BUILD_BENCHMARK_CHECKS` controls CTest registration and requires
benchmarks to be enabled. With checks off, the two benchmark executables and
common driver still build; Python is not required. The current benchmark uses
C++23 when available and otherwise C++20. Google Benchmark itself is built as
C++17 and is never installed or exported.

## Current-tree operation registry

Names follow `csv2/<operation>/<source>/<dataset>`. Use `--csv2-list` to see
the exact operations available with the selected standard library and mmap
configuration.

| Group | Operations |
| --- | --- |
| source | `file-read`, `mmap-open`, `mmap-touch`, `parse-borrowed`, `parse-owned`, conditional `parse-span` |
| traversal | `rows`, `rows-cells` |
| extraction | row raw; cell raw/decoded/content with fresh or reused string; decoded fresh/reused vector |
| validation | `strict`, `invalid-early`, `invalid-middle`, `invalid-late` |
| conversion | `integer-bool-error`, conditional `integer-expected` |
| ranges | `pipeline`, conditional `to-container` |
| index | `build`, `sequential`, deterministic `random` |
| writer | raw/escaped × direct/streamable, plus `always-direct` |

`file-read` measures opening and reading the file. `mmap-open` measures a fresh
mapping; `mmap-touch` touches one byte per page and the final byte of an
already prepared mapping. All parsing, traversal, extraction, validation,
conversion, ranges, index, and writer inputs are prepared before timing.
Reused extraction buffers and Writer output capacity are also reserved before
timing.

Writer direct kernels pass contiguous strings; streamable kernels use a
non-owning wrapper with an explicit inserter. Both escaped paths consume the
same predecoded rows, so CSV decoding is measured only by extraction kernels.
Writer checksum calculation happens after timing. The current-tree registry
uses distinct timed and verification function pointers, so checksum branches
and row/cell metadata traversal cannot enter timed kernels. The common driver
likewise writes into a preallocated fixed buffer and asserts that its checksum
mixer is never called while the timer is active.

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

The line begins with `protocol=csv2-current-v2` and includes decimal `uint64_t`
checksum, bytes, rows, cells, allocations, and allocated bytes. The
instrumented `csv2_benchmark_allocations` executable replaces ordinary and
C++17 aligned `new`/`new[]`. Verification fails when an operation marked
zero-allocation allocates. CI currently gates zero allocation for traversal,
borrowed parsing, reused extraction, strict validation/conversion/ranges, and
direct Writer paths. `checks/expected_checksums.json` is executable test data:
CI runs every listed operation and compares complete wire fields and the full
decimal checksum; prefix matches are rejected.

### Timing

After a successful verify call, pass ordinary Google Benchmark options:

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

The executable uses real time. `--csv2-source all` registers every supported
source; mmap operations disappear completely from an explicit
`-DCSV2_HAS_MMAP=0` build.

## Deterministic corpus

`datasets/manifest.json` records generator version, specified LCG32 seed,
scale, parameters, byte size, SHA-256, rows, cells, raw/content checksums, and
strict-valid status. Committed fixtures are deliberately small and cover:

- startup, tall/narrow, short unquoted, and wide rows;
- quote-heavy, doubled quotes, quoted LF, and CRLF;
- empty/trailing fields, a long field, numeric fields, and header/empty lines;
- UTF-8 byte payloads and 15/16, 31/32, 63/64, 255/256, 4095/4096 boundaries;
- strict-invalid input at early, middle, and late positions.

Reproduce the committed corpus without writing it:

```bash
python3 benchmark/generate_datasets.py --check
```

Generate a larger corpus only under an ignored build tree:

```bash
python3 benchmark/generate_datasets.py \
  --output build-benchmark/corpus/fixtures \
  --manifest build-benchmark/corpus/manifest.json \
  --scale 100
python3 benchmark/generate_datasets.py \
  --output build-benchmark/corpus/fixtures \
  --manifest build-benchmark/corpus/manifest.json \
  --scale 100 --check
```

With `CSV2_VERIFICATION_PROFILE=perf`, CMake exposes the equivalent explicit
target `csv2_benchmark_corpus`; its multiplier is controlled by
`CSV2_BENCHMARK_CORPUS_SCALE` and defaults to 100. The target is not part of
the default build and does not start a timing run.

## Cross-revision common driver

Never compare two revisions' historical benchmark programs. Compile the same
candidate `benchmark/compare/common_driver.cpp`, compiler, and flags against
both exact header archives. The driver emits `csv2-common-v2` and supports
`rows_cells`, `legacy_writer_raw`, and `legacy_mmap_rows_cells`. Define
`CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1` on both sides only when both
header revisions support the four modern Writer operations.

```bash
BASE="$(git merge-base master HEAD)"
CANDIDATE="$(git rev-parse HEAD)"
COMPARE="build-benchmark/compare"
mkdir -p "$COMPARE/base" "$COMPARE/candidate" "$COMPARE/bin"
git archive "$BASE" include | tar -x -C "$COMPARE/base"
git archive "$CANDIDATE" include | tar -x -C "$COMPARE/candidate"

c++ -std=c++11 -O3 -DNDEBUG -I"$COMPARE/base/include" \
  -DCSV2_BENCHMARK_REVISION=\"$BASE\" \
  benchmark/compare/common_driver.cpp -o "$COMPARE/bin/baseline"
c++ -std=c++11 -O3 -DNDEBUG -I"$COMPARE/candidate/include" \
  -DCSV2_BENCHMARK_REVISION=\"$CANDIDATE\" \
  benchmark/compare/common_driver.cpp -o "$COMPARE/bin/candidate"
```

The driver prepares buffer traversal and Writer rows outside its timer.
`legacy_mmap_rows_cells` intentionally maps and traverses inside the measured
scope to reproduce the old positional benchmark. Each operation performs an
untimed semantic checksum; a mismatch prevents a performance decision.

## Comparison pipeline

`run_suite.py` is a compatibility wrapper around `tools/csv2bench/runner.py`.
It resolves every executable, adapter, dataset, calibration, and output path;
rejects direct, symlink, and hardlink output aliases; hashes all artifacts;
revalidates them after measurement; and checkpoints reports with a unique
same-directory temporary file plus atomic replace.

Run an A/A calibration first, then A/B with the same context:

```bash
python3 benchmark/run_suite.py \
  --baseline "$COMPARE/bin/candidate" \
  --candidate "$COMPARE/bin/candidate" \
  --baseline-revision "$CANDIDATE" \
  --candidate-revision "$CANDIDATE" \
  --adapter-source benchmark/compare/common_driver.cpp \
  --datasets build-benchmark/corpus/fixtures \
  --operations rows_cells,legacy_writer_raw \
  --sources buffer,mmap \
  --files short_unquoted.csv,quote_heavy.csv,multiline.csv,crlf.csv \
  --runs 20 --warmups 3 --iterations 10 --mode aa \
  --evidence-level controlled --cpu-affinity 0 \
  --compiler "$(c++ --version | head -1)" \
  --compiler-flags='-std=c++11 -O3 -DNDEBUG' \
  --output "$COMPARE/aa.json"

python3 benchmark/run_suite.py \
  --baseline "$COMPARE/bin/baseline" \
  --candidate "$COMPARE/bin/candidate" \
  --baseline-revision "$BASE" \
  --candidate-revision "$CANDIDATE" \
  --adapter-source benchmark/compare/common_driver.cpp \
  --datasets build-benchmark/corpus/fixtures \
  --operations rows_cells,legacy_writer_raw \
  --sources buffer,mmap \
  --files short_unquoted.csv,quote_heavy.csv,multiline.csv,crlf.csv \
  --runs 20 --warmups 3 --iterations 10 --mode compare \
  --calibration "$COMPARE/aa.json" \
  --evidence-level controlled --cpu-affinity 0 \
  --compiler "$(c++ --version | head -1)" \
  --compiler-flags='-std=c++11 -O3 -DNDEBUG' \
  --output "$COMPARE/ab.json"
```

Run the process itself under the declared affinity, for example
`taskset -c 0 python3 ...`; controlled mode rejects an affinity mismatch.
Numeric CLI fields accept unsigned ASCII decimal only. Signs, whitespace,
zero iterations, and overflow are rejected before measurement.

The report retains launch order, raw output, every sample, provenance, median,
MAD, and deterministic paired-bootstrap 95% interval. A regression is reported
only when candidate median throughput drops beyond
`max(5%, comparison noise, A/A noise)` and the complete interval lies below
parity.

## Fixed-machine metrics

`collect_metrics.py` independently verifies the exact current-tree wire before
accepting timing JSON. It can record allocations, Google Benchmark real-time
samples, Linux PMU counters, peak RSS, executable text/data/BSS sizes, and an
optional clean-build duration:

```bash
taskset -c 0 python3 benchmark/collect_metrics.py \
  --executable build-benchmark/benchmark/current/csv2_benchmark \
  --allocation-executable \
    build-benchmark/benchmark/current/csv2_benchmark_allocations \
  --revision "$CANDIDATE" \
  --compiler "$(c++ --version | head -1)" \
  --compiler-flags='-O3 -DNDEBUG' \
  --compiler-executable "$(command -v c++)" \
  --compile-commands build-benchmark/compile_commands.json \
  --operation traversal/rows-cells \
  --input build-benchmark/corpus/fixtures/short_unquoted.csv \
  --source buffer --runs 20 \
  --minimum-time 0.5s --warmup-seconds 0.5 \
  --evidence-level controlled --cpu-affinity 0 \
  --build-command \
    'cmake --build build-benchmark --target csv2_benchmark csv2_benchmark_allocations --clean-first --parallel' \
  --post-build-command \
    'cmake --build build-benchmark --target csv2_benchmark_corpus' \
  --output build-benchmark/fixed-machine.json
```

Controlled metrics currently require Linux, at least 20 repetitions, matching
CPU affinity, positive warmup, a libpfm-enabled Google Benchmark build, and
complete cycles/instructions/branch-misses plus RSS/size and clean-build timing
collection. The untimed post-build command must regenerate and check
`csv2_benchmark_corpus` after `--clean-first`, so corpus generation does not
pollute compilation time while the measured input and uploaded manifest remain
available. The wire revision must exactly match `--revision`. The
declared compiler executable and the hashed `compile_commands.json` must agree,
binding the report to the actual current-tree build. Both pipelines hash their
entry point and complete imported Python helper closure as one deterministic
source bundle; A/B rejects an A/A calibration produced by a different bundle.
`--skip-pmu`, `--skip-rss`, and `--skip-size` are smoke-only relaxations.

## Evidence classes and protocols

- `exploratory` is suitable for GitHub-hosted runners and local smoke tests.
  Reports are reviewable artifacts but cannot support a regression verdict.
- `controlled` requires a stable Linux machine, fixed affinity, A/A noise
  calibration, three or more warmups, and at least 20 paired runs. Only a
  completed controlled report is decision-eligible.

The fixed contracts are `csv2-common-v2`, `csv2-current-v2`,
`csv2-benchmark-report-v3`, and `csv2-fixed-machine-metrics-v3`. Older or
unknown versions are rejected rather than converted. Every completed JSON has
a sibling SHA-256 artifact manifest. See
[`protocol/README.md`](protocol/README.md) for the wire boundary and schemas.

The manual `Performance evidence` workflow produces exploratory artifacts on
a hosted runner or controlled artifacts only on a self-hosted runner carrying
the `csv2-perf` label. When `candidate_ref` is supplied, the workflow checks
out that revision before building the current-tree benchmark and verifies the
resolved source `HEAD` against the report revision. This Stage B infrastructure
change makes no library performance claim.
