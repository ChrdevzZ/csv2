#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/mio.hpp>
#endif

#include <cstdint>
#include <system_error>
#include <utility>

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
HANDLE closed_handles[4] = {};

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
  for (std::size_t i = 0; i < 4; ++i)
    closed_handles[i] = nullptr;
}

HANDLE test_file_handle() {
  return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(1));
}

HANDLE test_mapping_handle() {
  return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(2));
}

HANDLE test_replacement_file_handle() {
  return reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(3));
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

HANDLE CreateFileMapping(HANDLE, void *, DWORD, DWORD, DWORD, const char *) {
  ++create_mapping_calls;
  last_error = create_mapping_error;
  return create_mapping_result;
}

void *MapViewOfFile(HANDLE, DWORD, DWORD, DWORD, SIZE_T) {
  ++map_view_calls;
  last_error = map_view_error;
  return map_view_result;
}

BOOL CloseHandle(HANDLE handle) {
  if (close_calls < 4)
    closed_handles[close_calls] = handle;
  ++close_calls;
  last_error = close_error;
  return 1;
}

BOOL FlushViewOfFile(const void *, SIZE_T) { return 1; }
BOOL FlushFileBuffers(HANDLE) { return 1; }
BOOL UnmapViewOfFile(const void *) { return 1; }

int main() {
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
  return successful_move_and_failed_remap_preserve_owned_mapping();
}
