#ifndef CSV2_BENCHMARK_CURRENT_ALLOCATION_HPP
#define CSV2_BENCHMARK_CURRENT_ALLOCATION_HPP

#include <benchmark/benchmark.h>

#include <cstddef>
#include <cstdint>

namespace csv2_benchmark {
namespace allocation {

struct Counts {
  std::uint64_t allocations;
  std::uint64_t bytes;
};

void reset(bool enabled) noexcept;
Counts counts() noexcept;

class MemoryManager : public benchmark::MemoryManager {
public:
  void Start() override;
  void Stop(benchmark::MemoryManager::Result &result) override;
};

} // namespace allocation
} // namespace csv2_benchmark

#endif
