#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("writer.raw.write-empty-and-forward-iterable-rows", "writer.raw") {
  std::ostringstream output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(output);

  writer.write_row(std::vector<std::string>());
  writer.write_row(std::vector<std::string>({""}));
  writer.write_row(std::list<std::string>({"a", "b"}));
  writer.write_row(std::forward_list<std::string>({"x", "y", "z"}));

  CSV2_REQUIRE(output.str() == "\n\na,b\nx,y,z\n");
}

CSV2_TEST_CASE("writer.raw.preserve-historical-writer-record-byte-delimiter-policies",
               "writer.raw") {
  std::ostringstream lf_output;
  csv2::Writer<csv2::delimiter<'\n'>, std::ostringstream> lf_writer(lf_output);
  lf_writer.write_row(std::vector<std::string>({"a", "b"}));
  CSV2_REQUIRE(lf_output.str() == "a\nb\n");

  std::ostringstream cr_output;
  csv2::Writer<csv2::delimiter<'\r'>, std::ostringstream> cr_writer(cr_output);
  cr_writer.write_row(std::vector<std::string>({"a", "b"}));
  CSV2_REQUIRE(cr_output.str() == "a\rb\n");
}

CSV2_TEST_CASE("writer.raw.write-adl-ranges-and-contiguous-character-fields-directly",
               "writer.raw") {
  DirectWriteTrackingStream output;
  csv2::basic_writer<csv2::delimiter<','>, DirectWriteTrackingStream> writer(output);
  const std::string row[] = {"alpha", "beta"};
  writer.write_row(row);

  CSV2_REQUIRE(output.str() == "alpha,beta\n");
  CSV2_REQUIRE(output.write_calls == 2);

  std::ostringstream numbers;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> number_writer(numbers);
  number_writer.write_row(std::vector<int>({1, 2}));
  CSV2_REQUIRE(numbers.str() == "1,2\n");

  MinimalWriteStream minimal_stream;
  csv2::Writer<csv2::delimiter<','>, MinimalWriteStream> minimal_writer(minimal_stream);
  minimal_writer.write_row(std::vector<std::string>({"alpha", "beta"}));
  CSV2_REQUIRE(minimal_stream.value == "alpha,beta\n");

  DecoratingStringStream decorating_stream;
  csv2::Writer<csv2::delimiter<','>, DecoratingStringStream> decorating_writer(decorating_stream);
  decorating_writer.write_row(std::vector<std::string>({"alpha", "beta"}));
  CSV2_REQUIRE(decorating_stream.value == "<alpha>,<beta>\n");

  ChainedInsertionStream chained_stream;
  csv2::Writer<csv2::delimiter<','>, ChainedInsertionStream> chained_writer(chained_stream);
  chained_writer.write_row(std::vector<std::string>({"alpha", "beta"}));
  CSV2_REQUIRE(chained_stream.value == "S{alpha},P{beta}\n");

  std::ostringstream const_range_output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> const_range_writer(const_range_output);
  ConstSelectingRow const_selecting_row;
  const_range_writer.write_row(const_selecting_row);
  CSV2_REQUIRE(const_range_output.str() == "const\n");

#if CSV2_HAS_STRING_VIEW
  DecoratingStringStream view_stream;
  csv2::Writer<csv2::delimiter<','>, DecoratingStringStream> view_writer(view_stream);
  const std::string_view views[] = {"alpha", "beta"};
  view_writer.write_row(views);
  CSV2_REQUIRE(view_stream.value == "[alpha],[beta]\n");
#endif

  MinimalWriteStream minimal_escaped_stream;
  csv2::EscapingWriter<csv2::delimiter<','>, MinimalWriteStream, csv2::stream_ownership::leave_open>
      minimal_escaped_writer(minimal_escaped_stream);
  minimal_escaped_writer.write_row(std::vector<std::string>({"a,b"}));
  CSV2_REQUIRE(minimal_escaped_stream.value == "\"a,b\"\n");
}

#if CSV2_HAS_RANGES
CSV2_TEST_CASE("writer.raw.write-cxx20-view-pipelines", "writer.raw") {
  std::ostringstream output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(output);
  const std::vector<std::string> fields = {"a", "skip", "b"};
  auto selected =
      fields | std::views::filter([](const std::string &field) { return field != "skip"; });
  writer.write_row(selected);

  const std::vector<std::string> counted_fields = {"x", "y", "ignored"};
  const auto counted = std::ranges::subrange(std::counted_iterator(counted_fields.begin(), 2),
                                             std::default_sentinel);
  writer.write_row(counted);
  CSV2_REQUIRE(output.str() == "a,b\nx,y\n");
}
#endif

CSV2_TEST_CASE("writer.raw.write-a-forward-iterable-collection-of-rows", "writer.raw") {
  std::ostringstream output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(output);
  const std::forward_list<std::vector<std::string>> rows = {{"a", "b"}, {}, {"c", "d", "e"}};

  writer.write_rows(rows);

  CSV2_REQUIRE(output.str() == "a,b\n\nc,d,e\n");
}
