#include "../registry.hpp"

#include <iterator>
#include <string>
#include <vector>

namespace csv2_benchmark {
namespace {

enum class CellMode { raw, decoded, content };

template <typename Container>
void copy_cell(const BenchmarkReader::Cell &cell, Container &output, CellMode mode) {
  if (mode == CellMode::raw)
    cell.copy_raw_to(std::back_inserter(output));
  else if (mode == CellMode::decoded)
    cell.decode_to(std::back_inserter(output));
  else
    cell.copy_content_to(std::back_inserter(output));
}

template <bool Verify, typename Container>
Result extract_reused(Context &context, Source source, CellMode mode, Container &output,
                      TimedObserver &observer) {
  Result result;
  for (const BenchmarkReader::Row row : context.reader(source)) {
    ++result.rows;
    for (const BenchmarkReader::Cell cell : row) {
      output.clear();
      copy_cell(cell, output, mode);
      ++result.cells;
      result.bytes += static_cast<std::uint64_t>(output.size());
      if (Verify)
        mix_bytes(result, output.data(), output.size());
      else
        observer.memory(output);
    }
  }
  if constexpr (!Verify)
    observe_result(observer, result);
  return result;
}

template <bool Verify, typename Container>
Result extract_fresh(Context &context, Source source, CellMode mode, TimedObserver &observer) {
  Result result;
  for (const BenchmarkReader::Row row : context.reader(source)) {
    ++result.rows;
    for (const BenchmarkReader::Cell cell : row) {
      Container output;
      copy_cell(cell, output, mode);
      ++result.cells;
      result.bytes += static_cast<std::uint64_t>(output.size());
      if (Verify)
        mix_bytes(result, output.data(), output.size());
      else
        observer.memory(output);
    }
  }
  if constexpr (!Verify)
    observe_result(observer, result);
  return result;
}

template <bool Verify>
Result row_raw(Context &context, Source source, TimedObserver &observer) {
  Result result;
  std::string &output = context.reset_string_scratch();
  for (const BenchmarkReader::Row row : context.reader(source)) {
    output.clear();
    row.read_raw_value(output);
    ++result.rows;
    result.bytes += static_cast<std::uint64_t>(output.size());
    if (Verify)
      mix_bytes(result, output.data(), output.size());
    else
      observer.memory(output);
  }
  if constexpr (!Verify)
    observe_result(observer, result);
  return result;
}

template <bool Verify> Result raw_reused_string(Context &c, Source s, TimedObserver &observer) {
  std::string &output = c.reset_string_scratch();
  return extract_reused<Verify>(c, s, CellMode::raw, output, observer);
}
template <bool Verify> Result raw_fresh_string(Context &c, Source s, TimedObserver &observer) {
  return extract_fresh<Verify, std::string>(c, s, CellMode::raw, observer);
}
template <bool Verify>
Result decoded_reused_string(Context &c, Source s, TimedObserver &observer) {
  std::string &output = c.reset_string_scratch();
  return extract_reused<Verify>(c, s, CellMode::decoded, output, observer);
}
template <bool Verify>
Result decoded_fresh_string(Context &c, Source s, TimedObserver &observer) {
  return extract_fresh<Verify, std::string>(c, s, CellMode::decoded, observer);
}
template <bool Verify>
Result content_reused_string(Context &c, Source s, TimedObserver &observer) {
  std::string &output = c.reset_string_scratch();
  return extract_reused<Verify>(c, s, CellMode::content, output, observer);
}
template <bool Verify>
Result content_fresh_string(Context &c, Source s, TimedObserver &observer) {
  return extract_fresh<Verify, std::string>(c, s, CellMode::content, observer);
}
template <bool Verify>
Result decoded_reused_vector(Context &c, Source s, TimedObserver &observer) {
  std::vector<char> &output = c.reset_vector_scratch();
  return extract_reused<Verify>(c, s, CellMode::decoded, output, observer);
}
template <bool Verify>
Result decoded_fresh_vector(Context &c, Source s, TimedObserver &observer) {
  return extract_fresh<Verify, std::vector<char>>(c, s, CellMode::decoded, observer);
}

} // namespace

void register_extraction_operations(Registry &registry) {
  unsigned sources = source_buffer;
#if CSV2_HAS_MMAP
  sources |= source_mmap;
#endif
  registry.add("extraction/row-raw/reused-string", sources,
               prepare_reader | prepare_string_scratch, OperationScope::extraction,
               row_raw<false>, row_raw<true>, true);
  registry.add("extraction/cell-raw/reused-string", sources,
               prepare_reader | prepare_string_scratch, OperationScope::extraction,
               raw_reused_string<false>, raw_reused_string<true>, true);
  registry.add("extraction/cell-raw/fresh-string", sources, prepare_reader,
               OperationScope::extraction, raw_fresh_string<false>, raw_fresh_string<true>);
  registry.add("extraction/cell-decoded/reused-string", sources,
               prepare_reader | prepare_string_scratch, OperationScope::extraction,
               decoded_reused_string<false>, decoded_reused_string<true>, true);
  registry.add("extraction/cell-decoded/fresh-string", sources, prepare_reader,
               OperationScope::extraction, decoded_fresh_string<false>, decoded_fresh_string<true>);
  registry.add("extraction/cell-decoded/reused-vector", sources,
               prepare_reader | prepare_vector_scratch, OperationScope::extraction,
               decoded_reused_vector<false>, decoded_reused_vector<true>, true);
  registry.add("extraction/cell-decoded/fresh-vector", sources, prepare_reader,
               OperationScope::extraction, decoded_fresh_vector<false>, decoded_fresh_vector<true>);
  registry.add("extraction/cell-content/reused-string", sources,
               prepare_reader | prepare_string_scratch, OperationScope::extraction,
               content_reused_string<false>, content_reused_string<true>, true);
  registry.add("extraction/cell-content/fresh-string", sources, prepare_reader,
               OperationScope::extraction, content_fresh_string<false>, content_fresh_string<true>);
}

} // namespace csv2_benchmark
