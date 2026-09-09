#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/errors.hpp>
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#endif

#include <type_traits>

static_assert(std::is_move_constructible<csv2::Reader<>>::value,
              "C++26 forward compilation must preserve the public surface");

void csv2_cxx26_compile_only() {
  csv2::Reader<> reader;
  reader.parse_owned("forward,compatible");
}
