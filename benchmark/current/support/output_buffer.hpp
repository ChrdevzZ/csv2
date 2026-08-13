#ifndef CSV2_BENCHMARK_CURRENT_OUTPUT_BUFFER_HPP
#define CSV2_BENCHMARK_CURRENT_OUTPUT_BUFFER_HPP

#include <cstddef>
#include <streambuf>
#include <vector>

namespace csv2_benchmark {

class OutputBuffer : public std::streambuf {
  std::vector<char> storage_;

protected:
  std::streamsize xsputn(const char *data, std::streamsize size) override;
  int_type overflow(int_type character) override;

public:
  void reserve(std::size_t capacity);
  void reset() noexcept;
  const char *data() const noexcept { return storage_.data(); }
  std::size_t size() const noexcept;
};

} // namespace csv2_benchmark

#endif
