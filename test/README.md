# CSV2 test suite

The test tree validates the same public behavior through modular headers and
the generated single header without changing CSV2's C++11 consumer contract.
The repository root remains compatible with CMake 3.10; this subdirectory is
parsed only when tests or fuzzers are enabled and requires CMake 3.16.

## Layout

```text
test/
├── cmake/       manifest, matrix generation, dependency loading, registration
├── support/     assertion backends and narrowly scoped shared test types
├── runtime/     behavioral cases grouped into 13 stable domains
├── contracts/   compile-only header, feature, standard, and mmap contracts
├── platform/    isolated platform emulation and WinAPI injection checks
├── fixtures/    byte-stable input data
├── fuzz/        Reader and Writer round-trip fuzz targets and seed corpora
```

`test/support/include/csv2_test/test_support.hpp` is a compatibility umbrella.
New support code belongs in the focused header that owns it: `sinks.hpp`,
`streams.hpp`, `string_like.hpp`, `temporary_file.hpp`, `platform.hpp`, or
`reader_support.hpp`. The `csv2_test_support` target supplies only test support
code, include paths, and fixture definitions; it does not install, export, or
propagate into `csv2::csv2`.

## Runtime domains and stable IDs

The runtime suite is organized into these domains:

| Domain | Contract |
| --- | --- |
| `reader.scan` | record and field boundary semantics |
| `reader.iterate` | iterator behavior and classic algorithm use |
| `reader.extract` | raw, decoded, content, sink, and container extraction |
| `reader.source` | borrowed, owned, view, span, and mmap lifetimes |
| `reader.validate` | strict validation and diagnostic positions |
| `reader.convert` | integer conversion and conditional `expected` adapters |
| `reader.ranges` | C++20 range/view/borrowed-range contracts |
| `reader.index` | explicit row indexing and iterator behavior |
| `writer.raw` | compatible raw Writer output |
| `writer.escape` | minimal/always quoting and round-trip behavior |
| `writer.stream` | stream ownership, formatting, state, and exceptions |
| `mio.mapping` | mapping errors, offsets, handles, and writable mappings |
| `property.roundtrip` | deterministic Reader/Writer properties |

Every test case has a stable ID such as `reader.scan.trailing-empty`. IDs are
the runtime filtering and reporting interface; executable registration and
execution, rather than source-text parsing, validate the cases.
CTest executes one aggregated binary per
`standard × header form × variant`, but registers a separate invocation for
each domain:

```text
csv2.runtime.<domain>.<modular|single>.cxx<standard>.<normal|no_mmap|no_exceptions>
```

Do not infer coverage from a hard-coded test count. Select tests by name or
labels, for example:

```bash
ctest --test-dir build -R '^csv2\.runtime\.reader\.validate\.' \
  --output-on-failure
ctest --test-dir build -L no_exceptions --output-on-failure
```

On Windows sanitizer builds, use
`platform/run_windows_sanitizer_tests.ps1`. It validates the
`sanitizer-runtime` CTest JSON manifest, invokes each unmodified test command
without CTest's incompatible sanitizer output capture, enforces the registered
timeout, and writes JUnit. It never adds Catch2-only or minitest-only arguments.

## Dual assertion backends

The runtime sources use `CSV2_TEST_CASE`, `CSV2_CHECK`, `CSV2_REQUIRE`, and the
other macros in `assertions.hpp`:

- `-DCSV2_TEST_ASSERTION_BACKEND=auto` (the default) uses the vendored Catch2
  3.15.3 split library for C++14–23 normal variants, while C++11 and every
  non-normal variant use CSV2's small non-throwing runner.
- `-DCSV2_TEST_ASSERTION_BACKEND=minitest` forces every runtime target to use
  the small non-throwing runner and leaves the Catch2 project unloaded.

The minitest `REQUIRE` path records the failure and returns from the current
test function; it never uses an exception for control flow. Exception-only
cases must be guarded so the same semantic source compiles with exceptions
disabled. Each scenario is a separate `CSV2_TEST_CASE`; the suite does not use
Catch2 sections or a minitest section emulation, so setup, filtering, and
failure boundaries have the same granularity in both backends. Each static
registrar owns its intrusive list node, so registration
has no fixed capacity and performs no dynamic allocation. A separate contract
registers and executes 600 cases to prevent a silent capacity regression.

## Sanitizer smoke slice

`csv2_sanitizer_smoke` is an opt-in build target for the canonical sanitizer
CI slice. It depends on these runtime executables:

```text
csv2_runtime_modular_cxx20_normal
csv2_runtime_single_cxx23_normal
csv2_runtime_modular_cxx11_no_mmap
csv2_runtime_single_cxx11_no_exceptions
```

It also builds both minitest registry executables, both standalone fuzz-smoke
executables, and the two Linux WinAPI injection executables. The target is not
part of `ALL`; build it explicitly with:

```bash
cmake -S . -B build -DCSV2_BUILD_TESTS=ON -DCSV2_ENABLE_SANITIZERS=ON \
  -DCSV2_TEST_ASSERTION_BACKEND=minitest
cmake --build build --target csv2_sanitizer_smoke
ctest --test-dir build -L sanitizer-smoke --output-on-failure
```

An explicit build requires `CSV2_TEST_ASSERTION_BACKEND=minitest`; it fails
closed for every other backend and if the configured toolchain cannot provide
a required canonical runtime dimension. Compile-only contracts and Catch2 are
intentionally outside this slice. `sanitizer-smoke` is the focused CI label;
the existing `sanitizer-runtime` label remains the preserved full
cross-platform sanitizer suite.

## Profiles

Profiles choose depth only; they never enable components implicitly.

| Profile | Runtime matrix |
| --- | --- |
| `quick` | C++11 and C++20 normal modular/single; C++23 feature slice modular/single; C++11/C++23 endpoint no-mmap and no-exceptions variants |
| `full` | supported C++11/14/17/20/23 × modular/single × normal/no-mmap/no-exceptions, filtered by domain capabilities; C++26 compile-only |
| `perf` | quick correctness gate used alongside the independent performance pipeline |

The normal quick workflow is:

```bash
cmake -S . -B build -DCSV2_BUILD_TESTS=ON \
  -DCSV2_REQUIRE_PYTHON_AUDITS=ON \
  -DCSV2_VERIFICATION_PROFILE=quick
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Use `-DCSV2_VERIFICATION_PROFILE=full` for the complete local matrix. CMake and
the compiler must advertise a standard before that standard is added.
Python 3.10 runs the vendor-tool safety tests, benchmark checks, and performance
pipeline. Quick C++ runtime and compile targets can still build without it;
full/perf profiles and CI require it through `CSV2_REQUIRE_PYTHON_AUDITS`.

Tests and fuzzers are independent:

```bash
# Runtime tests only
cmake -S . -B build-tests -DCSV2_BUILD_TESTS=ON

# Non-Windows Clang/libFuzzer only; runtime tests remain disabled
cmake -S . -B build-fuzz -G Ninja \
  -DCMAKE_CXX_COMPILER=clang++ -DCSV2_BUILD_FUZZERS=ON
cmake --build build-fuzz --target csv2_fuzz csv2_fuzz_writer
```

## Adding or changing a test

1. Put behavior in the owning file under `runtime/`; do not create another
   aggregate executable.
2. Give each case a stable `<domain>.<behavior>` ID and the matching domain
   tag.
3. If a new source or capability is needed, update the declaration in
   `runtime/CMakeLists.txt`. The manifest validates profiles and capability
   requirements; the build validates source inputs.
4. Add standard-specific compile contracts under `contracts/`, not to a
   runtime domain.
5. Add a minimal regression fixture only when inline bytes would obscure the
   test, and preserve its exact bytes.
6. Run the focused domain for modular and single-header forms, then the quick
   profile.

## Fixtures

The files formerly under `test/inputs` remain under `fixtures/upstream`.
`.gitattributes` disables text
conversion and whitespace normalization for CSV fixtures and fuzz seeds, so
CRLF and quoted-LF inputs remain byte-for-byte stable.

Temporary output uses process-unique names and scoped cleanup. Never write a
test artifact to a fixed source-tree path; CTest may run domain invocations in
parallel.

## Property tests and fuzzing

`property.roundtrip` uses a specified LCG seed and deterministic rows to check
minimal and always quoting with `no_trimming`. The libFuzzer targets extend
that invariant:

- `csv2_fuzz` exercises traversal, extraction, validation, conversion, and
  indexing with default and non-default policies.
- `csv2_fuzz_writer` converts arbitrary bytes to fields, writes with minimal
  escaping, parses strictly, and requires exactly one output record, the exact
  cell count, and exact content round-trip. Its standalone oracle rejects a
  valid first record followed by any extra record.

Replay committed corpora before starting an open-ended fuzz session:

```bash
./build-fuzz/test/fuzz/csv2_fuzz -runs=50000 test/fuzz/corpus/reader
./build-fuzz/test/fuzz/csv2_fuzz_writer -runs=50000 test/fuzz/corpus/writer
```

Minimize a crash and merge useful inputs with libFuzzer's standard modes:

```bash
./build-fuzz/test/fuzz/csv2_fuzz -minimize_crash=1 crash.csv
mkdir -p build-fuzz/merged-reader
./build-fuzz/test/fuzz/csv2_fuzz -merge=1 \
  build-fuzz/merged-reader test/fuzz/corpus/reader build-fuzz/new-corpus
```

Raw corpora and crash files stay in ignored build directories. Commit only a
small reproducer that is useful in both the stable suite and seed corpus.

## Verification dependencies

Catch2 is an offline test-only snapshot. Its targets are
loaded with `EXCLUDE_FROM_ALL`, receive neither CSV2
Werror/sanitizer/coverage flags nor install/export rules, and are absent when
only C++11/no-exceptions tests or fuzzers are configured. The loader rejects
pre-existing target names and restores the complete parent CMake Cache state.
See
[`third_party/verification/README.md`](../third_party/verification/README.md).

GNU 14 runtime-test aggregates retain `-Warray-bounds` and
`-Wstringop-overread` as warnings rather than errors. At `-O3`, GCC can issue
these diagnostics for the unreachable 64-byte scanner branch after propagating
the object size of short `std::string` fixtures through the header-only Reader.
The exception is limited to those two diagnostics and to runtime-test targets;
all other first-party warnings remain errors.
