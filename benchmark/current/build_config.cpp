#include "build_config.hpp"

namespace csv2_benchmark {
namespace build_config {

const char *revision() noexcept {
#if defined(CSV2_BENCHMARK_REVISION)
  return CSV2_BENCHMARK_REVISION;
#else
  return "unstamped";
#endif
}

const char *default_input() noexcept {
#if defined(CSV2_BENCHMARK_DEFAULT_INPUT)
  return CSV2_BENCHMARK_DEFAULT_INPUT;
#else
  return nullptr;
#endif
}

} // namespace build_config
} // namespace csv2_benchmark
