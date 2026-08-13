#include "registry.hpp"

#include <stdexcept>

namespace csv2_benchmark {

void Registry::add(const char *id, unsigned sources, Kernel timed_kernel,
                   Kernel verification_kernel, bool expect_zero_allocations) {
  if (!id || !*id || !timed_kernel || !verification_kernel || sources == source_none)
    throw std::invalid_argument("invalid benchmark operation registration");
  if (find(id))
    throw std::logic_error(std::string("duplicate benchmark operation: ") + id);
  operations_.push_back(
      Operation{id, sources, expect_zero_allocations, timed_kernel, verification_kernel});
}

const Operation *Registry::find(const std::string &id) const noexcept {
  for (const Operation &operation : operations_) {
    if (operation.id == id)
      return &operation;
  }
  return nullptr;
}

bool source_enabled(unsigned mask, Source source) noexcept {
  const unsigned value = source == Source::file
                             ? source_file
                             : (source == Source::buffer ? source_buffer : source_mmap);
  return (mask & value) != 0;
}

void register_all_operations(Registry &registry) {
  register_source_operations(registry);
  register_traversal_operations(registry);
  register_extraction_operations(registry);
  register_validation_operations(registry);
  register_conversion_operations(registry);
  register_ranges_operations(registry);
  register_index_operations(registry);
  register_writer_operations(registry);
}

} // namespace csv2_benchmark
