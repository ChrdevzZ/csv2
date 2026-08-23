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
  const BenchmarkReader::RowIndex &index = context.row_index(source);
  Result result;
  result.rows = static_cast<std::uint64_t>(index.size());
  std::size_t observed_size = 0;
  const char *observed_data = nullptr;
  for (std::size_t position = 0; position < index.size(); ++position) {
    const BenchmarkReader::Row row = index[position];
    observed_size = row.raw_size();
    observed_data = row.raw_data();
    result.bytes += static_cast<std::uint64_t>(observed_size);
    if (Verify) {
      mix(result, static_cast<std::uint64_t>(row.raw_size()));
      mix_bytes(result, row.raw_data(), row.raw_size());
    }
  }
  if constexpr (!Verify) {
    observer.value(observed_size);
    observer.value(observed_data);
    observe_result(observer, result);
  }
  return result;
}

template <bool Verify>
Result random_lookup(Context &context, Source source, TimedObserver &observer) {
  const BenchmarkReader::RowIndex &index = context.row_index(source);
  const std::vector<std::size_t> &positions = context.random_positions(source);
  Result result;
  result.rows = static_cast<std::uint64_t>(positions.size());
  std::size_t observed_size = 0;
  const char *observed_data = nullptr;
  for (const std::size_t position : positions) {
    const BenchmarkReader::Row row = index[position];
    observed_size = row.raw_size();
    observed_data = row.raw_data();
    result.bytes += static_cast<std::uint64_t>(observed_size);
    if (Verify) {
      mix(result, static_cast<std::uint64_t>(position));
      mix(result, static_cast<std::uint64_t>(observed_size));
      mix_bytes(result, row.raw_data(), row.raw_size());
    }
  }
  if constexpr (!Verify) {
    observer.value(observed_size);
    observer.value(observed_data);
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
  registry.add("index/sequential-lookup", sources, prepare_reader | prepare_index,
               OperationScope::index, sequential<false>, sequential<true>, true);
  registry.add("index/random-lookup", sources,
               prepare_reader | prepare_index | prepare_random_positions,
               OperationScope::index, random_lookup<false>, random_lookup<true>, true);
}

} // namespace csv2_benchmark
