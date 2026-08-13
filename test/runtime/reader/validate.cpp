#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("reader.validate.use-a-custom-trim-policy-on-complete-field-bounds",
               "reader.validate") {
  using ContextTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                         csv2::first_row_is_header<false>, ContextTrim>;
  ContextTrimReader reader;
  std::string input("~~\"a\"~~,~~b~~");
  CSV2_REQUIRE(reader.parse(input));
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"\"a\"", "b"}));

  csv2::parse_error error;
  CSV2_REQUIRE(reader.validate(error));
}

CSV2_TEST_CASE("reader.validate.do-not-validate-a-suffix-using-a-different-trim-context",
               "reader.validate") {
  using SingleByteTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                            csv2::first_row_is_header<false>, SingleByteOnlyTrim>;
  SingleByteTrimReader reader;
  std::string input("\"a\"x");
  CSV2_REQUIRE(reader.parse(input));
  csv2::parse_error error;
  CSV2_REQUIRE_FALSE(reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  CSV2_REQUIRE(error.byte_offset == 3);
}

CSV2_TEST_CASE("reader.validate.preserve-quote-structure-when-the-trim-policy-includes-quotes",
               "reader.validate") {
  using QuoteTrimReader =
      csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_characters<'"'>>;
  using MixedTrimReader =
      csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_characters<' ', '"'>>;

  CSV2_SUBCASE("A lone opening quote remains visible") {
    QuoteTrimReader reader;
    std::string input("\"");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE_FALSE(reader.validate(error));
    CSV2_REQUIRE(error.code == csv2::parse_errc::unclosed_quote);
    CSV2_REQUIRE(error.byte_offset == 0);
    CSV2_REQUIRE(error.row == 1);
    CSV2_REQUIRE(error.column == 1);
  }

  CSV2_SUBCASE("A quoted empty field remains valid") {
    QuoteTrimReader reader;
    std::string input("\"\"");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE(reader.validate(error));
  }

  CSV2_SUBCASE("A quoted value remains valid") {
    QuoteTrimReader reader;
    std::string input("\"a\"");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE(reader.validate(error));
  }

  CSV2_SUBCASE("A trailing quote in an unquoted field remains visible") {
    QuoteTrimReader reader;
    std::string input("a\"");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE_FALSE(reader.validate(error));
    CSV2_REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
    CSV2_REQUIRE(error.byte_offset == 1);
  }

  CSV2_SUBCASE("Non-structural trim bytes can still surround a quoted field") {
    MixedTrimReader reader;
    std::string input("  \"a\"  ");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE(reader.validate(error));
  }
}

CSV2_TEST_CASE("reader.validate.preserve-structural-diagnostics-after-a-quoted-field-suffix",
               "reader.validate") {
  using TrimmedReader =
      csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_whitespace>;

  CSV2_SUBCASE("A bare carriage return follows trimmable bytes") {
    TrimmedReader reader;
    std::string input("\"a\" \r");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE_FALSE(reader.validate(error));
    CSV2_REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
    CSV2_REQUIRE(error.byte_offset == 4);
    CSV2_REQUIRE(error.row == 1);
    CSV2_REQUIRE(error.column == 1);
  }

  CSV2_SUBCASE("A quote follows trimmable bytes") {
    TrimmedReader reader;
    std::string input("\"a\"  \"b\"");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE_FALSE(reader.validate(error));
    CSV2_REQUIRE(error.code == csv2::parse_errc::invalid_doubled_quote);
    CSV2_REQUIRE(error.byte_offset == 5);
  }

  CSV2_SUBCASE("Ordinary content follows trimmable bytes") {
    TrimmedReader reader;
    std::string input("\"a\"  x");
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE_FALSE(reader.validate(error));
    CSV2_REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
    CSV2_REQUIRE(error.byte_offset == 5);
  }
}

#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
CSV2_TEST_CASE("reader.validate.propagate-exceptions-from-a-user-trim-policy", "reader.validate") {
  using ThrowingTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                          csv2::first_row_is_header<false>, ThrowingTrim>;
  ThrowingTrimReader reader;
  std::string input("value");
  CSV2_REQUIRE(reader.parse(input));

  std::string value;
  CSV2_REQUIRE_THROWS_AS(reader.begin()->begin()->read_value(value), std::runtime_error);
  csv2::parse_error error;
  CSV2_REQUIRE_THROWS_AS(reader.validate(error), std::runtime_error);
#if CSV2_HAS_EXPECTED
  CSV2_REQUIRE_THROWS_AS(static_cast<void>(reader.begin()->begin()->parse_expected<int>()),
                         std::runtime_error);
  CSV2_REQUIRE_THROWS_AS(static_cast<void>(reader.validate_expected()), std::runtime_error);
#endif
}
#endif

CSV2_TEST_CASE("reader.validate.validate-a-shared-delimiter-and-quote-with-quote-precedence",
               "reader.validate") {
  using SharedDelimiterQuoteReader = csv2::Reader<csv2::delimiter<'"'>, csv2::quote_character<'"'>,
                                                  csv2::first_row_is_header<false>>;
  SharedDelimiterQuoteReader reader;
  std::string input("a\"b");
  CSV2_REQUIRE(reader.parse(input));
  CSV2_REQUIRE(std::distance(reader.begin()->begin(), reader.begin()->end()) == 1);

  csv2::parse_error error;
  CSV2_REQUIRE_FALSE(reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
  CSV2_REQUIRE(error.byte_offset == 1);
}

CSV2_TEST_CASE("reader.validate.allow-a-bare-carriage-return-inside-a-quoted-field",
               "reader.validate") {
  ReaderWithoutHeader reader;
  std::string input("\"a\rb\",c\n");
  CSV2_REQUIRE(reader.parse(input));
  csv2::parse_error error;
  CSV2_REQUIRE(reader.validate(error));
}

CSV2_TEST_CASE("reader.validate.validate-strict-csv-syntax-without-changing-permissive-traversal",
               "reader.validate") {
  const char *valid_inputs[] = {"a,b\n1,2",       " \t\"a\"\"b\" \t,c", "a,\"b\nc\",d",
                                "a,\"b\r\nc\",d", "a,\"b\rc\",d",       "a,b\n1\n2,3,4"};
  for (const char *input_value : valid_inputs) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE(reader.validate(error));
    CSV2_REQUIRE(error.code == csv2::parse_errc::none);
  }

  struct InvalidCase {
    const char *input;
    csv2::parse_errc code;
    std::size_t offset;
    std::size_t row;
    std::size_t column;
  };
  const InvalidCase invalid_inputs[] = {
      {"a\"b,c", csv2::parse_errc::unexpected_quote, 1, 1, 1},
      {"\"a,b", csv2::parse_errc::unclosed_quote, 0, 1, 1},
      {"\"a\"x,b", csv2::parse_errc::characters_after_closing_quote, 3, 1, 1},
      {"\"a\" \"b\"", csv2::parse_errc::invalid_doubled_quote, 4, 1, 1},
      {"a\rb", csv2::parse_errc::bare_carriage_return, 1, 1, 1},
      {"a,b\nc,\"d\"x", csv2::parse_errc::characters_after_closing_quote, 9, 2, 2},
  };

  for (const auto &test_case : invalid_inputs) {
    ReaderWithoutHeader reader;
    std::string input(test_case.input);
    CSV2_REQUIRE(reader.parse(input));
    csv2::parse_error error;
    CSV2_REQUIRE_FALSE(reader.validate(error));
    CSV2_REQUIRE(error.code == test_case.code);
    CSV2_REQUIRE(error.byte_offset == test_case.offset);
    CSV2_REQUIRE(error.row == test_case.row);
    CSV2_REQUIRE(error.column == test_case.column);
    CSV2_REQUIRE(read_rows(reader).size() >= 1);
  }
}

CSV2_TEST_CASE("reader.validate.allow-carriage-returns-inside-a-quoted-field-during-validation",
               "reader.validate") {
  ReaderWithoutHeader reader;
  std::string input("\"a\rb\",c\n");
  CSV2_REQUIRE(reader.parse(input));
  csv2::parse_error error;
  CSV2_REQUIRE(reader.validate(error));
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"\"a\rb\"", "c"}));
}

CSV2_TEST_CASE("reader.validate.validate-structural-characters-before-overlapping-trim-characters",
               "reader.validate") {
  using DelimiterTrimReader =
      csv2::Reader<csv2::delimiter<';'>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_characters<' ', ';'>>;
  DelimiterTrimReader delimiter_reader;
  std::string delimiter_input(";\"b\"x");
  CSV2_REQUIRE(delimiter_reader.parse(delimiter_input));
  csv2::parse_error error;
  CSV2_REQUIRE_FALSE(delimiter_reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  CSV2_REQUIRE(error.byte_offset == 4);
  CSV2_REQUIRE(error.row == 1);
  CSV2_REQUIRE(error.column == 2);

  delimiter_input = "\"a\";\"b\"x";
  CSV2_REQUIRE(delimiter_reader.parse(delimiter_input));
  CSV2_REQUIRE_FALSE(delimiter_reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  CSV2_REQUIRE(error.byte_offset == 7);
  CSV2_REQUIRE(error.row == 1);
  CSV2_REQUIRE(error.column == 2);

  using LineEndingTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                            csv2::first_row_is_header<false>,
                                            csv2::trim_policy::trim_characters<' ', '\r', '\n'>>;
  LineEndingTrimReader line_reader;
  std::string line_input("\n\"b\"x");
  CSV2_REQUIRE(line_reader.parse(line_input));
  CSV2_REQUIRE_FALSE(line_reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  CSV2_REQUIRE(error.byte_offset == 4);
  CSV2_REQUIRE(error.row == 2);
  CSV2_REQUIRE(error.column == 1);

  line_input = "\"a\"\r\n\"b\"x";
  CSV2_REQUIRE(line_reader.parse(line_input));
  CSV2_REQUIRE_FALSE(line_reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  CSV2_REQUIRE(error.byte_offset == 8);
  CSV2_REQUIRE(error.row == 2);
  CSV2_REQUIRE(error.column == 1);

  line_input = "\rX";
  CSV2_REQUIRE(line_reader.parse(line_input));
  CSV2_REQUIRE_FALSE(line_reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
  CSV2_REQUIRE(error.byte_offset == 0);
  CSV2_REQUIRE(error.row == 1);
  CSV2_REQUIRE(error.column == 1);

  line_input = "\"a\"\rX";
  CSV2_REQUIRE(line_reader.parse(line_input));
  CSV2_REQUIRE_FALSE(line_reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
  CSV2_REQUIRE(error.byte_offset == 3);
  CSV2_REQUIRE(error.row == 1);
  CSV2_REQUIRE(error.column == 1);

  using SharedDelimiterQuoteReader = csv2::Reader<csv2::delimiter<'"'>, csv2::quote_character<'"'>,
                                                  csv2::first_row_is_header<false>>;
  SharedDelimiterQuoteReader shared_reader;
  std::string shared_input("\"a\"x");
  CSV2_REQUIRE(shared_reader.parse(shared_input));
  CSV2_REQUIRE_FALSE(shared_reader.validate(error));
  CSV2_REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  CSV2_REQUIRE(error.byte_offset == 3);
  CSV2_REQUIRE(error.row == 1);
  CSV2_REQUIRE(error.column == 1);
}
