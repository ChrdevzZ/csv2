#include "../registry.hpp"

#include <cstdint>

namespace csv2_benchmark {
namespace {

template <bool Verify> Result build(Context &context, Source source, TimedObserver &observer) {
  BenchmarkReader::RowIndex index = context.reader(source).index();
  Result result;
  result.rows = static_cast<std::uint64_t>(index.size());
  result.bytes = static_cast<std::uint64_t>(context.input_size());
  if (Verify)
    mix(result, result.rows);
  else {
    observer.value(index);
    observe_result(observer, result);
  }
  return result;
}

template <bool Verify> Result sequential(Context &context, Source source, TimedObserver &observer) {
  BenchmarkReader::RowIndex index = context.reader(source).index();
  Result result;
  result.rows = static_cast<std::uint64_t>(index.size());
  for (std::size_t position = 0; position < index.size(); ++position) {
    const BenchmarkReader::Row row = index[position];
    result.bytes += static_cast<std::uint64_t>(row.raw_size());
    if (Verify)
      mix(result, static_cast<std::uint64_t>(row.raw_size()));
  }
  if constexpr (!Verify) {
    observer.value(index);
    observe_result(observer, result);
  }
  return result;
}

template <bool Verify>
Result random_lookup(Context &context, Source source, TimedObserver &observer) {
  BenchmarkReader::RowIndex index = context.reader(source).index();
  Result result;
  result.rows = static_cast<std::uint64_t>(index.size());
  std::uint32_t state = 0x43535632u;
  for (std::size_t count = 0; count < index.size(); ++count) {
    state = state * 1664525u + 1013904223u;
    const std::size_t position = index.empty() ? 0 : state % index.size();
    if (index.empty())
      break;
    const BenchmarkReader::Row row = index[position];
    result.bytes += static_cast<std::uint64_t>(row.raw_size());
    if (Verify) {
      mix(result, static_cast<std::uint64_t>(position));
      mix(result, static_cast<std::uint64_t>(row.raw_size()));
    }
  }
  if constexpr (!Verify) {
    observer.value(index);
    observer.value(state);
    observe_result(observer, result);
  }
  return result;
}

} // namespace

void register_index_operations(Registry &registry) {
  unsigned sources = source_buffer;
#if CSV2_HAS_MMAP
  sources |= source_mmap;
#endif
  registry.add("index/build", sources, prepare_reader, OperationScope::index, build<false>,
               build<true>);
  registry.add("index/sequential", sources, prepare_reader, OperationScope::index,
               sequential<false>, sequential<true>);
  registry.add("index/random", sources, prepare_reader, OperationScope::index, random_lookup<false>,
               random_lookup<true>);
}

} // namespace csv2_benchmark
