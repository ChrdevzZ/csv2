<p align="center">
  <img height="75" src="img/logo.png" alt="csv2"/>
</p>

<p align="center">
  <a href="https://github.com/ChrdevzZ/csv2/actions/workflows/ci.yml"><img src="https://github.com/ChrdevzZ/csv2/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="#compiling-tests"><img src="https://img.shields.io/badge/C%2B%2B-11-00599C.svg?logo=cplusplus&amp;logoColor=white" alt="C++11 minimum"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

Fast, header-only C++11 CSV reader and writer with zero-copy iteration and
single-header distribution.

The modular headers under `include/csv2/` are the maintained source of truth.
`single_include/csv2/csv2.hpp` is generated from them; CI builds and tests both
header forms.

## Project Lineage

CSV2 was created by [Pranav (`p-ranav`)](https://github.com/p-ranav) and is developed upstream at
[p-ranav/csv2](https://github.com/p-ranav/csv2). This repository is an independent downstream fork. It preserves the
original copyright, contributor history, and MIT license.

| Reference | Location |
| --- | --- |
| Original project | [p-ranav/csv2](https://github.com/p-ranav/csv2) |
| Original author | [Pranav (`p-ranav`)](https://github.com/p-ranav) |
| Original contributors | [Upstream contributors](https://github.com/p-ranav/csv2/graphs/contributors) |
| This fork | [ChrdevzZ/csv2](https://github.com/ChrdevzZ/csv2) |
| Source comparison | [Upstream `master` to fork `master`](https://github.com/p-ranav/csv2/compare/master...ChrdevzZ:csv2:master) |
| License | [MIT](LICENSE) |

## What This Fork Adds

The fork keeps the original C++11 interface, permissive Reader, and raw Writer as its compatibility baseline. It adds
the following capabilities without raising the `csv2::csv2` target's minimum language requirement:

- standard-library feature detection and conditional C++17, C++20, and C++23 interfaces;
- explicit borrowed and owned input APIs, constrained mmap paths, standard iterators and ranges, strict validation,
  integer conversion, and `RowIndex`;
- generic append sinks and output iterators, batched field copying, and one shared scanning core for modular and
  single-header builds;
- Range-based Writer input, explicit stream ownership, and raw, minimal, or always-quoted output policies;
- installed CMake and pkg-config metadata, no-mmap and no-exceptions builds, cross-standard tests, sanitizers,
  Reader/Writer fuzzing, and an auditable benchmark evidence pipeline.

Structural traversal remains allocation-free. Operations that deliberately materialize strings, take ownership of
input, or build a `RowIndex` may allocate. Performance claims require controlled evidence; hosted timing is never used
as a regression gate.

## Table of Contents

- [Project Lineage](#project-lineage)
- [What This Fork Adds](#what-this-fork-adds)
- [CSV Reader](#csv-reader)
- [CSV Writer](#csv-writer)
- [Standards and Compatibility](#standards-and-compatibility)
- [Performance Benchmark](#performance-benchmark)
- [Compiling Tests](#compiling-tests)
- [Installing and Consuming with CMake](#installing-and-consuming-with-cmake)
- [Generating Single Header](#generating-single-header)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)
- [License](#license)

## CSV Reader

The original Reader interface remains the shortest path for memory-mapped CSV files. Its template policies select the
delimiter, quote character, header handling, and trimming behavior:

```cpp
#include <csv2/reader.hpp>

#include <string>

int main() {
  csv2::Reader<csv2::delimiter<','>,
               csv2::quote_character<'"'>,
               csv2::first_row_is_header<true>,
               csv2::trim_policy::trim_whitespace>
      csv;

  if (!csv.mmap("foo.csv"))
    return 1;

  const auto header = csv.header();
  (void)header;

  for (const auto row : csv) {
    for (const auto cell : row) {
      std::string value;
      cell.read_value(value);
      // Use value.
    }
  }
}
```

The same Reader can borrow an existing buffer. Keep the string alive and unchanged for as long as the Reader uses it:

```cpp
#include <csv2/reader.hpp>

#include <string>

int main() {
  std::string input = "name,count\nwidgets,42\n";
  csv2::Reader<> csv;
  return csv.parse(input) ? 0 : 1;
}
```

### Input Ownership and Lifetime

| Interface | Ownership | Availability | Contract |
| --- | --- | --- | --- |
| `mmap(path)` | Reader owns the mapping | C++11 when mmap is enabled | Returns `false` on ordinary open or mapping failure |
| `parse(lvalue)` | Borrowed | C++11 | The source address and extent must remain valid |
| `parse(rvalue)` | Reader-owned | C++11 | The Reader takes or materializes independent storage |
| `parse_borrowed(data, size)` | Borrowed | C++11 | Borrows exactly the supplied byte range |
| `parse_owned(string)` | Reader-owned | C++11 | Stores an independent source |
| `parse_view(string_view)` | Borrowed | C++17 | The view and its backing storage must remain valid |
| `parse_borrowed(span)` | Borrowed | C++20 | Adapts `std::span<const char>` without copying |

Selecting a source replaces the previous one. Destroying, resizing, reallocating, or mutating borrowed storage
invalidates all rows, cells, iterators, indexes, and views obtained from it. Concurrent mutation and iteration are not
supported.

Mapped paths require accessible NUL-terminated storage. Narrow C strings, character arrays, and
`std::basic_string<char, ...>` are supported; Windows also accepts wide forms, and C++17 adds
`std::filesystem::path`. A legacy sized character range must contain one final NUL and no embedded NUL.
`std::basic_string_view` is rejected as a path because it does not guarantee an accessible terminator.

Use the `std::error_code&` mmap overload for diagnostics. The caller retains a native file handle and keeps it open for
the mapping's lifetime. Define `CSV2_HAS_MMAP=0` consistently to remove the mapping layer.

### Record and Field Semantics

Records may end with LF or CRLF. Inside a quoted field both are content, and a doubled quote does not close the field.
A final terminator does not add another empty record. Permissive iteration treats a standalone CR as content; strict
validation rejects one outside a quoted field.

A trailing delimiter creates a final empty cell; an empty record has zero cells. With `first_row_is_header<true>`,
`header()` returns the first record and iteration starts at the next one. Row widths may differ.

Reader delimiters cannot be CR or LF because those bytes define record boundaries. The configured trim policy applies
to decoded field access and strict validation; it does not change raw byte ranges.

### Field Extraction

Field access is intentionally split into raw, decoded, and content forms:

| Operation | Result |
| --- | --- |
| `raw_data()` / `raw_size()` | Borrowed bytes exactly as stored in the record |
| `read_raw_value(container)` | Appends the raw bytes to a compatible container |
| `copy_raw_to(output)` | Copies raw bytes through an output iterator |
| `raw_trimmed_view()` / `read_view()` | C++17 borrowed view after trim policy, with outer quotes retained |
| `read_value(container)` | Appends trimmed data and folds doubled quotes; outer quotes remain |
| `decode_to(output)` | Output-iterator form of `read_value` |
| `copy_content_to(output)` | Trims, removes a valid outer quote pair, and folds doubled quotes |

These operations append without clearing the destination. They support strings, sequence containers, available PMR
strings, custom append sinks, and output iterators. `has_escaped_quotes()` reports doubled quote pairs found during
boundary scanning.

Rows expose the same raw byte view and can copy a complete logical record without rescanning its cells.

### Validation and Integer Conversion

Iteration preserves the original permissive behavior. The read-only, allocation-free `validate(parse_error&)` rejects
quotes in unquoted fields, unclosed or invalid doubled quotes, non-trim content after a closing quote, and bare CR.
Errors include a byte offset and logical row and column.

`Cell::try_parse(Integer&, conversion_error&, base)` consumes a complete integer in bases 2–36, excludes bool and
character types, and leaves the destination unchanged on failure. C++17 can use `std::from_chars`; the C++11 fallback
has the same result contract.

When the library supplies C++23 `std::expected`, `validate_expected()`, `mmap_expected()`, and
`parse_expected<Integer>()` are also available. Bool and error-object interfaces remain the portable baseline.

### Ranges and Row Indexing

Row and cell iterators satisfy traditional C++11 iterator interfaces. In C++20, Row is also a forward, borrowed view;
Reader is not borrowed because an rvalue Reader may own its source.

`Reader::index()` builds a random-access, sized `RowIndex`, allocating one bounds entry per selected row while borrowing
the source. It follows the header policy, can omit empty records, and is never created or cached implicitly.

### Reader API

The table below is an index, not a replacement for the declarations in
[`include/csv2/reader.hpp`](include/csv2/reader.hpp).

| Area | Primary interfaces |
| --- | --- |
| Source selection | `mmap`, `parse`, `parse_borrowed`, `parse_owned`, `parse_view` |
| Shape and traversal | `header`, `begin`, `end`, `rows`, `cols` |
| Raw access | Row/Cell `raw_data`, `raw_size`, `read_raw_value`, `copy_raw_to` |
| Decoded access | Cell `read_value`, `decode_to`, `copy_content_to`, `raw_trimmed_view` |
| Validation | `validate`, conditionally `validate_expected` |
| Conversion | `try_parse`, conditionally `parse_expected` |
| Indexed access | `index`, `RowIndex::size`, `operator[]`, random-access iterators |

## CSV Writer

The original Writer remains the default raw-output interface. It accepts a stream by reference and can write one row or
a range of rows:

```cpp
#include <csv2/writer.hpp>

#include <fstream>
#include <string>
#include <vector>

int main() {
  std::ofstream stream("foo.csv");
  if (!stream)
    return 1;

  {
    csv2::Writer<csv2::delimiter<','>> writer(stream);
    const std::vector<std::vector<std::string>> rows = {
        {"a", "b", "c"},
        {"1", "2", "3"},
        {"4", "5", "6"},
    };
    writer.write_rows(rows);
  } // The default Writer closes a close-capable stream.

  return stream ? 0 : 1;
}
```

### Output Policies

| Interface or policy | Behavior | Intended use |
| --- | --- | --- |
| `Writer` / `quote_policy::none` | Writes field representations unchanged | Source compatibility and pre-escaped data |
| `EscapingWriter` / `quote_policy::minimal` | Quotes fields containing the delimiter, quote, CR, or LF and doubles embedded quotes | General CSV output |
| `quote_policy::always` | Quotes every field and doubles embedded quotes | Output that must preserve otherwise ambiguous empty shapes |

Raw output may be invalid CSV when a field contains structural characters. Select `EscapingWriter` to apply ordinary
CSV quoting rules.

### Ranges and Field Dispatch

Writer uses ADL `begin` and `end` for arrays, containers, iterator/sentinel ranges, and C++20 views. Custom stream
insertion takes precedence; otherwise contiguous character fields use direct writes and other streamable values keep the
destination's formatting state.

Quoting writers scan contiguous character fields and write segments. Other values are formatted with the destination's
state before escaping; final stream state and one-shot width follow the normal iostream contract.

### Stream Ownership

Writer borrows a stream that must outlive it. The historical two-parameter Writer closes streams that provide `close()`
and transfers that responsibility when moved.

Select `stream_ownership::leave_open` when the caller owns closure. Explicit `close()` is idempotent and reports errors
under either policy; destruction does not emit close exceptions. Closed and moved-from writers ignore writes.

### Round-Trip Boundaries

Every Writer terminates rows with LF. CR or LF remains selectable as a delimiter for compatibility, but produces
ambiguous output that quoting cannot repair.

A zero-field row and a raw or minimally quoted single empty field both produce one newline. Use
`quote_policy::always` to distinguish those shapes.

### Writer API

The authoritative declarations are in [`include/csv2/writer.hpp`](include/csv2/writer.hpp).

| Interface | Purpose |
| --- | --- |
| `Writer<Delimiter, Stream>` | Compatible raw writer with close-on-destroy ownership |
| `basic_writer<Delimiter, Stream, Ownership, QuotePolicy>` | Explicit ownership and quoting policy |
| `EscapingWriter<Delimiter, Stream, Ownership>` | Convenience alias for minimal quoting |
| `write_row(range)` | Writes one row followed by LF |
| `write_rows(range)` | Writes a range of rows |
| `close()` | Closes at most once and reports stream errors |

## Standards and Compatibility

`csv2::csv2` declares only `cxx_std_11`. Later adapters appear only when their headers and SD-6 macros are available:

| Language/library level | CSV2 facilities |
| --- | --- |
| C++11 | Reader and Writer compatibility APIs, explicit ownership, generic sinks, strict validation, integer fallback, `RowIndex`, and escaping policies |
| C++14 | The same public surface with additional constexpr support where permitted |
| C++17 | `std::string_view` input/views, `std::filesystem::path`, `std::from_chars`, and PMR container support when supplied by the library |
| C++20 | `std::span<const char>` input and Row range/view integration |
| C++23 | `std::expected` error adapters and consumer-side ranges facilities when supplied by the library |
| C++26 | Forward compile checks only; no C++26 CSV2 feature contract |

Feature detection lives in [`include/csv2/detail/config.hpp`](include/csv2/detail/config.hpp); a language mode alone does
not guarantee a library facility. Consumers select their standard explicitly:

```cmake
target_link_libraries(app PRIVATE csv2::csv2)
target_compile_features(app PRIVATE cxx_std_20)
set_target_properties(app PROPERTIES CXX_EXTENSIONS OFF)
```

All standards use the same scanner and record semantics. `CSV2_HAS_MMAP=0` removes mapping, and no-exceptions builds
retain the ordinary interface.

## Performance Benchmark

The benchmark registry covers sources, traversal, extraction, validation, conversion, ranges, indexing, and Writer
dispatch. Setup, timing, and semantic verification are separate; optimized builds observe live results and failures do
not produce successful measurements. Each timing process measures one operation and one concrete source, so unrelated
preparation and peak RSS do not share a `Context`.

Exact checksums and allocation contracts remain outside timing. Hosted CI gates their protocols and observers, but
hosted throughput is exploratory. The formal comparison driver is uninstrumented;
a separate timer-scope audit build proves Reader/checksum boundaries and is
rejected by report generation. `source/mmap-touch-pretouched` explicitly touches
the same page-stride addresses during setup and timing without claiming OS
residency. A portability check validates registry/manifest coverage, while the
exhaustive owner verifies and dry-runs every registered operation.

```bash
cmake -S . -B build-benchmark -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCSV2_BUILD_BENCHMARK_CHECKS=ON \
  -DCSV2_REQUIRE_PYTHON_AUDITS=ON \
  -DCSV2_BENCHMARK_REVISION="$(git rev-parse HEAD)"
cmake --build build-benchmark --parallel
ctest --test-dir build-benchmark -L benchmark-checksum \
  --no-tests=error --output-on-failure
```

Cross-revision runs export one C++11 driver and both header trees from immutable Git objects. Controlled evidence also
requires a reviewed machine profile, controlled Linux environment, affinity, A/A calibration, matching checksums, three
warmups, 20 paired runs, machine metrics, and a finalized evidence bundle. Reports are validated by reparsing primary
wires and recomputing statistics; fixed metrics must match one cross-revision semantic case exactly. See
[`benchmark/README.md`](benchmark/README.md) and
[`benchmark/protocol/README.md`](benchmark/protocol/README.md).

## Compiling Tests

Verification is disabled by default. A representative local run is:

```bash
cmake -S . -B build \
  -DCSV2_BUILD_TESTS=ON \
  -DCSV2_REQUIRE_PYTHON_AUDITS=ON \
  -DCSV2_VERIFICATION_PROFILE=quick
cmake --build build --parallel
ctest --test-dir build --no-tests=error --output-on-failure
```

| Option | Purpose |
| --- | --- |
| `CSV2_BUILD_TESTS` | Runtime domains and compile contracts |
| `CSV2_BUILD_BENCHMARKS` | Current-tree and common benchmark executables |
| `CSV2_BUILD_BENCHMARK_CHECKS` | Deterministic benchmark CTest checks; requires benchmarks |
| `CSV2_BENCHMARKS_EXCLUDE_FROM_ALL` | Configure benchmark targets without adding them to the default `all` target |
| `CSV2_BUILD_FUZZERS` | Clang/libFuzzer Reader and Writer targets on supported platforms |
| `CSV2_ENABLE_SANITIZERS` | Sanitizers for first-party verification targets |
| `CSV2_REQUIRE_PYTHON_AUDITS` | Fail unless the Python 3.10 audits are available |

`CSV2_VERIFICATION_PROFILE=quick|full|perf` changes verification depth without enabling components. The root remains
CMake 3.10 compatible; enabled test and benchmark subprojects require CMake 3.16.

Quick covers representative C++11, C++20, and C++23 slices and no-mmap/no-exceptions endpoints. Full expands the
C++11–23, modular/single-header, and variant matrix; C++26 is compile-only. Details live in
[`test/README.md`](test/README.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and
[`third_party/verification/README.md`](third_party/verification/README.md).

The always-run `CI` workflow classifies the complete Git diff and ends in one
stable `CI / gate`. Documentation-only changes run preflight and the Gate;
unknown paths fail safe by selecting every owner. Selected changes call the
reusable Linux, Windows, macOS, fuzz, exact-head full, and
performance-protocol workflows. Manual full and performance runs retain the
broader platform matrix and controlled self-hosted path.

## Installing and Consuming with CMake

For an in-tree dependency, link the namespaced target:

```cmake
add_subdirectory(path/to/csv2)
target_link_libraries(app PRIVATE csv2::csv2)
```

To install csv2 as a CMake package:

```bash
cmake -S . -B build-install -DCMAKE_BUILD_TYPE=Release
cmake --build build-install
cmake --install build-install --prefix /absolute/path/to/csv2-prefix
```

An installed consumer uses:

```cmake
cmake_minimum_required(VERSION 3.10)
project(csv2_consumer LANGUAGES CXX)

find_package(csv2 CONFIG REQUIRED)
add_executable(csv2_consumer main.cpp)
target_link_libraries(csv2_consumer PRIVATE csv2::csv2)
```

Configure with `-DCMAKE_PREFIX_PATH=/absolute/path/to/csv2-prefix`. Unix-like installs also provide
`pkg-config --cflags csv2`.

The package installs modular headers, CMake/pkg-config metadata, and licenses. It excludes tests, fuzzers, benchmarks,
third-party verification libraries, and their tools. The generated single header is distributed separately.

## Generating Single Header

The original amalgamation workflow remains available:

```bash
python3 utils/amalgamate/amalgamate.py -c single_include.json -s .
```

Commit modular and generated header changes together. Source-tree comparisons
and other one-off repository-shape checks belong in local review, not in the
tracked test suite or required CI.

Applications using the generated distribution add `single_include/` to their include path and include
`<csv2/csv2.hpp>`.

## Contributing

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing behavior, verification, generated
headers, or vendored sources. The test and benchmark READMEs define their manifests and evidence rules.

Preserve C++11 and default behavior unless a change adds an explicit opt-in interface. Public header changes require
focused tests and regenerated output.

## Acknowledgements

CSV2 was created by [Pranav (`p-ranav`)](https://github.com/p-ranav). Its
[contributors](https://github.com/p-ranav/csv2/graphs/contributors) established the Reader, Writer, fixtures, benchmark,
and amalgamated distribution inherited by this fork.

Memory mapping vendors [mandreyel/mio](https://github.com/mandreyel/mio) under [`LICENSE.mio`](LICENSE.mio).
Verification-only Catch2 and Google Benchmark provenance is recorded in
[`third_party/verification/README.md`](third_party/verification/README.md).

## License

CSV2 and this fork's modifications are available under the [MIT License](LICENSE).
Vendored components retain their own license notices.
