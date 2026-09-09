#ifndef CSV2_BENCHMARK_CURRENT_RESULT_HPP
#define CSV2_BENCHMARK_CURRENT_RESULT_HPP

#include <cstddef>
#include <cstdint>

namespace csv2_benchmark {

// Stable protocol seed; checksum mixing intentionally does not implement FNV-1a.
constexpr std::uint64_t checksum_seed = 1469598103934665603ull;

enum class KernelStatus : std::uint8_t {
  ok,
  input_open_failed,
  input_read_failed,
  input_changed,
  mmap_failed,
  parse_failed,
  output_overflow,
  output_stream_failed
};

const char *kernel_status_name(KernelStatus status) noexcept;

struct Result {
  KernelStatus status;
  int native_error;
  std::uint64_t checksum;
  std::uint64_t bytes;
  std::uint64_t rows;
  std::uint64_t cells;
  std::uint64_t allocations;
  std::uint64_t allocated_bytes;

  Result() noexcept
      : status(KernelStatus::ok), native_error(0), checksum(checksum_seed), bytes(0), rows(0),
        cells(0), allocations(0), allocated_bytes(0) {}

  bool ok() const noexcept { return status == KernelStatus::ok; }
};

inline void fail(Result &result, KernelStatus status, int native_error = 0) noexcept {
  result.status = status;
  result.native_error = native_error;
}

void mix(Result &result, std::uint64_t value) noexcept;
void mix_bytes(Result &result, const char *data, std::size_t size) noexcept;

} // namespace csv2_benchmark

#endif
