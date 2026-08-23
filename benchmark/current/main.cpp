#include "context.hpp"
#include "registry.hpp"
#include "support/allocation.hpp"

#include <benchmark/benchmark.h>

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <exception>
#include <iostream>
#include <string>

#ifndef CSV2_BENCHMARK_REVISION
#define CSV2_BENCHMARK_REVISION "unstamped"
#endif

namespace csv2_benchmark {
namespace {

bool source_selected(const std::string &selection, Source source) {
  return selection == "all" || selection == source_name(source);
}

std::string safe_component(std::string value) {
  for (char &character : value) {
    const unsigned char byte = static_cast<unsigned char>(character);
    if (!std::isalnum(byte) && character != '-' && character != '_' && character != '.')
      character = '_';
  }
  return value.empty() ? "unnamed" : value;
}

unsigned selected_sources(const Operation &operation, const Options &options) {
  unsigned selected = source_none;
  const Source sources[] = {Source::file, Source::buffer, Source::mmap};
  for (const Source source : sources) {
    if (source_enabled(operation.sources, source) && source_selected(options.source, source))
      selected |= source == Source::file ? source_file
                                         : (source == Source::buffer ? source_buffer : source_mmap);
  }
  return selected;
}

template <typename Function>
std::size_t for_each_selected_source(const Operation &operation, const Options &options,
                                     Function function) {
  std::size_t selected = 0;
  const Source sources[] = {Source::file, Source::buffer, Source::mmap};
  for (const Source source : sources) {
    if (!source_enabled(operation.sources, source) || !source_selected(options.source, source))
      continue;
    ++selected;
    function(source);
  }
  return selected;
}

int list_operations(const Registry &registry, const Options &options) {
  std::size_t selected = 0;
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    selected += for_each_selected_source(operation, options, [&](Source source) {
      std::cout << operation.id << " source=" << source_name(source)
                << " scope=" << operation_scope_name(operation.scope)
                << " semantic_case_id=" << operation.semantic_case_id
                << " byte_basis=" << operation.byte_basis
                << " zero_allocations=" << (operation.expect_zero_allocations ? "true" : "false")
                << '\n';
    });
  }
  if (selected == 0) {
    std::cerr << "no operation/source combination matched the request\n";
    return 2;
  }
  return 0;
}

bool load_selected_context(const Registry &registry, Context &context, const Options &options,
                           std::string &error) {
  unsigned requirements = prepare_none;
  unsigned sources = source_none;
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    const unsigned operation_sources = selected_sources(operation, options);
    if (operation_sources == source_none)
      continue;
    requirements |= operation.preparations;
    sources |= operation_sources;
  }
  if (sources == source_none) {
    error = "no operation/source combination matched the request";
    return false;
  }
  return context.load(options.input, requirements, sources, error);
}

bool preflight_selected_operations(const Registry &registry, const Context &context,
                                   const Options &options, std::string &error) {
  for (const Operation &operation : registry.operations()) {
    if ((!options.operation.empty() && options.operation != operation.id) || !operation.preflight)
      continue;
    bool passed = true;
    for_each_selected_source(operation, options, [&](Source source) {
      if (passed && !operation.preflight(context, source, error))
        passed = false;
    });
    if (!passed) {
      error = operation.id + ": " + error;
      return false;
    }
  }
  return true;
}

int audit_preparation(const Context &context) {
  std::cout << "prepared=" << context.preparation_description()
            << " decoded_rows=" << context.decoded_rows().size()
            << " streamable_rows=" << context.streamable_rows().size()
            << " output_capacity=" << context.output_buffer().capacity() << '\n';
  return 0;
}

int verify_operations(Registry &registry, Context &context, const Options &options) {
  bool selected = false;
  bool allocation_failure = false;
  bool kernel_failure = false;
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    for_each_selected_source(operation, options, [&](Source source) {
      selected = true;
      allocation::reset(true);
      TimedObserver unused_observer;
      Result result = operation.verification_kernel(context, source, unused_observer);
      const allocation::Counts counts = allocation::counts();
      allocation::reset(false);
      result.allocations = counts.allocations;
      result.allocated_bytes = counts.bytes;

      if (!result.ok()) {
        kernel_failure = true;
        std::cerr << "operation=" << operation.id << " source=" << source_name(source)
                  << " kernel_status=" << kernel_status_name(result.status)
                  << " native_error=" << result.native_error << '\n';
        return;
      }

      std::cout << "protocol=csv2-current-v3" << " revision=" << CSV2_BENCHMARK_REVISION
                << " operation=" << operation.id << " source=" << source_name(source)
                << " dataset=" << safe_component(context.dataset_name())
                << " semantic_case_id=" << operation.semantic_case_id
                << " scope=" << operation_scope_name(operation.scope)
                << " byte_basis=" << operation.byte_basis << " checksum=" << result.checksum
                << " bytes=" << result.bytes << " rows=" << result.rows << " cells=" << result.cells
                << " allocations=" << result.allocations
                << " allocated_bytes=" << result.allocated_bytes << '\n';
      if (operation.expect_zero_allocations && result.allocations != 0) {
        allocation_failure = true;
        std::cerr << "operation " << operation.id << " allocated " << result.allocations
                  << " times in its verified execution\n";
      }
    });
  }
  if (!selected) {
    std::cerr << "no operation/source combination matched the request\n";
    return 2;
  }

  return kernel_failure ? 4 : (allocation_failure ? 3 : 0);
}

int audit_observers(Registry &registry, Context &context, const Options &options) {
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
  bool selected = false;
  bool missing_observation = false;
  bool kernel_failure = false;
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    for_each_selected_source(operation, options, [&](Source source) {
      selected = true;
      TimedObserver observer;
      Result result = operation.timed_kernel(context, source, observer);
      if (!result.ok()) {
        kernel_failure = true;
        std::cerr << "operation=" << operation.id << " source=" << source_name(source)
                  << " kernel_status=" << kernel_status_name(result.status)
                  << " native_error=" << result.native_error << '\n';
        return;
      }
      std::cout << "operation=" << operation.id << " source=" << source_name(source)
                << " value_observations=" << observer.value_observations()
                << " memory_observations=" << observer.memory_observations() << '\n';
      benchmark::DoNotOptimize(result.bytes);
      if (observer.value_observations() == 0 && observer.memory_observations() == 0)
        missing_observation = true;
    });
  }
  if (!selected) {
    std::cerr << "no operation/source combination matched the request\n";
    return 2;
  }
  return kernel_failure ? 4 : (missing_observation ? 3 : 0);
#else
  (void)registry;
  (void)context;
  (void)options;
  std::cerr << "observer audit is unavailable in this benchmark build\n";
  return 2;
#endif
}

std::size_t register_timing_benchmarks(Registry &registry, Context &context,
                                       const Options &options) {
  std::size_t selected = 0;
  const std::string dataset = safe_component(context.dataset_name());
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    const Operation *const selected_operation = &operation;
    selected += for_each_selected_source(operation, options, [&](Source source) {
      const std::string name = "csv2/" + operation.id + "/" + source_name(source) + "/" + dataset;
      benchmark::RegisterBenchmark(name, [&context, selected_operation,
                                          source](benchmark::State &state) {
        Result result;
        TimedObserver observer;
        for (auto ignored : state) {
          (void)ignored;
          result = selected_operation->timed_kernel(context, source, observer);
          if (!result.ok()) {
            state.SkipWithError(kernel_status_name(result.status));
            break;
          }
        }
        if (!result.ok())
          return;
        state.SetBytesProcessed(static_cast<std::int64_t>(state.iterations()) *
                                static_cast<std::int64_t>(context.input_size()));
        const std::uint64_t items = result.cells ? result.cells : result.rows;
        state.SetItemsProcessed(static_cast<std::int64_t>(state.iterations()) *
                                static_cast<std::int64_t>(items));
        state.counters["rows/iteration"] = static_cast<double>(result.rows);
        state.counters["cells/iteration"] = static_cast<double>(result.cells);
        state.counters["operation_bytes/iteration"] = static_cast<double>(result.bytes);
      })->UseRealTime();
    });
  }
  return selected;
}

} // namespace
} // namespace csv2_benchmark

int main(int argc, char **argv) {
  using namespace csv2_benchmark;
  try {
    Options options;
    std::string error;
    if (!parse_options(argc, argv, options, error)) {
      std::cerr << error << '\n';
      return 2;
    }

    Registry registry;
    register_all_operations(registry);
    if (!options.operation.empty() && !registry.find(options.operation)) {
      std::cerr << "unknown operation: " << options.operation << '\n';
      return 2;
    }
    if (options.list)
      return list_operations(registry, options);

    const bool batch_mode = options.verify || options.observer_audit || options.preparation_audit;
    if (!batch_mode) {
      if (options.operation.empty()) {
        std::cerr << "timing requires exactly one --csv2-operation\n";
        return 2;
      }
      if (options.source == "all") {
        std::cerr << "timing requires one concrete --csv2-source\n";
        return 2;
      }
    }

    Context context;
    if (!load_selected_context(registry, context, options, error)) {
      std::cerr << error << '\n';
      return 2;
    }
    if (!preflight_selected_operations(registry, context, options, error)) {
      std::cerr << error << '\n';
      return 2;
    }
    if (options.output_capacity_set)
      context.limit_output_capacity_for_test(options.output_capacity);
    context.force_output_stream_failure_for_test(options.force_output_stream_failure);
    if (!options.input_path_after_load.empty())
      context.replace_input_path_for_test(options.input_path_after_load);
    context.force_input_read_failure_for_test(options.force_input_read_failure);
    if (options.verify)
      return verify_operations(registry, context, options);
    if (options.observer_audit)
      return audit_observers(registry, context, options);
    if (options.preparation_audit)
      return audit_preparation(context);

    benchmark::Initialize(&argc, argv);
    if (benchmark::ReportUnrecognizedArguments(argc, argv))
      return 2;
    if (register_timing_benchmarks(registry, context, options) == 0) {
      std::cerr << "no operation/source combination matched the request\n";
      return 2;
    }
#if defined(CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING)
    allocation::MemoryManager memory_manager;
    benchmark::RegisterMemoryManager(&memory_manager);
#endif
    benchmark::RunSpecifiedBenchmarks();
    benchmark::Shutdown();
    return 0;
  } catch (const std::exception &exception) {
    std::cerr << exception.what() << '\n';
    return 2;
  }
}
