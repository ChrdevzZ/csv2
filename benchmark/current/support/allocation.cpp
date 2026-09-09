#include "allocation.hpp"

#include <cstdlib>
#include <limits>
#include <new>

#if defined(_WIN32)
#include <malloc.h>
#endif

namespace csv2_benchmark {
namespace allocation {
namespace {

bool tracking_enabled = false;
Counts tracked = {0, 0};

} // namespace

void reset(bool enabled) noexcept {
  tracked.allocations = 0;
  tracked.bytes = 0;
  tracking_enabled = enabled;
}

Counts counts() noexcept { return tracked; }

void record(std::size_t size) noexcept {
  if (!tracking_enabled)
    return;
  ++tracked.allocations;
  tracked.bytes += static_cast<std::uint64_t>(size);
}

void MemoryManager::Start() { reset(true); }

void MemoryManager::Stop(benchmark::MemoryManager::Result &result) {
  const Counts final_counts = counts();
  reset(false);
  result.num_allocs = static_cast<std::int64_t>(final_counts.allocations);
  result.total_allocated_bytes = static_cast<std::int64_t>(final_counts.bytes);
  result.memory_iterations = 1;
}

} // namespace allocation
} // namespace csv2_benchmark

#if defined(CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING)
void *operator new(std::size_t size) {
  const std::size_t allocation_size = size == 0 ? 1 : size;
  void *const memory = std::malloc(allocation_size);
  if (memory == 0)
    throw std::bad_alloc();
  csv2_benchmark::allocation::record(size);
  return memory;
}

void *operator new[](std::size_t size) {
  const std::size_t allocation_size = size == 0 ? 1 : size;
  void *const memory = std::malloc(allocation_size);
  if (memory == 0)
    throw std::bad_alloc();
  csv2_benchmark::allocation::record(size);
  return memory;
}

void operator delete(void *memory) noexcept { std::free(memory); }
void operator delete[](void *memory) noexcept { std::free(memory); }
void operator delete(void *memory, std::size_t) noexcept { std::free(memory); }
void operator delete[](void *memory, std::size_t) noexcept { std::free(memory); }

#if defined(__cpp_aligned_new) && __cpp_aligned_new >= 201606L
namespace {

void *csv2_allocate_aligned(std::size_t size, std::size_t alignment) {
  const std::size_t allocation_size = size == 0 ? 1 : size;
#if defined(_WIN32)
  return _aligned_malloc(allocation_size, alignment);
#else
  void *memory = 0;
  return ::posix_memalign(&memory, alignment, allocation_size) == 0 ? memory : 0;
#endif
}

void csv2_free_aligned(void *memory) noexcept {
#if defined(_WIN32)
  _aligned_free(memory);
#else
  std::free(memory);
#endif
}

} // namespace

void *operator new(std::size_t size, std::align_val_t alignment) {
  void *const memory = csv2_allocate_aligned(size, static_cast<std::size_t>(alignment));
  if (memory == 0)
    throw std::bad_alloc();
  csv2_benchmark::allocation::record(size);
  return memory;
}

void *operator new[](std::size_t size, std::align_val_t alignment) {
  void *const memory = csv2_allocate_aligned(size, static_cast<std::size_t>(alignment));
  if (memory == 0)
    throw std::bad_alloc();
  csv2_benchmark::allocation::record(size);
  return memory;
}

void operator delete(void *memory, std::align_val_t) noexcept { csv2_free_aligned(memory); }
void operator delete[](void *memory, std::align_val_t) noexcept { csv2_free_aligned(memory); }
void operator delete(void *memory, std::size_t, std::align_val_t) noexcept {
  csv2_free_aligned(memory);
}
void operator delete[](void *memory, std::size_t, std::align_val_t) noexcept {
  csv2_free_aligned(memory);
}
#endif
#endif
