#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("writer.stream.write-to-streams-with-and-without-close", "writer.stream") {
  std::ostringstream memory_stream;
  {
    csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(memory_stream);
    writer.write_row(std::vector<std::string>({"a", "b"}));
  }
  CSV2_REQUIRE(memory_stream.str() == "a,b\n");

  const char *const output_path = writer_output_path();
  std::remove(output_path);
  std::ofstream file_stream(output_path);
  CSV2_REQUIRE(file_stream.is_open());
  {
    csv2::Writer<csv2::delimiter<','>, std::ofstream> writer(file_stream);
    writer.write_row(std::vector<std::string>({"1", "2"}));
  }
  CSV2_REQUIRE_FALSE(file_stream.is_open());
  std::ifstream output(output_path);
  std::ostringstream output_contents;
  output_contents << output.rdbuf();
  CSV2_REQUIRE(output_contents.str() == "1,2\n");
  output.close();
  std::remove(output_path);

  LvalueCloseStream lvalue_close_stream;
  {
    csv2::Writer<csv2::delimiter<','>, LvalueCloseStream> writer(lvalue_close_stream);
    writer.write_row(std::vector<std::string>({"x", "y"}));
  }
  CSV2_REQUIRE(lvalue_close_stream.closed);
  CSV2_REQUIRE(lvalue_close_stream.str() == "x,y\n");
}

CSV2_TEST_CASE("writer.stream.consume-stream-width-on-the-next-writer-field", "writer.stream") {
  std::ostringstream raw_output;
  raw_output << std::setfill('_') << std::left << std::setw(4);
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::none>
      raw(raw_output);
  raw.write_row(std::vector<std::string>({"x", "y"}));
  CSV2_REQUIRE(raw_output.str() == "x___,y\n");
  CSV2_REQUIRE(raw_output.width() == 0);

  std::ostringstream empty_output;
  empty_output << std::setfill('_') << std::right << std::setw(3);
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::none>
      empty(empty_output);
  empty.write_row(std::vector<std::string>({"", "y"}));
  CSV2_REQUIRE(empty_output.str() == "___,y\n");
  CSV2_REQUIRE(empty_output.width() == 0);

  std::ostringstream minimal_output;
  minimal_output << std::setfill('_') << std::left << std::setw(4);
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      minimal(minimal_output);
  minimal.write_row(std::vector<std::string>({"a,b", "z"}));
  CSV2_REQUIRE(minimal_output.str() == "\"a,b_\",z\n");
  CSV2_REQUIRE(minimal_output.width() == 0);

  std::ostringstream always_output;
  always_output << std::setfill('_') << std::right << std::setw(4);
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::always>
      always(always_output);
  always.write_row(std::vector<std::string>({"x", "z"}));
  CSV2_REQUIRE(always_output.str() == "\"___x\",\"z\"\n");
  CSV2_REQUIRE(always_output.width() == 0);

  DirectWriteTrackingStream direct_output;
  csv2::basic_writer<csv2::delimiter<','>, DirectWriteTrackingStream> direct(direct_output);
  direct.write_row(std::vector<std::string>({"alpha", "beta"}));
  CSV2_REQUIRE(direct_output.write_calls == 2);

  std::ostringstream formatted_contiguous_output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> formatted_contiguous(
      formatted_contiguous_output);
  formatted_contiguous.write_row(std::vector<FormattedContiguousValue>(1));
  CSV2_REQUIRE(formatted_contiguous_output.str() == "[formatted]\n");

  std::ostringstream raw_range_output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> raw_range(raw_range_output);
  raw_range.write_row(std::vector<std::vector<char>>(1, std::vector<char>({'r', 'a', 'w'})));
  CSV2_REQUIRE(raw_range_output.str() == "raw\n");
}

CSV2_TEST_CASE("writer.stream.propagate-formatted-writer-state-and-preserve-insertion-exceptions",
               "writer.stream") {
  typedef csv2::EscapingWriter<csv2::delimiter<';'>, std::ostringstream,
                               csv2::stream_ownership::leave_open>
      EscapingSemicolonWriter;

  std::ostringstream fail_output;
  EscapingSemicolonWriter fail_writer(fail_output);
  fail_writer.write_row(
      std::vector<StatefulFormattedValue>(1, StatefulFormattedValue(std::ios_base::failbit)));
  CSV2_REQUIRE(fail_output.str() == "a,b");
  CSV2_REQUIRE(fail_output.fail());
  CSV2_REQUIRE_FALSE(fail_output.bad());

  std::ostringstream bad_output;
  EscapingSemicolonWriter bad_writer(bad_output);
  bad_writer.write_row(
      std::vector<StatefulFormattedValue>(1, StatefulFormattedValue(std::ios_base::badbit)));
  CSV2_REQUIRE(bad_output.str() == "a,b");
  CSV2_REQUIRE(bad_output.bad());

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
  std::ostringstream throwing_output;
  throwing_output.exceptions(std::ios_base::failbit);
  EscapingSemicolonWriter throwing_writer(throwing_output);
  CSV2_CHECK_THROWS_AS(throwing_writer.write_row(std::vector<StatefulFormattedValue>(
                           1, StatefulFormattedValue(std::ios_base::failbit))),
                       std::ios_base::failure);
  CSV2_REQUIRE(throwing_output.str() == "a,b");
  CSV2_REQUIRE(throwing_output.fail());

  std::ostringstream consuming_output;
  consuming_output << std::setw(4);
  EscapingSemicolonWriter consuming_writer(consuming_output);
  CSV2_CHECK_THROWS_AS(consuming_writer.write_row(std::vector<ConsumingThrowValue>(1)),
                       WriterUserError);
  CSV2_REQUIRE(consuming_output.width() == 0);

  std::ostringstream unformatted_output;
  unformatted_output << std::setw(4);
  EscapingSemicolonWriter unformatted_writer(unformatted_output);
  CSV2_CHECK_THROWS_AS(unformatted_writer.write_row(std::vector<UnformattedThrowValue>(1)),
                       WriterUserError);
  CSV2_REQUIRE(unformatted_output.width() == 4);

  std::ostringstream stateful_throw_output;
  stateful_throw_output.exceptions(std::ios_base::failbit);
  EscapingSemicolonWriter stateful_throw_writer(stateful_throw_output);
  CSV2_CHECK_THROWS_AS(stateful_throw_writer.write_row(std::vector<StatefulThrowValue>(1)),
                       WriterUserError);
  CSV2_REQUIRE(stateful_throw_output.fail());
#endif
}

CSV2_TEST_CASE("writer.stream.leave-borrowed-streams-open-unless-close-is-explicit",
               "writer.stream") {
  CountingCloseStream implicit_stream;
  {
    csv2::basic_writer<csv2::delimiter<','>, CountingCloseStream,
                       csv2::stream_ownership::leave_open, csv2::quote_policy::none>
        writer(implicit_stream);
    writer.write_row(std::vector<std::string>({"a"}));
  }
  CSV2_REQUIRE(implicit_stream.close_count == 0);
  CSV2_REQUIRE(implicit_stream.str() == "a\n");

  CountingCloseStream explicit_stream;
  {
    csv2::basic_writer<csv2::delimiter<','>, CountingCloseStream,
                       csv2::stream_ownership::leave_open, csv2::quote_policy::none>
        writer(explicit_stream);
    writer.close();
  }
  CSV2_REQUIRE(explicit_stream.close_count == 1);
}

CSV2_TEST_CASE("writer.stream.transfer-and-release-writer-close-responsibility-exactly-once",
               "writer.stream") {
  using CountingWriter = csv2::Writer<csv2::delimiter<','>, CountingCloseStream>;
  CSV2_REQUIRE_FALSE(std::is_copy_constructible<CountingWriter>::value);
  CSV2_REQUIRE_FALSE(std::is_copy_assignable<CountingWriter>::value);
  CSV2_REQUIRE(std::is_nothrow_move_constructible<CountingWriter>::value);
  CSV2_REQUIRE(std::is_nothrow_move_assignable<CountingWriter>::value);

  CountingCloseStream moved_stream;
  {
    CountingWriter source(moved_stream);
    CountingWriter destination(std::move(source));
    source.write_row(std::vector<std::string>({"ignored"}));
    destination.close();
    destination.write_row(std::vector<std::string>({"ignored"}));
  }
  CSV2_REQUIRE(moved_stream.close_count == 1);
  CSV2_REQUIRE(moved_stream.str().empty());

  CountingCloseStream source_stream;
  CountingCloseStream replaced_stream;
  {
    CountingWriter source(source_stream);
    CountingWriter destination(replaced_stream);
    destination = std::move(source);
    CSV2_REQUIRE(replaced_stream.close_count == 1);
  }
  CSV2_REQUIRE(source_stream.close_count == 1);
  CSV2_REQUIRE(replaced_stream.close_count == 1);

  CountingCloseStream explicitly_closed_stream;
  {
    CountingWriter writer(explicitly_closed_stream);
    writer.close();
    writer.close();
  }
  CSV2_REQUIRE(explicitly_closed_stream.close_count == 1);
}

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
CSV2_TEST_CASE(
    "writer.stream.report-explicit-writer-close-errors-and-suppress-destructor-close-errors",
    "writer.stream") {
  using ThrowingWriter = csv2::Writer<csv2::delimiter<','>, ThrowingCloseStream>;

  ThrowingCloseStream explicit_stream;
  {
    ThrowingWriter writer(explicit_stream);
    CSV2_REQUIRE_THROWS_AS(writer.close(), CloseError);
  }
  CSV2_REQUIRE(explicit_stream.close_count == 1);

  ThrowingCloseStream destructor_stream;
  { ThrowingWriter writer(destructor_stream); }
  CSV2_REQUIRE(destructor_stream.close_count == 1);
}
#endif
