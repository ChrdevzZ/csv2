#include "result.hpp"

namespace csv2_benchmark {

const char *kernel_status_name(KernelStatus status) noexcept {
  switch (status) {
  case KernelStatus::ok:
    return "ok";
  case KernelStatus::input_open_failed:
    return "input_open_failed";
  case KernelStatus::input_read_failed:
    return "input_read_failed";
  case KernelStatus::input_changed:
    return "input_changed";
  case KernelStatus::mmap_failed:
    return "mmap_failed";
  case KernelStatus::parse_failed:
    return "parse_failed";
  case KernelStatus::output_overflow:
    return "output_overflow";
  case KernelStatus::output_stream_failed:
    return "output_stream_failed";
  }
  return "unknown";
}

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
