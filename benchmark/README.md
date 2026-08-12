# CSV2 benchmark suite

`csv2_benchmark` prepares buffer or mmap sources before starting the operation
timer, then prints a deterministic checksum plus GiB/s, rows/s, cells/s, and
optional allocation counts. Supported operations are `map_only`,
`rows_only`, `rows_cells`, `raw_to_string`, `decoded_to_string`,
`decoded_to_vector`, `ranges_pipeline`, `integer_conversion`, `writer_raw`,
and `writer_escaped`. All operations except `map_only` accept both `buffer` and
`mmap` sources.

The separate `csv2_benchmark_allocations` executable replaces C++ `new`/`new[]`
to count calls and requested bytes inside the timed operation. Pass it
`--track-allocations`; `--expect-allocations N` additionally turns that count
into a deterministic assertion. CI uses this instrumented binary to prove
structural row/cell traversal remains allocation-free, while normal throughput
runs use the uninstrumented `csv2_benchmark` executable.

Generate the deterministic corpora in an ignored build directory:

```bash
python3 benchmark/generate_datasets.py build/benchmark-data --rows 10000
```

First calibrate A/A noise on the fixed machine, then compare baseline and
candidate executables. The runner alternates execution order, requires at
least 20 samples, checks result checksums, and records medians, MAD, and a 95%
bootstrap interval:

```bash
python3 benchmark/run_suite.py \
  --baseline build-baseline/benchmark/csv2_benchmark \
  --candidate build-candidate/benchmark/csv2_benchmark \
  --datasets build/benchmark-data --runs 20 --iterations 10 \
  --output build/benchmark-report.json
```

`--runs` controls the number of independently launched, alternating samples.
`--iterations` repeats the selected operation inside each timed sample; increase
it until each sample is long enough to dominate timer and scheduler noise.

A regression is reported only when candidate median throughput drops by more
than `max(5%, 2 * baseline_MAD / baseline_median)` and the complete bootstrap
interval is below parity. Retain an optimization only when its target case
improves under the same rule and short unquoted, quote-heavy, multiline, and
CRLF cases show no significant regression.

On Linux, `collect_metrics.py` records operation-scoped hardware counters,
cycles/byte, instructions/byte, branch misses, peak RSS, allocation counts, and
executable text/data/BSS sizes in one JSON report. The benchmark opens a
disabled `perf_event_open` group and enables it only around the same operation
measured by the throughput timer; source preparation and result formatting are
excluded. Reports retain every raw sample, its multiplexing scale, the median,
and the MAD. Peak RSS is explicitly labeled `whole_process` because it includes
source preparation. The script can also time a quoted clean build command:

```bash
python3 benchmark/collect_metrics.py \
  --executable build/benchmark/csv2_benchmark \
  --operation rows_cells --input build/benchmark-data/short_unquoted.csv \
  --source buffer --iterations 20 --runs 20 \
  --build-command 'cmake --build build --clean-first --parallel' \
  --output build/fixed-machine-metrics.json
```

Hosted CI only compiles this suite and verifies the small-fixture checksums; it
never enforces timing thresholds.

Use `--skip-counters` (the legacy spelling `--skip-perf` remains accepted),
`--skip-rss`, or `--skip-size` only for smoke-testing on machines without the
corresponding Linux facilities.
