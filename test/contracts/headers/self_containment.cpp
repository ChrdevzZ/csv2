#if defined(CSV2_TEST_HEADER_MIO)
#include <csv2/mio.hpp>
#elif defined(CSV2_TEST_HEADER_PARAMETERS)
#include <csv2/parameters.hpp>
#elif defined(CSV2_TEST_HEADER_ERRORS)
#include <csv2/errors.hpp>
#elif defined(CSV2_TEST_HEADER_READER)
#include <csv2/reader.hpp>
#elif defined(CSV2_TEST_HEADER_WRITER)
#include <csv2/writer.hpp>
#elif defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#error "A public header must be selected for the self-containment test"
#endif

#if defined(CSV2_EXPECT_NO_MIO) && CSV2_HAS_MMAP
#error "CSV2_HAS_MMAP must remain disabled"
#endif

#if defined(CSV2_EXPECT_NO_MIO) && defined(MIO_MMAP_HEADER)
#error "mio must not be included when CSV2_HAS_MMAP is disabled"
#endif

static_assert(true, "compiling this translation unit is the assertion");
