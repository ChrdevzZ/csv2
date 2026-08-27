#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("reader.iterate.compare-const-iterators-and-expose-a-trailing-empty-cell-before-end",
               "reader.iterate") {
  ReaderWithoutHeader reader;
  std::string input("a,b\nc,d");
  CSV2_REQUIRE(reader.parse(input));

  const auto row_begin = reader.begin();
  const auto row_begin_copy = row_begin;
  const auto row_end = reader.end();
  static_assert(noexcept(row_begin == row_begin_copy), "RowIterator equality must be noexcept");
  static_assert(noexcept(row_begin != row_end), "RowIterator inequality must be noexcept");
  CSV2_REQUIRE(row_begin == row_begin_copy);
  CSV2_REQUIRE(row_begin != row_end);

  const auto row = *row_begin;
  auto cell_iterator = row.begin();
  const auto first_cell = cell_iterator;
  ++cell_iterator;
  const auto second_cell = cell_iterator;
  const auto cell_end = row.end();
  static_assert(noexcept(first_cell == second_cell), "CellIterator equality must be noexcept");
  static_assert(noexcept(first_cell != cell_end), "CellIterator inequality must be noexcept");
  CSV2_REQUIRE(first_cell != second_cell);
  CSV2_REQUIRE(second_cell != cell_end);

  ReaderWithoutHeader trailing_reader;
  std::string trailing_input("a,");
  CSV2_REQUIRE(trailing_reader.parse(trailing_input));
  const auto trailing_row = *trailing_reader.begin();
  auto trailing_cell = trailing_row.begin();
  ++trailing_cell;
  const auto trailing_end = trailing_row.end();
  CSV2_REQUIRE(trailing_cell != trailing_end);
  std::string trailing_value;
  (*trailing_cell).read_value(trailing_value);
  CSV2_REQUIRE(trailing_value.empty());
  ++trailing_cell;
  CSV2_REQUIRE(trailing_cell == trailing_end);
}

CSV2_TEST_CASE("reader.iterate.use-default-and-post-incremented-iterators-with-classic-algorithms",
               "reader.iterate") {
  ReaderWithoutHeader::RowIterator default_row_a;
  ReaderWithoutHeader::RowIterator default_row_b;
  CSV2_REQUIRE(default_row_a == default_row_b);

  ReaderWithoutHeader reader;
  std::string input("a,b\nc,d");
  CSV2_REQUIRE(reader.parse(input));
  CSV2_REQUIRE(std::distance(reader.begin(), reader.end()) == 2);
  CSV2_REQUIRE(reader.begin()->raw_size() == 3);
  CSV2_REQUIRE((*reader.begin()).begin()->raw_size() == 1);
  CSV2_REQUIRE(reader.index().begin()->raw_size() == 3);

  auto row = reader.begin();
  const auto first_row = row++;
  CSV2_REQUIRE(first_row != row);

  auto cells = (*first_row).begin();
  ReaderWithoutHeader::Row::CellIterator default_cell_a;
  ReaderWithoutHeader::Row::CellIterator default_cell_b;
  CSV2_REQUIRE(default_cell_a == default_cell_b);
  const auto first_cell = cells++;
  CSV2_REQUIRE(first_cell != cells);
  std::string value;
  (*first_cell).read_value(value);
  CSV2_REQUIRE(value == "a");
}
