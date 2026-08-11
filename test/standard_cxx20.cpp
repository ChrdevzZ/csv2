#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/reader.hpp>
#endif

#include <concepts>
#include <ranges>
#include <span>

using cxx20_reader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::first_row_is_header<false>>;
static_assert(std::ranges::forward_range<cxx20_reader>);
static_assert(std::ranges::view<cxx20_reader::Row>);
static_assert(std::ranges::borrowed_range<cxx20_reader::Row>);
static_assert(!std::ranges::borrowed_range<cxx20_reader>);
static_assert(std::ranges::random_access_range<cxx20_reader::RowIndex>);
static_assert(std::ranges::sized_range<cxx20_reader::RowIndex>);

void csv2_cxx20_contract(std::span<const char> bytes) {
  cxx20_reader reader;
  reader.parse_borrowed(bytes);
}
