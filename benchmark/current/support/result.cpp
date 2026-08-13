#include "result.hpp"

namespace csv2_benchmark {

void mix(Result &result, std::uint64_t value) noexcept {
  result.checksum ^=
      value + 0x9e3779b97f4a7c15ull + (result.checksum << 6) + (result.checksum >> 2);
}

void mix_bytes(Result &result, const char *data, std::size_t size) noexcept {
  mix(result, static_cast<std::uint64_t>(size));
  for (std::size_t index = 0; index < size; ++index)
    mix(result, static_cast<unsigned char>(data[index]));
}

} // namespace csv2_benchmark
