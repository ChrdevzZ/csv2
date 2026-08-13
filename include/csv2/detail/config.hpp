#pragma once

// Normalize the language mode. MSVC reports its selected standard through
// _MSVC_LANG unless /Zc:__cplusplus is enabled.
#if defined(_MSVC_LANG)
#define CSV2_CPLUSPLUS _MSVC_LANG
#else
#define CSV2_CPLUSPLUS __cplusplus
#endif

#define CSV2_DETAIL_HAS_VERSION_HEADER 0
#define CSV2_DETAIL_HAS_STRING_VIEW_HEADER 0

#if CSV2_CPLUSPLUS >= 201703L
#if defined(__has_include)
#if __has_include(<string_view>)
#undef CSV2_DETAIL_HAS_STRING_VIEW_HEADER
#define CSV2_DETAIL_HAS_STRING_VIEW_HEADER 1
#endif
#else
#undef CSV2_DETAIL_HAS_STRING_VIEW_HEADER
#define CSV2_DETAIL_HAS_STRING_VIEW_HEADER 1
#endif
#endif

#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS >= 202002L &&              \
    defined(__has_include) && !defined(CSV2_DETAIL_FORCE_HEADER_PROBES)
#if __has_include(<version>)
#undef CSV2_DETAIL_HAS_VERSION_HEADER
#define CSV2_DETAIL_HAS_VERSION_HEADER 1
#include <version>
#endif
#endif

// A conforming library can provide an SD-6 macro only from the facility's
// header, and a partial <version> may omit a facility that its own header
// supplies. Probe each missing macro independently and gate every API on the
// resulting macro value below.
#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS >= 201703L
#if defined(__has_include)
#if (!defined(__cpp_lib_string_view) || __cpp_lib_string_view < 201606L) &&                        \
    CSV2_DETAIL_HAS_STRING_VIEW_HEADER
#include <string_view>
#endif
#if (!defined(__cpp_lib_filesystem) || __cpp_lib_filesystem < 201703L) && __has_include(<filesystem>)
#include <filesystem>
#endif
#if (!defined(__cpp_lib_to_chars) || __cpp_lib_to_chars < 201611L) && __has_include(<charconv>)
#include <charconv>
#endif
#if (!defined(__cpp_lib_memory_resource) || __cpp_lib_memory_resource < 201603L) &&                \
    __has_include(<memory_resource>)
#include <memory_resource>
#endif
#else
#include <charconv>
#include <filesystem>
#include <memory_resource>
#include <string_view>
#endif
#endif

#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS >= 202002L
#if defined(__has_include)
#if (!defined(__cpp_lib_span) || __cpp_lib_span < 202002L) && __has_include(<span>)
#include <span>
#endif
#if (!defined(__cpp_lib_ranges) || __cpp_lib_ranges < 201911L ||                                   \
     !defined(__cpp_lib_ranges_to_container)) &&                                                   \
    __has_include(<ranges>)
#include <ranges>
#endif
#else
#include <ranges>
#include <span>
#endif
#endif

#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS > 202002L
#if defined(__has_include)
#if (!defined(__cpp_lib_expected) || __cpp_lib_expected < 202202L) && __has_include(<expected>)
#include <expected>
#endif
#else
#include <expected>
#endif
#endif

#if defined(__has_cpp_attribute)
#if CSV2_CPLUSPLUS >= 201703L && __has_cpp_attribute(nodiscard)
#define CSV2_NODISCARD [[nodiscard]]
#else
#define CSV2_NODISCARD
#endif
#else
#define CSV2_NODISCARD
#endif

#if CSV2_CPLUSPLUS >= 201402L
#define CSV2_CONSTEXPR14 constexpr
#else
#define CSV2_CONSTEXPR14
#endif

#if CSV2_CPLUSPLUS >= 201703L
#define CSV2_CONSTEXPR17 constexpr
#else
#define CSV2_CONSTEXPR17
#endif

#if defined(_MSC_VER)
#define CSV2_FORCE_INLINE __forceinline
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__OPTIMIZE__)
#define CSV2_FORCE_INLINE inline __attribute__((always_inline))
#else
#define CSV2_FORCE_INLINE inline
#endif

#if defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES)
#define CSV2_HAS_STRING_VIEW 0
#define CSV2_HAS_FILESYSTEM 0
#define CSV2_HAS_CHARCONV 0
#define CSV2_HAS_MEMORY_RESOURCE 0
#define CSV2_HAS_SPAN 0
#define CSV2_HAS_RANGES 0
#define CSV2_HAS_EXPECTED 0
#define CSV2_HAS_RANGES_TO_CONTAINER 0
#else
#if defined(__cpp_lib_string_view) && __cpp_lib_string_view >= 201606L
#define CSV2_HAS_STRING_VIEW 1
#else
#define CSV2_HAS_STRING_VIEW 0
#endif

#if defined(__cpp_lib_filesystem) && __cpp_lib_filesystem >= 201703L
#define CSV2_HAS_FILESYSTEM 1
#else
#define CSV2_HAS_FILESYSTEM 0
#endif

#if defined(__cpp_lib_to_chars) && __cpp_lib_to_chars >= 201611L
#define CSV2_HAS_CHARCONV 1
#else
#define CSV2_HAS_CHARCONV 0
#endif

#if defined(__cpp_lib_memory_resource) && __cpp_lib_memory_resource >= 201603L
#define CSV2_HAS_MEMORY_RESOURCE 1
#else
#define CSV2_HAS_MEMORY_RESOURCE 0
#endif

#if defined(__cpp_lib_span) && __cpp_lib_span >= 202002L
#define CSV2_HAS_SPAN 1
#else
#define CSV2_HAS_SPAN 0
#endif

#if defined(__cpp_lib_ranges) && __cpp_lib_ranges >= 201911L
#define CSV2_HAS_RANGES 1
#else
#define CSV2_HAS_RANGES 0
#endif

#if defined(__cpp_lib_expected) && __cpp_lib_expected >= 202202L
#define CSV2_HAS_EXPECTED 1
#else
#define CSV2_HAS_EXPECTED 0
#endif

#if defined(__cpp_lib_ranges_to_container) && __cpp_lib_ranges_to_container >= 202202L
#define CSV2_HAS_RANGES_TO_CONTAINER 1
#else
#define CSV2_HAS_RANGES_TO_CONTAINER 0
#endif
#endif

#ifndef CSV2_HAS_MMAP
#if defined(__has_include)
#if defined(_WIN32)
#if __has_include(<windows.h>)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#elif __has_include(<sys/mman.h>) && __has_include(<fcntl.h>) &&                                 \
    __has_include(<sys/stat.h>) && __has_include(<unistd.h>)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#elif defined(_WIN32) || defined(__unix__) || defined(__unix) || defined(__APPLE__)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#endif
