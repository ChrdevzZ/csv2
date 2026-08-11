#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/detail/config.hpp>
#include <csv2/reader.hpp>
#endif

#include <filesystem>
#include <string_view>

static_assert(CSV2_HAS_STRING_VIEW, "C++17 contract requires std::string_view");
static_assert(CSV2_HAS_FILESYSTEM, "C++17 contract requires std::filesystem::path");

void csv2_cxx17_contract() {
  csv2::Reader<> reader;
  const std::string_view view("a,b");
  const std::filesystem::path path("input.csv");
  (void)path;
  reader.parse_view(view);
}
