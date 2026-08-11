<p align="center">
  <img height="75" src="img/logo.png" alt="csv2"/>
</p>

<p align="center">
  <a href="https://github.com/ChrdevzZ/csv2/actions/workflows/linux.yml"><img src="https://github.com/ChrdevzZ/csv2/actions/workflows/linux.yml/badge.svg" alt="Linux"></a>
  <a href="https://github.com/ChrdevzZ/csv2/actions/workflows/windows.yml"><img src="https://github.com/ChrdevzZ/csv2/actions/workflows/windows.yml/badge.svg" alt="Windows"></a>
  <a href="https://github.com/ChrdevzZ/csv2/actions/workflows/macos.yml"><img src="https://github.com/ChrdevzZ/csv2/actions/workflows/macos.yml/badge.svg" alt="macOS"></a>
  <img src="https://img.shields.io/badge/C%2B%2B-11-blue.svg" alt="C++11">
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
keep that string alive and must not perform an operation that invalidates its
`c_str()` pointer while the reader is in use. Passing an rvalue string transfers
the contents to storage owned by the reader, so parsing a temporary is safe.
When C++17 is available, `parse_view()` remains a borrowed API and the
`std::string_view` storage must outlive reader access. Calling `mmap()`,
`parse()`, or `parse_view()` replaces the previous input source. Passing a
view of the same reader's owned or mapped source back to `parse_view()` keeps
that backing storage alive and selects the view without copying.

`Reader::mmap()` returns `false` for ordinary open or mapping failures and
clears the previous source; it does not translate those failures into
exceptions. Use the overload accepting `std::error_code&` when the reason is
needed. Memory mapping can be disabled consistently for all translation units
with `CSV2_HAS_MMAP=0`.

Records may be terminated by LF or CRLF. LF and CRLF inside a quoted field are
part of that field, and doubled quote characters (`""`) do not close it. A final
record delimiter terminates the last record without creating another empty
record; delimiters before the final one can still represent empty records.
Standalone CR characters are treated as record content.

A field delimiter at the end of a non-empty record creates a final empty
`Cell`. A record containing no characters remains an empty `Row` with zero
cells. `Cell::read_value()` trims according to the configured policy, retains
outer quote characters, folds each adjacent pair of configured quote
characters into one, and appends the decoded value without modifying content
already present in the output container.

### Performance Benchmark

The benchmark executable performs one memory-map and full cell traversal per
process. Use an external harness such as Hyperfine for isolated repetitions;
the command below performs 3 warmup runs followed by 5 measured runs.

```bash
cmake -S . -B build-benchmark \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-benchmark --target csv2_benchmark
hyperfine --warmup 3 --runs 5 \
  './build-benchmark/benchmark/csv2_benchmark /absolute/path/input.csv'
```

The table below is historical (23 September 2022). Compare new measurements
only when the input, csv2 commit, compiler, flags, operating system, CPU, and
storage are recorded consistently. CI currently verifies that the benchmark
compiles in the Linux GCC and Windows MSVC jobs; it does not run performance
measurements.

#### System Details

| Type            | Value                                                                                                     |
| --------------- | --------------------------------------------------------------------------------------------------------- |
| Processor       | 11th Gen Intel(R) Core(TM) i9-11900KF @ 3.50GHz   3.50 GHz                                                |
| Installed RAM   | 32.0 GB (31.9 GB usable)                                                                                  |
| SSD             | [ADATA SX8200PNP](https://www.adata.com/upload/downloadfile/Datasheet_XPG%20SX8200%20Pro_EN_20181017.pdf) |
| OS              | Ubuntu 20.04 LTS running on WSL in Windows 11                                                             |
| C++ Compiler    | g++ (Ubuntu 10.3.0-1ubuntu1~20.04) 10.3.0                                                                 |

#### Results (as of 23 SEP 2022)

| Dataset | File Size | Rows | Cols | Time |
|:---     |       ---:|  ---:|  ---:|  ---:|
| [Denver Crime Data](https://www.kaggle.com/paultimothymooney/denver-crime-data) | 111 MB | 479,100 | 19 | 0.102s |
| [AirBnb Paris Listings](https://www.kaggle.com/juliatb/airbnb-paris) | 196 MB | 141,730 | 96 | 0.170s |
| [2015 Flight Delays and Cancellations](https://www.kaggle.com/usdot/flight-delays) | 574 MB | 5,819,079 | 31 | 0.603s |
| [StackLite: Stack Overflow questions](https://www.kaggle.com/stackoverflow/stacklite) | 870 MB | 17,203,824 | 7 | 0.911s |
| [Used Cars Dataset](https://www.kaggle.com/austinreese/craigslist-carstrucks-data) | 1.4 GB | 539,768 | 25 | 0.947s |
| [Title-Based Semantic Subject Indexing](https://www.kaggle.com/hsrobo/titlebased-semantic-subject-indexing) | 3.7 GB | 12,834,026 | 4 |2.867s|
| [Bitcoin tweets - 16M tweets](https://www.kaggle.com/alaix14/bitcoin-tweets-20160101-to-20190329) | 4 GB | 47,478,748 | 9 | 3.290s |
| [DDoS Balanced Dataset](https://www.kaggle.com/devendra416/ddos-datasets) | 6.3 GB | 12,794,627 | 85 | 6.963s |
| [Seattle Checkouts by Title](https://www.kaggle.com/city-of-seattle/seattle-checkouts-by-title) | 7.1 GB | 34,892,623 | 11 | 7.698s |
| [SHA-1 password hash dump](https://www.kaggle.com/urvishramaiya/have-i-been-pwnd) | 11 GB | 2,62,974,241 | 2 | 10.775s |
| [DOHUI NOH scaled_data](https://www.kaggle.com/seaa0612/scaled-data) | 16 GB | 496,782 | 3213 | 16.553s |

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
  template <typename StringType>
  bool mmap(StringType&& filename);
  template <typename StringType>
  bool mmap(StringType&& filename, std::error_code& error);

  // Lvalues are borrowed; rvalues are owned by the Reader
  template <typename StringType>
  bool parse(StringType&& contents);

  // C++17: externally owned storage remains borrowed. A view into this
  // Reader's current owned or mapped source retains that backing source.
  bool parse_view(std::string_view contents);

  // Shape
  size_t rows(bool ignore_empty_lines = false) const;
  size_t cols() const;
  
  // Row iterator
  // If first_row_is_header, row iteration will start
  // from the second row
  RowIterator begin() const;
  RowIterator end() const;

  // Access the first row of the CSV
  Row header() const;
};
```

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
};
```

## CSV Writer

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

This is intentionally a basic writer: values are emitted exactly as supplied.
It does not quote or escape delimiters, quote characters, or newlines. A row
with zero values writes one newline, as does a row containing one empty string,
so those two shapes are not reversibly distinguishable.

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
```

## Compiling Tests

```bash
cmake -S . -B build -DCSV2_BUILD_TESTS=ON
cmake --build build --config Debug
ctest --test-dir build -C Debug --output-on-failure
```

The test build runs the same behavioral suite against the modular and
single-header forms in strict C++11, C++14, C++17, C++20, and C++23 modes.
CMake 3.12 or newer is required to request C++20, and CMake 3.20 or newer is
required to request C++23. Those modes are registered only when the compiler
advertises support through CMake; older supported toolchains register every
mode they understand. The build also checks every public header independently
in C++11 and C++17 modes and adds no-exceptions and platform-failure-path tests
where supported.

`-DCSV2_ENABLE_SANITIZERS=ON` enables ASan and UBSan with GCC, Clang, and
AppleClang. With the Microsoft compiler it enables MSVC AddressSanitizer only.
The option deliberately rejects Clang-CL because the repository does not
currently define a supported sanitizer configuration for that frontend.

| Standard | Modular runtime test | Single-header runtime test |
|:---------|:---------------------|:---------------------------|
| C++11 | `csv2.module.cxx11` | `csv2.single_header.cxx11` |
| C++14 | `csv2.module.cxx14` | `csv2.single_header.cxx14` |
| C++17 | `csv2.module.cxx17` | `csv2.single_header.cxx17` |
| C++20 | `csv2.module.cxx20` | `csv2.single_header.cxx20` |
| C++23 | `csv2.module.cxx23` | `csv2.single_header.cxx23` |

The `CSV2_REQUIRE_MODERN_STANDARD_TESTS` option is an enforcement switch for
modern CI: configuration fails unless all four exact C++20/C++23 CTest names
in the table are registered. Local compatibility remains conditional, while
the Linux GCC 13 job enables this switch so that CI cannot silently lose those
four variants.

CI is split into Linux, Windows, and macOS workflows, with warnings treated as
errors throughout:

- Linux GCC 13 builds the benchmark, runs the full test suite, requires the
  C++20/C++23 variants, installs the package, builds and runs an independent
  `find_package(csv2 CONFIG REQUIRED)` consumer, and checks single-header
  regeneration.
- Linux Clang 18 with libc++ runs the tests under ASan and UBSan and checks
  first-party C++ formatting.
- Windows runs MSVC Debug (including benchmark compilation and installation),
  a separate MSVC Release AddressSanitizer configuration, and Clang-CL Release.
  The sanitizer job directly runs every test executable except the deliberately
  expected-to-fail no-mmap benchmark probe.
- macOS builds and tests with AppleClang.

The workflows run for pushes and pull requests targeting `main` or `master`,
merge queues, and manual dispatch. Repository-side workflow files cannot by
themselves configure GitHub branch-protection or ruleset policy.

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
