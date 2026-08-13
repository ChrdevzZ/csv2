#ifndef CSV2_BENCHMARK_CURRENT_RESULT_HPP
#define CSV2_BENCHMARK_CURRENT_RESULT_HPP

#include <cstddef>
#include <cstdint>

namespace csv2_benchmark {

struct Result {
  std::uint64_t checksum;
  std::uint64_t bytes;
  std::uint64_t rows;
  std::uint64_t cells;
  std::uint64_t allocations;
  std::uint64_t allocated_bytes;

  Result() noexcept
      : checksum(1469598103934665603ull), bytes(0), rows(0), cells(0), allocations(0),
        allocated_bytes(0) {}
};

void mix(Result &result, std::uint64_t value) noexcept;
void mix_bytes(Result &result, const char *data, std::size_t size) noexcept;

} // namespace csv2_benchmark

#endif
