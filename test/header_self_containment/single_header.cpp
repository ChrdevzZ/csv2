#include <csv2/csv2.hpp>

#if defined(CSV2_EXPECT_NO_MIO) && defined(MIO_MMAP_HEADER)
#error "mio must not be included when CSV2_HAS_MMAP is disabled"
#endif

void csv2_single_header_is_self_contained() {}
