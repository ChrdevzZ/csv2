#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

CSV2_TEST_CASE("reader.convert.convert-complete-integer-field-content-without-modifying-failures",
               "reader.convert") {
  ReaderWithoutHeader reader;
  std::string input("42,-2147483648,2147483648,12x,+7,101,\"17\"");
  CSV2_REQUIRE(reader.parse(input));
  auto cell = (*reader.begin()).begin();
  csv2::conversion_error error;

  int value = -1;
  CSV2_REQUIRE((*cell).try_parse(value, error));
  CSV2_REQUIRE(value == 42);
  CSV2_REQUIRE(error.code == csv2::conversion_errc::none);

  ++cell;
  CSV2_REQUIRE((*cell).try_parse(value, error));
  CSV2_REQUIRE(value == (std::numeric_limits<int>::min)());

  ++cell;
  value = 9;
  CSV2_REQUIRE_FALSE((*cell).try_parse(value, error));
  CSV2_REQUIRE(value == 9);
  CSV2_REQUIRE(error.code == csv2::conversion_errc::result_out_of_range);

  ++cell;
  CSV2_REQUIRE_FALSE((*cell).try_parse(value, error));
  CSV2_REQUIRE(error.code == csv2::conversion_errc::trailing_characters);
  CSV2_REQUIRE(error.byte_offset == 2);

  ++cell;
  CSV2_REQUIRE_FALSE((*cell).try_parse(value, error));
  CSV2_REQUIRE(error.code == csv2::conversion_errc::invalid_argument);
  CSV2_REQUIRE(error.byte_offset == 0);

  ++cell;
  CSV2_REQUIRE((*cell).try_parse(value, error, 2));
  CSV2_REQUIRE(value == 5);

  ++cell;
  CSV2_REQUIRE((*cell).try_parse(value, error));
  CSV2_REQUIRE(value == 17);

  value = 11;
  CSV2_REQUIRE_FALSE((*cell).try_parse(value, error, 1));
  CSV2_REQUIRE(value == 11);
  CSV2_REQUIRE(error.code == csv2::conversion_errc::invalid_base);

  ReaderWithoutHeader sign_reader;
  std::string sign_input("-");
  CSV2_REQUIRE(sign_reader.parse(sign_input));
  value = 12;
  CSV2_REQUIRE_FALSE(sign_reader.begin()->begin()->try_parse(value, error));
  CSV2_REQUIRE(value == 12);
  CSV2_REQUIRE(error.code == csv2::conversion_errc::invalid_argument);
  CSV2_REQUIRE(error.byte_offset == 0);
}

#if CSV2_HAS_EXPECTED
CSV2_TEST_CASE("reader.convert.expose-cxx23-expected-adapters-when-the-library-provides-them",
               "reader.convert") {
  ReaderWithoutHeader reader;
  std::string input("42,invalid");
  CSV2_REQUIRE(reader.parse(input));
  CSV2_REQUIRE(reader.validate_expected().has_value());

  auto cell = (*reader.begin()).begin();
  const auto parsed = (*cell).template parse_expected<int>();
  CSV2_REQUIRE(parsed == 42);
  ++cell;
  const auto failed = (*cell).template parse_expected<int>();
  CSV2_REQUIRE_FALSE(failed.has_value());
  CSV2_REQUIRE(failed.error().code == csv2::conversion_errc::invalid_argument);

#if CSV2_HAS_MMAP
  ReaderWithoutHeader mapped;
  CSV2_REQUIRE(mapped.mmap_expected(fixture_path("test_01.csv")).has_value());
  const auto missing = mapped.mmap_expected(fixture_path("this-file-does-not-exist.csv"));
  CSV2_REQUIRE_FALSE(missing.has_value());
  CSV2_REQUIRE(missing.error());
#endif
}
#endif
