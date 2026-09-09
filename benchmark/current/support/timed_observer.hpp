#ifndef CSV2_BENCHMARK_CURRENT_TIMED_OBSERVER_HPP
#define CSV2_BENCHMARK_CURRENT_TIMED_OBSERVER_HPP

#include <benchmark/benchmark.h>

#include <cstddef>
#include <type_traits>

namespace csv2_benchmark {

// Timed kernels must make their actual product observable before local storage is
// cleared or destroyed. The audit counters compile out of normal benchmark builds.
class TimedObserver {
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
  std::size_t value_observations_;
  std::size_t memory_observations_;
#endif

public:
  TimedObserver() noexcept
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
      : value_observations_(0), memory_observations_(0)
#endif
  {
  }

  template <typename T>
  typename std::enable_if<!std::is_const<T>::value, void>::type value(T &observed) noexcept {
    benchmark::DoNotOptimize(observed);
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
    ++value_observations_;
#endif
  }

  template <typename Buffer>
  typename std::enable_if<!std::is_const<Buffer>::value, void>::type
  memory(Buffer &observed) noexcept {
    const void *data = observed.size() == 0 ? nullptr : observed.data();
    std::size_t size = observed.size();
    benchmark::DoNotOptimize(data);
    benchmark::DoNotOptimize(size);
    benchmark::ClobberMemory();
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
    ++memory_observations_;
#endif
  }

  std::size_t value_observations() const noexcept {
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
    return value_observations_;
#else
    return 0;
#endif
  }

  std::size_t memory_observations() const noexcept {
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
    return memory_observations_;
#else
    return 0;
#endif
  }
};

} // namespace csv2_benchmark

#endif
