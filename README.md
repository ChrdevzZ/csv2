<p align="center">
  <img height="75" src="img/logo.png" alt="csv2"/>
</p>

## Table of Contents

*    [CSV Reader](#csv-reader)
     *    [Performance Benchmark](#performance-benchmark)
     *    [Reader API](#reader-api)
*    [CSV Writer](#csv-writer)
     *    [Writer API](#writer-api)
*    [Compiling Tests](#compiling-tests)
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
`parse()`, or `parse_view()` replaces the previous input source.

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
mkdir build-benchmark
cd build-benchmark
cmake .. \
  -DCSV2_BUILD_BENCHMARKS=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build . --target csv2_benchmark
hyperfine --warmup 3 --runs 5 \
  './benchmark/csv2_benchmark /absolute/path/input.csv'
```

The table below is historical (23 September 2022). Compare new measurements
only when the input, csv2 commit, compiler, flags, operating system, CPU, and
storage are recorded consistently.

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
  
  // Use this if you'd like to mmap and read from file
  template <typename StringType>
  bool mmap(StringType&& filename);
  template <typename StringType>
  bool mmap(StringType&& filename, std::error_code& error);

  // Lvalues are borrowed; rvalues are owned by the Reader
  template <typename StringType>
  bool parse(StringType&& contents);

  // C++17: borrowed view; its storage must outlive Reader access
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
mkdir build
cd build
cmake .. -DCSV2_BUILD_TESTS=ON
cmake --build .
ctest --output-on-failure
```

The test build compiles the modular and single-header forms in strict C++11
and C++17 modes, checks every public header independently, and adds
no-exceptions and platform-failure-path tests where supported. With GCC,
Clang, or AppleClang, add `-DCSV2_ENABLE_SANITIZERS=ON` to enable ASan and
UBSan.

## Generating Single Header

```bash
python3 utils/amalgamate/amalgamate.py -c single_include.json -s .
```

## Contributing
Contributions are welcome, have a look at the [CONTRIBUTING.md](CONTRIBUTING.md) document for more information.

## License
The project is available under the [MIT](https://opensource.org/licenses/MIT) license.
