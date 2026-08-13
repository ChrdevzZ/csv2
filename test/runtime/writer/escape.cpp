#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("writer.escape.escape-csv-fields-with-explicit-minimal-and-always-quote-policies",
               "writer.escape") {
  std::ostringstream minimal_output;
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      minimal(minimal_output);
  minimal.write_row(
      std::vector<std::string>({"plain", "a,b", "a\"b", "line\nbreak", "car\rriage", ""}));
  CSV2_REQUIRE(minimal_output.str() ==
               "plain,\"a,b\",\"a\"\"b\",\"line\nbreak\",\"car\rriage\",\n");

  std::ostringstream always_output;
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::always>
      always(always_output);
  always.write_row(std::vector<std::string>({"a", "\"b\"", ""}));
  CSV2_REQUIRE(always_output.str() == "\"a\",\"\"\"b\"\"\",\"\"\n");

  std::ostringstream minimal_empty_output;
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      minimal_empty(minimal_empty_output);
  minimal_empty.write_row(std::vector<std::string>());
  minimal_empty.write_row(std::vector<std::string>(1));
  CSV2_REQUIRE(minimal_empty_output.str() == "\n\n");

  std::ostringstream always_empty_output;
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::always>
      always_empty(always_empty_output);
  always_empty.write_row(std::vector<std::string>());
  always_empty.write_row(std::vector<std::string>(1));
  CSV2_REQUIRE(always_empty_output.str() == "\n\"\"\n");

  std::ostringstream formatted_output;
  formatted_output << std::hex;
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      formatted(formatted_output);
  const std::vector<CommaFormattedValue> values = {{15, 16}};
  formatted.write_row(values);
  CSV2_REQUIRE(formatted_output.str() == "\"f,10\"\n");

  DirectWriteTrackingStream direct_output;
  csv2::EscapingWriter<csv2::delimiter<','>, DirectWriteTrackingStream,
                       csv2::stream_ownership::leave_open>
      direct(direct_output);
  direct.write_row(std::vector<std::string>({"a,b"}));
  CSV2_REQUIRE(direct_output.str() == "\"a,b\"\n");
  CSV2_REQUIRE(direct_output.write_calls == 3);
}
