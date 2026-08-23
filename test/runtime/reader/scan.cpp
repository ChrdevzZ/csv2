#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("reader.scan.honor-delimiter-quote-and-trim-policies", "reader.scan") {
  using TrimmedReader =
      csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'\''>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_whitespace>;
  TrimmedReader trimmed;
  std::string trimmed_input(" a | 'b|c' | 'd''e' ");
  CSV2_REQUIRE(trimmed.parse(trimmed_input));
  CSV2_REQUIRE(read_cells(*trimmed.begin()) == std::vector<std::string>({"a", "'b|c'", "'d'e'"}));

  using UntrimmedReader =
      csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'\''>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::no_trimming>;
  UntrimmedReader untrimmed;
  std::string untrimmed_input(" a | b ");
  CSV2_REQUIRE(untrimmed.parse(untrimmed_input));
  CSV2_REQUIRE(read_cells(*untrimmed.begin()) == std::vector<std::string>({" a ", " b "}));
}

CSV2_TEST_CASE(
    "reader.scan.keep-shared-delimiter-and-quote-semantics-stable-across-the-scanner-threshold",
    "reader.scan") {
  using SharedDelimiterQuoteReader = csv2::Reader<csv2::delimiter<'"'>, csv2::quote_character<'"'>,
                                                  csv2::first_row_is_header<false>>;
  const std::size_t prefix_lengths[] = {63, 64, 65};
  for (const std::size_t prefix_length : prefix_lengths) {
    SharedDelimiterQuoteReader reader;
    std::string input(prefix_length, 'a');
    input += "\"b";
    CSV2_REQUIRE(reader.parse(input));
    const auto row = *reader.begin();
    CSV2_REQUIRE(std::distance(row.begin(), row.end()) == 1);
    CSV2_REQUIRE(row.begin()->raw_size() == prefix_length + 2);
  }
}

CSV2_TEST_CASE("reader.scan.give-a-newline-quote-policy-precedence-over-record-boundaries",
               "reader.scan") {
  using NewlineQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\n'>,
                                          csv2::first_row_is_header<false>>;
  NewlineQuoteReader reader;
  std::string input("\na\n,b");
  CSV2_REQUIRE(reader.parse(input));

  csv2::parse_error error;
  CSV2_REQUIRE(reader.validate(error));
  CSV2_REQUIRE(reader.rows() == 1);
  CSV2_REQUIRE(reader.index().size() == 1);
  CSV2_REQUIRE(std::distance(reader.begin()->begin(), reader.begin()->end()) == 2);
}

CSV2_TEST_CASE("reader.scan.preserve-a-closing-carriage-return-quote-before-line-feed",
               "reader.scan") {
  using CarriageReturnQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\r'>,
                                                 csv2::first_row_is_header<false>>;
  CarriageReturnQuoteReader reader;
  std::string input("\ra\r\nb");
  CSV2_REQUIRE(reader.parse(input));

  csv2::parse_error error;
  CSV2_REQUIRE(reader.validate(error));
  CSV2_REQUIRE(reader.rows() == 2);
  CSV2_REQUIRE(reader.begin()->raw_size() == 3);
  std::string raw;
  reader.begin()->read_raw_value(raw);
  CSV2_REQUIRE(raw == std::string("\ra\r", 3));
}

CSV2_TEST_CASE("reader.scan.preserve-an-opening-carriage-return-quote-before-line-feed",
               "reader.scan") {
  using CarriageReturnQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\r'>,
                                                 csv2::first_row_is_header<false>>;
  CarriageReturnQuoteReader reader;
  std::string input("\r\nx\r");
  CSV2_REQUIRE(reader.parse(input));

  csv2::parse_error error;
  CSV2_REQUIRE(reader.validate(error));
  CSV2_REQUIRE(reader.rows() == 1);
  CSV2_REQUIRE(reader.begin()->raw_size() == input.size());
}

CSV2_TEST_CASE("reader.scan.reject-a-line-feed-quote-outside-a-quoted-field", "reader.scan") {
  using NewlineQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\n'>,
                                          csv2::first_row_is_header<false>>;
  NewlineQuoteReader reader;
  std::string input("a\nb");
  CSV2_REQUIRE(reader.parse(input));

  csv2::parse_error error;
  CSV2_REQUIRE_FALSE(reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
  CSV2_REQUIRE(error.byte_offset == 1);
}

CSV2_TEST_CASE("reader.scan.report-a-bare-carriage-return-before-a-line-feed-quote",
               "reader.scan") {
  using NewlineQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\n'>,
                                          csv2::first_row_is_header<false>>;
  NewlineQuoteReader reader;
  std::string input("a\r\nb");
  CSV2_REQUIRE(reader.parse(input));

  csv2::parse_error error;
  CSV2_REQUIRE_FALSE(reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
  CSV2_REQUIRE(error.byte_offset == 1);
}

CSV2_TEST_CASE("reader.scan.reject-a-carriage-return-quote-outside-a-quoted-field", "reader.scan") {
  using CarriageReturnQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\r'>,
                                                 csv2::first_row_is_header<false>>;
  CarriageReturnQuoteReader reader;
  std::string input("a\rb");
  CSV2_REQUIRE(reader.parse(input));

  csv2::parse_error error;
  CSV2_REQUIRE_FALSE(reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
  CSV2_REQUIRE(error.byte_offset == 1);
}

CSV2_TEST_CASE("reader.scan.scan-cell-boundaries-through-the-shared-fast-path", "reader.scan") {
  ReaderWithoutHeader reader;
  const std::string wide_field(160, 'x');
  const std::string input = wide_field + ",\"quoted,field\",\"a\"\"b\",tail,";
  CSV2_REQUIRE(reader.parse(input));
  CSV2_REQUIRE(read_cells(*reader.begin()) ==
               std::vector<std::string>({wide_field, "\"quoted,field\"", "\"a\"b\"", "tail", ""}));
}

CSV2_TEST_CASE("reader.scan.handle-record-terminators-and-quoted-newlines", "reader.scan") {
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
    CSV2_REQUIRE(reader.parse(input));
    CSV2_REQUIRE(read_rows(reader) == test_case.expected);
  }
}

CSV2_TEST_CASE("reader.scan.preserve-trailing-empty-fields-and-normalize-empty-records",
               "reader.scan") {
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
      CSV2_REQUIRE(reader.parse(input));
      CSV2_REQUIRE(read_rows(reader) ==
                   std::vector<std::vector<std::string>>({field_case.expected}));
    }
  }

  const char *empty_record_inputs[] = {"a\n\nb\n", "a\r\n\r\nb\r\n"};
  for (const auto input_value : empty_record_inputs) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    CSV2_REQUIRE(reader.parse(input));
    CSV2_REQUIRE(reader.rows() == 3);
    CSV2_REQUIRE(reader.rows(true) == 2);
    CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"a"}, {}, {"b"}}));
  }

  const char *single_empty_records[] = {"\n", "\r\n"};
  for (const auto input_value : single_empty_records) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    CSV2_REQUIRE(reader.parse(input));
    CSV2_REQUIRE(reader.rows() == 1);
    CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{}}));
  }

  ReaderWithHeader header_reader;
  std::string header_input("h1,h2,\r\nvalue1,value2,");
  CSV2_REQUIRE(header_reader.parse(header_input));
  CSV2_REQUIRE(read_cells(header_reader.header()) == std::vector<std::string>({"h1", "h2", ""}));
  CSV2_REQUIRE(header_reader.cols() == 3);
  CSV2_REQUIRE(read_rows(header_reader) ==
               std::vector<std::vector<std::string>>({{"value1", "value2", ""}}));
}
