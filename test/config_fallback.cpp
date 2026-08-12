#define CSV2_DETAIL_FORCE_HEADER_PROBES 1

#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/detail/config.hpp>
#endif

#ifndef CSV2_DETAIL_HAS_VERSION_HEADER
#error "config.hpp must expose which feature-macro discovery path was used"
#endif

static_assert(CSV2_DETAIL_HAS_VERSION_HEADER == 0,
              "the fallback contract must not include <version>");

#if defined(__cpp_lib_string_view) && __cpp_lib_string_view >= 201606L
static_assert(CSV2_HAS_STRING_VIEW, "<string_view> feature macro was not detected");
#endif
#if defined(__cpp_lib_filesystem) && __cpp_lib_filesystem >= 201703L
static_assert(CSV2_HAS_FILESYSTEM, "<filesystem> feature macro was not detected");
#endif
#if defined(__cpp_lib_to_chars) && __cpp_lib_to_chars >= 201611L
static_assert(CSV2_HAS_CHARCONV, "<charconv> feature macro was not detected");
#endif
#if defined(__cpp_lib_memory_resource) && __cpp_lib_memory_resource >= 201603L
static_assert(CSV2_HAS_MEMORY_RESOURCE, "<memory_resource> feature macro was not detected");
#endif
#if defined(__cpp_lib_span) && __cpp_lib_span >= 202002L
static_assert(CSV2_HAS_SPAN, "<span> feature macro was not detected");
#endif
#if defined(__cpp_lib_ranges) && __cpp_lib_ranges >= 201911L
static_assert(CSV2_HAS_RANGES, "<ranges> feature macro was not detected");
#endif
#if defined(__cpp_lib_expected) && __cpp_lib_expected >= 202202L
static_assert(CSV2_HAS_EXPECTED, "<expected> feature macro was not detected");
#endif
#if defined(__cpp_lib_ranges_to_container) && __cpp_lib_ranges_to_container >= 202202L
static_assert(CSV2_HAS_RANGES_TO_CONTAINER, "<ranges> ranges::to feature macro was not detected");
#endif
