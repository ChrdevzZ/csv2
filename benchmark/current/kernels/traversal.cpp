#include "../registry.hpp"
#include "helpers.hpp"

namespace csv2_benchmark {
namespace {

template <bool Verify> Result rows(Context &context, Source source, TimedObserver &observer) {
  Result result;
  for (const BenchmarkReader::Row row : context.reader(source))
    account_row<Verify>(result, row);
  if constexpr (!Verify)
    observe_result(observer, result);
  return result;
}

template <bool Verify>
Result rows_cells(Context &context, Source source, TimedObserver &observer) {
  Result result;
  for (const BenchmarkReader::Row row : context.reader(source)) {
    ++result.rows;
    for (const BenchmarkReader::Cell cell : row)
      account_cell<Verify>(result, cell);
  }
  if constexpr (!Verify)
    observe_result(observer, result);
  return result;
}

} // namespace

void register_traversal_operations(Registry &registry) {
  unsigned sources = source_buffer;
#if CSV2_HAS_MMAP
  sources |= source_mmap;
#endif
  registry.add("traversal/rows", sources, rows<false>, rows<true>, true);
  registry.add("traversal/rows-cells", sources, rows_cells<false>, rows_cells<true>, true);
}

} // namespace csv2_benchmark
