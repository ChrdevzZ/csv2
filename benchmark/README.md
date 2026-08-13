# CSV2 benchmark suite

The suite has two deliberately separate roles:

- `csv2_benchmark` measures operations available in the current source tree.
- `common_driver.cpp` is a C++11, version-neutral adapter used for reviewable
  baseline/candidate comparisons.

Do not compile each revision's historical `benchmark/main.cpp` and compare the
outputs. Its command line, output protocol, and timed scope have changed. The
common driver must be the same source file and use the same compiler and flags
for both header trees.

Numeric command-line values use canonical unsigned ASCII decimal syntax. Signs,
whitespace, non-digits, and values outside the destination type are rejected
before any input preparation or measurement begins. `--iterations` must be
greater than zero; checksum and allocation expectations may be zero.

## Current-tree operation checks

`csv2_benchmark` prepares buffer or mmap sources before starting the operation
timer, except that mapping is the timed work for `map_only`. It then prints a
deterministic checksum plus GiB/s, rows/s, cells/s, and optional allocation
counts. GiB/s is normalized by input-corpus bytes for every operation,
including writers; it is not writer output bandwidth. Supported operations are
`map_only`, `rows_only`, `rows_cells`, `raw_to_string`, `decoded_to_string`,
`decoded_to_vector`, `ranges_pipeline`, `integer_conversion`,
`writer_raw_direct`, `writer_raw_streamable`, `writer_escaped_direct`, and
`writer_escaped_streamable`. All operations except `map_only` accept buffer
and mmap sources.

The writer names describe the dispatch path as well as the output policy.
`direct` passes contiguous character fields without an `operator<<` overload;
`streamable` uses an explicit inserter to force generic stream formatting.
The escaped operations share the same strings decoded before the timer,
hardware-counter scope, and allocation reset: the direct form passes each
`std::string`, while the streamable form passes a non-owning wrapper. CSV
decoding remains the separate `decoded_to_string` operation. The direct writer
allocation checks require zero allocations inside the measured operation.

The separate `csv2_benchmark_allocations` executable replaces C++
`new`/`new[]` to count calls and requested bytes inside the timed operation.
Pass it `--track-allocations`; `--expect-allocations N` additionally makes the
count a deterministic assertion. CI uses this instrumented binary to prove
structural row/cell traversal remains allocation-free. Normal throughput runs
use the uninstrumented executable.

```bash
CANDIDATE="$(git rev-parse HEAD)"
cmake -S . -B build-benchmark -G Ninja \
  -DCSV2_BUILD_TESTS=ON \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCSV2_BENCHMARK_REVISION="$CANDIDATE" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-benchmark --parallel
ctest --test-dir build-benchmark -L benchmark-checksum \
  --no-tests=error --output-on-failure
```

These current-tree operations may establish absolute behavior, checksum, and
allocation contracts. Operations that do not exist in the baseline cannot
support a cross-revision speedup claim.

## Reproducible baseline/candidate comparison

Generate deterministic short, wide, quote-heavy, doubled-quote, multiline,
CRLF, trailing-empty, and long-field corpora outside the source tree:

```bash
python3 benchmark/generate_datasets.py build/benchmark-data --rows 10000
```

Extract the exact baseline headers, then compile the tracked common driver
twice. The example baseline is the parent of this modernization; substitute
the review's exact base revision when necessary.

```bash
BASE=9504e0b
CANDIDATE="$(git rev-parse HEAD)"
mkdir -p build
COMPARE="$(mktemp -d build/compare.XXXXXX)"
mkdir "$COMPARE/base-tree" "$COMPARE/candidate-tree"
git archive "$BASE" include | tar -x -C "$COMPARE/base-tree"
git archive "$CANDIDATE" include benchmark/common_driver.cpp |
  tar -x -C "$COMPARE/candidate-tree"
DRIVER="$COMPARE/candidate-tree/benchmark/common_driver.cpp"

g++ -std=c++11 -O3 -DNDEBUG \
  -I"$COMPARE/base-tree/include" \
  -DCSV2_BENCHMARK_REVISION="\"$BASE\"" \
  "$DRIVER" -o "$COMPARE/baseline"
g++ -std=c++11 -O3 -DNDEBUG \
  -I"$COMPARE/candidate-tree/include" \
  -DCSV2_BENCHMARK_REVISION="\"$CANDIDATE\"" \
  "$DRIVER" -o "$COMPARE/candidate"

"$COMPARE/baseline" --describe
"$COMPARE/candidate" --describe
```

The shared protocol always exposes these comparison operations:

- `rows_cells`: input preparation is outside the timer; only row/cell
  traversal is timed. Buffer and mmap sources are supported when available.
- `legacy_writer_raw`: raw rows are materialized before the timer and only the
  historical Writer call is timed. It is available against the pre-modernized
  header tree and uses the `writer_only` scope.
- `legacy_mmap_rows_cells`: each iteration maps and traverses the file inside
  the timer, while reader destruction and unmapping remain outside it. This
  reproduces the scope of the original positional benchmark. This operation
  only supports the `mmap` source; the runner rejects a selection that requests
  it without `mmap` rather than silently changing the requested source.

Defining `CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1` when compiling both
sides additionally exposes the current four direct/streamable Writer
operations. Use that mode only when both compared header revisions provide the
modern Writer interfaces. Leave it undefined for the `9504e0b` modernization
comparison. For example, a Review(3)-only comparison against `5235deb` adds
the same definition to both compile commands:

```bash
MODERN_WRITER=-DCSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1
g++ -std=c++11 -O3 -DNDEBUG $MODERN_WRITER \
  -I"$COMPARE/base-tree/include" \
  -DCSV2_BENCHMARK_REVISION="\"$BASE\"" "$DRIVER" -o "$COMPARE/baseline"
g++ -std=c++11 -O3 -DNDEBUG $MODERN_WRITER \
  -I"$COMPARE/candidate-tree/include" \
  -DCSV2_BENCHMARK_REVISION="\"$CANDIDATE\"" "$DRIVER" -o "$COMPARE/candidate"
```

Every comparison operation emits a deterministic checksum. Traversal operations
compute an untimed raw-content checksum; Writer operations hash the bytes sent
to the output stream inside the measured scope. The runner rejects any
same-operation semantic mismatch before making a performance decision.

Calibrate A/A noise with the exact candidate executable that will be compared.
Then run A/B with the same datasets, cases, iterations, compiler description,
flags, and machine:

```bash
COMPILER="$(g++ --version | sed -n '1p')"
FILES=short_unquoted.csv,wide_rows.csv,quote_heavy.csv,doubled_quotes.csv,\
quoted_lf.csv,crlf.csv,empty_and_trailing.csv,long_field.csv

python3 benchmark/run_suite.py \
  --baseline "$COMPARE/candidate" \
  --candidate "$COMPARE/candidate" \
  --baseline-revision "$CANDIDATE" \
  --candidate-revision "$CANDIDATE" \
  --adapter-source "$DRIVER" \
  --datasets build/benchmark-data --files "$FILES" \
  --operations rows_cells --sources buffer \
  --runs 20 --warmups 3 --iterations 10 --mode aa \
  --compiler "$COMPILER" \
  --compiler-flags='-std=c++11 -O3 -DNDEBUG' \
  --output "$COMPARE/calibration.json"

python3 benchmark/run_suite.py \
  --baseline "$COMPARE/baseline" \
  --candidate "$COMPARE/candidate" \
  --baseline-revision "$BASE" \
  --candidate-revision "$CANDIDATE" \
  --adapter-source "$DRIVER" \
  --datasets build/benchmark-data --files "$FILES" \
  --operations rows_cells --sources buffer \
  --runs 20 --warmups 3 --iterations 10 --mode compare \
  --calibration "$COMPARE/calibration.json" \
  --compiler "$COMPILER" \
  --compiler-flags='-std=c++11 -O3 -DNDEBUG' \
  --output "$COMPARE/comparison.json"
```

For the whole-modernization comparison select
`rows_cells,legacy_mmap_rows_cells,legacy_writer_raw` with the appropriate
buffer/mmap sources. For a modern Writer-only comparison compile both sides
with the opt-in definition and select the four modern Writer operations.

The runner alternates launch order and retains every warmup and measured
launch, command, raw stdout/stderr, and derived throughput. It also records
executable, adapter, runner, and dataset SHA-256 hashes; declared revisions;
compiler and flags; recorded host identity; a best-effort CPU identity and its
source; logical CPU count; medians; MAD; and a deterministic paired-bootstrap
95% interval. Reports are atomically checkpointed after each case and carry
`running`, `completed`, or `failed` status; only completed A/A reports are
accepted as calibration.
All input artifacts are resolved to canonical paths before description,
hashing, or invocation. The logical dataset names remain stable in the report,
but execution and revalidation use the resolved targets. The report output is
rejected when it is the same path, symlink, or hardlink as the runner, adapter,
either executable, the calibration, or any selected CSV. Before marking a
report completed, the runner revalidates both executables, the shared adapter,
the runner, the calibration, and every dataset against their recorded bytes
and SHA-256. Checkpoints use a unique temporary file in the output directory,
flush and sync it, then atomically replace the report.

A regression is reported only when candidate median throughput drops by more
than the maximum of 5%, the comparison's baseline noise, and the matching A/A
noise, and the complete bootstrap interval is below parity. The runner rejects
a calibration produced with another candidate binary, adapter, runner,
dataset, compiler context, run count, iteration count, warmup count, or
recorded host identity. Use
`--allow-uncalibrated` only for smoke tests, never for a performance claim.

Retain an optimization only when its target case improves under this rule and
short-unquoted, quote-heavy, multiline, CRLF, wide-row, and long-field cases
show no significant regression. Keep the JSON report with the review evidence;
summary numbers without that report are not reproducible results.

## Fixed-machine counters

On Linux, `collect_metrics.py` records operation-scoped hardware counters,
cycles/byte, instructions/byte, branch misses, peak RSS, allocation counts, and
executable text/data/BSS sizes. The benchmark enables its `perf_event_open`
group only around the same operation measured by the throughput timer. Counters
cover the calling thread in both user and kernel mode (hypervisor execution is
excluded), so `map_only` includes its mapping syscalls rather than reporting a
user-space fragment as the complete operation. The fixed machine must permit
kernel-inclusive per-thread counters; collection fails instead of silently
falling back to user-only data. Peak RSS is labeled `whole_process` because it
includes source preparation.

The JSON retains every raw counter sample and multiplexing scale plus machine
identity, best-effort CPU identity and its source, compiler, flags, revision,
executable/allocation-executable hashes, dataset hash, collector hash, every
benchmark/RSS/build command and raw stdout/stderr, checksum results, medians,
and MAD:

The current-tree executables emit the configured `CSV2_BENCHMARK_REVISION`;
the collector rejects a result whose embedded revision differs from
`--revision`. When `--build-command` is present, that command completes before
the executables are canonicalized, checked for output aliases, hashed, or
measured, and its working directory and raw output are retained. Before
publishing the report, the collector revalidates the collector source, both
executables, and the dataset against their recorded sizes and SHA-256 hashes.
Its checkpoints use the same unique-temporary-file and atomic-replace protocol
as the suite runner.

```bash
python3 benchmark/collect_metrics.py \
  --executable build-benchmark/benchmark/csv2_benchmark \
  --allocation-executable \
    build-benchmark/benchmark/csv2_benchmark_allocations \
  --revision "$CANDIDATE" \
  --compiler "$COMPILER" \
  --compiler-flags='-O3 -DNDEBUG -std=c++20' \
  --operation rows_cells \
  --input build/benchmark-data/short_unquoted.csv \
  --source buffer --iterations 20 --runs 20 \
  --build-command 'cmake --build build-benchmark --clean-first --parallel' \
  --output build/fixed-machine-metrics.json
```

Use `--skip-counters` (the legacy `--skip-perf` spelling remains accepted),
`--skip-rss`, or `--skip-size` only for smoke testing on machines without the
corresponding Linux facilities.

Hosted CI compiles the suite and verifies small-fixture checksums. It never
enforces timing or hardware-counter thresholds.

When `CSV2_HAS_MMAP` is not set as a CMake variable, the benchmark build probes
the same public header used by its executables and registers mmap checksum tests
only when that probe succeeds. Configure with `-DCSV2_HAS_MMAP=0` for an
explicit no-mmap benchmark build; the value is propagated to every benchmark
target, and the checksum suite verifies that mmap operations are rejected.
