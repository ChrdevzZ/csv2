#include "registry.hpp"

#include <stdexcept>

namespace csv2_benchmark {

namespace {

std::string semantic_case_id(const char *id) {
  std::string result("csv2.");
  result += id;
  for (char &character : result) {
    if (character == '/')
      character = '.';
  }
  result += ".v1";
  return result;
}

} // namespace

void Registry::add(const char *id, unsigned sources, unsigned preparations, OperationScope scope,
                   Kernel timed_kernel, Kernel verification_kernel, bool expect_zero_allocations,
                   Preflight preflight) {
  if (!id || !*id || !timed_kernel || !verification_kernel || sources == source_none)
    throw std::invalid_argument("invalid benchmark operation registration");
  if (find(id))
    throw std::logic_error(std::string("duplicate benchmark operation: ") + id);
  operations_.push_back(Operation{id, semantic_case_id(id), "input_corpus", sources, preparations,
                                  scope, expect_zero_allocations, timed_kernel, verification_kernel,
                                  preflight});
}

const char *operation_scope_name(OperationScope scope) noexcept {
  switch (scope) {
  case OperationScope::source_only:
    return "source_only";
  case OperationScope::traversal:
    return "traversal_only";
  case OperationScope::extraction:
    return "extraction_only";
  case OperationScope::validation:
    return "validation_only";
  case OperationScope::conversion:
    return "conversion_only";
  case OperationScope::ranges:
    return "ranges_only";
  case OperationScope::index:
    return "index_only";
  case OperationScope::writer_only:
    return "writer_only";
  }
  return "unknown";
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
