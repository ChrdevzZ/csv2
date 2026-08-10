#include "doctest.hpp"

#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#endif

#include <cstddef>
#include <cstdio>
#include <exception>
#include <fstream>
#include <forward_list>
#include <list>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>
#include <vector>

#if defined(__linux__)
#include <dirent.h>
#elif defined(_WIN32)
#include <windows.h>
#endif

using doctest::test_suite;

namespace {

using ReaderWithoutHeader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                         csv2::first_row_is_header<false>>;
using ReaderWithHeader =
    csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>, csv2::first_row_is_header<true>>;

template <typename RowType> std::vector<std::string> read_cells(const RowType &row) {
  std::vector<std::string> result;
  for (const auto cell : row) {
    std::string value;
    cell.read_value(value);
    result.push_back(value);
  }
  return result;
}

template <typename ReaderType>
std::vector<std::vector<std::string>> read_rows(const ReaderType &reader) {
  std::vector<std::vector<std::string>> result;
  for (const auto row : reader)
    result.push_back(read_cells(row));
  return result;
}

struct StringLikeView {
  StringLikeView(const char *data, std::size_t size) : data(data), size_in_bytes(size) {}

  const char *c_str() const { return data; }
  std::size_t size() const { return size_in_bytes; }

  const char *data;
  std::size_t size_in_bytes;
};

class LvalueCloseStream : public std::ostringstream {
public:
  LvalueCloseStream() : closed(false) {}

  void close() & { closed = true; }

  bool closed;
};

class CountingCloseStream : public std::ostringstream {
public:
  void close() { ++close_count; }

  int close_count{0};
};

class ThrowingCloseStream : public std::ostringstream {
public:
  void close() {
    ++close_count;
    throw std::runtime_error("close failed");
  }

  int close_count{0};
};

class ReserveTrackingBuffer {
public:
  explicit ReserveTrackingBuffer(const char *prefix) : value(prefix) {}

  std::size_t size() const { return value.size(); }
  void reserve(std::size_t requested) {
    last_reserve = requested;
    value.reserve(requested);
  }
  void push_back(char character) { value.push_back(character); }

  std::string value;
  std::size_t last_reserve{0};
};

#if CSV2_HAS_MMAP && (defined(__linux__) || defined(_WIN32))
std::size_t process_handle_count() {
#if defined(_WIN32)
  DWORD count = 0;
  if (!::GetProcessHandleCount(::GetCurrentProcess(), &count))
    return std::numeric_limits<std::size_t>::max();
  return static_cast<std::size_t>(count);
#else
  DIR *directory = ::opendir("/proc/self/fd");
  if (!directory)
    return std::numeric_limits<std::size_t>::max();

  std::size_t count = 0;
  while (::readdir(directory))
    ++count;
  ::closedir(directory);
  return count;
#endif
}
#endif

const char *writer_output_path() {
#if defined(CSV2_TEST_WRITER_OUTPUT)
  return CSV2_TEST_WRITER_OUTPUT;
#elif defined(CSV2_TEST_SINGLE_HEADER)
  return "csv2-single-header-writer-output.csv";
#else
  return "csv2-module-writer-output.csv";
#endif
}

} // namespace

#if CSV2_HAS_MMAP
TEST_CASE("Read a file, its header, rows, columns, and cells" * test_suite("Reader")) {
  ReaderWithHeader reader;
  REQUIRE(reader.mmap("inputs/test_01.csv"));

  REQUIRE(read_cells(reader.header()) == std::vector<std::string>({"a", "b", "c"}));
  REQUIRE(reader.cols() == 3);
  REQUIRE(reader.rows() == 2);
  REQUIRE(read_rows(reader) ==
          std::vector<std::vector<std::string>>({{"1", "2", "3"}, {"4", "5", "6"}}));
}
#endif

TEST_CASE("Honor delimiter, quote, and trim policies" * test_suite("Reader")) {
  using TrimmedReader =
      csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'\''>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_whitespace>;
  TrimmedReader trimmed;
  std::string trimmed_input(" a | 'b|c' | 'd''e' ");
  REQUIRE(trimmed.parse(trimmed_input));
  REQUIRE(read_cells(*trimmed.begin()) == std::vector<std::string>({"a", "'b|c'", "'d'e'"}));

  using UntrimmedReader =
      csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'\''>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::no_trimming>;
  UntrimmedReader untrimmed;
  std::string untrimmed_input(" a | b ");
  REQUIRE(untrimmed.parse(untrimmed_input));
  REQUIRE(read_cells(*untrimmed.begin()) == std::vector<std::string>({" a ", " b "}));
}

TEST_CASE("Handle record terminators and quoted newlines" * test_suite("Reader")) {
  struct RecordCase {
    const char *input;
    std::vector<std::vector<std::string>> expected;
  };
  const RecordCase cases[] = {
      {"a,b\n1,2", {{"a", "b"}, {"1", "2"}}},
      {"a,b\n1,2\n", {{"a", "b"}, {"1", "2"}}},
      {"a,b\r\n1,2", {{"a", "b"}, {"1", "2"}}},
      {"a,b\r\n1,2\r\n", {{"a", "b"}, {"1", "2"}}},
      {"a,b\rstandalone", {{"a", "b\rstandalone"}}},
      {"a,\"b\nc\",d\r\n1,\"x\r\ny\",3\r\n", {{"a", "\"b\nc\"", "d"}, {"1", "\"x\r\ny\"", "3"}}},
      {"a,\"b\"\"c\nstill\",d\nx,y,z\n", {{"a", "\"b\"c\nstill\"", "d"}, {"x", "y", "z"}}},
      {"a,\"b\nc,d", {{"a", "\"b\nc,d"}}},
  };

  for (const auto &test_case : cases) {
    ReaderWithoutHeader reader;
    std::string input(test_case.input);
    REQUIRE(reader.parse(input));
    REQUIRE(read_rows(reader) == test_case.expected);
  }
}

TEST_CASE("Expose the address and length of each logical row" * test_suite("Reader")) {
  struct AddressCase {
    const char *input;
    std::vector<std::size_t> offsets;
    std::vector<std::string> records;
  };

  const AddressCase cases[] = {
      {"a,b\nc,d", {0, 4}, {"a,b", "c,d"}},
      {"a,b\r\nc,d", {0, 5}, {"a,b", "c,d"}},
      {"a,\"b\nc\"\nd,e", {0, 8}, {"a,\"b\nc\"", "d,e"}},
      {"a\n\nb", {0, 2, 3}, {"a", "", "b"}},
  };

  for (const auto &test_case : cases) {
    ReaderWithoutHeader reader;
    std::string input(test_case.input);
    REQUIRE(reader.parse(input));

    auto row = reader.begin();
    for (std::size_t i = 0; i < test_case.offsets.size(); ++i, ++row) {
      REQUIRE(row != reader.end());
      const auto value = *row;
      REQUIRE(value.address() == input.data() + test_case.offsets[i]);
      REQUIRE(std::string(value.address(), value.length()) == test_case.records[i]);
    }
    REQUIRE(row == reader.end());
  }

  ReaderWithoutHeader empty;
  REQUIRE(empty.header().address() == nullptr);
  REQUIRE(empty.header().length() == 0);
}

TEST_CASE("Preserve trailing empty fields and normalize empty records" * test_suite("Reader")) {
  struct FieldCase {
    const char *row;
    std::vector<std::string> expected;
  };
  const FieldCase field_cases[] = {
      {"a,", {"a", ""}}, {",", {"", ""}}, {",,", {"", "", ""}}, {"a,,", {"a", "", ""}}};
  const char *terminators[] = {"", "\n", "\r\n"};

  for (const auto &field_case : field_cases) {
    for (const auto terminator : terminators) {
      ReaderWithoutHeader reader;
      std::string input(field_case.row);
      input += terminator;
      REQUIRE(reader.parse(input));
      REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({field_case.expected}));
    }
  }

  const char *empty_record_inputs[] = {"a\n\nb\n", "a\r\n\r\nb\r\n"};
  for (const auto input_value : empty_record_inputs) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    REQUIRE(reader.parse(input));
    REQUIRE(reader.rows() == 3);
    REQUIRE(reader.rows(true) == 2);
    REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"a"}, {}, {"b"}}));
  }

  const char *single_empty_records[] = {"\n", "\r\n"};
  for (const auto input_value : single_empty_records) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    REQUIRE(reader.parse(input));
    REQUIRE(reader.rows() == 1);
    REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{}}));
  }

  ReaderWithHeader header_reader;
  std::string header_input("h1,h2,\r\nvalue1,value2,");
  REQUIRE(header_reader.parse(header_input));
  REQUIRE(read_cells(header_reader.header()) == std::vector<std::string>({"h1", "h2", ""}));
  REQUIRE(header_reader.cols() == 3);
  REQUIRE(read_rows(header_reader) ==
          std::vector<std::vector<std::string>>({{"value1", "value2", ""}}));
}

TEST_CASE("Read raw and decoded cell values by appending to the output" * test_suite("Reader")) {
  struct QuoteCase {
    const char *input;
    const char *expected;
  };
  const QuoteCase quote_cases[] = {{"\"\"", "\""},
                                   {"\"\"\"\"", "\"\""},
                                   {"\"a\"\"b\"", "\"a\"b\""},
                                   {"\"a\"\"b\"\"c\"", "\"a\"b\"c\""}};
  for (const auto &quote_case : quote_cases) {
    ReaderWithoutHeader reader;
    std::string input(quote_case.input);
    REQUIRE(reader.parse(input));
    REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({quote_case.expected}));
  }

  ReaderWithoutHeader reader;
  std::string input(" \t\"a\"\"b\"\t ");
  REQUIRE(reader.parse(input));
  const auto cell = *(*reader.begin()).begin();

  std::string raw("raw:");
  cell.read_raw_value(raw);
  REQUIRE(raw == "raw: \t\"a\"\"b\"\t ");

  std::string decoded("value:");
  cell.read_value(decoded);
  REQUIRE(decoded == "value:\"a\"b\"");
}

TEST_CASE("Reserve for existing output when appending a raw row" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,b");
  REQUIRE(reader.parse(input));

  ReserveTrackingBuffer output("pre:");
  (*reader.begin()).read_raw_value(output);
  REQUIRE(output.last_reserve == 7);
  REQUIRE(output.value == "pre:a,b");
}

TEST_CASE("Own rvalue input, borrow lvalue input, and preserve input across moves" *
          test_suite("Reader")) {
  ReaderWithoutHeader temporary_reader;
  const std::string first_cell(512, 'a');
  const std::string temporary_payload = first_cell + ",b\nc,d";
  REQUIRE(temporary_reader.parse(std::string(temporary_payload)));
  std::vector<std::string> heap_churn(512, std::string(temporary_payload.size(), 'x'));
  REQUIRE(heap_churn.size() == 512);
  REQUIRE(read_rows(temporary_reader) ==
          std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));

  ReaderWithoutHeader borrowed_reader;
  std::string borrowed_input("borrowed,data");
  REQUIRE(borrowed_reader.parse(borrowed_input));
  REQUIRE((*borrowed_reader.begin()).address() == borrowed_input.c_str());

  ReaderWithoutHeader string_like_reader;
  std::string string_like_input("generic,value");
  REQUIRE(string_like_reader.parse(
      StringLikeView(string_like_input.c_str(), string_like_input.size())));
  string_like_input.assign(string_like_input.size(), 'x');
  REQUIRE(read_rows(string_like_reader) ==
          std::vector<std::vector<std::string>>({{"generic", "value"}}));

  ReaderWithoutHeader moved(std::move(temporary_reader));
  REQUIRE(temporary_reader.rows() == 0);
  REQUIRE(read_rows(moved) ==
          std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));

  ReaderWithoutHeader assigned;
  assigned = std::move(moved);
  REQUIRE(moved.rows() == 0);
  REQUIRE(read_rows(assigned) ==
          std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));
}

TEST_CASE("Clear old input when replacing a source or a source fails" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  REQUIRE(reader.parse(std::string("owned,data")));

  std::string borrowed("borrowed,data");
  REQUIRE(reader.parse(borrowed));
  REQUIRE((*reader.begin()).address() == borrowed.c_str());

  REQUIRE_FALSE(reader.parse(std::string()));
  REQUIRE(reader.rows() == 0);

#if CSV2_HAS_MMAP
  REQUIRE(reader.parse(borrowed));
  REQUIRE_FALSE(reader.mmap("inputs/this-file-does-not-exist.csv"));
  REQUIRE(reader.rows() == 0);

  REQUIRE(reader.parse(borrowed));
  REQUIRE_FALSE(reader.mmap("inputs/empty.csv"));
  REQUIRE(reader.rows() == 0);
#endif
}

#if CSV2_HAS_MMAP
TEST_CASE("Report mmap errors and release handles after mapping failures" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::error_code error = std::make_error_code(std::errc::address_in_use);
  REQUIRE(reader.mmap("inputs/test_01.csv", error));
  REQUIRE_FALSE(error);

  REQUIRE_FALSE(reader.mmap("inputs/this-file-does-not-exist.csv", error));
  REQUIRE(error);
  REQUIRE(reader.rows() == 0);

  REQUIRE_FALSE(reader.mmap("inputs/empty.csv", error));
  REQUIRE(error);
#if defined(_WIN32)
  REQUIRE(error.value() == ERROR_FILE_INVALID);
#endif

#if defined(__linux__) || defined(_WIN32)
  const std::size_t handles_before = process_handle_count();
  REQUIRE(handles_before != std::numeric_limits<std::size_t>::max());
  for (int attempt = 0; attempt < 2048; ++attempt) {
    mio::mmap_source mapping;
    mapping.map("inputs/empty.csv", error);
    REQUIRE(error);
#if defined(_WIN32)
    REQUIRE(error.value() == ERROR_FILE_INVALID);
#endif
  }
  REQUIRE(process_handle_count() == handles_before);
#endif

  mio::mmap_source mapping;
  mapping.map("inputs/test_01.csv", std::numeric_limits<std::size_t>::max(), 2, error);
  REQUIRE(error);
  REQUIRE(error == std::errc::invalid_argument);
  REQUIRE(error.category() == std::generic_category());
}
#endif

#if ((defined(_MSVC_LANG) && _MSVC_LANG >= 201703L) || __cplusplus >= 201703L)
TEST_CASE("Borrow storage passed through parse_view" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("view,data");
  REQUIRE(reader.parse_view(std::string_view(input)));
  REQUIRE((*reader.begin()).address() == input.data());
}
#endif

TEST_CASE("Compare const iterators and expose a trailing empty cell before end" *
          test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,b\nc,d");
  REQUIRE(reader.parse(input));

  const auto row_begin = reader.begin();
  const auto row_begin_copy = row_begin;
  const auto row_end = reader.end();
  static_assert(noexcept(row_begin == row_begin_copy), "RowIterator equality must be noexcept");
  static_assert(noexcept(row_begin != row_end), "RowIterator inequality must be noexcept");
  REQUIRE(row_begin == row_begin_copy);
  REQUIRE(row_begin != row_end);

  const auto row = *row_begin;
  auto cell_iterator = row.begin();
  const auto first_cell = cell_iterator;
  ++cell_iterator;
  const auto second_cell = cell_iterator;
  const auto cell_end = row.end();
  static_assert(noexcept(first_cell == second_cell), "CellIterator equality must be noexcept");
  static_assert(noexcept(first_cell != cell_end), "CellIterator inequality must be noexcept");
  REQUIRE(first_cell != second_cell);
  REQUIRE(second_cell != cell_end);

  ReaderWithoutHeader trailing_reader;
  std::string trailing_input("a,");
  REQUIRE(trailing_reader.parse(trailing_input));
  const auto trailing_row = *trailing_reader.begin();
  auto trailing_cell = trailing_row.begin();
  ++trailing_cell;
  const auto trailing_end = trailing_row.end();
  REQUIRE(trailing_cell != trailing_end);
  std::string trailing_value;
  (*trailing_cell).read_value(trailing_value);
  REQUIRE(trailing_value.empty());
  ++trailing_cell;
  REQUIRE(trailing_cell == trailing_end);
}

TEST_CASE("Write to streams with and without close" * test_suite("Writer")) {
  std::ostringstream memory_stream;
  {
    csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(memory_stream);
    writer.write_row(std::vector<std::string>({"a", "b"}));
  }
  REQUIRE(memory_stream.str() == "a,b\n");

  const char *const output_path = writer_output_path();
  std::remove(output_path);
  std::ofstream file_stream(output_path);
  REQUIRE(file_stream.is_open());
  {
    csv2::Writer<csv2::delimiter<','>, std::ofstream> writer(file_stream);
    writer.write_row(std::vector<std::string>({"1", "2"}));
  }
  REQUIRE_FALSE(file_stream.is_open());
  std::ifstream output(output_path);
  std::ostringstream output_contents;
  output_contents << output.rdbuf();
  REQUIRE(output_contents.str() == "1,2\n");
  output.close();
  std::remove(output_path);

  LvalueCloseStream lvalue_close_stream;
  {
    csv2::Writer<csv2::delimiter<','>, LvalueCloseStream> writer(lvalue_close_stream);
    writer.write_row(std::vector<std::string>({"x", "y"}));
  }
  REQUIRE(lvalue_close_stream.closed);
  REQUIRE(lvalue_close_stream.str() == "x,y\n");
}

TEST_CASE("Write empty and forward-iterable rows" * test_suite("Writer")) {
  std::ostringstream output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(output);

  writer.write_row(std::vector<std::string>());
  writer.write_row(std::vector<std::string>({""}));
  writer.write_row(std::list<std::string>({"a", "b"}));
  writer.write_row(std::forward_list<std::string>({"x", "y", "z"}));

  REQUIRE(output.str() == "\n\na,b\nx,y,z\n");
}

TEST_CASE("Transfer and release Writer close responsibility exactly once" * test_suite("Writer")) {
  using CountingWriter = csv2::Writer<csv2::delimiter<','>, CountingCloseStream>;
  REQUIRE_FALSE(std::is_copy_constructible<CountingWriter>::value);
  REQUIRE_FALSE(std::is_copy_assignable<CountingWriter>::value);
  REQUIRE(std::is_nothrow_move_constructible<CountingWriter>::value);
  REQUIRE(std::is_nothrow_move_assignable<CountingWriter>::value);

  CountingCloseStream moved_stream;
  {
    CountingWriter source(moved_stream);
    CountingWriter destination(std::move(source));
    source.write_row(std::vector<std::string>({"ignored"}));
    destination.close();
    destination.write_row(std::vector<std::string>({"ignored"}));
  }
  REQUIRE(moved_stream.close_count == 1);
  REQUIRE(moved_stream.str().empty());

  CountingCloseStream source_stream;
  CountingCloseStream replaced_stream;
  {
    CountingWriter source(source_stream);
    CountingWriter destination(replaced_stream);
    destination = std::move(source);
    REQUIRE(replaced_stream.close_count == 1);
  }
  REQUIRE(source_stream.close_count == 1);
  REQUIRE(replaced_stream.close_count == 1);

  CountingCloseStream explicitly_closed_stream;
  {
    CountingWriter writer(explicitly_closed_stream);
    writer.close();
    writer.close();
  }
  REQUIRE(explicitly_closed_stream.close_count == 1);
}

TEST_CASE("Report explicit Writer close errors and suppress destructor close errors" *
          test_suite("Writer")) {
  using ThrowingWriter = csv2::Writer<csv2::delimiter<','>, ThrowingCloseStream>;

  ThrowingCloseStream explicit_stream;
  {
    ThrowingWriter writer(explicit_stream);
    REQUIRE_THROWS_AS(writer.close(), std::runtime_error);
  }
  REQUIRE(explicit_stream.close_count == 1);

  ThrowingCloseStream destructor_stream;
  {
    ThrowingWriter writer(destructor_stream);
  }
  REQUIRE(destructor_stream.close_count == 1);
}
