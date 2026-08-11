#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/errors.hpp>
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#endif

#include <string>
#include <type_traits>

using cxx11_reader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::first_row_is_header<false>>;
static_assert(!std::is_copy_constructible<cxx11_reader>::value,
              "Reader source ownership must remain move-only");
static_assert(std::is_default_constructible<cxx11_reader::RowIterator>::value,
              "C++11 iterator algorithms require a default constructor");

void csv2_cxx11_contract() {
  cxx11_reader reader;
  std::string input("1,2");
  csv2::parse_error parse_error;
  csv2::conversion_error conversion_error;
  int value = 0;
  if (reader.parse(input) && reader.validate(parse_error))
    (*(*reader.begin()).begin()).try_parse(value, conversion_error);
}
