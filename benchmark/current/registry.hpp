#ifndef CSV2_BENCHMARK_CURRENT_REGISTRY_HPP
#define CSV2_BENCHMARK_CURRENT_REGISTRY_HPP

#include "context.hpp"
#include "support/result.hpp"

#include <string>
#include <vector>

namespace csv2_benchmark {

using Kernel = Result (*)(Context &, Source);

enum SourceMask { source_none = 0, source_file = 1, source_buffer = 2, source_mmap = 4 };

struct Operation {
  std::string id;
  unsigned sources;
  bool expect_zero_allocations;
  Kernel timed_kernel;
  Kernel verification_kernel;
};

class Registry {
  std::vector<Operation> operations_;

public:
  void add(const char *id, unsigned sources, Kernel timed_kernel, Kernel verification_kernel,
           bool expect_zero_allocations = false);
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
