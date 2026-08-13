#include <csv2_test/assertions.hpp>
#include <csv2_test/csv2_headers.hpp>

#include <string>
#include <vector>

namespace {

typedef csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                     csv2::first_row_is_header<false>> test_reader;

std::vector<std::string> read_first_row(test_reader &reader) {
  std::vector<std::string> values;
  test_reader::Row row = *reader.begin();
  for (test_reader::Row::CellIterator cell = row.begin(); cell != row.end(); ++cell) {
    std::string value;
    cell->read_value(value);
    values.push_back(value);
  }
  return values;
}

} // namespace

CSV2_TEST_CASE("reader.scan.trailing-empty", "reader.scan") {
  test_reader reader;
  std::string input("a,,\r\n");
  CSV2_REQUIRE(reader.parse(input));
  const std::vector<std::string> expected = {"a", "", ""};
  CSV2_CHECK_EQ(read_first_row(reader), expected);
}
