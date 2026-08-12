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
and mutation requirements. Calling `mmap()`, `parse()`, or `parse_view()`
replaces the previous input source. Passing a view of the same reader's owned
or mapped source back to `parse_view()` keeps that backing storage alive and
selects the view without copying.

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
mapping fails with `std::errc::invalid_argument`. A `std::string_view` remains
rejected because its range does not promise an accessible terminator. A native
file handle may also be mapped; the caller retains ownership and must keep it
open for the mapped source's lifetime.

`include/csv2/mio.hpp` vendors [mandreyel/mio](https://github.com/mandreyel/mio),
first imported by csv2 commit `e51a8df` on 2020-04-23. Its MIT license remains
in `LICENSE.mio`. Local csv2 patches preserve mapping ownership/error handling,
support explicit no-mmap builds, and restrict file paths to the safe types
listed above; no independent upstream version tag was recorded by the original
import.

Records may be terminated by LF or CRLF. LF and CRLF inside a quoted field are
part of that field, and doubled quote characters (`""`) do not close it. A final
record delimiter terminates the last record without creating another empty
record; delimiters before the final one can still represent empty records.
Standalone CR characters are treated as record content. Field delimiters are
configurable but cannot be CR or LF because those bytes are reserved for record
boundaries; an unsupported delimiter is rejected at compile time.

A field delimiter at the end of a non-empty record creates a final empty
`Cell`. A record containing no characters remains an empty `Row` with zero
cells. `Cell::read_value()` trims according to the configured policy, retains
outer quote characters, folds each adjacent pair of configured quote
characters into one, and appends the decoded value without modifying content
already present in the output container.

### Performance Benchmark

`csv2_benchmark` measures one operation in the current source tree: mapping,
row and cell traversal, extraction, ranges, integer conversion, or writing.
Source preparation is outside each operation timer except for `map_only`, where
mapping is the operation being measured. GiB/s always uses input-corpus bytes
as its denominator, including writer operations; it is not writer output
bandwidth. The benchmark emits a semantic checksum and optional allocation or
hardware-counter data. Hosted CI verifies checksums and the zero-allocation
traversal contract; hosted timing is never used to accept or reject a change.

```bash
CANDIDATE="$(git rev-parse HEAD)"
cmake -S . -B build-benchmark \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCSV2_BENCHMARK_REVISION="$CANDIDATE" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-benchmark --target csv2_benchmark
./build-benchmark/benchmark/csv2_benchmark \
  --operation rows_cells --input /absolute/path/input.csv \
  --source mmap --iterations 20
```

Cross-revision claims use the separate C++11 `common_driver.cpp`, extracted
from the candidate commit and compiled unchanged against both exact archived
header trees. See
[`benchmark/README.md`](benchmark/README.md) for reproducible extraction and
build commands, A/A calibration, paired execution, raw-sample retention, and
the provenance required for a reviewable result. No comparative performance
number is published without its machine-specific JSON report.

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
Contiguous character fields are scanned and written in segments; other
streamable values are first formatted with a copy of the destination stream's
locale, flags, precision, and fill state, then escaped. A row with zero values
writes one newline, as does a raw row containing one empty string, so those two
raw shapes are not reversibly distinguishable.

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
cmake -S . -B build -DCSV2_BUILD_TESTS=ON
cmake --build build --config Debug
ctest --test-dir build -C Debug --output-on-failure
```

The test build runs the same behavioral suite against the modular and
single-header forms in strict C++11, C++14, C++17, C++20, and C++23 modes. It
also adds C++26 forward-compatibility compile-only targets when CMake and the compiler
advertise that mode. CMake 3.12 or newer is required to request C++20, CMake
3.20 or newer is required to request C++23, and CMake 3.30 or newer is required
to request C++26. C++11 through C++23 prove behavior; C++26 only proves that
the public surface still compiles and does not enable any C++26-only feature.
These modes prove that csv2 builds and behaves correctly in
the selected language mode; they do not claim that a compiler or standard
library completely implements every feature of that standard. Older supported
toolchains register every mode they understand. The build also checks every
public header independently in C++11, C++17, C++20, and C++23 modes, runs
no-mmap through C++23, runs no-exceptions in C++11/C++20/C++23, compiles
standard-specific contract translation units, and includes deterministic fuzz
and benchmark checksum smoke tests.

`-DCSV2_ENABLE_SANITIZERS=ON` enables ASan and UBSan with GCC, Clang, and
AppleClang. With the Microsoft compiler it enables MSVC AddressSanitizer only.
With x64 Clang-CL it enables ASan and UBSan, discovers and validates the
compiler-rt libraries installed beside the selected compiler, and links the
required dynamic ASan and standalone UBSan runtimes. Clang-CL sanitizer builds
must use a non-Debug CRT configuration; CI uses Release because Clang-CL ASan
does not support the Debug CRT. The Clang-CL configuration disables only the
UBSan `object-size` check because it diagnoses the MSVC standard library's
`forward_list` pseudo-node implementation. Linux enables leak detection through
ASan; Windows disables it because LeakSanitizer is not supported there.

| Standard | Modular runtime test | Single-header runtime test |
|:---------|:---------------------|:---------------------------|
| C++11 | `csv2.module.cxx11` | `csv2.single_header.cxx11` |
| C++14 | `csv2.module.cxx14` | `csv2.single_header.cxx14` |
| C++17 | `csv2.module.cxx17` | `csv2.single_header.cxx17` |
| C++20 | `csv2.module.cxx20` | `csv2.single_header.cxx20` |
| C++23 | `csv2.module.cxx23` | `csv2.single_header.cxx23` |
| C++26 compile-only | `csv2_standard_contract_module_cxx26` | `csv2_standard_contract_single_cxx26` |

The `CSV2_REQUIRE_MODERN_STANDARD_TESTS` option is an enforcement switch for
modern CI: configuration fails unless all four exact C++20/C++23 CTest names
in the table are registered. Local compatibility remains conditional, while
all Linux, Windows, and macOS CI jobs enable this switch so that a toolchain
change cannot silently remove those four variants.

`CSV2_REQUIRE_CXX26_TESTS` is a separate opt-in enforcement switch. CI enables
it only for stable compiler lines whose CMake feature set advertises
`cxx_std_26`; configuration then fails unless both exact C++26 compile-only
targets in the table are registered. Other compiler rows continue to enforce
C++20 and C++23 without making a false C++26 support claim.

CI selects stable compiler lines already supplied by the stable hosted runner
or its distribution. It deliberately avoids preview runner images, compiler
snapshots, PPAs, and nightly LLVM repositories. The compiler ID and version
line are verified by CMake during configuration; stable runner servicing may
advance the patch component without silently changing the enforced line.

CI is split into Linux, Windows, and macOS workflows, with warnings treated as
errors throughout:

| Platform | Normal coverage | Sanitizer coverage |
|:---------|:----------------|:-------------------|
| Linux | GCC 14 and Clang 18 with libc++; full tests, benchmark checksums, installation consumer | Separate GCC 14 and Clang 18 ASan/UBSan jobs with leak detection |
| Windows | MSVC 19.51 and Clang-CL 22.1; MSVC verifies benchmark checksums and installation consumer | MSVC ASan and Clang-CL ASan/UBSan |
| macOS | AppleClang 21 full tests, benchmark checksums, installation consumer | — |

The Linux GCC job also builds an independent
`find_package(csv2 CONFIG REQUIRED)` consumer and verifies single-header
regeneration. The non-sanitized Linux Clang job checks first-party formatting
with Clang Format 18. Sanitizer jobs run the labeled runtime suite; Windows
executes its generated CTest manifest directly to avoid CTest/ASan
process-management problems. A separate pull-request, weekly, and manually
dispatchable workflow runs the deterministic fuzz smoke, a 5,000-input
libFuzzer corpus smoke, and all benchmark checksums.

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
