#include "../registry.hpp"

namespace csv2_benchmark {
namespace {

template <bool Verify> Result try_parse_integer(Context &context, Source source) {
  Result result;
  for (const BenchmarkReader::Row row : context.reader(source)) {
    ++result.rows;
    for (const BenchmarkReader::Cell cell : row) {
      std::int64_t value = 0;
      csv2::conversion_error error;
      const bool valid = cell.try_parse(value, error);
      ++result.cells;
      result.bytes += static_cast<std::uint64_t>(cell.raw_size());
      if (Verify) {
        mix(result, valid ? 1u : 0u);
        mix(result,
            valid ? static_cast<std::uint64_t>(value) : static_cast<std::uint64_t>(error.code));
        mix(result, static_cast<std::uint64_t>(error.byte_offset));
      }
    }
  }
  return result;
}

#if CSV2_HAS_EXPECTED
template <bool Verify> Result parse_expected_integer(Context &context, Source source) {
  Result result;
  for (const BenchmarkReader::Row row : context.reader(source)) {
    ++result.rows;
    for (const BenchmarkReader::Cell cell : row) {
      const std::expected<std::int64_t, csv2::conversion_error> value =
          cell.parse_expected<std::int64_t>();
      ++result.cells;
      result.bytes += static_cast<std::uint64_t>(cell.raw_size());
      if (Verify) {
        mix(result, value.has_value() ? 1u : 0u);
        mix(result, value ? static_cast<std::uint64_t>(*value)
                          : static_cast<std::uint64_t>(value.error().code));
        if (!value)
          mix(result, static_cast<std::uint64_t>(value.error().byte_offset));
      }
    }
  }
  return result;
}
#endif

} // namespace

void register_conversion_operations(Registry &registry) {
  unsigned sources = source_buffer;
#if CSV2_HAS_MMAP
  sources |= source_mmap;
#endif
  registry.add("conversion/integer-bool-error", sources, try_parse_integer<false>,
               try_parse_integer<true>, true);
#if CSV2_HAS_EXPECTED
  registry.add("conversion/integer-expected", sources, parse_expected_integer<false>,
               parse_expected_integer<true>, true);
#endif
}

} // namespace csv2_benchmark
