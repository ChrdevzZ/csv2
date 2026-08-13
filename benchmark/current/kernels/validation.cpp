#include "../registry.hpp"

namespace csv2_benchmark {
namespace {

template <bool Verify>
Result validate(Context &context, Source source, TimedObserver &observer) {
  Result result;
  csv2::parse_error error;
  bool valid = context.reader(source).validate(error);
  result.bytes = static_cast<std::uint64_t>(context.input_size());
  if (Verify) {
    mix(result, valid ? 1u : 0u);
    mix(result, static_cast<std::uint64_t>(error.code));
    mix(result, static_cast<std::uint64_t>(error.byte_offset));
    mix(result, static_cast<std::uint64_t>(error.row));
    mix(result, static_cast<std::uint64_t>(error.column));
  } else {
    observer.value(valid);
    observer.value(error.code);
    observer.value(error.byte_offset);
    observer.value(error.row);
    observer.value(error.column);
    observe_result(observer, result);
  }
  return result;
}

} // namespace

void register_validation_operations(Registry &registry) {
  unsigned sources = source_buffer;
#if CSV2_HAS_MMAP
  sources |= source_mmap;
#endif
  registry.add("validation/strict", sources, validate<false>, validate<true>, true);
  registry.add("validation/invalid-early", sources, validate<false>, validate<true>, true);
  registry.add("validation/invalid-middle", sources, validate<false>, validate<true>, true);
  registry.add("validation/invalid-late", sources, validate<false>, validate<true>, true);
}

} // namespace csv2_benchmark
