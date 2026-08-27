#ifndef CSV2_BENCHMARK_CURRENT_REGISTRY_HPP
#define CSV2_BENCHMARK_CURRENT_REGISTRY_HPP

#include "context.hpp"
#include "support/result.hpp"
#include "support/timed_observer.hpp"

#include <string>
#include <vector>

namespace csv2_benchmark {

using Kernel = Result (*)(Context &, Source, TimedObserver &);
using Preflight = bool (*)(const Context &, Source, std::string &);

inline void observe_result(TimedObserver &observer, Result &result) noexcept {
  observer.value(result.bytes);
  observer.value(result.rows);
  observer.value(result.cells);
}

enum class OperationScope {
  source_only,
  traversal,
  extraction,
  validation,
  conversion,
  ranges,
  index,
  writer_only
};

const char *operation_scope_name(OperationScope scope) noexcept;

struct Operation {
  std::string id;
  std::string semantic_case_id;
  std::string byte_basis;
  unsigned sources;
  unsigned preparations;
  OperationScope scope;
  bool expect_zero_allocations;
  Kernel timed_kernel;
  Kernel verification_kernel;
  Preflight preflight;
};

class Registry {
  std::vector<Operation> operations_;

public:
  void add(const char *id, unsigned sources, unsigned preparations, OperationScope scope,
           Kernel timed_kernel, Kernel verification_kernel, bool expect_zero_allocations = false,
           Preflight preflight = nullptr);
  const std::vector<Operation> &operations() const noexcept { return operations_; }
  const Operation *find(const std::string &id) const noexcept;
};

void register_source_operations(Registry &registry);
void register_traversal_operations(Registry &registry);
void register_extraction_operations(Registry &registry);
void register_validation_operations(Registry &registry);
void register_conversion_operations(Registry &registry);
void register_ranges_operations(Registry &registry);
void register_index_operations(Registry &registry);
void register_writer_operations(Registry &registry);
void register_all_operations(Registry &registry);

bool source_enabled(unsigned mask, Source source) noexcept;

} // namespace csv2_benchmark

#endif
