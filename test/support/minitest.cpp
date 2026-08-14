#include <csv2_test/case_registry.hpp>

#include <cstring>
#include <iostream>

namespace csv2_test {
namespace {

test_case *&registry_head() {
  static test_case *head = 0;
  return head;
}

int &failure_count() {
  static int count = 0;
  return count;
}

} // namespace

registrar::registrar(const char *id, const char *domain, test_function function) {
  entry_.id = id;
  entry_.domain = domain;
  entry_.function = function;
  entry_.next = registry_head();
  registry_head() = &entry_;
}

void record_failure(const char *expression, const char *file, int line) {
  ++failure_count();
  std::cerr << file << ':' << line << ": assertion failed: " << expression << '\n';
}

int run_registered_tests(const char *domain_filter) {
  int selected = 0;
  int failed_cases = 0;
  for (test_case *entry = registry_head(); entry != 0; entry = entry->next) {
    if (domain_filter != 0 && std::strcmp(domain_filter, entry->domain) != 0)
      continue;
    ++selected;
    const int failures_before = failure_count();
    entry->function();
    if (failure_count() != failures_before) {
      ++failed_cases;
      std::cerr << "FAILED: " << entry->id << '\n';
    }
  }
  if (selected == 0) {
    std::cerr << "no csv2 tests matched the requested domain\n";
    return 2;
  }
  if (failed_cases != 0) {
    std::cerr << failed_cases << " test case(s) failed\n";
    return 1;
  }
  std::cout << selected << " test case(s) passed\n";
  return 0;
}

} // namespace csv2_test
