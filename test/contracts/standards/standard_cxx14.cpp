#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/detail/config.hpp>
#include <csv2/parameters.hpp>
#endif

CSV2_CONSTEXPR14 int csv2_cxx14_increment(int value) { return ++value; }
static_assert(csv2_cxx14_increment(1) == 2, "CSV2_CONSTEXPR14 must enable C++14 constexpr");
static_assert(csv2::delimiter<';'>::value == ';', "parameter values remain constexpr");
