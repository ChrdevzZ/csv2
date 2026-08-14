#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/detail/config.hpp>
#include <csv2/reader.hpp>
#endif

#include <type_traits>
#include <utility>

#if defined(CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
static_assert(!CSV2_HAS_EXPECTED, "missing expected must disable its optional API");
static_assert(!CSV2_HAS_RANGES_TO_CONTAINER, "missing ranges::to must disable its optional API");
#endif

#if CSV2_HAS_EXPECTED
#include <expected>

using cxx23_reader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::first_row_is_header<false>>;
static_assert(std::is_same<decltype(std::declval<const cxx23_reader &>().validate_expected()),
                           std::expected<void, csv2::parse_error>>::value);
#endif

void csv2_cxx23_contract() {
#if CSV2_HAS_EXPECTED
  cxx23_reader reader;
  reader.parse_owned("42");
  const auto value = (*(*reader.begin()).begin()).parse_expected<int>();
  (void)value;
#endif
}
