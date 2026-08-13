<p align="center">
  <img height="75" src="img/logo.png" alt="csv2"/>
</p>

<p align="center">
  <a href="https://github.com/ChrdevzZ/csv2/actions/workflows/linux.yml"><img src="https://github.com/ChrdevzZ/csv2/actions/workflows/linux.yml/badge.svg" alt="Linux"></a>
  <a href="https://github.com/ChrdevzZ/csv2/actions/workflows/windows.yml"><img src="https://github.com/ChrdevzZ/csv2/actions/workflows/windows.yml/badge.svg" alt="Windows"></a>
  <a href="https://github.com/ChrdevzZ/csv2/actions/workflows/macos.yml"><img src="https://github.com/ChrdevzZ/csv2/actions/workflows/macos.yml/badge.svg" alt="macOS"></a>
  <a href="#compiling-tests"><img src="https://img.shields.io/badge/C%2B%2B-11-00599C.svg?logo=cplusplus&amp;logoColor=white" alt="C++11 minimum"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

Fast, header-only C++11 CSV reader and writer with zero-copy iteration and
single-header distribution.

The modular headers under `include/csv2/` are the maintained source of truth.
`single_include/csv2/csv2.hpp` is generated from them and is verified for exact
synchronization in Linux CI.

## Table of Contents

*    [CSV Reader](#csv-reader)
     *    [Performance Benchmark](#performance-benchmark)
     *    [Reader API](#reader-api)
*    [CSV Writer](#csv-writer)
     *    [Writer API](#writer-api)
*    [Compiling Tests](#compiling-tests)
*    [Installing and Consuming with CMake](#installing-and-consuming-with-cmake)
*    [Generating Single Header](#generating-single-header)
*    [Contributing](#contributing)
*    [License](#license)

## CSV Reader

```cpp
#include <csv2/reader.hpp>

int main() {
  csv2::Reader<csv2::delimiter<','>, 
               csv2::quote_character<'"'>, 
               csv2::first_row_is_header<true>,
               csv2::trim_policy::trim_whitespace> csv;
               
  if (csv.mmap("foo.csv")) {
    const auto header = csv.header();
    for (const auto row: csv) {
      for (const auto cell: row) {
        // Do something with cell value
        // std::string value;
        // cell.read_value(value);
      }
    }
  }
}
```

### Input Lifetime and Record Semantics

`Reader::parse()` borrows an lvalue string without copying it. The caller must
keep both its address and extent valid while csv2 accesses it. Destruction,
reallocation, or a size change invalidates the Reader's source selection; call
`parse()` or `parse_borrowed()` again before further access. Any in-place byte
mutation invalidates every previously obtained Row, Cell, iterator, RowIndex,
and raw or decoded view. After a same-extent mutation, discard those values and
reacquire them from the Reader. Concurrent source mutation and parsing or
iteration are not supported.

Passing an rvalue string transfers the contents to storage owned by the reader,
so parsing a temporary is safe. When C++17 is available, `parse_view()` remains
a borrowed API and the `std::string_view` storage has the same address, extent,
and mutation requirements. Calling `mmap()`, `parse()`, `parse_borrowed()`,
`parse_owned()`, or `parse_view()` replaces the previous input source. Passing
an exact range of the same reader's owned or mapped source back to
`parse_borrowed()` or `parse_view()` keeps that backing storage alive and
selects the range without copying.

For ownership-visible code, `parse_borrowed(const char*, size_t)` accepts an
exact byte range and never copies, while `parse_owned(std::string)` stores an
independent source. C++20 additionally accepts `std::span<const char>` through
`parse_borrowed`. The legacy `parse()` overloads retain their existing lvalue
borrow/rvalue ownership behavior.

`Reader::mmap()` returns `false` for ordinary open or mapping failures and
clears the previous source; it does not translate those failures into
exceptions. Use the overload accepting `std::error_code&` when the reason is
needed. Memory mapping can be disabled consistently for all translation units
with `CSV2_HAS_MMAP=0`. In that mode, including either `csv2/reader.hpp` or the
modular `csv2/mio.hpp` does not expose or compile the vendored mapping layer.

Mapped paths must provide NUL-terminated storage. Supported path types are
`const char*`/character arrays and `std::basic_string<char, ...>`; Windows also
accepts the corresponding wide forms. C++17 adds `std::filesystem::path`.
Legacy sized character ranges such as `std::vector<char>` are accepted only
when they contain exactly one NUL at the end and no embedded NUL; otherwise
mapping fails with `std::errc::invalid_argument`. Every
`std::basic_string_view` specialization remains rejected because its range does
not promise an accessible terminator. A native file handle may also be mapped;
the caller retains ownership and must keep it open for the mapped source's
lifetime.

`include/csv2/mio.hpp` vendors [mandreyel/mio](https://github.com/mandreyel/mio),
first imported by csv2 commit `e51a8df` on 2020-04-23. Its MIT license remains
in `LICENSE.mio`. Local csv2 patches preserve mapping ownership/error handling,
request readable protection for writable POSIX mappings, support explicit
no-mmap builds, and restrict file paths to the safe types listed above; no
independent upstream version tag was recorded by the original import.

Records may be terminated by LF or CRLF. LF and CRLF inside a quoted field are
part of that field, and doubled quote characters (`""`) do not close it. A final
record delimiter terminates the last record without creating another empty
record; delimiters before the final one can still represent empty records.
Standalone CR characters are treated as record content. Reader field
delimiters are configurable but cannot be CR or LF because those bytes are
reserved for record boundaries. `Reader` and `RowIndex` reject those delimiter
policies at compile time.

A field delimiter at the end of a non-empty record creates a final empty
`Cell`. A record containing no characters remains an empty `Row` with zero
cells. `Cell::read_value()` trims according to the configured policy, retains
outer quote characters, folds each adjacent pair of configured quote
characters into one, and appends the decoded value without modifying content
already present in the output container.

### Performance Benchmark

The independent benchmark subproject provides a registry of source, traversal,
extraction, validation, conversion, ranges, index, and Writer operations. Each
kernel has an explicit setup/timed/verification boundary. Exact checksums and
allocation contracts are verified separately from Google Benchmark timing;
GiB/s consistently uses input-corpus bytes. Hosted CI builds every operation
group and checks protocol, checksum, CLI, and zero-allocation contracts, but
never accepts or rejects a change from hosted timing.

```bash
cmake -S . -B build-benchmark -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCSV2_BUILD_BENCHMARK_CHECKS=ON \
  -DCSV2_BENCHMARK_REVISION="$(git rev-parse HEAD)"
cmake --build build-benchmark --parallel
ctest --test-dir build-benchmark -L benchmark-checksum \
  --no-tests=error --output-on-failure
```

Cross-revision claims use the same C++11
[`common_driver.cpp`](benchmark/compare/common_driver.cpp) against both exact
header archives, followed by A/A calibration and alternating A/B runs. Reports
bind revisions, binaries, driver, corpus, machine, compiler, raw samples, and
statistics by hash. Hosted results are marked `exploratory`; only a fixed
Linux machine satisfying the `controlled` protocol is decision-eligible. See
[`benchmark/README.md`](benchmark/README.md) for operations, deterministic
corpus generation, protocol versions, and reproducible commands.

### Reader API

Here is the public API available to you:

```cpp
template <class delimiter = delimiter<','>, 
          class quote_character = quote_character<'"'>,
          class first_row_is_header = first_row_is_header<true>,
          class trim_policy = trim_policy::trim_whitespace>
class Reader {
public:
  Reader() = default;
  Reader(const Reader&) = delete;
  Reader& operator=(const Reader&) = delete;
  Reader(Reader&&);
  Reader& operator=(Reader&&);

  
  // Present when CSV2_HAS_MMAP is enabled
  // StringType is a supported NUL-terminated path type, not string_view.
  template <typename StringType>
  bool mmap(StringType&& filename);
  template <typename StringType>
  bool mmap(StringType&& filename, std::error_code& error);

  // C++23, when std::expected is provided
  template <typename StringType>
  std::expected<void, std::error_code> mmap_expected(StringType&& filename);

  // Lvalues are borrowed; rvalues are owned by the Reader
  template <typename StringType>
  bool parse(StringType&& contents);

  bool parse_borrowed(const char* data, size_t size);
  bool parse_owned(std::string contents);

  // C++20
  bool parse_borrowed(std::span<const char> contents);

  // C++17: externally owned storage remains borrowed. A view into this
  // Reader's current owned or mapped source retains that backing source.
  bool parse_view(std::string_view contents);

  // Shape
  size_t rows(bool ignore_empty_lines = false) const;
  size_t cols() const;

  // Explicitly allocate one bounds pair per selected logical record.
  // The returned index borrows this Reader's active source.
  RowIndex index(bool ignore_empty_lines = false) const;

  // Optional strict, zero-allocation validation. Existing iteration remains
  // permissive. byte_offset is zero-based; row/column are one-based logical
  // record and field numbers.
  // noexcept when trim_policy::trim is noexcept
  bool validate(parse_error& error) const /* conditionally noexcept */;

  // C++23, when the standard library provides std::expected
  // noexcept when trim_policy::trim is noexcept
  std::expected<void, parse_error> validate_expected() const
      /* conditionally noexcept */;
  
  // Row iterator
  // If first_row_is_header, row iteration will start
  // from the second row
  RowIterator begin() const;
  RowIterator end() const;

  // Access the first row of the CSV
  Row header() const;
};
```

`Row::raw_data()/raw_size()` and `Cell::raw_data()/raw_size()` expose non-owning
byte ranges that follow the source invalidation rules above.
`Cell::has_escaped_quotes()` reports whether doubled quote pairs were observed
during boundary scanning. In C++17,
`Cell::raw_trimmed_view()` returns the trim-policy-adjusted raw view; the older
`read_view()` name remains available.

The reusable row and cell implementations are also available as
namespace-scope `csv2::basic_row` and `csv2::basic_cell`. `Reader::Row` and
`Reader::Cell` remain real nested classes for source and specialization
compatibility and are zero-state facades over those implementations. In C++20,
Row models a view, borrowed range, and forward range, so a temporary Row can
enter a views pipeline. Reader itself is deliberately not a borrowed range
because an rvalue Reader may own the selected bytes.

`Reader::validate()` is an explicit strict layer over the same source. It
rejects quotes in unquoted fields, unclosed quotes, invalid doubled quotes,
non-trim content after a closing quote, and bare carriage returns. CR and LF
remain valid inside quoted fields, and rows may contain different numbers of
fields. Calling it never changes the permissive behavior of iteration.

`Reader::index()` explicitly builds a random-access, sized `RowIndex`. It
stores the start and content end of each selected logical record, skips the
configured header, and optionally excludes empty records. Indexed dereference
is therefore constant time. The index borrows the selected bytes: externally
borrowed storage remains governed by its caller, while destroying or replacing
a Reader-owned or mapped source invalidates indexes into that source. A
RowIndex iterator additionally requires its RowIndex object to remain alive.
Reader never creates or retains an index implicitly.

Here's the `Row` class:

```cpp
// Row class
class Row {
public:
  // Address and length of this row's raw logical-record contents
  const char* address() const noexcept;
  size_t length() const;

  // Get raw contents of the row
  void read_raw_value(Container& value) const;
  
  // Cell iterator
  CellIterator begin() const;
  CellIterator end() const;
};
```

and here's the `Cell` class:

```cpp
// Cell class
class Cell {
public:
  // C++17: trimmed, non-owning view into the Reader's active source
  std::string_view read_view() const;

  // Get raw contents of the cell
  void read_raw_value(Container& value) const;
  
  // Get converted contents of the cell
  // Handles escaped content, e.g., 
  // """foo""" => ""foo""
  void read_value(Container& value) const;

  // Complete integer conversion, base 2..36. On failure value is unchanged.
  template<class Integer>
  bool try_parse(Integer& value, conversion_error& error, int base = 10) const;

  // C++23, when the standard library provides std::expected
  template<class Integer>
  std::expected<Integer, conversion_error> parse_expected(int base = 10) const;
};
```

Integer conversion excludes `bool` and character types, consumes the whole
trimmed field content, and strips a valid pair of outer quotes. C++17 and newer
use `std::from_chars`; the C++11 fallback has the same base, range, sign, and
complete-consumption rules. Neither path allocates.

## CSV Writer

`Writer` accepts standard ranges through ADL `begin`/`end`, including native
arrays and C++20 iterator/sentinel views. It preserves the historical
insertion-first contract, so a custom stream's `operator<<` for a field type
takes precedence; otherwise contiguous `char` ranges fall back to one
`write()` call. `basic_writer` uses its direct contiguous-character fast path
for standard strings and string views. Arithmetic and other streamable values
preserve the stream's locale and formatting state.

The two-parameter `Writer` preserves the original close-on-destroy behavior.
Use the four-parameter `basic_writer` with `stream_ownership::leave_open` when
the caller retains close responsibility. Explicit `basic_writer::close()`
still closes a close-capable stream under either ownership policy and reports
its errors.

This library also provides a basic `csv2::Writer` class - one that can be used to write CSV rows to file. Here's a basic usage:

```cpp
#include <csv2/writer.hpp>
#include <vector>
#include <string>
using namespace csv2;

int main() {
    std::ofstream stream("foo.csv");
    {
        Writer<delimiter<','>> writer(stream);
        const std::vector<std::vector<std::string>> rows = {
            {"a", "b", "c"},
            {"1", "2", "3"},
            {"4", "5", "6"}
        };
        writer.write_rows(rows);
    } // closes stream
}
```

`Writer` borrows the stream object, which must outlive it, but assumes the sole
responsibility for closing a stream that provides `void close()`. It is
move-only, and moving it transfers that responsibility. Call `Writer::close()`
when close errors must be observed; it is idempotent, and the destructor never
lets a close exception escape. Do not close the underlying stream directly
while an active `Writer` still owns that responsibility. After a Writer is
closed or moved from, further write calls have no effect.

The default `quote_policy::none` preserves the original raw behavior: values
are emitted exactly as supplied. `EscapingWriter` selects
`quote_policy::minimal`, quoting fields containing the delimiter, a quote, CR,
or LF and doubling embedded quotes. `quote_policy::always` quotes every field.
For source compatibility, `Writer` continues to accept CR and LF delimiter
policies; `basic_writer` and `EscapingWriter` use the same delimiter domain.
Because every Writer emits LF as the row terminator, those delimiter choices
produce ambiguous, non-round-trippable output; quoting policies cannot remove
that ambiguity. Use a delimiter other than CR or LF for output intended to be
parsed as CSV.
Contiguous character fields are scanned and written in segments; other
streamable values are first formatted with a copy of the destination stream's
locale, flags, precision, and fill state, then escaped. A row with zero values
writes one newline, as does a raw or minimally quoted row containing one empty
string, so those shapes are not reversibly distinguishable. Use
`quote_policy::always` when that distinction must survive serialization.

### Writer API

Here is the public API available to you:

```cpp
template <class delimiter = delimiter<','>, typename Stream = std::ofstream>
class Writer {
public:
  Writer(Stream& stream) noexcept;
  Writer(const Writer&) = delete;
  Writer& operator=(const Writer&) = delete;
  Writer(Writer&&) noexcept;
  Writer& operator=(Writer&&) noexcept;

  // Close at most once and report stream exceptions to the caller
  void close();

  // Use this to write a single row to file
  void write_row(container_of_strings row);

  // Use this to write a list of rows to file
  void write_rows(container_of_rows rows);
};

template <class delimiter = delimiter<','>, typename Stream = std::ofstream,
          typename Ownership = stream_ownership::close_on_destroy,
          typename QuotePolicy = quote_policy::none>
class basic_writer;

template <class delimiter = delimiter<','>, typename Stream = std::ofstream,
          typename Ownership = stream_ownership::close_on_destroy>
using EscapingWriter =
    basic_writer<delimiter, Stream, Ownership, quote_policy::minimal>;
```

The historical two-parameter `Writer` remains the default raw writer and
closes streams that provide `close()`. Use `basic_writer` when ownership or an
explicit quote policy must be selected; unsupported policy types are rejected
at compile time. `EscapingWriter` is its minimal-quoting convenience alias.

## Compiling Tests

```bash
cmake -S . -B build -DCSV2_BUILD_TESTS=ON \
  -DCSV2_VERIFICATION_PROFILE=quick
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Verification components are off by default and independently selectable:

| Option | Purpose |
| --- | --- |
| `CSV2_BUILD_TESTS` | runtime domains and compile contracts |
| `CSV2_BUILD_BENCHMARKS` | current and common benchmark executables |
| `CSV2_BUILD_BENCHMARK_CHECKS` | deterministic benchmark CTest checks; requires benchmarks |
| `CSV2_BUILD_FUZZERS` | non-Windows Clang/libFuzzer Reader and Writer targets |

`CSV2_VERIFICATION_PROFILE` accepts `quick`, `full`, or `perf` and controls
depth only; it never enables a component. The root remains CMake 3.10
compatible when all options are off. Enabling tests, fuzzers, or benchmarks
enters an isolated CMake 3.16 subdirectory and uses only offline vendored
verification dependencies.

The quick profile runs C++11 and C++20 behavior through modular and
single-header forms, a C++23 feature slice, and no-mmap/no-exceptions endpoint
variants. The full profile expands supported C++11/14/17/20/23 combinations;
C++26 remains compile-only. Each `standard × header form × variant` builds one
aggregate executable, while 13 stable domains are separately selectable by
CTest name and labels. C++11 and every no-exceptions variant use a small
non-throwing runner; C++14–23 normal variants use the vendored Catch2 split
library.

`-DCSV2_ENABLE_SANITIZERS=ON` enables ASan and UBSan with GCC, Clang, and
AppleClang. With the Microsoft compiler it enables MSVC AddressSanitizer only.
With x64 Clang-CL it enables ASan and UBSan, discovers and validates the
compiler-rt libraries installed beside the selected compiler, and links the
required dynamic ASan and standalone UBSan runtimes. Clang-CL sanitizer builds
must use a non-Debug CRT configuration; CI uses Release because Clang-CL ASan
does not support the Debug CRT. The Clang-CL configuration disables only the
UBSan `object-size` check because it diagnoses the MSVC standard library's
`forward_list` pseudo-node implementation. Linux enables leak detection through
ASan; Windows disables it because LeakSanitizer is not supported there. Windows
sanitizer jobs still use the CTest JSON manifest as the source of truth, but a
small runner executes each exact command with an inherited console because
CTest output capture can deadlock instrumented MSVC/Clang-CL processes. The
runner preserves each command, working directory, timeout, and JUnit result.

Runtime CTest names follow:

```text
csv2.runtime.<domain>.<modular|single>.cxx<standard>.<normal|no_mmap|no_exceptions>
```

`CSV2_REQUIRE_MODERN_STANDARD_TESTS` is an enforcement switch for modern CI:
configuration fails if the required C++20/C++23 slices are not registered.

`CSV2_REQUIRE_CXX26_TESTS` is a separate opt-in enforcement switch. CI enables
it only for stable compiler lines whose CMake feature set advertises
`cxx_std_26`; configuration then fails unless both modular and single-header
C++26 compile-only targets are registered. Other compiler rows continue to
enforce C++20 and C++23 without making a false C++26 support claim.

CI selects stable compiler lines already supplied by the stable hosted runner
or its distribution. It deliberately avoids preview runner images, compiler
snapshots, PPAs, and nightly LLVM repositories. The compiler ID and version
line are verified by CMake during configuration; stable runner servicing may
advance the patch component without silently changing the enforced line.

Automatic quick workflows preserve the existing Linux, Windows, macOS, and
fuzz/benchmark check identities. Manual `Full verification` and `Performance
evidence` workflows provide the exhaustive matrix and version-bound evidence:

| Tier | Trigger | Scope |
| --- | --- | --- |
| quick | pull request/push | representative runtime matrix, contracts, checksum/allocation checks, install consumers, fuzz smoke |
| full | manual | full standard/header/variant matrix, C++26 compile-only, extended fuzz, install consumers, non-blocking coverage |
| perf | manual | generated corpus, A/A and A/B reports, current-tree metrics; hosted is always exploratory |

Every platform verifies that installing with all verification components
enabled exports no Catch2 or Google Benchmark files and builds the tracked
CMake consumer under `test/contracts/consumer`. Linux also exercises its
relocatable pkg-config consumer. CI uploads JUnit, coverage, corpus manifests,
and benchmark reports as artifacts and never depends on a hard-coded test
count. Full topology and contributor instructions are in
[`test/README.md`](test/README.md), [`benchmark/README.md`](benchmark/README.md),
and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Installing and Consuming with CMake

csv2 installs an exported CMake package, its modular headers, pkg-config
metadata, and licenses. A minimal installation is:

```bash
cmake -S . -B build-install -DCMAKE_BUILD_TYPE=Release
cmake --build build-install
cmake --install build-install --prefix /absolute/path/to/csv2-prefix
```

An independent consumer can then use the namespaced interface target:

```cmake
cmake_minimum_required(VERSION 3.10)
project(csv2_consumer LANGUAGES CXX)

find_package(csv2 CONFIG REQUIRED)
add_executable(csv2_consumer main.cpp)
target_link_libraries(csv2_consumer PRIVATE csv2::csv2)
```

Configure that consumer with
`-DCMAKE_PREFIX_PATH=/absolute/path/to/csv2-prefix`. Linux GCC CI performs this
configure/build/run check against the freshly installed package.

## Generating Single Header

```bash
python3 utils/amalgamate/amalgamate.py -c single_include.json -s .
```

Commit modular-header and generated single-header changes together. To verify
that generation is reproducible, run the command above and then:

```bash
git diff --exit-code -- single_include/csv2/csv2.hpp
```

## Contributing
Contributions are welcome, have a look at the [CONTRIBUTING.md](CONTRIBUTING.md) document for more information.

## License
The project is available under the [MIT](https://opensource.org/licenses/MIT) license.
