#ifndef CSV2_BENCHMARK_CURRENT_SUPPORT_MAPPING_TOUCH_HPP
#define CSV2_BENCHMARK_CURRENT_SUPPORT_MAPPING_TOUCH_HPP

#include <cstddef>

namespace csv2_benchmark {

inline unsigned char touch_mapping_bytes(const char *data, std::size_t size) noexcept {
  volatile unsigned char sink = 0;
  const std::size_t stride = 4096;
  for (std::size_t index = 0; index < size; index += stride)
    sink = static_cast<unsigned char>(sink ^ static_cast<unsigned char>(data[index]));
  if (size != 0)
    sink = static_cast<unsigned char>(sink ^ static_cast<unsigned char>(data[size - 1]));
  return sink;
}

} // namespace csv2_benchmark

#endif
