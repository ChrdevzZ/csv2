# Benchmark protocols

CSV2 benchmark artifacts are versioned contracts. Producers and consumers
reject unknown and older versions; there is no implicit migration path.

| Contract | Version | Purpose |
| --- | --- | --- |
| common driver wire | `csv2-common-v4` | one self-described C++11 comparison result |
| current verify wire | `csv2-current-v3` | exact checksum, allocation, and semantic identity |
| build manifest | `csv2-benchmark-build-v1` | immutable source and audited build identity |
| comparison report | `csv2-benchmark-report-v5` | paired A/A or A/B primary observations and derived results |
| fixed-machine metrics | `csv2-fixed-machine-metrics-v5` | bound timing, PMU, RSS, size, and provenance |
| complete evidence | `csv2-performance-evidence-bundle-v2` | cross-checked final decision gate |
| artifact manifest | `csv2-artifact-manifest-v3` | component/evidence inputs and output digests |
| machine profile | `csv2-machine-profile-v1` | reviewed identity and operating constraints for controlled evidence |

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
escape hatch restricted to `exploratory`; it can never participate in a
decision-eligible evidence bundle.

## Reports

`csv2-benchmark-report-v5` embeds both common-driver build manifests, exact
artifacts and descriptions, operation scope/source contracts, datasets, host,
compiler context, complete Python runner bundle, launch order, raw samples,
and derived statistics. Its validator reparses every saved stdout wire,
reconstructs the complete `(phase, round, order)` launch schedule, and
recomputes per-launch throughput, medians, MADs, deterministic paired-bootstrap
intervals, both-side comparison noise, calibrated A/A noise, thresholds, and
verdicts. Mutation of a primary observation or a derived field invalidates the
report. A/A requires the same revision, owned build identity, and executable
hash on both sides; A/B requires distinct commits. A/B accepts only a completed
A/A report with the same candidate build identity, runner/adapter bundle,
datasets, affinity, flags, run count, warmups, and iterations.

`csv2-fixed-machine-metrics-v5` embeds the owned current-tree build manifest
and binds semantic verification, allocation verification, Google Benchmark
samples, PMU counters, peak RSS, code size, and clean isolated build timing.
Its timing summaries are rederived from saved samples. A
`comparison_binding` names the exact dataset, semantic case ID, scope, source,
and byte basis that must match one and only one A/B case. Controlled reports
require cycles, instructions, branch misses, RSS, size, positive warmup, at
least 20 repetitions, exact affinity, and complete invocation records.

Every current and common wire carries a stable `semantic_case_id`, `scope`,
`source`, and `byte_basis`. These fields state what was measured independently
of either harness's operation spelling. A binding is rejected when any field
differs, so a metric for setup plus traversal cannot substantiate a
traversal-only comparison.

Component report lifecycle is `running` to `completed` or `failed`. A completed,
owned, controlled component satisfying its semantic gates sets
`controlled_complete=true`, but every v5 comparison or metrics report keeps
`decision_eligible=false`. This prevents an A/A, A/B, or fixed-metrics file from
claiming a final verdict in isolation.

`finalize_evidence.py` is the only final decision gate. It consumes an A/A
report, its A/B report, fixed-machine metrics, all three artifact manifests,
and the generated corpus manifest. It rehashes every input and corpus member,
then requires matching candidate revisions and source trees, compiler identity,
machine profile and affinity, candidate build identity, calibration reference,
and exact semantic comparison binding. The resulting
`csv2-performance-evidence-bundle-v2` may set
`decision_eligible=true` only when all three inputs are controlled-complete;
an exploratory bundle always sets it to false. Protocol validity proves the
recorded artifact and measurement relationship; it does not independently
prove that a machine is thermally or operationally stable.

Controlled A/A, A/B, and fixed metrics carry the same resolved
`csv2-machine-profile-v1` digest and runtime observation. The observation must
match the profile's CPU model, architecture, logical CPU count, allowed
affinity, kernel release, governor, and turbo/boost state. A generic Linux host
or affinity setting cannot self-declare controlled status. Exploratory evidence
does not require a profile and is never decision-eligible.

Every completed component and final evidence bundle is accompanied by
`csv2-artifact-manifest-v3`. Writers reject direct, symlink, and hardlink
output aliases and use unique, flushed and fsynced same-directory temporary
files. Component reports publish before their bound SHA-256 manifest. The
finalizer reverses that commit order: it stages the bundle, publishes the
manifest prerequisite, and atomically publishes the eligible bundle last, so
an interrupted run cannot leave an unbound decision document. Final evidence
paths must be new; the finalizer never overwrites a prior publication. A
fixed-metrics manifest closes and validates the collector source bundle, timing and
allocation executables, dataset, and (for an owned build) the paired compiler
executable and compile-command artifacts. Evidence manifests close the seven
component/corpus inputs plus the exact finalizer source bundle. The two
benchmark executables must declare the same revision, and every recorded digest
is canonical SHA-256.

Repeated source operations use explicit cache semantics.
`source/file-read-cached` does not claim cold-storage behavior, and
`source/mmap-touch-resident` does not claim first-page-fault cost. Actual timing
accepts one operation and one concrete compatible source per process; suite
orchestration starts separate processes rather than merging unrelated Context
preparation or peak RSS.
