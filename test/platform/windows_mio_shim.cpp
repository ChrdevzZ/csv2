
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <limits>
#include <memory>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>

typedef void *HANDLE;
typedef std::uint32_t DWORD;
typedef int BOOL;
typedef std::size_t SIZE_T;

struct LARGE_INTEGER {
  std::int64_t QuadPart;
};

struct SYSTEM_INFO {
  DWORD dwAllocationGranularity;
};

#define INVALID_HANDLE_VALUE reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(-1))
#define GENERIC_READ 0x80000000u
#define GENERIC_WRITE 0x40000000u
#define FILE_SHARE_READ 0x00000001u
#define FILE_SHARE_WRITE 0x00000002u
#define OPEN_EXISTING 3u
#define FILE_ATTRIBUTE_NORMAL 0x00000080u
#define PAGE_READONLY 0x00000002u
#define PAGE_READWRITE 0x00000004u
#define FILE_MAP_READ 0x00000004u
#define FILE_MAP_WRITE 0x00000002u
#define ERROR_ACCESS_DENIED 5u
#define ERROR_NOT_ENOUGH_MEMORY 8u
#define ERROR_FILE_INVALID 1006u

void GetSystemInfo(SYSTEM_INFO *system_info);
DWORD GetLastError();
HANDLE CreateFileA(const char *path, DWORD desired_access, DWORD share_mode,
                   void *security_attributes, DWORD creation_disposition,
                   DWORD flags_and_attributes, HANDLE template_file);
HANDLE CreateFileW(const wchar_t *path, DWORD desired_access, DWORD share_mode,
                   void *security_attributes, DWORD creation_disposition,
                   DWORD flags_and_attributes, HANDLE template_file);
BOOL GetFileSizeEx(HANDLE file, LARGE_INTEGER *file_size);
HANDLE CreateFileMapping(HANDLE file, void *attributes, DWORD protection, DWORD maximum_size_high,
                         DWORD maximum_size_low, const char *name);
void *MapViewOfFile(HANDLE mapping, DWORD desired_access, DWORD offset_high, DWORD offset_low,
                    SIZE_T bytes_to_map);
BOOL CloseHandle(HANDLE handle);
BOOL FlushViewOfFile(const void *base_address, SIZE_T bytes_to_flush);
BOOL FlushFileBuffers(HANDLE file);
BOOL UnmapViewOfFile(const void *base_address);

#if !defined(_WIN32)
#define _WIN32
#define CSV2_TEST_UNDEFINE_WIN32
#endif

#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/mio.hpp>
#endif

#if defined(CSV2_TEST_UNDEFINE_WIN32)
#undef _WIN32
#undef CSV2_TEST_UNDEFINE_WIN32
#endif

namespace {

DWORD last_error = 0;
HANDLE open_file_result = INVALID_HANDLE_VALUE;
DWORD open_file_error = 0;
BOOL query_size_result = 0;
DWORD query_size_error = 0;
std::int64_t query_size = 0;
HANDLE create_mapping_result = nullptr;
DWORD create_mapping_error = 0;
void *map_view_result = nullptr;
DWORD map_view_error = 0;
DWORD close_error = 0;
int map_view_calls = 0;
int create_mapping_calls = 0;
int close_calls = 0;
int flush_view_calls = 0;
int flush_file_calls = 0;
DWORD create_mapping_size_high = 0;
DWORD create_mapping_size_low = 0;
DWORD map_view_offset_high = 0;
DWORD map_view_offset_low = 0;
SIZE_T map_view_length = 0;
HANDLE closed_handles[8] = {};

void reset_scenario() {
  last_error = 0;
  open_file_result = INVALID_HANDLE_VALUE;
  open_file_error = 0;
  query_size_result = 0;
  query_size_error = 0;
  query_size = 0;
  create_mapping_result = nullptr;
  create_mapping_error = 0;
  map_view_result = nullptr;
  map_view_error = 0;
  close_error = 0;
  map_view_calls = 0;
  create_mapping_calls = 0;
  close_calls = 0;
  flush_view_calls = 0;
  flush_file_calls = 0;
  create_mapping_size_high = 0;
  create_mapping_size_low = 0;
  map_view_offset_high = 0;
  map_view_offset_low = 0;
  map_view_length = 0;
  for (std::size_t i = 0; i < 8; ++i)
    closed_handles[i] = nullptr;
}

HANDLE test_file_handle() { return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(1)); }

HANDLE test_mapping_handle() { return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(2)); }

HANDLE test_replacement_file_handle() {
  return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(3));
}

HANDLE test_replacement_mapping_handle() {
  return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(4));
}

HANDLE test_final_mapping_handle() {
  return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(5));
}

int size_query_failure_releases_file_handle() {
  reset_scenario();
  open_file_result = test_file_handle();
  query_size_error = ERROR_ACCESS_DENIED;

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map("file.csv", error);

  if (error.value() != ERROR_ACCESS_DENIED)
    return 1;
  if (close_calls != 1 || closed_handles[0] != test_file_handle())
    return 2;
  return 0;
}

int open_failure_preserves_error_without_closing_invalid_handle() {
  reset_scenario();
  open_file_error = ERROR_ACCESS_DENIED;

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map("missing.csv", error);

  if (error.value() != ERROR_ACCESS_DENIED)
    return 29;
  if (close_calls != 0 || create_mapping_calls != 0 || map_view_calls != 0)
    return 30;
  return 0;
}

int invalid_file_size_is_rejected_and_releases_file_handle() {
  reset_scenario();
  open_file_result = test_file_handle();
  query_size_result = 1;
  query_size = -1;

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map("file.csv", error);

  if (error != std::errc::value_too_large)
    return 3;
  if (create_mapping_calls != 0)
    return 4;
  if (close_calls != 1 || closed_handles[0] != test_file_handle())
    return 5;
  return 0;
}

int creation_failure_releases_file_handle_without_followup_calls() {
  reset_scenario();
  open_file_result = test_file_handle();
  query_size_result = 1;
  query_size = 1;
  create_mapping_error = ERROR_FILE_INVALID;

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map("file.csv", error);

  if (error.value() != ERROR_FILE_INVALID)
    return 6;
  if (map_view_calls != 0)
    return 7;
  if (close_calls != 1 || closed_handles[0] != test_file_handle())
    return 8;
  return 0;
}

int view_failure_preserves_error_and_releases_both_handles() {
  reset_scenario();
  open_file_result = test_file_handle();
  query_size_result = 1;
  query_size = 1;
  create_mapping_result = test_mapping_handle();
  map_view_error = ERROR_NOT_ENOUGH_MEMORY;
  close_error = ERROR_ACCESS_DENIED;

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map("file.csv", error);

  if (error.value() != ERROR_NOT_ENOUGH_MEMORY)
    return 9;
  if (map_view_calls != 1)
    return 10;
  if (close_calls != 2 || closed_handles[0] != test_mapping_handle() ||
      closed_handles[1] != test_file_handle())
    return 11;
  return 0;
}

int successful_move_and_failed_remap_preserve_owned_mapping() {
  reset_scenario();
  char mapped_byte = 'x';
  open_file_result = test_file_handle();
  query_size_result = 1;
  query_size = 1;
  create_mapping_result = test_mapping_handle();
  map_view_result = &mapped_byte;

  std::error_code error;
  {
    mio::mmap_source source;
    source.map("file.csv", error);
    if (error || !source.is_open() || !source.is_mapped())
      return 12;

    mio::mmap_source moved(std::move(source));
    if (source.is_open() || source.is_mapped() || !moved.is_mapped() ||
        moved.mapping_handle() != test_mapping_handle())
      return 13;

    open_file_result = test_replacement_file_handle();
    create_mapping_result = nullptr;
    create_mapping_error = ERROR_FILE_INVALID;
    moved.map("replacement.csv", error);
    if (error.value() != ERROR_FILE_INVALID)
      return 14;
    if (!moved.is_mapped() || moved.mapping_handle() != test_mapping_handle() ||
        moved.data() != &mapped_byte)
      return 15;
    if (close_calls != 1 || closed_handles[0] != test_replacement_file_handle())
      return 16;
  }

  if (close_calls != 3 || closed_handles[1] != test_mapping_handle() ||
      closed_handles[2] != test_file_handle())
    return 17;
  return 0;
}

int own_handle_remap_preserves_file_handle_and_strong_guarantee() {
  reset_scenario();
  char mapped_bytes[8] = {};
  open_file_result = test_file_handle();
  query_size_result = 1;
  query_size = 8;
  create_mapping_result = test_mapping_handle();
  map_view_result = mapped_bytes;

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map("file.csv", error);
  if (error || mapping.file_handle() != test_file_handle())
    return 18;

  const HANDLE owned_file_handle = mapping.file_handle();
  create_mapping_result = test_replacement_mapping_handle();
  mapping.map(owned_file_handle, 1, 1, error);
  if (error || mapping.file_handle() != owned_file_handle || mapping.data() != mapped_bytes + 1)
    return 19;
  if (close_calls != 1 || closed_handles[0] != test_mapping_handle())
    return 20;

  create_mapping_result = nullptr;
  create_mapping_error = ERROR_NOT_ENOUGH_MEMORY;
  mapping.map(owned_file_handle, 2, 1, error);
  if (error.value() != ERROR_NOT_ENOUGH_MEMORY ||
      mapping.mapping_handle() != test_replacement_mapping_handle() ||
      mapping.data() != mapped_bytes + 1)
    return 21;
  if (close_calls != 1)
    return 22;

  create_mapping_result = test_final_mapping_handle();
  create_mapping_error = 0;
  mapping.map(owned_file_handle, 2, 1, error);
  if (error || mapping.file_handle() != owned_file_handle || mapping.data() != mapped_bytes + 2)
    return 23;
  if (close_calls != 2 || closed_handles[1] != test_replacement_mapping_handle())
    return 24;

  mapping.unmap();
  if (close_calls != 4 || closed_handles[2] != test_final_mapping_handle() ||
      closed_handles[3] != owned_file_handle)
    return 25;
  return 0;
}

int writable_sync_flushes_view_and_file_once() {
  reset_scenario();
  char mapped_byte = 'x';
  open_file_result = test_file_handle();
  query_size_result = 1;
  query_size = 1;
  create_mapping_result = test_mapping_handle();
  map_view_result = &mapped_byte;

  std::error_code error;
  mio::mmap_sink mapping;
  mapping.map("file.csv", error);
  if (error)
    return 26;

  mapping.sync(error);
  if (error)
    return 27;
  if (flush_view_calls != 1 || flush_file_calls != 1)
    return 28;

  mapping.unmap();
  return 0;
}

int non_aligned_offset_uses_aligned_view_and_exact_lengths() {
  reset_scenario();
  char mapped_bytes[4] = {'a', 'b', 'c', 'd'};
  query_size_result = 1;
  query_size = 8192;
  create_mapping_result = test_mapping_handle();
  map_view_result = mapped_bytes;

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map(test_file_handle(), 4097, 2, error);
  if (error || mapping.data() != mapped_bytes + 1 || mapping.size() != 2 ||
      mapping.mapping_offset() != 1 || mapping.mapped_length() != 3)
    return 31;
  if (create_mapping_size_high != 0 || create_mapping_size_low != 4099)
    return 32;
  if (map_view_offset_high != 0 || map_view_offset_low != 4096 || map_view_length != 3)
    return 33;
  mapping.unmap();
  if (close_calls != 1 || closed_handles[0] != test_mapping_handle())
    return 34;
  return 0;
}

} // namespace

void GetSystemInfo(SYSTEM_INFO *system_info) { system_info->dwAllocationGranularity = 4096; }

DWORD GetLastError() { return last_error; }

HANDLE CreateFileA(const char *, DWORD, DWORD, void *, DWORD, DWORD, HANDLE) {
  last_error = open_file_error;
  return open_file_result;
}

HANDLE CreateFileW(const wchar_t *, DWORD, DWORD, void *, DWORD, DWORD, HANDLE) {
  last_error = open_file_error;
  return open_file_result;
}

BOOL GetFileSizeEx(HANDLE, LARGE_INTEGER *file_size) {
  last_error = query_size_error;
  if (query_size_result)
    file_size->QuadPart = query_size;
  return query_size_result;
}

HANDLE CreateFileMapping(HANDLE, void *, DWORD, DWORD maximum_size_high, DWORD maximum_size_low,
                         const char *) {
  ++create_mapping_calls;
  create_mapping_size_high = maximum_size_high;
  create_mapping_size_low = maximum_size_low;
  last_error = create_mapping_error;
  return create_mapping_result;
}

void *MapViewOfFile(HANDLE, DWORD, DWORD offset_high, DWORD offset_low, SIZE_T bytes_to_map) {
  ++map_view_calls;
  map_view_offset_high = offset_high;
  map_view_offset_low = offset_low;
  map_view_length = bytes_to_map;
  last_error = map_view_error;
  return map_view_result;
}

BOOL CloseHandle(HANDLE handle) {
  if (close_calls < 8)
    closed_handles[close_calls] = handle;
  ++close_calls;
  last_error = close_error;
  return 1;
}

BOOL FlushViewOfFile(const void *, SIZE_T) {
  ++flush_view_calls;
  return 1;
}
BOOL FlushFileBuffers(HANDLE) {
  ++flush_file_calls;
  return 1;
}
BOOL UnmapViewOfFile(const void *) { return 1; }

int main() {
  const int open_failure = open_failure_preserves_error_without_closing_invalid_handle();
  if (open_failure != 0)
    return open_failure;
  const int size_failure = size_query_failure_releases_file_handle();
  if (size_failure != 0)
    return size_failure;
  const int invalid_size = invalid_file_size_is_rejected_and_releases_file_handle();
  if (invalid_size != 0)
    return invalid_size;
  const int creation_failure = creation_failure_releases_file_handle_without_followup_calls();
  if (creation_failure != 0)
    return creation_failure;
  const int view_failure = view_failure_preserves_error_and_releases_both_handles();
  if (view_failure != 0)
    return view_failure;
  const int move_and_failed_remap = successful_move_and_failed_remap_preserve_owned_mapping();
  if (move_and_failed_remap != 0)
    return move_and_failed_remap;
  const int own_handle_remap = own_handle_remap_preserves_file_handle_and_strong_guarantee();
  if (own_handle_remap != 0)
    return own_handle_remap;
  const int writable_sync = writable_sync_flushes_view_and_file_once();
  if (writable_sync != 0)
    return writable_sync;
  return non_aligned_offset_uses_aligned_view_and_exact_lengths();
}
