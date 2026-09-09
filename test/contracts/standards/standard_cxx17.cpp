#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/detail/config.hpp>
#include <csv2/reader.hpp>
#endif

#include <type_traits>

#if CSV2_HAS_FILESYSTEM
#include <filesystem>
#endif
#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif

#if !defined(CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
static_assert(CSV2_HAS_STRING_VIEW, "the full C++17 contract requires std::string_view");
static_assert(CSV2_HAS_FILESYSTEM, "the full C++17 contract requires std::filesystem::path");
#else
static_assert(!CSV2_HAS_STRING_VIEW, "missing string_view must disable its optional API");
static_assert(!CSV2_HAS_FILESYSTEM, "missing filesystem must disable its optional API");
static_assert(!CSV2_HAS_CHARCONV, "missing charconv must disable its optional API");
static_assert(!CSV2_HAS_MEMORY_RESOURCE, "missing memory_resource must disable its optional API");
#endif

void csv2_cxx17_contract() {
  csv2::Reader<> reader;
#if CSV2_HAS_STRING_VIEW
  const std::string_view view("a,b");
  reader.parse_view(view);
#endif
#if CSV2_HAS_FILESYSTEM
  const std::filesystem::path path("input.csv");
  (void)path;
#endif
  (void)reader;
}
#if CSV2_HAS_STRING_VIEW
using cxx17_reader = csv2::Reader<csv2::delimiter<','>>;
static_assert(std::is_same<decltype(&cxx17_reader::Cell::read_view),
                           std::string_view (cxx17_reader::Cell::*)() const>::value,
              "the historical Cell read_view member must remain owned by Reader::Cell");
#endif
