#ifndef CSV2_TEST_CSV2_HEADERS_HPP
#define CSV2_TEST_CSV2_HEADERS_HPP

#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#endif

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

#endif
