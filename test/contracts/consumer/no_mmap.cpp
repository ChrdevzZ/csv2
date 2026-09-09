#include <csv2/mio.hpp>

#ifdef MIO_MMAP_HEADER
#error "mio must be absent when CSV2_HAS_MMAP=0"
#endif

#include <csv2/errors.hpp>
#include <csv2/parameters.hpp>
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>

int main() { return CSV2_HAS_MMAP; }
