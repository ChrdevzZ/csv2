#ifndef CSV2_TEST_ASSERTIONS_HPP
#define CSV2_TEST_ASSERTIONS_HPP

#if defined(CSV2_TEST_USE_CATCH2)

#include <catch2/catch_test_macros.hpp>

#define CSV2_TEST_CASE(id, domain) TEST_CASE(id, "[" domain "]")
#define CSV2_CHECK(expression) CHECK(static_cast<bool>(expression))
#define CSV2_REQUIRE(expression) REQUIRE(static_cast<bool>(expression))
#define CSV2_CHECK_EQ(actual, expected) CHECK(static_cast<bool>((actual) == (expected)))
#define CSV2_REQUIRE_FALSE(expression) REQUIRE_FALSE(static_cast<bool>(expression))
#define CSV2_REQUIRE_THROWS(expression) REQUIRE_THROWS(expression)
#define CSV2_REQUIRE_THROWS_AS(expression, exception) REQUIRE_THROWS_AS(expression, exception)
#define CSV2_CHECK_THROWS_AS(expression, exception) CHECK_THROWS_AS(expression, exception)

#else

#include <csv2_test/case_registry.hpp>

#define CSV2_TEST_JOIN_IMPL(left, right) left##right
#define CSV2_TEST_JOIN(left, right) CSV2_TEST_JOIN_IMPL(left, right)
#define CSV2_TEST_CASE_IMPL(id, domain, number)                                                    \
  static void CSV2_TEST_JOIN(csv2_test_function_, number)();                                       \
  static ::csv2_test::registrar CSV2_TEST_JOIN(csv2_test_registrar_, number)(                      \
      id, domain, &CSV2_TEST_JOIN(csv2_test_function_, number));                                   \
  static void CSV2_TEST_JOIN(csv2_test_function_, number)()
#define CSV2_TEST_CASE(id, domain) CSV2_TEST_CASE_IMPL(id, domain, __COUNTER__)

#define CSV2_CHECK(expression)                                                                     \
  do {                                                                                             \
    if (!(expression))                                                                             \
      ::csv2_test::record_failure(#expression, __FILE__, __LINE__);                                \
  } while (false)
#define CSV2_REQUIRE(expression)                                                                   \
  do {                                                                                             \
    if (!(expression)) {                                                                           \
      ::csv2_test::record_failure(#expression, __FILE__, __LINE__);                                \
      return;                                                                                      \
    }                                                                                              \
  } while (false)
#define CSV2_CHECK_EQ(actual, expected) CSV2_CHECK((actual) == (expected))
#define CSV2_REQUIRE_FALSE(expression) CSV2_REQUIRE(!(expression))

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
#define CSV2_REQUIRE_THROWS(expression)                                                            \
  CSV2_REQUIRE(::csv2_test::throws_any([&]() { static_cast<void>(expression); }))
#define CSV2_REQUIRE_THROWS_AS(expression, exception)                                              \
  CSV2_REQUIRE(::csv2_test::throws_as<exception>([&]() { static_cast<void>(expression); }))
#define CSV2_CHECK_THROWS_AS(expression, exception)                                                \
  CSV2_CHECK(::csv2_test::throws_as<exception>([&]() { static_cast<void>(expression); }))
#endif

#endif

#endif
