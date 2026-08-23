#include "../registry.hpp"

namespace csv2_benchmark {
namespace {

enum class ValidationScenario { valid, invalid_early, invalid_middle, invalid_late };

template <ValidationScenario Scenario>
bool validation_preflight(const Context &context, Source source, std::string &message) {
  csv2::parse_error error;
  const bool valid = context.reader(source).validate(error);
  if constexpr (Scenario == ValidationScenario::valid) {
    if (valid && error.code == csv2::parse_errc::none)
      return true;
    message = "input does not satisfy the valid CSV contract";
    return false;
  } else {
    if (valid || error.code == csv2::parse_errc::none || error.row == 0 || error.column == 0) {
      message = "input does not satisfy an invalid CSV contract";
      return false;
    }
    const std::size_t quarter = context.input_size() / 4 + (context.input_size() % 4 == 0 ? 0 : 1);
    const bool early = error.byte_offset < quarter;
    const bool late = error.byte_offset >= context.input_size() - quarter;
    if constexpr (Scenario == ValidationScenario::invalid_early) {
      if (early && error.code == csv2::parse_errc::unexpected_quote)
        return true;
      message = "input does not contain the expected early unexpected_quote error";
    } else if constexpr (Scenario == ValidationScenario::invalid_middle) {
      if (!early && !late && error.code == csv2::parse_errc::unclosed_quote)
        return true;
      message = "input does not contain the expected middle unclosed_quote error";
    } else {
      if (late && error.code == csv2::parse_errc::characters_after_closing_quote)
        return true;
      message = "input does not contain the expected late characters_after_closing_quote error";
    }
    return false;
  }
}

template <bool Verify> Result validate(Context &context, Source source, TimedObserver &observer) {
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
  registry.add("validation/valid", sources, prepare_reader, OperationScope::validation,
               validate<false>, validate<true>, true,
               validation_preflight<ValidationScenario::valid>);
  registry.add("validation/invalid-early", sources, prepare_reader, OperationScope::validation,
               validate<false>, validate<true>, true,
               validation_preflight<ValidationScenario::invalid_early>);
  registry.add("validation/invalid-middle", sources, prepare_reader, OperationScope::validation,
               validate<false>, validate<true>, true,
               validation_preflight<ValidationScenario::invalid_middle>);
  registry.add("validation/invalid-late", sources, prepare_reader, OperationScope::validation,
               validate<false>, validate<true>, true,
               validation_preflight<ValidationScenario::invalid_late>);
}

} // namespace csv2_benchmark
