#include <csv2/detail/config.hpp>

#ifndef CSV2_CPLUSPLUS
#error "CSV2_CPLUSPLUS must report the active language mode"
#endif
#ifndef CSV2_FORCE_INLINE
#error "CSV2_FORCE_INLINE must be available to internal hot paths"
#endif

static_assert(CSV2_CPLUSPLUS >= 201103L, "csv2 requires C++11 or newer");
static_assert(CSV2_HAS_STRING_VIEW == 0 || CSV2_HAS_STRING_VIEW == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_FILESYSTEM == 0 || CSV2_HAS_FILESYSTEM == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_CHARCONV == 0 || CSV2_HAS_CHARCONV == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_SPAN == 0 || CSV2_HAS_SPAN == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_RANGES == 0 || CSV2_HAS_RANGES == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_EXPECTED == 0 || CSV2_HAS_EXPECTED == 1,
              "feature flags must be boolean preprocessor values");
static_assert(CSV2_HAS_RANGES_TO_CONTAINER == 0 || CSV2_HAS_RANGES_TO_CONTAINER == 1,
              "feature flags must be boolean preprocessor values");

CSV2_NODISCARD CSV2_CONSTEXPR14 int csv2_config_contract() noexcept {
  return CSV2_CPLUSPLUS >= 201103L ? 0 : 1;
}
