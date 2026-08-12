#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/reader.hpp>
#endif

#if CSV2_HAS_RANGES
#include <concepts>
#include <ranges>
#endif
#if CSV2_HAS_SPAN
#include <span>
#endif

#include <string>

using cxx20_reader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::first_row_is_header<false>>;

struct cxx20_owning_row : cxx20_reader::Row {
  std::string storage{"abc"};

  std::string::iterator begin() { return storage.begin(); }
  std::string::iterator end() { return storage.end(); }
};
#if !defined(CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
static_assert(CSV2_HAS_RANGES, "the full C++20 contract requires std::ranges");
static_assert(CSV2_HAS_SPAN, "the full C++20 contract requires std::span");
#else
static_assert(!CSV2_HAS_RANGES, "missing ranges must disable its optional API");
static_assert(!CSV2_HAS_SPAN, "missing span must disable its optional API");
#endif
#if CSV2_HAS_RANGES
static_assert(std::ranges::forward_range<cxx20_reader>);
static_assert(std::ranges::view<cxx20_reader::Row>);
static_assert(std::ranges::borrowed_range<cxx20_reader::Row>);
static_assert(!std::ranges::borrowed_range<cxx20_reader>);
static_assert(std::ranges::range<cxx20_owning_row>);
static_assert(!std::ranges::view<cxx20_owning_row>);
static_assert(!std::ranges::borrowed_range<cxx20_owning_row>);
static_assert(std::ranges::random_access_range<cxx20_reader::RowIndex>);
static_assert(std::ranges::sized_range<cxx20_reader::RowIndex>);
#endif

#if CSV2_HAS_SPAN
void csv2_cxx20_contract(std::span<const char> bytes) {
  cxx20_reader reader;
  reader.parse_borrowed(bytes);
}
#else
void csv2_cxx20_contract() {}
#endif
