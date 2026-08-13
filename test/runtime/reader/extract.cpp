#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

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

CSV2_TEST_CASE("reader.extract.reserve-for-existing-output-when-appending-a-raw-row",
               "reader.extract") {
  ReaderWithoutHeader reader;
  std::string input("a,b");
  CSV2_REQUIRE(reader.parse(input));

  ReserveTrackingBuffer output("pre:");
  (*reader.begin()).read_raw_value(output);
  CSV2_REQUIRE(output.last_reserve == 7);
  CSV2_REQUIRE(output.value == "pre:a,b");
}

CSV2_TEST_CASE("reader.extract.append-a-raw-row-to-a-reserve-only-output-type", "reader.extract") {
  ReaderWithoutHeader reader;
  std::string input("a,b");
  CSV2_REQUIRE(reader.parse(input));

  ReserveOnlyBuffer output("pre:");
  (*reader.begin()).read_raw_value(output);
  CSV2_REQUIRE(output.last_reserve == 3);
  CSV2_REQUIRE(output.value == "pre:a,b");
}
