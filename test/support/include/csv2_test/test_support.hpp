#ifndef CSV2_TEST_TEST_SUPPORT_HPP
#define CSV2_TEST_TEST_SUPPORT_HPP

#include <csv2_test/assertions.hpp>
#include <csv2_test/csv2_headers.hpp>
#include <csv2_test/fixtures.hpp>
#include <csv2_test/platform.hpp>
#include <csv2_test/reader_support.hpp>
#include <csv2_test/sinks.hpp>
#include <csv2_test/streams.hpp>
#include <csv2_test/string_like.hpp>
#include <csv2_test/temporary_file.hpp>

#if defined(CSV2_TEST_NO_EXCEPTIONS)
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
#error "The no-exceptions test must be compiled with exception handling disabled"
#endif
#endif

#if defined(CSV2_TEST_NO_MMAP) && CSV2_HAS_MMAP
#error "CSV2_HAS_MMAP must remain disabled"
#endif

#if defined(CSV2_TEST_NO_MMAP) && defined(MIO_MMAP_HEADER)
#error "mio must not be included when CSV2_HAS_MMAP is disabled"
#endif

#include <algorithm>
#include <deque>
#include <forward_list>
#include <iomanip>
#include <list>
#include <system_error>

#if CSV2_HAS_MEMORY_RESOURCE
#include <memory_resource>
#endif
#if CSV2_HAS_FILESYSTEM
#include <filesystem>
#endif
#if CSV2_HAS_SPAN
#include <span>
#endif

#endif
