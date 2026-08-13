#include "../registry.hpp"

#if CSV2_HAS_RANGES
#include <ranges>
#include <vector>
#endif

namespace csv2_benchmark {

#if CSV2_HAS_RANGES
namespace {

template <bool Verify> Result pipeline(Context &context, Source source) {
  Result result;
  const auto rows =
      context.reader(source) | std::views::transform([](BenchmarkReader::Row row) { return row; });
  for (const BenchmarkReader::Row row : rows) {
    ++result.rows;
    const auto sizes =
        row | std::views::transform([](BenchmarkReader::Cell cell) { return cell.raw_size(); });
    for (const std::size_t size : sizes) {
      ++result.cells;
      result.bytes += static_cast<std::uint64_t>(size);
      if (Verify)
        mix(result, static_cast<std::uint64_t>(size));
    }
  }
  return result;
}

#if CSV2_HAS_RANGES_TO_CONTAINER
template <bool Verify> Result to_container(Context &context, Source source) {
  Result result;
  for (const BenchmarkReader::Row row : context.reader(source)) {
    const std::vector<std::size_t> sizes =
        row | std::views::transform([](BenchmarkReader::Cell cell) { return cell.raw_size(); }) |
        std::ranges::to<std::vector>();
    ++result.rows;
    result.cells += static_cast<std::uint64_t>(sizes.size());
    for (const std::size_t size : sizes) {
      result.bytes += static_cast<std::uint64_t>(size);
      if (Verify)
        mix(result, static_cast<std::uint64_t>(size));
    }
  }
  return result;
}
#endif

} // namespace
#endif

void register_ranges_operations(Registry &registry) {
#if CSV2_HAS_RANGES
  unsigned sources = source_buffer;
#if CSV2_HAS_MMAP
  sources |= source_mmap;
#endif
  registry.add("ranges/pipeline", sources, pipeline<false>, pipeline<true>, true);
#if CSV2_HAS_RANGES_TO_CONTAINER
  registry.add("ranges/to-container", sources, to_container<false>, to_container<true>);
#endif
#else
  (void)registry;
#endif
}

} // namespace csv2_benchmark
