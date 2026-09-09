#ifndef CSV2_TEST_TEMPORARY_FILE_HPP
#define CSV2_TEST_TEMPORARY_FILE_HPP

#include <csv2_test/assertions.hpp>
#include <csv2_test/csv2_headers.hpp>

#include <cstdio>
#include <fstream>
#include <string>
#include <utility>

#if defined(_WIN32)
#include <process.h>
#elif defined(__unix__) || defined(__APPLE__)
#include <unistd.h>
#endif

namespace csv2_test {

inline const char *writer_output_path() {
  static const std::string path = []() {
#if defined(CSV2_TEST_WRITER_OUTPUT)
    std::string base(CSV2_TEST_WRITER_OUTPUT);
#elif defined(CSV2_TEST_SINGLE_HEADER)
    std::string base("csv2-single-header-writer-output.csv");
#else
    std::string base("csv2-module-writer-output.csv");
#endif
#if defined(_WIN32)
    return base + '.' + std::to_string(static_cast<unsigned long>(::_getpid()));
#elif defined(__unix__) || defined(__APPLE__)
    return base + '.' + std::to_string(static_cast<unsigned long>(::getpid()));
#else
    return base;
#endif
  }();
  return path.c_str();
}

class ScopedFileRemoval {
public:
  explicit ScopedFileRemoval(std::string path) : path_(std::move(path)) {}
  ~ScopedFileRemoval() { std::remove(path_.c_str()); }

private:
  std::string path_;
};

#if CSV2_HAS_MMAP
inline void write_binary_file(const std::string &path, const std::string &contents) {
  std::ofstream output(path.c_str(), std::ios::binary | std::ios::trunc);
  CSV2_REQUIRE(output.is_open());
  output.write(contents.data(), static_cast<std::streamsize>(contents.size()));
  CSV2_REQUIRE(output.good());
}
#endif

} // namespace csv2_test

#endif
