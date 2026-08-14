# Benchmark protocols

CSV2 benchmark artifacts are versioned contracts. Producers and consumers
reject unknown and older versions; there is no implicit migration path.

| Contract | Version | Purpose |
| --- | --- | --- |
| common driver wire | `csv2-common-v3` | one self-described C++11 comparison result |
| current verify wire | `csv2-current-v2` | exact checksum and allocation verification |
| build manifest | `csv2-benchmark-build-v1` | immutable source and audited build identity |
| comparison report | `csv2-benchmark-report-v4` | paired A/A or A/B samples and decisions |
| fixed-machine metrics | `csv2-fixed-machine-metrics-v4` | timing, PMU, RSS, size, and provenance |
| artifact manifest | `csv2-artifact-manifest-v2` | report, build, and tool-bundle digests |

Wire output is one whitespace-separated line of unique `key=value` fields.
Integer checksums are canonical decimal `uint64_t`; they never pass through a
floating-point benchmark counter. A failed or unsupported kernel returns a
nonzero process status and does not emit a success wire.

JSON producers validate both the closed schemas in `schemas/` and the
standard-library semantic rules in `tools/csv2bench/protocol.py`. The semantic
layer enforces lifecycle, revision, owned-build, calibration, affinity,
sample-count, verification, allocation, timing, PMU, RSS, code-size, and build
evidence relationships that are awkward to express in JSON Schema. New fields
are allowed only in objects explicitly marked extensible.

## Build ownership and identity

`csv2-benchmark-build-v1` has two kinds:

- `common-driver` exports the exact header tree and the candidate adapter from
  immutable Git blobs, rejects links and unsafe paths, and records every blob
  OID/hash, the compiler path/hash/version, full and normalized argv, build
  output, and executable hash.
- `current-tree` exports the complete candidate tree, creates an isolated
  CMake/Ninja Release build, and audits the File API codemodel,
  `compile_commands.json`, target compile groups, include roots, revision
  definition, caller-supplied compiler flags, link commands, executables, and
  generated corpus manifest. Every exported blob, tool, build record, target,
  and corpus manifest is rehashed after measurement before completion.

The tools re-read Git objects and all build inputs before completion. A build
identity digest omits incidental workspace paths but includes every semantic
input and output. Baseline and candidate common drivers must use equivalent
normalized commands apart from the declared revision/include/output slots.
MSVC common-driver builds add deterministic path mapping and reproducible
linking arguments so the same Git objects retain one audited identity across
separate A/A and A/B workspaces; those arguments remain visible in the build
manifest.

Owned builds are the default. `--external-artifacts` is an explicit legacy
escape hatch restricted to `exploratory`; it can never make a report
decision-eligible.

## Reports

`csv2-benchmark-report-v4` embeds both common-driver build manifests, exact
artifacts and descriptions, operation scope/source contracts, datasets, host,
compiler context, complete Python runner bundle, launch order, raw samples,
and derived statistics. A/B accepts only a completed A/A report with the same
candidate build identity, runner/adapter bundle, datasets, affinity, flags,
run count, warmups, and iterations.

`csv2-fixed-machine-metrics-v4` embeds the owned current-tree build manifest
and binds semantic verification, allocation verification, Google Benchmark
samples, PMU counters, peak RSS, code size, and clean isolated build timing.
Controlled reports require cycles, instructions, branch misses, RSS, size,
positive warmup, at least 20 repetitions, exact affinity, and complete
invocation records.

Report lifecycle is `running` to `completed` or `failed`. Only a completed,
owned, controlled document satisfying every semantic gate may set
`decision_eligible=true`. Protocol validity proves the recorded artifact and
measurement relationship; it does not independently prove that a machine is
thermally or operationally stable.

Every completed report is accompanied by `csv2-artifact-manifest-v2`. Writers
reject direct, symlink, and hardlink output aliases, create a unique temporary
file in the destination directory, flush and fsync it, atomically replace the
destination, and then publish the bound SHA-256 manifest.
