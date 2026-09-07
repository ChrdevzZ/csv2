#include "../current/registry.hpp"
#include "../current/support/allocation.hpp"

#include <csv2/writer.hpp>

#include <cstddef>
#include <iostream>
#include <string>

namespace {

template <typename QuotePolicy, typename Rows>
bool check(csv2_benchmark::Context &context, const csv2_benchmark::Operation &operation,
           const Rows &rows, bool allocating = false) {
  using namespace csv2_benchmark;
  TimedObserver observer;
  const auto write_once = [&] {
    csv2::basic_writer<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open,
                       QuotePolicy>
        writer(context.reset_output());
    writer.write_rows(rows);
  };
  // Warm both paths before comparing work; library initialization is not a kernel cost.
  write_once();
  operation.verification_kernel(context, Source::buffer, observer);

  allocation::reset(true);
  write_once();
  const allocation::Counts expected = allocation::counts();
  allocation::reset(false);
  Result output;
  mix_bytes(output, context.output_buffer().data(), context.output_buffer().size());
  const std::size_t output_size = context.output_buffer().size();

  allocation::reset(true);
  const Result actual = operation.verification_kernel(context, Source::buffer, observer);
  const allocation::Counts measured = allocation::counts();
  allocation::reset(false);
  const bool allocation_kind =
      operation.expect_zero_allocations
          ? expected.allocations == 0
          : !allocating || (expected.allocations > 0 && expected.bytes > 0);
  if (!allocation_kind || measured.allocations != expected.allocations ||
      measured.bytes != expected.bytes || !actual.ok() || actual.checksum != output.checksum ||
      actual.bytes != output_size || actual.rows != context.decoded_row_count() ||
      actual.cells != context.decoded_cell_count()) {
    std::cerr << operation.id << ": one write allocations=" << expected.allocations
              << " bytes=" << expected.bytes
              << "; verification allocations=" << measured.allocations
              << " bytes=" << measured.bytes << '\n';
    return false;
  }
  return true;
}

} // namespace

int main(int argc, char **argv) {
  using namespace csv2_benchmark;
  if (argc != 2)
    return 2;
  Context context;
  std::string error;
  if (!context.load(
          argv[1], prepare_reader | prepare_decoded_rows | prepare_streamable_rows | prepare_output,
          source_buffer, error)) {
    std::cerr << error << '\n';
    return 2;
  }
  Registry registry;
  register_writer_operations(registry);
  bool passed = check<csv2::quote_policy::none>(context, *registry.find("writer/raw-direct"),
                                                context.decoded_rows());
  passed &= check<csv2::quote_policy::none>(context, *registry.find("writer/raw-streamable"),
                                            context.streamable_rows());
  passed &= check<csv2::quote_policy::minimal>(context, *registry.find("writer/escaped-direct"),
                                               context.decoded_rows());
  passed &= check<csv2::quote_policy::minimal>(context, *registry.find("writer/escaped-streamable"),
                                               context.streamable_rows(), true);
  passed &= check<csv2::quote_policy::always>(context, *registry.find("writer/always-direct"),
                                              context.decoded_rows());
  return passed ? 0 : 1;
}
