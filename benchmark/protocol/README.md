# Benchmark protocols

CSV2 benchmark artifacts are deliberately versioned and are never converted
implicitly. A consumer must reject every unknown or older value.

| Contract | Version | Purpose |
|---|---|---|
| common driver wire | `csv2-common-v2` | one C++11 comparison result per process |
| current verify wire | `csv2-current-v2` | exact checksum and allocation verification |
| comparison report | `csv2-benchmark-report-v3` | paired A/A or A/B samples and decisions |
| fixed-machine metrics | `csv2-fixed-machine-metrics-v3` | timing, PMU, RSS, size, and provenance |

Wire output is a single whitespace-separated line of unique `key=value`
fields. Integer checksum fields are decimal `uint64_t`; they are not transported
through floating-point benchmark counters. Report writers use a unique
same-directory temporary file, flush and fsync it, then atomically replace the
destination.

The JSON schemas in `schemas/` define the stable top-level contract. Producers
may add data only inside explicitly extensible objects; a schema version change
is required for incompatible meaning or required-field changes.
