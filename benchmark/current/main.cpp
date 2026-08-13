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

template <typename Function>
void for_each_selected_source(const Operation &operation, const Options &options,
                              const Context *context, Function function) {
  const Source sources[] = {Source::file, Source::buffer, Source::mmap};
  for (const Source source : sources) {
    if (!source_enabled(operation.sources, source) || !source_selected(options.source, source))
      continue;
    if (source == Source::mmap && context && !context->mmap_ready())
      continue;
    function(source);
  }
}

int list_operations(const Registry &registry, const Options &options) {
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    for_each_selected_source(operation, options, nullptr, [&](Source source) {
      std::cout << operation.id << " source=" << source_name(source)
                << " zero_allocations=" << (operation.expect_zero_allocations ? "true" : "false")
                << '\n';
    });
  }
  return 0;
}

int verify_operations(Registry &registry, Context &context, const Options &options) {
  bool selected = false;
  bool allocation_failure = false;
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    for_each_selected_source(operation, options, &context, [&](Source source) {
      selected = true;
      allocation::reset(true);
      TimedObserver unused_observer;
      Result result = operation.verification_kernel(context, source, unused_observer);
      const allocation::Counts counts = allocation::counts();
      allocation::reset(false);
      result.allocations = counts.allocations;
      result.allocated_bytes = counts.bytes;

      std::cout << "protocol=csv2-current-v2" << " revision=" << CSV2_BENCHMARK_REVISION
                << " operation=" << operation.id << " source=" << source_name(source)
                << " dataset=" << safe_component(context.dataset_name())
                << " checksum=" << result.checksum << " bytes=" << result.bytes
                << " rows=" << result.rows << " cells=" << result.cells
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

  return allocation_failure ? 3 : 0;
}

int audit_observers(Registry &registry, Context &context, const Options &options) {
#if defined(CSV2_BENCHMARK_OBSERVER_AUDIT)
  bool selected = false;
  bool missing_observation = false;
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    for_each_selected_source(operation, options, &context, [&](Source source) {
      selected = true;
      TimedObserver observer;
      Result result = operation.timed_kernel(context, source, observer);
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
  return missing_observation ? 3 : 0;
#else
  (void)registry;
  (void)context;
  (void)options;
  std::cerr << "observer audit is unavailable in this benchmark build\n";
  return 2;
#endif
}

void register_timing_benchmarks(Registry &registry, Context &context, const Options &options) {
  const std::string dataset = safe_component(context.dataset_name());
  for (const Operation &operation : registry.operations()) {
    if (!options.operation.empty() && options.operation != operation.id)
      continue;
    const Operation *const selected_operation = &operation;
    for_each_selected_source(operation, options, &context, [&](Source source) {
      const std::string name = "csv2/" + operation.id + "/" + source_name(source) + "/" + dataset;
      benchmark::RegisterBenchmark(name, [&context, selected_operation,
                                          source](benchmark::State &state) {
        Result result;
        TimedObserver observer;
        for (auto ignored : state) {
          (void)ignored;
          result = selected_operation->timed_kernel(context, source, observer);
        }
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

    Context context;
    if (!context.load(options.input, error)) {
      std::cerr << error << '\n';
      return 2;
    }
    if (options.source == "mmap" && !context.mmap_ready()) {
      std::cerr << "mmap source is unavailable for this build or input\n";
      return 2;
    }
    if (options.verify)
      return verify_operations(registry, context, options);
    if (options.observer_audit)
      return audit_observers(registry, context, options);

    benchmark::Initialize(&argc, argv);
    if (benchmark::ReportUnrecognizedArguments(argc, argv))
      return 2;
    register_timing_benchmarks(registry, context, options);
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
