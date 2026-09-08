#include <csv2_test/assertions.hpp>
#include <csv2_test/reader_support.hpp>
#include <csv2_test/sinks.hpp>

#include <cstddef>
#include <deque>
#include <iterator>
#include <list>
#include <memory>
#include <string>
#include <vector>

#if CSV2_HAS_MEMORY_RESOURCE
#include <memory_resource>
#endif

using namespace csv2_test;

namespace {
struct AllocationCounts {
  std::size_t calls = 0;
  std::size_t elements = 0;
};

template <class T> struct CountingAllocator {
  using value_type = T;
  AllocationCounts *counts;
  explicit CountingAllocator(AllocationCounts &value) : counts(&value) {}
  template <class U> CountingAllocator(const CountingAllocator<U> &other) : counts(other.counts) {}
  T *allocate(std::size_t count) {
    ++counts->calls;
    counts->elements += count;
    return std::allocator<T>().allocate(count);
  }
  void deallocate(T *data, std::size_t count) { std::allocator<T>().deallocate(data, count); }
  template <class U> struct rebind {
    using other = CountingAllocator<U>;
  };
  template <class U> bool operator==(const CountingAllocator<U> &other) const {
    return counts == other.counts;
  }
  template <class U> bool operator!=(const CountingAllocator<U> &other) const {
    return !(*this == other);
  }
};
} // namespace

CSV2_TEST_CASE("reader.extract.preserve-amortized-growth-and-reuse-output-capacity",
               "reader.extract") {
  ReaderWithoutHeader reader;
  std::string input = "\"" + std::string(64, 'a') + "\"\"b\"";
  CSV2_REQUIRE(reader.parse(input));
  const auto row = *reader.begin();
  const auto cell = *row.begin();
  const std::string decoded = "\"" + std::string(64, 'a') + "\"b\"";
  using Buffer = std::vector<char, CountingAllocator<char>>;
  for (int operation = 0; operation != 3; ++operation) {
    const std::string &chunk = operation == 1 ? decoded : input;
    const auto extract = [&](Buffer &output) {
      if (operation == 0)
        cell.read_raw_value(output);
      else if (operation == 1)
        cell.read_value(output);
      else
        row.read_raw_value(output);
    };
    AllocationCounts actual_counts, reference_counts;
    Buffer actual{CountingAllocator<char>(actual_counts)};
    Buffer reference{CountingAllocator<char>(reference_counts)};
    extract(actual);
    for (char character : chunk)
      reference.push_back(character);
    CSV2_CHECK(actual == reference);
    CSV2_CHECK(actual_counts.calls <= reference_counts.calls);
    actual.clear();
    reference.clear();
    actual.push_back(':');
    reference.push_back(':');
    for (std::size_t repeat = 0; repeat != 256; ++repeat) {
      extract(actual);
      for (char character : chunk)
        reference.push_back(character);
    }
    CSV2_CHECK(actual == reference);
    // Compare with ordinary vector growth, allowing different geometric factors.
    CSV2_CHECK(actual_counts.calls <= 2 * reference_counts.calls);
    CSV2_CHECK(actual_counts.elements <= 2 * reference_counts.elements);
    actual.reserve(reference.size());
    const std::size_t calls = actual_counts.calls;
    for (int reuse = 0; reuse != 2; ++reuse) {
      actual.clear();
      extract(actual);
      CSV2_CHECK(std::string(actual.begin(), actual.end()) == chunk);
      actual.clear();
      actual.push_back(':');
      for (std::size_t repeat = 0; repeat != 256; ++repeat)
        extract(actual);
      CSV2_CHECK(actual == reference);
      CSV2_CHECK(actual_counts.calls == calls);
    }
  }
}

CSV2_TEST_CASE("reader.extract.preserve-original-cell-bounds-for-custom-trim-policies",
               "reader.extract") {
  using AbsoluteTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                          csv2::first_row_is_header<false>, AbsoluteOffsetTrim>;
  AbsoluteTrimReader reader;
  std::string input("a,xb");
  AbsoluteOffsetTrim::expected_buffer() = input.data();
  CSV2_REQUIRE(reader.parse(input));
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"a", "b"}));
}

CSV2_TEST_CASE("reader.extract.expose-the-address-and-length-of-each-logical-row",
               "reader.extract") {
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
    CSV2_REQUIRE(reader.parse(input));

    auto row = reader.begin();
    for (std::size_t i = 0; i < test_case.offsets.size(); ++i, ++row) {
      CSV2_REQUIRE(row != reader.end());
      const auto value = *row;
      CSV2_REQUIRE(value.address() == input.data() + test_case.offsets[i]);
      CSV2_REQUIRE(std::string(value.address(), value.length()) == test_case.records[i]);
    }
    CSV2_REQUIRE(row == reader.end());
  }

  ReaderWithoutHeader empty;
  CSV2_REQUIRE(empty.header().address() == nullptr);
  CSV2_REQUIRE(empty.header().length() == 0);
}

CSV2_TEST_CASE("reader.extract.read-raw-and-decoded-cell-values-by-appending-to-the-output",
               "reader.extract") {
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
    CSV2_REQUIRE(reader.parse(input));
    CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({quote_case.expected}));
  }

  ReaderWithoutHeader reader;
  std::string input(" \t\"a\"\"b\"\t ");
  CSV2_REQUIRE(reader.parse(input));
  const auto cell = *(*reader.begin()).begin();

  std::string raw("raw:");
  cell.read_raw_value(raw);
  CSV2_REQUIRE(raw == "raw: \t\"a\"\"b\"\t ");

  std::string decoded("value:");
  cell.read_value(decoded);
  CSV2_REQUIRE(decoded == "value:\"a\"b\"");
}

CSV2_TEST_CASE("reader.extract.do-not-reserve-when-reading-an-empty-raw-range", "reader.extract") {
  const PublicCell cell;
  RejectZeroReserveBuffer cell_output;
  cell.read_raw_value(cell_output);
  CSV2_REQUIRE_FALSE(cell_output.reserve_called);

  const PublicRow row;
  RejectZeroReserveBuffer row_output;
  row.read_raw_value(row_output);
  CSV2_REQUIRE_FALSE(row_output.reserve_called);
}

CSV2_TEST_CASE("reader.extract.copy-fields-to-generic-containers-and-output-iterators",
               "reader.extract") {
  ReaderWithoutHeader reader;
  std::string input(" \t\"a\"\"b\"\t ");
  CSV2_REQUIRE(reader.parse(input));
  const auto cell = *(*reader.begin()).begin();

  std::deque<char> raw;
  cell.read_raw_value(raw);
  CSV2_REQUIRE(std::string(raw.begin(), raw.end()) == input);

  std::list<char> decoded;
  cell.read_value(decoded);
  CSV2_REQUIRE(std::string(decoded.begin(), decoded.end()) == "\"a\"b\"");

  AppendOnlyBuffer appended;
  cell.read_value(appended);
  CSV2_REQUIRE(appended.value == "\"a\"b\"");

  std::vector<char> copied;
  cell.copy_raw_to(std::back_inserter(copied));
  CSV2_REQUIRE(std::string(copied.begin(), copied.end()) == input);

  char decoded_buffer[32] = {};
  char *const decoded_end = cell.decode_to(decoded_buffer);
  CSV2_REQUIRE(std::string(decoded_buffer, decoded_end) == "\"a\"b\"");

  std::string content;
  cell.copy_content_to(std::back_inserter(content));
  CSV2_REQUIRE(content == "a\"b");

#if CSV2_HAS_MEMORY_RESOURCE
  std::pmr::monotonic_buffer_resource resource;
  std::pmr::string pmr_value(&resource);
  cell.read_value(pmr_value);
  CSV2_REQUIRE(pmr_value == "\"a\"b\"");
#endif
}

CSV2_TEST_CASE("reader.extract.batch-contiguous-raw-and-decoded-field-segments", "reader.extract") {
  ReaderWithoutHeader reader;
  std::string input("plain,\"a\"\"b\"\"c\"");
  CSV2_REQUIRE(reader.parse(input));
  const auto row = *reader.begin();

  AppendCountingBuffer raw_row;
  row.read_raw_value(raw_row);
  CSV2_REQUIRE(raw_row.value == input);
  CSV2_REQUIRE(raw_row.append_calls == 1);

  auto cell = row.begin();
  AppendCountingBuffer plain;
  (*cell).read_value(plain);
  CSV2_REQUIRE(plain.value == "plain");
  CSV2_REQUIRE(plain.append_calls == 1);

  ++cell;
  AppendCountingBuffer escaped;
  (*cell).read_value(escaped);
  CSV2_REQUIRE(escaped.value == "\"a\"b\"c\"");
  CSV2_REQUIRE(escaped.append_calls == 3);
}

#if CSV2_HAS_STRING_VIEW
CSV2_TEST_CASE("reader.extract.expose-an-empty-view-from-a-default-cell", "reader.extract") {
  const PublicCell cell;
  CSV2_REQUIRE(cell.raw_trimmed_view().empty());
  CSV2_REQUIRE(cell.read_view().empty());
}
#endif

CSV2_TEST_CASE("reader.extract.preserve-existing-output-when-appending-a-raw-row",
               "reader.extract") {
  ReaderWithoutHeader reader;
  std::string input("a,b");
  CSV2_REQUIRE(reader.parse(input));

  std::string output("pre:");
  (*reader.begin()).read_raw_value(output);
  CSV2_REQUIRE(output == "pre:a,b");
}

CSV2_TEST_CASE("reader.extract.append-a-raw-row-to-a-reserve-only-output-type", "reader.extract") {
  ReaderWithoutHeader reader;
  std::string input("a,b");
  CSV2_REQUIRE(reader.parse(input));

  ReserveOnlyBuffer output("pre:");
  (*reader.begin()).read_raw_value(output);
  CSV2_REQUIRE(output.value == "pre:a,b");
}
