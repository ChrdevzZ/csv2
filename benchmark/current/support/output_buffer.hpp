#ifndef CSV2_BENCHMARK_CURRENT_OUTPUT_BUFFER_HPP
#define CSV2_BENCHMARK_CURRENT_OUTPUT_BUFFER_HPP

#include <cstddef>
#include <streambuf>
#include <vector>

namespace csv2_benchmark {

class OutputBuffer : public std::streambuf {
  std::vector<char> storage_;
  bool overflowed_;

protected:
  std::streamsize xsputn(const char *data, std::streamsize size) override;
  int_type overflow(int_type character) override;

public:
  OutputBuffer() noexcept : overflowed_(false) {}
  void reserve(std::size_t capacity);
  void reset() noexcept;
  char *data() noexcept { return storage_.data(); }
  const char *data() const noexcept { return storage_.data(); }
  std::size_t size() const noexcept;
  bool overflowed() const noexcept { return overflowed_; }
};

} // namespace csv2_benchmark

#endif
