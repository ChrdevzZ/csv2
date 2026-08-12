#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/detail/config.hpp>
#endif

#ifndef CSV2_CPLUSPLUS
#error "CSV2_CPLUSPLUS must report the active language mode"
#endif
#ifndef CSV2_FORCE_INLINE
#error "CSV2_FORCE_INLINE must be available to internal hot paths"
#endif
#ifndef CSV2_DETAIL_HAS_VERSION_HEADER
#error "config.hpp must expose which feature-macro discovery path was used"
#endif

static_assert(CSV2_CPLUSPLUS >= 201103L, "csv2 requires C++11 or newer");
#if CSV2_CPLUSPLUS < 202002L
static_assert(CSV2_DETAIL_HAS_VERSION_HEADER == 0,
              "pre-C++20 configuration must not directly include <version>");
#endif
static_assert(CSV2_HAS_STRING_VIEW == 0 || CSV2_HAS_STRING_VIEW == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_FILESYSTEM == 0 || CSV2_HAS_FILESYSTEM == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_CHARCONV == 0 || CSV2_HAS_CHARCONV == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_MEMORY_RESOURCE == 0 || CSV2_HAS_MEMORY_RESOURCE == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_SPAN == 0 || CSV2_HAS_SPAN == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_RANGES == 0 || CSV2_HAS_RANGES == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_EXPECTED == 0 || CSV2_HAS_EXPECTED == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_RANGES_TO_CONTAINER == 0 || CSV2_HAS_RANGES_TO_CONTAINER == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_MMAP == 0 || CSV2_HAS_MMAP == 1,
              "feature flags must be boolean preprocessor values");

CSV2_NODISCARD CSV2_CONSTEXPR14 int csv2_config_contract() noexcept {
  return CSV2_CPLUSPLUS >= 201103L ? 0 : 1;
}
