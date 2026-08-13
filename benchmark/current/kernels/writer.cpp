#include "../registry.hpp"

#include <csv2/writer.hpp>

#include <stdexcept>

namespace csv2_benchmark {
namespace {

template <bool Verify, typename QuotePolicy, typename Rows>
Result write(Context &context, const Rows &rows, TimedObserver &observer) {
  std::ostream &stream = context.reset_output();
  csv2::basic_writer<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open,
                     QuotePolicy>
      writer(stream);
  writer.write_rows(rows);

  Result result;
  result.rows = context.decoded_row_count();
  result.cells = context.decoded_cell_count();
  result.bytes = static_cast<std::uint64_t>(context.output_buffer().size());
  if (context.output_buffer().overflowed())
    fail(result, KernelStatus::output_overflow);
  else if (!stream)
    fail(result, KernelStatus::output_stream_failed);
  if (Verify)
    mix_bytes(result, context.output_buffer().data(), context.output_buffer().size());
  else {
    std::ios::iostate stream_state = stream.rdstate();
    observer.value(stream_state);
    observer.memory(context.output_buffer());
    observe_result(observer, result);
  }
  return result;
}

template <typename QuotePolicy, typename Rows>
Result verify_write(Context &context, const Rows &rows, TimedObserver &observer) {
  Result first = write<true, QuotePolicy>(context, rows, observer);
  Result second = write<true, QuotePolicy>(context, rows, observer);
  if (first.checksum != second.checksum || first.bytes != second.bytes ||
      first.rows != second.rows || first.cells != second.cells)
    throw std::runtime_error("writer benchmark output is not deterministic");
  return first;
}

template <bool Verify> Result raw_direct(Context &context, Source, TimedObserver &observer) {
  if constexpr (Verify)
    return verify_write<csv2::quote_policy::none>(context, context.decoded_rows(), observer);
  else
    return write<false, csv2::quote_policy::none>(context, context.decoded_rows(), observer);
}
template <bool Verify> Result raw_streamable(Context &context, Source, TimedObserver &observer) {
  if constexpr (Verify)
    return verify_write<csv2::quote_policy::none>(context, context.streamable_rows(), observer);
  else
    return write<false, csv2::quote_policy::none>(context, context.streamable_rows(), observer);
}
template <bool Verify> Result escaped_direct(Context &context, Source, TimedObserver &observer) {
  if constexpr (Verify)
    return verify_write<csv2::quote_policy::minimal>(context, context.decoded_rows(), observer);
  else
    return write<false, csv2::quote_policy::minimal>(context, context.decoded_rows(), observer);
}
template <bool Verify>
Result escaped_streamable(Context &context, Source, TimedObserver &observer) {
  if constexpr (Verify)
    return verify_write<csv2::quote_policy::minimal>(context, context.streamable_rows(), observer);
  else
    return write<false, csv2::quote_policy::minimal>(context, context.streamable_rows(), observer);
}
template <bool Verify> Result always_direct(Context &context, Source, TimedObserver &observer) {
  if constexpr (Verify)
    return verify_write<csv2::quote_policy::always>(context, context.decoded_rows(), observer);
  else
    return write<false, csv2::quote_policy::always>(context, context.decoded_rows(), observer);
}

} // namespace

void register_writer_operations(Registry &registry) {
  const unsigned direct = prepare_reader | prepare_decoded_rows | prepare_output;
  const unsigned streamable = direct | prepare_streamable_rows;
  registry.add("writer/raw-direct", source_buffer, direct, OperationScope::writer_only,
               raw_direct<false>, raw_direct<true>, true);
  registry.add("writer/raw-streamable", source_buffer, streamable, OperationScope::writer_only,
               raw_streamable<false>, raw_streamable<true>);
  registry.add("writer/escaped-direct", source_buffer, direct, OperationScope::writer_only,
               escaped_direct<false>, escaped_direct<true>, true);
  registry.add("writer/escaped-streamable", source_buffer, streamable,
               OperationScope::writer_only, escaped_streamable<false>, escaped_streamable<true>);
  registry.add("writer/always-direct", source_buffer, direct, OperationScope::writer_only,
               always_direct<false>, always_direct<true>, true);
}

} // namespace csv2_benchmark
