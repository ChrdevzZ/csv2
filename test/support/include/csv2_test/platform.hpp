#ifndef CSV2_TEST_PLATFORM_HPP
#define CSV2_TEST_PLATFORM_HPP

#include <csv2_test/csv2_headers.hpp>

#include <cstddef>
#include <limits>

#if CSV2_HAS_MMAP && defined(__linux__)
#include <dirent.h>
#elif CSV2_HAS_MMAP && defined(_WIN32)
#include <windows.h>
#endif

namespace csv2_test {

#if CSV2_HAS_MMAP && (defined(__linux__) || defined(_WIN32))
inline std::size_t process_handle_count() {
#if defined(_WIN32)
  DWORD count = 0;
  if (!::GetProcessHandleCount(::GetCurrentProcess(), &count))
    return (std::numeric_limits<std::size_t>::max)();
  return static_cast<std::size_t>(count);
#else
  DIR *directory = ::opendir("/proc/self/fd");
  if (!directory)
    return (std::numeric_limits<std::size_t>::max)();
  std::size_t count = 0;
  while (::readdir(directory))
    ++count;
  ::closedir(directory);
  return count;
#endif
}
#endif

} // namespace csv2_test

#endif
