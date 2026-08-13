#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("reader.index.build-an-explicit-random-access-row-index-from-logical-record-offsets",
               "reader.index") {
  ReaderWithHeader reader;
  std::string input("h1,h2\n\n\"a\nb\",c\nx,y\n");
  CSV2_REQUIRE(reader.parse(input));

  const auto all_rows = reader.index();
  CSV2_REQUIRE(all_rows.size() == 3);
  CSV2_REQUIRE(read_cells(all_rows[0]).empty());
  CSV2_REQUIRE(read_cells(all_rows[1]) == std::vector<std::string>({"\"a\nb\"", "c"}));
  CSV2_REQUIRE(read_cells(all_rows[2]) == std::vector<std::string>({"x", "y"}));
  CSV2_REQUIRE(all_rows[1].raw_data() == input.data() + 7);

  const auto non_empty_rows = reader.index(true);
  CSV2_REQUIRE(non_empty_rows.size() == 2);
  CSV2_REQUIRE(non_empty_rows.end() - non_empty_rows.begin() == 2);
  CSV2_REQUIRE(read_cells(*(non_empty_rows.begin() + 1)) == std::vector<std::string>({"x", "y"}));
  CSV2_REQUIRE(read_cells(non_empty_rows.begin()[0]) ==
               std::vector<std::string>({"\"a\nb\"", "c"}));

  const ReaderWithHeader::RowIndex invalid(nullptr, 4, 0, false);
  CSV2_REQUIRE(invalid.empty());

#if CSV2_HAS_RANGES
  static_assert(std::ranges::random_access_range<ReaderWithHeader::RowIndex>);
  static_assert(std::ranges::sized_range<ReaderWithHeader::RowIndex>);
#endif
}
