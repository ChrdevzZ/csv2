#ifndef CSV2_BENCHMARK_CURRENT_KERNELS_HELPERS_HPP
#define CSV2_BENCHMARK_CURRENT_KERNELS_HELPERS_HPP

#include "../context.hpp"
#include "../support/result.hpp"

#include <cstdint>

namespace csv2_benchmark {

template <bool Verify>
inline void account_cell(Result &result, const BenchmarkReader::Cell &cell) noexcept {
  ++result.cells;
  result.bytes += static_cast<std::uint64_t>(cell.raw_size());
  if (Verify) {
    mix(result, static_cast<std::uint64_t>(cell.raw_size()));
    if (cell.raw_size())
      mix_bytes(result, cell.raw_data(), cell.raw_size());
  }
}

template <bool Verify>
inline void account_row(Result &result, const BenchmarkReader::Row &row) noexcept {
  ++result.rows;
  result.bytes += static_cast<std::uint64_t>(row.raw_size());
  if (Verify) {
    mix(result, static_cast<std::uint64_t>(row.raw_size()));
    if (row.raw_size())
      mix_bytes(result, row.raw_data(), row.raw_size());
  }
}

} // namespace csv2_benchmark

#endif
