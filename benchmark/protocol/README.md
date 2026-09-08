# Benchmark protocols

CSV2 benchmark artifacts are versioned contracts. Producers and consumers
reject unknown and older versions; there is no implicit migration path.

| Contract | Version | Purpose |
| --- | --- | --- |
| common driver wire | `csv2-common-v5` | one self-described C++11 comparison result with explicit instrumentation and capabilities |
| current verify wire | `csv2-current-v4` | exact checksum, allocation, and semantic identity |
| build manifest | `csv2-benchmark-build-v2` | immutable source and audited build identity |
| comparison report | `csv2-benchmark-report-v7` | paired A/A or A/B primary observations and derived results |
| fixed-machine metrics | `csv2-fixed-machine-metrics-v8` | bound timing, PMU, RSS, size, and provenance |
| complete evidence | `csv2-performance-evidence-bundle-v4` | cross-checked final decision gate |
| artifact manifest | `csv2-artifact-manifest-v4` | component/evidence inputs and output digests |
| machine profile | `csv2-machine-profile-v1` | reviewed identity and operating constraints for controlled evidence |
| current case inventory | `csv2-benchmark-case-manifest-v3` | independent expected operation, source, dataset, and semantic contract |

Wire output is one whitespace-separated line of unique `key=value` fields.
Integer checksums are canonical decimal `uint64_t`; they never pass through a
floating-point benchmark counter. A failed or unsupported kernel returns a
nonzero process status and does not emit a success wire.

JSON producers validate reports with the standard-library rules in
`tools/csv2bench/protocol.py`. Contract tests also exercise the published closed
schemas in `schemas/` through an offline subset validator. The runtime validator
enforces lifecycle, revision, owned-build, calibration, affinity,
sample-count, verification, allocation, timing, PMU, RSS, code-size, and build
evidence relationships that are awkward to express in JSON Schema. New fields
are allowed only in objects explicitly marked extensible.

## Build ownership and identity

`csv2-benchmark-build-v2` has two kinds:

- `common-driver` exports the exact header tree and the candidate adapter from
  immutable Git blobs, rejects links and unsafe paths, and records every blob
  OID/hash, the compiler path/hash/version, full and normalized argv, build
  output, and executable hash.
- `current-tree` exports the complete candidate tree, creates an isolated
  CMake/Ninja Release build, and audits the File API codemodel,
  `compile_commands.json`, target compile groups, include roots, revision
  definition, caller-supplied compiler flags, link commands, executables, and
  generated corpus manifest. Every exported blob, tool, build record, target,
  and corpus manifest is rehashed after measurement before completion. Its
  ordered flags and audited compile groups must leave `-O2`, `-O3`, or `/O2`
  effective and must leave `NDEBUG` defined; a later debug optimization or
  undefinition override invalidates the build.

The tools batch-read Git blobs with exact object-type, size, framing, and OID
checks, and recheck exported files and build inputs before completion. Export
revalidation reconstructs the declared selection from the same immutable tree
listing and requires its complete file set to equal the manifest inventory.
Authentic blobs alone do not establish a complete export. Duplicate and
overlapping selections are rejected. Every
Git read disables replacement objects, including commit resolution, tree
traversal, blob export, and manifest verification, so local replacement refs
cannot change the content attributed to a recorded revision.
Common-driver comparison identities normalize the source and output location
slots needed for A/A and A/B compatibility. Current-tree provenance remains
bound to its isolated build workspace; it is not a relocatable cache identity.
Baseline and candidate common drivers must use equivalent normalized commands
apart from the declared revision/include/output slots.
MSVC common-driver builds add deterministic path mapping and reproducible
linking arguments so the same Git objects retain one audited identity across
separate A/A and A/B workspaces; those arguments remain visible in the build
manifest.

GNU/Clang common builds run from the exported adapter root and apply builder-owned
`-ffile-prefix-map` arguments to both adapter and header roots. Debug information
and file macros therefore use stable logical paths, including for `-g3`, across
separate A/A and A/B workspaces. Actual and normalized commands are checked
together; caller-supplied path mappings remain forbidden. Debug symbols are
retained, and A/A still requires identical executable hashes.
Byte-identical debug builds have been verified with GCC and Clang on Linux;
this does not establish reproducibility for every compiler and target format.

Owned builds are the default. `--external-artifacts` is an explicit mode
restricted to `exploratory`; it can never participate in a decision-eligible
evidence bundle. External build/post-build hooks are preparation: afterward,
executables, datasets, and the compilation database are rebound, and compiler
matching is recomputed. The declared compiler identity remains fixed. Once
measurement starts, subsequent artifact drift is rejected.

The common-driver build manifest records `instrumentation=none` and its ordered
capability set. Legacy reader and Writer capabilities are always present;
`modern-writer` is present only when a requested operation needs the modern
Writer adapter. Operation, source, and dataset selections are validated before
the owned builder exports any Git object, and runtime descriptions/results must
match the recorded build capabilities. Both the online builder and offline
report validator require the build command to define timer auditing as disabled,
bind the exact revision, and include the modern Writer definition exactly when
the recorded capability requires it; caller compiler flags cannot override these
reserved definitions.
Response files and forced preprocessor inputs are not accepted in owned common
driver compiler flags because the manifest cannot audit their hidden contents;
preprocessor pass-through options are rejected for the same reason.
MSVC options and macro names retain compiler case sensitivity: `/O2 /DNDEBUG`
is valid; `/o2 /dNDEBUG` is not an equivalent spelling.

## Reports

`csv2-benchmark-report-v7` embeds both common-driver build manifests, exact
artifacts and descriptions, operation scope/source contracts, datasets, host,
compiler context, complete Python runner bundle, launch order, raw samples,
and derived statistics. Its validator reparses every saved stdout wire,
reconstructs the complete `(phase, round, order)` launch schedule, and binds
each launch argv to its side's executable, dataset path, operation,
source, and iteration count. Description argv and saved wire output must match
the structured driver description. Validation also recomputes per-launch
throughput, medians, MADs, deterministic paired-bootstrap intervals, both-side comparison noise, calibrated A/A noise, thresholds, and
verdicts. Mutation of a primary observation or a derived field invalidates the
report. A/A requires the same revision, owned build identity, and executable
hash on both sides; A/B requires distinct commits. A/B accepts only a completed
A/A report with the same candidate build identity, runner/adapter bundle,
datasets, affinity, flags, run count, warmups, and iterations.
The online runner and finalizer share the run-count, warmup, and
iterations-per-run comparison rule; internally valid reports with different
sampling settings cannot form calibrated evidence.

`csv2-fixed-machine-metrics-v8` embeds the owned current-tree build manifest
and binds semantic verification, allocation verification, Google Benchmark
samples, PMU counters, peak RSS, code size, and clean isolated build timing.
The collector reuses the canonical compiler artifact selected by the owned
builder, whether the CLI supplied a program name or an absolute path.
Owned and external collection select the compiler's version interface: native
MSVC uses `/Bv /?`, while GNU and Clang use `--version`. Both output streams
are retained; failed probes and identities with no non-whitespace output are
rejected. Probe environments remain owned by their respective collection paths.
`build_argv` and `build_log` cover compilation and linking of the two benchmark
executables and their declared dependencies. Corpus generation follows in
`corpus_argv` and `corpus_log`, outside the clean-build interval; its manifest
remains bound to the build. Both commands are checked against the controlled
contract. `clean_build` must match the recorded build command, duration, and
output. Owned `post_build` is null: successful build and preparation records
already reside in the build manifest. External exploratory collection retains
its optional real post-build hook.
Timing, PMU, and RSS subprocesses remove inherited `BENCHMARK_*` variables
(case-insensitively), so their Google Benchmark settings come from the collector
commands and library defaults. Ordinary timing does not inherit dry-run or PMU
overrides. RSS also sets `LC_ALL=C`. Build and post-build hooks retain their
existing environment policy. This is measurement-option control, not complete
isolation of dynamic libraries or system state.
Earlier combined build-and-corpus durations are not directly comparable, and
subtracting a separately measured generator duration cannot recover the original
compilation interval. These internal command contracts reject older combined
records; no report conversion or parallel compatibility route is provided.
Its verification and allocation fields are reconstructed from their recorded
stdout, and their operation, revision, input, and semantic context must agree.
Writer allocation accounting covers one execution of the prepared rows. Historical
revisions that executed verification twice report cumulative allocations for two
writes; revision and build identity must be considered before comparing those
measurements with single-execution results.
Saved commands and benchmark names must match the bound artifacts and selected
operation. Timing and PMU summaries are rederived from saved samples, and each
real-time sample must satisfy `seconds * bytes_per_second = input corpus size`
within floating-point rounding tolerance. The input size is the dataset
artifact size, which can differ from the operation's verified output bytes. A
`comparison_binding` names the exact dataset, semantic case ID, scope, source,
and byte basis that must match one and only one A/B case. Controlled reports
require cycles, instructions, branch misses, RSS, size, positive warmup, at
least 20 repetitions, exact affinity, and complete invocation records.
Fixed-metrics v8 retains GNU time output in `peak_rss.time_output` and GNU
size stdout/stderr in `code_size`. The collector and offline validator share
the parsers used to reconstruct the structured values. RSS is whole-process
peak resident memory (`%M` in KiB), measured with one repetition and no extra
warmup; its wrapped benchmark argv must match the bound executable, input,
operation, and source. GNU size uses decimal Berkeley output bound to the same
executable. Its text/data/bss total is a section measure, not filesystem size;
Berkeley text includes read-only data. Filesystem fallback must equal the
executable artifact size and use `method: "filesystem"`. Older fixed-metrics
formats lack the required raw evidence and are rejected without conversion.

GNU peak-RSS and section-size collection is Linux-only. On other platforms,
including macOS, exploratory reports record `peak_rss: null` and code size as
filesystem `file_bytes` with `method: "filesystem"`. These fallbacks do not satisfy
controlled evidence requirements. Errors from supported Linux tools remain fatal.
Non-Linux component collection does not imply complete evidence-finalization
support: finalization still requires observable, non-empty affinity and matching
machine identities; unavailable CPU affinity is never replaced with a fabricated value.

Every current and common wire carries a stable `semantic_case_id`, `scope`,
`source`, and `byte_basis`. These fields state what was measured independently
of either harness's operation spelling. A binding is rejected when any field
differs, so a metric for setup plus traversal cannot substantiate a
traversal-only comparison.

Raw Writer IDs explicitly distinguish input representations:

| Operation | Common driver: original CSV fields | Current driver: decoded content |
| --- | --- | --- |
| raw-direct | `csv2.writer.raw-direct.raw-fields.v1` | `csv2.writer.raw-direct.decoded-content.v1` |
| raw-streamable | `csv2.writer.raw-streamable.raw-fields.v1` | `csv2.writer.raw-streamable.decoded-content.v1` |

The common raw paths preserve original quotes and escaping through borrowed
pointer/length references. Current raw paths consume decoded prepared strings.
They cannot substantiate each other's measurements. The ambiguous IDs
`csv2.writer.raw-direct.v1` and `csv2.writer.raw-streamable.v1` are retired and
rejected even in otherwise current-version reports. No silent reinterpretation
or cross-harness checksum equality substitutes for this contract.

Component report lifecycle is `running` to `completed` or `failed`. A completed,
owned, controlled component satisfying its semantic gates sets
`controlled_complete=true`, but every v7 comparison or metrics report keeps
`decision_eligible=false`. This prevents an A/A, A/B, or fixed-metrics file from
claiming a final verdict in isolation.

`finalize_evidence.py` is the only final decision gate. It consumes an A/A
report, its A/B report, fixed-machine metrics, all three artifact manifests,
and the generated corpus manifest. It rehashes every input and corpus member,
then requires matching candidate revisions and source trees, compiler identity,
machine profile and affinity, candidate build identity, calibration reference,
and exact semantic comparison binding. The resulting
`csv2-performance-evidence-bundle-v4` may set
`decision_eligible=true` only when all three inputs are controlled-complete;
an exploratory bundle always sets it to false. Protocol validity proves the
recorded artifact and measurement relationship; it does not independently
prove that a machine is thermally or operationally stable.

Finalization validates each loaded component report and rebuilds its derived
statistics once, then assembles one bundle. Publication still rechecks mutable
artifacts, builds and source exports, the profile file, and every corpus member;
those file checks do not repeat the unchanged samples' statistical calculations.

Build-input sanitization, Google Benchmark option control, and controlled runtime
policy are separate boundaries. Controlled collectors reject non-empty
`LD_PRELOAD` and `LD_AUDIT` settings before preparation, when loading the machine
profile, and at the existing sampling/completion boundaries. They require a
restart from a clean environment: filtering child-process variables cannot unload
libraries already loaded into the collector. Library search paths and required
SDK settings retain their existing policy. Intentional preload profiling remains
exploratory and must not be promoted to controlled evidence. The managed host,
system runtime (including system-wide loader configuration), and toolchain remain
trusted prerequisites; these checks do not establish complete runtime isolation.
See the [Linux dynamic loader documentation](https://man7.org/linux/man-pages/man8/ld.so.8.html)
for the distinct effects of injection and library search variables.

Controlled A/A, A/B, and fixed metrics carry the same resolved
`csv2-machine-profile-v1` digest and runtime observation. The observation must
match the profile's CPU model, architecture, logical CPU count, allowed
affinity, kernel release, governor, and turbo/boost state. A generic Linux host
or affinity setting cannot self-declare controlled status. Each controlled
report also binds its architecture, CPU model, logical CPU count, and actual
affinity to that observation; fixed metrics additionally bind the system and
kernel release. Agreement among components alone is insufficient. Affinity
must equal the recorded observation, not merely belong to `allowed_affinity`.
Collectors reobserve
this state before warmup/sampling and before completion; comparisons also check
case boundaries. CPU identifiers are explicit nonnegative identifiers, not
positions in a range derived from the logical CPU count. Actual affinity must
match the requested selection and remain within the reviewed profile. Mixed
governor observations retain each selected CPU's governor, so exchanging
governors between CPUs changes the observation. Uniform governor and
`unavailable` representations are unchanged. Existing profiles containing only
a mixed governor name set must be reviewed again against the actual machine;
the missing CPU associations cannot be inferred. Partially readable governor
state is rejected. These are
boundary checks, not continuous monitoring or a guarantee against all benchmark
noise. Offline binding validation and finalization never observe the reviewer's
machine. Exploratory evidence
does not require a profile and is never decision-eligible. The finalizer
reparses the bound profile artifact and requires its JSON content to equal the
profile embedded in all three component reports; a matching filename or digest
field alone is insufficient.

Every completed component and final evidence bundle is accompanied by
`csv2-artifact-manifest-v4`. Writers reject direct, symlink, and hardlink
output aliases and use unique, flushed and fsynced same-directory temporary
files. Component reports publish before their bound SHA-256 manifest. The
finalizer reverses that commit order: it stages the bundle, publishes the
manifest prerequisite, and atomically publishes the eligible bundle last, so
an interrupted run cannot leave an unbound decision document. Final evidence
paths must be new; the finalizer never overwrites a prior publication. A
fixed-metrics manifest closes and validates the collector source bundle, timing and
allocation executables, dataset, and (for an owned build) the paired compiler
executable and compile-command artifacts. External exploratory collection may
bind only the compiler artifact, with an unverified (null) compile-command
match count. A compile-command artifact always requires a compiler artifact;
owned builds require both. Evidence manifests close the seven
component/corpus inputs plus the exact finalizer source bundle. The two
benchmark executables must declare the same revision, and every recorded digest
is canonical SHA-256.

Repeated source operations use explicit cache semantics.
`source/file-read-cached` does not claim cold-storage behavior, and
`source/mmap-touch-pretouched` touches the same 4096-byte stride addresses and
final byte in setup and in the timed kernel. It does not claim first-page-fault
cost or continued OS residency. Actual timing
accepts one operation and one concrete compatible source per process; suite
orchestration starts separate processes rather than merging unrelated Context
preparation or peak RSS.

Corpus validation closes each strict diagnostic to `code`, `byte_offset`,
`row`, and `column` and checks it against the dataset's valid/invalid state.
Malformed or internally inconsistent diagnostics cannot enter a finalized
bundle even when the corpus file hashes themselves are correct.

## Controlled build inputs (build v2)

Build v2 requires `input_policy` and `dependencies`; build v1 is rejected.
Comparison v7, fixed-machine v7, artifact-manifest v4, and evidence-bundle v4
carry this stronger contract. `csv2-compile-dependencies-v2` records consumed
first-party paths and SHA-256 values against immutable Git exports, compiler
system inputs and roots, and every current-tree owned translation unit.
Missing, stale, incomplete, shadowed, or outside dependency evidence fails the
build before measurements. The common driver uses full GCC/Clang `-MD`
dependencies or MSVC `/sourceDependencies`; current-tree builds read Ninja's
actual object compilation dependency database, including shared core objects.
A separate preprocessing search-path probe identifies trusted compiler/SDK roots;
it does not substitute for the dependencies from the real compilation.

Caller flags use a compiler-family allowlist. Supported configurations include
optimization levels, `NDEBUG` definitions (split or joined), C++ standards,
GCC/Clang `-march`/`-mtune`/`-mcpu` and common SSE/AVX switches, `-stdlib`,
exceptions/RTTI/frame-pointer/aliasing/fast-math controls, LTO, debugging and
basic warnings; MSVC supports `/O`, `/std`, `/arch`, `/EHsc`, `/GR`, runtime,
floating-point, warnings, and reproducibility switches. Unknown options fail
closed. Input/search paths, forced includes, response/config files, compiler
plugins/specs, preprocessor passthrough, and caller `CSV2_*` definitions are
rejected. Release current-tree builds additionally require effective optimized
flags and `NDEBUG`. Clang receives tool-owned `--no-default-config` and
`--driver-mode=g++`, including when `clang++` resolves to the `clang` binary.

Compiler injection environment variables (including include overrides,
`CL`/`_CL_`, compiler search overrides, and CMake toolchain injection) are removed.
Required SDK environment is preserved; SDK, library-search, tool-path and related
values are bound into the identity. The compiler executable, linker and installed
standard library/SDK remain a trusted toolchain boundary, not a hermetic SDK
snapshot. These provenance checks run during build/validation, never measured loops.
