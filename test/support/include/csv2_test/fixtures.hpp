#ifndef CSV2_TEST_FIXTURES_HPP
#define CSV2_TEST_FIXTURES_HPP

#include <string>

#ifndef CSV2_TEST_FIXTURE_ROOT
#error "CSV2_TEST_FIXTURE_ROOT must identify the verified fixture directory"
#endif

namespace csv2_test {

inline std::string fixture_path(const char *name) {
  std::string path(CSV2_TEST_FIXTURE_ROOT);
#if defined(_WIN32)
  path += '\\';
#else
  path += '/';
#endif
  path += name;
  return path;
}

} // namespace csv2_test

#endif
