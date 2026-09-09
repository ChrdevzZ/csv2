#include <csv2_test/case_registry.hpp>

#include <cstring>
#include <iostream>

int main(int argc, char **argv) {
  const char *domain = 0;
  for (int argument = 1; argument < argc; ++argument) {
    if (std::strcmp(argv[argument], "--domain") == 0 && argument + 1 < argc) {
      domain = argv[++argument];
    } else {
      std::cerr << "usage: " << argv[0] << " [--domain DOMAIN]\n";
      return 2;
    }
  }
  return csv2_test::run_registered_tests(domain);
}
