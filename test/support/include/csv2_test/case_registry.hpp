#ifndef CSV2_TEST_CASE_REGISTRY_HPP
#define CSV2_TEST_CASE_REGISTRY_HPP

#include <cstddef>

namespace csv2_test {

typedef void (*test_function)();

struct test_case {
  const char *id;
  const char *domain;
  test_function function;
  test_case *next;
};

class registrar {
public:
  registrar(const char *id, const char *domain, test_function function);
};

void record_failure(const char *expression, const char *file, int line);
int run_registered_tests(const char *domain_filter);

class subcase {
public:
  explicit subcase(const char *) {}
  operator bool() const { return true; }
};

template <typename Exception, typename Function> bool throws_as(Function function) {
#if defined(CSV2_TEST_NO_EXCEPTIONS)
  (void)function;
  return false;
#else
  try {
    function();
  } catch (const Exception &) {
    return true;
  } catch (...) {
  }
  return false;
#endif
}

template <typename Function> bool throws_any(Function function) {
#if defined(CSV2_TEST_NO_EXCEPTIONS)
  (void)function;
  return false;
#else
  try {
    function();
  } catch (...) {
    return true;
  }
  return false;
#endif
}

} // namespace csv2_test

#endif
