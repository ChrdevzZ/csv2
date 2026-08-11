# CSV2 benchmark suite

`csv2_benchmark` measures one operation at a time and prints a deterministic
checksum plus GiB/s, rows/s, and cells/s. Supported operations are `map_only`,
`rows_only`, `rows_cells`, `raw_to_string`, `decoded_to_string`,
`decoded_to_vector`, `ranges_pipeline`, `integer_conversion`, `writer_raw`,
and `writer_escaped`. All operations except `map_only` accept both `buffer` and
`mmap` sources.

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
  --datasets build/benchmark-data --runs 20 \
  --output build/benchmark-report.json
```

A regression is reported only when candidate median throughput drops by more
than `max(5%, 2 * baseline_MAD / baseline_median)` and the complete bootstrap
interval is below parity. Retain an optimization only when its target case
improves under the same rule and short unquoted, quote-heavy, multiline, and
CRLF cases show no significant regression.

On Linux, collect hardware counters around an individual fixed case with
`perf stat -r 20 -e cycles,instructions,branches,branch-misses`; divide cycles
and instructions by the reported processed bytes. Record peak RSS with
`/usr/bin/time -v`, allocations with the platform allocator profiler, text/code
size with `size`, and clean compilation time with `/usr/bin/time`. Hosted CI
only compiles this suite and verifies the small-fixture checksums; it never
enforces timing thresholds.
