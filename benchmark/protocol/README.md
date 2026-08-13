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

The JSON schemas in `schemas/` close and define the stable top-level contract.
Producers also run the standard-library semantic validators in `protocol.py`
before publishing a completed report; those validators enforce cross-field
revision, lifecycle, run-count, affinity, calibration, and evidence rules that
JSON Schema cannot express concisely. Producers may add data only inside
explicitly extensible objects; a schema version change is required for
incompatible meaning or required-field changes.

## Producer and consumer rules

`csv2-common-v2` and `csv2-current-v2` are process-local verification wires.
They use canonical unsigned decimal fields, reject duplicate or unknown
required keys, and return a nonzero status for malformed arguments, semantic
mismatch, or an allocation-contract failure. Timing output is deliberately a
separate Google Benchmark JSON document.

`csv2-benchmark-report-v3` binds the common driver, both executables, exact
revisions, selected datasets, compiler context, host identity, every raw launch,
the complete Python tool source bundle, and derived paired statistics. Its
lifecycle is `running` → `completed` or
`failed`; a calibration consumer accepts only a completed A/A report with a
matching context.

`csv2-fixed-machine-metrics-v3` binds the current-tree executable, allocation
executable, collector, dataset, revision, compiler context, semantic verify,
timing samples, and the requested PMU/RSS/size/build measurements. Controlled
reports bind the compiler executable and `compile_commands.json`, cannot omit
any requested PMU counter, RSS, size, clean-build timing, or untimed generated
corpus restoration evidence, and are not decision-eligible until successful
completion.

Every completed report is accompanied by `csv2-artifact-manifest-v1`, which
records the report path and SHA-256. Producers canonicalize and hash every
input before use, reject output aliases, revalidate inputs before completion,
and publish with a same-directory atomic replace. These checks prevent a report
from describing one artifact while executing or overwriting another.

An `exploratory` report is never decision-eligible. A `controlled` comparison
must also satisfy the runner's minimum repetitions, affinity, and A/A
calibration contracts. Protocol validity establishes provenance and semantics;
it does not by itself prove stable hardware conditions.
