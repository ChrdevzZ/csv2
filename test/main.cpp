#if defined(CSV2_TEST_WINDOWS_API)

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

#elif defined(CSV2_TEST_HEADER_ONLY)

#if defined(CSV2_TEST_HEADER_MIO)
#include <csv2/mio.hpp>
#elif defined(CSV2_TEST_HEADER_PARAMETERS)
#include <csv2/parameters.hpp>
#elif defined(CSV2_TEST_HEADER_ERRORS)
#include <csv2/errors.hpp>
#elif defined(CSV2_TEST_HEADER_READER)
#include <csv2/reader.hpp>
#elif defined(CSV2_TEST_HEADER_WRITER)
#include <csv2/writer.hpp>
#elif defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#error "A public header must be selected for the self-containment test"
#endif

#if defined(CSV2_EXPECT_NO_MIO) && CSV2_HAS_MMAP
#error "CSV2_HAS_MMAP must remain disabled"
#endif

#if defined(CSV2_EXPECT_NO_MIO) && defined(MIO_MMAP_HEADER)
#error "mio must not be included when CSV2_HAS_MMAP is disabled"
#endif

static_assert(true, "compiling this translation unit is the assertion");

#else

#if defined(CSV2_TEST_NO_EXCEPTIONS) &&                                                            \
    (defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND))
#error "The no-exceptions test must be compiled with exception handling disabled"
#endif

#include "doctest.hpp"

#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#endif

#if defined(CSV2_TEST_NO_MMAP) && CSV2_HAS_MMAP
#error "CSV2_HAS_MMAP must remain disabled"
#endif

#if defined(CSV2_TEST_NO_MMAP) && defined(MIO_MMAP_HEADER)
#error "mio must not be included when CSV2_HAS_MMAP is disabled"
#endif

#include <algorithm>
#include <cstddef>
#include <cstdio>
#include <deque>
#include <exception>
#include <forward_list>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <limits>
#include <list>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>
#include <vector>

#if CSV2_HAS_MEMORY_RESOURCE
#include <memory_resource>
#endif

#if CSV2_HAS_FILESYSTEM
#include <filesystem>
#endif

#if CSV2_HAS_RANGES
#include <concepts>
#include <ranges>
#endif

#if CSV2_HAS_SPAN
#include <span>
#endif

#if defined(__linux__)
#include <dirent.h>
#elif defined(_WIN32)
#include <windows.h>
#endif

#if CSV2_HAS_MMAP && (defined(__unix__) || defined(__APPLE__))
#include <cerrno>
#include <fcntl.h>
#endif

using doctest::test_suite;

namespace {

using ReaderWithoutHeader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                         csv2::first_row_is_header<false>>;
using ReaderWithHeader =
    csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>, csv2::first_row_is_header<true>>;
using PublicRow = csv2::basic_row<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::trim_policy::trim_whitespace>;
using PublicCell = csv2::basic_cell<csv2::quote_character<'"'>, csv2::trim_policy::trim_whitespace>;
static_assert(std::is_base_of<PublicRow, ReaderWithoutHeader::Row>::value,
              "Reader::Row must reuse the namespace-scope implementation");
static_assert(std::is_base_of<PublicCell, ReaderWithoutHeader::Cell>::value,
              "Reader::Cell must reuse the namespace-scope implementation");
static_assert(sizeof(ReaderWithoutHeader::Row) == sizeof(PublicRow),
              "the nested Row facade must add no per-row state");
static_assert(sizeof(ReaderWithoutHeader::Cell) == sizeof(PublicCell),
              "the nested Cell facade must add no per-cell state");
static_assert(!std::is_same<ReaderWithoutHeader::Row, ReaderWithHeader::Row>::value,
              "Reader specializations must retain distinct nested Row types");
static_assert(!std::is_same<ReaderWithoutHeader::Cell, ReaderWithHeader::Cell>::value,
              "Reader specializations must retain distinct nested Cell types");
static_assert(std::is_same<decltype(std::declval<const ReaderWithoutHeader::RowIndex &>()[0]),
                           ReaderWithoutHeader::Row>::value,
              "Reader::RowIndex must return the corresponding nested Row type");
static_assert(sizeof(ReaderWithoutHeader::RowIterator) <= 5 * sizeof(void *),
              "RowIterator must remain a five-word cursor");
static_assert(sizeof(PublicRow::CellIterator) <= 5 * sizeof(void *),
              "CellIterator must not retain redundant range state");
#if defined(__cpp_char8_t)
static_assert(!csv2::detail::is_csv_integer<char8_t>::value,
              "character types must not use integer conversion");
#endif

#if CSV2_HAS_RANGES
using ConceptRowIterator = decltype(std::declval<ReaderWithoutHeader &>().begin());
using ConceptRow = decltype(*std::declval<ConceptRowIterator &>());
using ConceptCellIterator = decltype(std::declval<ConceptRow &>().begin());
static_assert(std::input_iterator<ConceptRowIterator>);
static_assert(std::forward_iterator<ConceptRowIterator>);
static_assert(std::input_iterator<ConceptCellIterator>);
static_assert(std::forward_iterator<ConceptCellIterator>);
static_assert(std::ranges::forward_range<ReaderWithoutHeader>);
static_assert(std::ranges::forward_range<ConceptRow>);
static_assert(std::ranges::view<ConceptRow>);
static_assert(std::ranges::borrowed_range<ConceptRow>);
static_assert(!std::ranges::borrowed_range<ReaderWithoutHeader>);
#endif

template <typename RowType> std::vector<std::string> read_cells(const RowType &row) {
  std::vector<std::string> result;
  for (const auto cell : row) {
    std::string value;
    cell.read_value(value);
    result.push_back(value);
  }
  return result;
}

template <typename ReaderType>
std::vector<std::vector<std::string>> read_rows(const ReaderType &reader) {
  std::vector<std::vector<std::string>> result;
  for (const auto row : reader)
    result.push_back(read_cells(row));
  return result;
}

struct StringLikeView {
  StringLikeView(const char *data, std::size_t size) : data(data), size_in_bytes(size) {}

  const char *c_str() const { return data; }
  std::size_t size() const { return size_in_bytes; }

  const char *data;
  std::size_t size_in_bytes;
};

struct SequencedStringLikeView {
  explicit SequencedStringLikeView(const std::string &value)
      : value(value), data_observed(false), sequence_valid(true) {}

  const char *c_str() const {
    data_observed = true;
    return value.c_str();
  }
  std::size_t size() const {
    if (!data_observed)
      sequence_valid = false;
    return value.size();
  }

  const std::string &value;
  mutable bool data_observed;
  mutable bool sequence_valid;
};

struct LazyAddressStringLikeView {
  explicit LazyAddressStringLikeView(std::string value) : value(std::move(value)) {}

  const char *c_str() const {
    if (storage.empty())
      storage = value;
    return storage.c_str();
  }
  std::size_t size() const { return value.size(); }

  std::string value;
  mutable std::string storage;
};

struct SequencedOwnedStringLike {
  SequencedOwnedStringLike(std::string value, bool &sequence_valid)
      : value(std::move(value)), sequence_valid(&sequence_valid), data_observed(false) {}

  const char *c_str() const {
    storage = value;
    data_observed = true;
    return storage.c_str();
  }
  std::size_t size() const {
    if (!data_observed) {
      *sequence_valid = false;
      return 0;
    }
    return storage.size();
  }

  std::string value;
  bool *sequence_valid;
  mutable bool data_observed;
  mutable std::string storage;
};

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
struct ThrowingOwnedStringLike {
  const char *c_str() const { throw std::runtime_error("materialization failure"); }
  std::size_t size() const { return 3; }
};

volatile std::size_t oversized_owned_string_size = (std::numeric_limits<std::size_t>::max)();

struct OversizedOwnedStringLike {
  const char *c_str() const { return "x"; }
  std::size_t size() const { return oversized_owned_string_size; }
};
#endif

class LvalueCloseStream : public std::ostringstream {
public:
  LvalueCloseStream() : closed(false) {}

  void close() & { closed = true; }

  bool closed;
};

struct AbsoluteOffsetTrim {
  static const char *expected_buffer;

  static std::pair<std::size_t, std::size_t> trim(const char *buffer, std::size_t start,
                                                  std::size_t end) {
    if (buffer == expected_buffer && start == 2 && start < end)
      ++start;
    return std::make_pair(start, end);
  }
};

const char *AbsoluteOffsetTrim::expected_buffer = nullptr;

struct ContextTrim {
  static std::pair<std::size_t, std::size_t> trim(const char *buffer, std::size_t start,
                                                  std::size_t end) {
    while (start < end && buffer[start] == '~' && start + 1 < end && buffer[start + 1] == '~')
      start += 2;
    while (start < end && buffer[end - 1] == '~' && start + 1 < end && buffer[end - 2] == '~')
      end -= 2;
    return std::make_pair(start, end);
  }
};

struct SingleByteOnlyTrim {
  static std::pair<std::size_t, std::size_t> trim(const char *, std::size_t start,
                                                  std::size_t end) {
    if (end - start == 1)
      return std::make_pair(end, end);
    return std::make_pair(start, end);
  }
};

#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
struct ThrowingTrim {
  static volatile bool enabled;

  static std::pair<std::size_t, std::size_t> trim(const char *, std::size_t start,
                                                  std::size_t end) {
    if (enabled)
      throw std::runtime_error("trim failure");
    return std::make_pair(start, end);
  }
};

volatile bool ThrowingTrim::enabled = true;
#endif

class CountingCloseStream : public std::ostringstream {
public:
  void close() { ++close_count; }

  int close_count{0};
};

class DirectWriteTrackingStream : public std::ostringstream {
public:
  DirectWriteTrackingStream &write(const char *data, std::streamsize size) {
    ++write_calls;
    std::ostringstream::write(data, size);
    return *this;
  }

  std::size_t write_calls{0};
};

class MinimalWriteStream {
public:
  MinimalWriteStream &write(const char *data, std::streamsize size) {
    value.append(data, static_cast<std::size_t>(size));
    return *this;
  }

  MinimalWriteStream &operator<<(char character) {
    value.push_back(character);
    return *this;
  }

  std::string value;
};

class DecoratingStringStream {
public:
  DecoratingStringStream &write(const char *data, std::streamsize size) {
    value.append(data, static_cast<std::size_t>(size));
    return *this;
  }

  DecoratingStringStream &operator<<(char character) {
    value.push_back(character);
    return *this;
  }

  DecoratingStringStream &operator<<(const std::string &field) {
    value += '<';
    value += field;
    value += '>';
    return *this;
  }

#if CSV2_HAS_STRING_VIEW
  DecoratingStringStream &operator<<(std::string_view field) {
    value += '[';
    value.append(field.data(), field.size());
    value += ']';
    return *this;
  }
#endif

  std::string value;
};

class ChainedInsertionStream {
public:
  class Proxy {
  public:
    explicit Proxy(ChainedInsertionStream &stream) : stream_(stream) {}
    Proxy &operator<<(const std::string &field) {
      stream_.value += "P{" + field + '}';
      return *this;
    }

  private:
    ChainedInsertionStream &stream_;
  };

  ChainedInsertionStream &operator<<(const std::string &field) {
    value += "S{" + field + '}';
    return *this;
  }
  Proxy operator<<(char character) {
    value.push_back(character);
    return Proxy(*this);
  }

  std::string value;
};

class ConstSelectingRow {
public:
  ConstSelectingRow() : mutable_field_("mutable"), const_field_("const") {}

  std::string *begin() { return &mutable_field_; }
  std::string *end() { return &mutable_field_ + 1; }
  const std::string *begin() const { return &const_field_; }
  const std::string *end() const { return &const_field_ + 1; }

private:
  std::string mutable_field_;
  std::string const_field_;
};

struct CommaFormattedValue {
  int left;
  int right;
};

std::ostream &operator<<(std::ostream &stream, const CommaFormattedValue &value) {
  return stream << value.left << ',' << value.right;
}

struct StatefulFormattedValue {
  explicit StatefulFormattedValue(std::ios_base::iostate state) : state(state) {}

  std::ios_base::iostate state;
};

std::ostream &operator<<(std::ostream &stream, const StatefulFormattedValue &value) {
  stream.write("a,b", 3);
  stream.setstate(value.state);
  return stream;
}

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
struct WriterUserError {};

struct ConsumingThrowValue {};

std::ostream &operator<<(std::ostream &stream, const ConsumingThrowValue &) {
  stream << "x";
  throw WriterUserError();
}

struct UnformattedThrowValue {};

std::ostream &operator<<(std::ostream &stream, const UnformattedThrowValue &) {
  stream.write("x", 1);
  throw WriterUserError();
}

struct StatefulThrowValue {};

std::ostream &operator<<(std::ostream &stream, const StatefulThrowValue &) {
  stream.write("x", 1);
  stream.setstate(std::ios_base::failbit);
  throw WriterUserError();
}
#endif

struct FormattedContiguousValue {
  const char *data() const { return "raw"; }
  std::size_t size() const { return 3; }
};

std::ostream &operator<<(std::ostream &stream, const FormattedContiguousValue &) {
  return stream << "[formatted]";
}

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
struct CloseError {};

class ThrowingCloseStream : public std::ostringstream {
public:
  void close() {
    ++close_count;
    throw CloseError();
  }

  int close_count{0};
};
#endif

class ReserveTrackingBuffer {
public:
  explicit ReserveTrackingBuffer(const char *prefix) : value(prefix) {}

  std::size_t size() const { return value.size(); }
  void reserve(std::size_t requested) {
    last_reserve = requested;
    value.reserve(requested);
  }
  void push_back(char character) { value.push_back(character); }

  std::string value;
  std::size_t last_reserve{0};
};

class ReserveOnlyBuffer {
public:
  explicit ReserveOnlyBuffer(const char *prefix) : value(prefix) {}

  void reserve(std::size_t requested) {
    last_reserve = requested;
    value.reserve(requested);
  }
  void push_back(char character) { value.push_back(character); }

  std::string value;
  std::size_t last_reserve{0};
};

class AppendOnlyBuffer {
public:
  void append(const char *data, std::size_t size) { value.append(data, size); }

  std::string value;
};

class AppendCountingBuffer {
public:
  void append(const char *data, std::size_t size) {
    ++append_calls;
    value.append(data, size);
  }

  std::string value;
  std::size_t append_calls{0};
};

class RejectZeroReserveBuffer {
public:
  void reserve(std::size_t) { reserve_called = true; }
  void push_back(char character) { value.push_back(character); }

  std::string value;
  bool reserve_called{false};
};

#if CSV2_HAS_MMAP && (defined(__linux__) || defined(_WIN32))
std::size_t process_handle_count() {
#if defined(_WIN32)
  DWORD count = 0;
  if (!::GetProcessHandleCount(::GetCurrentProcess(), &count))
    return (std::numeric_limits<std::size_t>::max)();
  return static_cast<std::size_t>(count);
#else
  DIR *directory = ::opendir("/proc/self/fd");
  if (!directory)
    return (std::numeric_limits<std::size_t>::max)();

  std::size_t count = 0;
  while (::readdir(directory))
    ++count;
  ::closedir(directory);
  return count;
#endif
}
#endif

const char *writer_output_path() {
#if defined(CSV2_TEST_WRITER_OUTPUT)
  return CSV2_TEST_WRITER_OUTPUT;
#elif defined(CSV2_TEST_SINGLE_HEADER)
  return "csv2-single-header-writer-output.csv";
#else
  return "csv2-module-writer-output.csv";
#endif
}

class ScopedFileRemoval {
public:
  explicit ScopedFileRemoval(std::string path) : path_(std::move(path)) {}
  ~ScopedFileRemoval() { std::remove(path_.c_str()); }

private:
  std::string path_;
};

#if CSV2_HAS_MMAP
void write_binary_file(const std::string &path, const std::string &contents) {
  std::ofstream output(path.c_str(), std::ios::binary | std::ios::trunc);
  REQUIRE(output.is_open());
  output.write(contents.data(), static_cast<std::streamsize>(contents.size()));
  REQUIRE(output.good());
}
#endif

} // namespace

#if CSV2_HAS_MMAP
TEST_CASE("Read a file, its header, rows, columns, and cells" * test_suite("Reader")) {
  ReaderWithHeader reader;
  REQUIRE(reader.mmap("inputs/test_01.csv"));

  REQUIRE(read_cells(reader.header()) == std::vector<std::string>({"a", "b", "c"}));
  REQUIRE(reader.cols() == 3);
  REQUIRE(reader.rows() == 2);
  REQUIRE(read_rows(reader) ==
          std::vector<std::vector<std::string>>({{"1", "2", "3"}, {"4", "5", "6"}}));
}
#endif

TEST_CASE("Honor delimiter, quote, and trim policies" * test_suite("Reader")) {
  using TrimmedReader =
      csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'\''>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_whitespace>;
  TrimmedReader trimmed;
  std::string trimmed_input(" a | 'b|c' | 'd''e' ");
  REQUIRE(trimmed.parse(trimmed_input));
  REQUIRE(read_cells(*trimmed.begin()) == std::vector<std::string>({"a", "'b|c'", "'d'e'"}));

  using UntrimmedReader =
      csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'\''>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::no_trimming>;
  UntrimmedReader untrimmed;
  std::string untrimmed_input(" a | b ");
  REQUIRE(untrimmed.parse(untrimmed_input));
  REQUIRE(read_cells(*untrimmed.begin()) == std::vector<std::string>({" a ", " b "}));
}

TEST_CASE("Preserve original cell bounds for custom trim policies" * test_suite("Reader")) {
  using AbsoluteTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                          csv2::first_row_is_header<false>, AbsoluteOffsetTrim>;
  AbsoluteTrimReader reader;
  std::string input("a,xb");
  AbsoluteOffsetTrim::expected_buffer = input.data();
  REQUIRE(reader.parse(input));
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"a", "b"}));
}

TEST_CASE("Evaluate borrowed string address before its extent" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  const std::string input("a,b");
  SequencedStringLikeView view(input);
  REQUIRE(reader.parse(view));
  REQUIRE(view.sequence_valid);
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"a", "b"}));

  LazyAddressStringLikeView lazy("c,d");
  REQUIRE(reader.parse(lazy));
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));
}

TEST_CASE("Materialize an owned string address before its extent" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  bool sequence_valid = true;
  REQUIRE(reader.parse(SequencedOwnedStringLike("c,d", sequence_valid)));
  REQUIRE(sequence_valid);
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
  REQUIRE_THROWS_AS(reader.parse(ThrowingOwnedStringLike()), std::runtime_error);
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));

  REQUIRE_THROWS(reader.parse(OversizedOwnedStringLike()));
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));
#endif
}

TEST_CASE("Use a custom trim policy on complete field bounds" * test_suite("Reader")) {
  using ContextTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                         csv2::first_row_is_header<false>, ContextTrim>;
  ContextTrimReader reader;
  std::string input("~~\"a\"~~,~~b~~");
  REQUIRE(reader.parse(input));
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"\"a\"", "b"}));

  csv2::parse_error error;
  REQUIRE(reader.validate(error));
}

TEST_CASE("Do not validate a suffix using a different trim context" * test_suite("Reader")) {
  using SingleByteTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                            csv2::first_row_is_header<false>, SingleByteOnlyTrim>;
  SingleByteTrimReader reader;
  std::string input("\"a\"x");
  REQUIRE(reader.parse(input));
  csv2::parse_error error;
  REQUIRE_FALSE(reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  REQUIRE(error.byte_offset == 3);
}

TEST_CASE("Preserve quote structure when the trim policy includes quotes" * test_suite("Reader")) {
  using QuoteTrimReader =
      csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_characters<'"'>>;
  using MixedTrimReader =
      csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_characters<' ', '"'>>;

  SUBCASE("A lone opening quote remains visible") {
    QuoteTrimReader reader;
    std::string input("\"");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::unclosed_quote);
    REQUIRE(error.byte_offset == 0);
    REQUIRE(error.row == 1);
    REQUIRE(error.column == 1);
  }

  SUBCASE("A quoted empty field remains valid") {
    QuoteTrimReader reader;
    std::string input("\"\"");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE(reader.validate(error));
  }

  SUBCASE("A quoted value remains valid") {
    QuoteTrimReader reader;
    std::string input("\"a\"");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE(reader.validate(error));
  }

  SUBCASE("A trailing quote in an unquoted field remains visible") {
    QuoteTrimReader reader;
    std::string input("a\"");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
    REQUIRE(error.byte_offset == 1);
  }

  SUBCASE("Non-structural trim bytes can still surround a quoted field") {
    MixedTrimReader reader;
    std::string input("  \"a\"  ");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE(reader.validate(error));
  }
}

TEST_CASE("Preserve structural diagnostics after a quoted-field suffix" * test_suite("Reader")) {
  using TrimmedReader =
      csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_whitespace>;

  SUBCASE("A bare carriage return follows trimmable bytes") {
    TrimmedReader reader;
    std::string input("\"a\" \r");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
    REQUIRE(error.byte_offset == 4);
    REQUIRE(error.row == 1);
    REQUIRE(error.column == 1);
  }

  SUBCASE("A quote follows trimmable bytes") {
    TrimmedReader reader;
    std::string input("\"a\"  \"b\"");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::invalid_doubled_quote);
    REQUIRE(error.byte_offset == 5);
  }

  SUBCASE("Ordinary content follows trimmable bytes") {
    TrimmedReader reader;
    std::string input("\"a\"  x");
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
    REQUIRE(error.byte_offset == 5);
  }
}

#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
TEST_CASE("Propagate exceptions from a user trim policy" * test_suite("Reader")) {
  using ThrowingTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                          csv2::first_row_is_header<false>, ThrowingTrim>;
  ThrowingTrimReader reader;
  std::string input("value");
  REQUIRE(reader.parse(input));

  std::string value;
  REQUIRE_THROWS_AS(reader.begin()->begin()->read_value(value), std::runtime_error);
  csv2::parse_error error;
  REQUIRE_THROWS_AS(reader.validate(error), std::runtime_error);
#if CSV2_HAS_EXPECTED
  REQUIRE_THROWS_AS(static_cast<void>(reader.begin()->begin()->parse_expected<int>()),
                    std::runtime_error);
  REQUIRE_THROWS_AS(static_cast<void>(reader.validate_expected()), std::runtime_error);
#endif
}
#endif

TEST_CASE("Keep shared delimiter and quote semantics stable across the scanner threshold" *
          test_suite("Reader")) {
  using SharedDelimiterQuoteReader = csv2::Reader<csv2::delimiter<'"'>, csv2::quote_character<'"'>,
                                                  csv2::first_row_is_header<false>>;
  const std::size_t prefix_lengths[] = {63, 64, 65};
  for (const std::size_t prefix_length : prefix_lengths) {
    SharedDelimiterQuoteReader reader;
    std::string input(prefix_length, 'a');
    input += "\"b";
    REQUIRE(reader.parse(input));
    const auto row = *reader.begin();
    REQUIRE(std::distance(row.begin(), row.end()) == 1);
    REQUIRE(row.begin()->raw_size() == prefix_length + 2);
  }
}

TEST_CASE("Validate a shared delimiter and quote with quote precedence" * test_suite("Reader")) {
  using SharedDelimiterQuoteReader = csv2::Reader<csv2::delimiter<'"'>, csv2::quote_character<'"'>,
                                                  csv2::first_row_is_header<false>>;
  SharedDelimiterQuoteReader reader;
  std::string input("a\"b");
  REQUIRE(reader.parse(input));
  REQUIRE(std::distance(reader.begin()->begin(), reader.begin()->end()) == 1);

  csv2::parse_error error;
  REQUIRE_FALSE(reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
  REQUIRE(error.byte_offset == 1);
}

TEST_CASE("Give a newline quote policy precedence over record boundaries" * test_suite("Reader")) {
  using NewlineQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\n'>,
                                          csv2::first_row_is_header<false>>;
  NewlineQuoteReader reader;
  std::string input("\na\n,b");
  REQUIRE(reader.parse(input));

  csv2::parse_error error;
  REQUIRE(reader.validate(error));
  REQUIRE(reader.rows() == 1);
  REQUIRE(reader.index().size() == 1);
  REQUIRE(std::distance(reader.begin()->begin(), reader.begin()->end()) == 2);
}

TEST_CASE("Allow a bare carriage return inside a quoted field" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("\"a\rb\",c\n");
  REQUIRE(reader.parse(input));
  csv2::parse_error error;
  REQUIRE(reader.validate(error));
}

TEST_CASE("Preserve carriage-return quote bytes at record boundaries" * test_suite("Reader")) {
  using CarriageReturnQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\r'>,
                                                 csv2::first_row_is_header<false>>;

  SUBCASE("closing quote before LF") {
    CarriageReturnQuoteReader reader;
    std::string input("\ra\r\nb");
    REQUIRE(reader.parse(input));

    csv2::parse_error error;
    REQUIRE(reader.validate(error));
    REQUIRE(reader.rows() == 2);
    REQUIRE(reader.begin()->raw_size() == 3);
    std::string raw;
    reader.begin()->read_raw_value(raw);
    REQUIRE(raw == std::string("\ra\r", 3));
  }

  SUBCASE("opening quote before LF") {
    CarriageReturnQuoteReader reader;
    std::string input("\r\nx\r");
    REQUIRE(reader.parse(input));

    csv2::parse_error error;
    REQUIRE(reader.validate(error));
    REQUIRE(reader.rows() == 1);
    REQUIRE(reader.begin()->raw_size() == input.size());
  }
}

TEST_CASE("Reject record-separator quotes outside a quoted field" * test_suite("Reader")) {
  SUBCASE("newline quote") {
    using NewlineQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\n'>,
                                            csv2::first_row_is_header<false>>;
    NewlineQuoteReader reader;
    std::string input("a\nb");
    REQUIRE(reader.parse(input));

    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
    REQUIRE(error.byte_offset == 1);
  }

  SUBCASE("newline quote after carriage return") {
    using NewlineQuoteReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\n'>,
                                            csv2::first_row_is_header<false>>;
    NewlineQuoteReader reader;
    std::string input("a\r\nb");
    REQUIRE(reader.parse(input));

    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
    REQUIRE(error.byte_offset == 1);
  }

  SUBCASE("carriage-return quote") {
    using CarriageReturnQuoteReader =
        csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'\r'>,
                     csv2::first_row_is_header<false>>;
    CarriageReturnQuoteReader reader;
    std::string input("a\rb");
    REQUIRE(reader.parse(input));

    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::unexpected_quote);
    REQUIRE(error.byte_offset == 1);
  }
}

TEST_CASE("Scan cell boundaries through the shared fast path" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  const std::string wide_field(160, 'x');
  const std::string input = wide_field + ",\"quoted,field\",\"a\"\"b\",tail,";
  REQUIRE(reader.parse(input));
  REQUIRE(read_cells(*reader.begin()) ==
          std::vector<std::string>({wide_field, "\"quoted,field\"", "\"a\"b\"", "tail", ""}));
}

TEST_CASE("Validate strict CSV syntax without changing permissive traversal" *
          test_suite("Reader")) {
  const char *valid_inputs[] = {"a,b\n1,2",       " \t\"a\"\"b\" \t,c", "a,\"b\nc\",d",
                                "a,\"b\r\nc\",d", "a,\"b\rc\",d",       "a,b\n1\n2,3,4"};
  for (const char *input_value : valid_inputs) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE(reader.validate(error));
    REQUIRE(error.code == csv2::parse_errc::none);
  }

  struct InvalidCase {
    const char *input;
    csv2::parse_errc code;
    std::size_t offset;
    std::size_t row;
    std::size_t column;
  };
  const InvalidCase invalid_inputs[] = {
      {"a\"b,c", csv2::parse_errc::unexpected_quote, 1, 1, 1},
      {"\"a,b", csv2::parse_errc::unclosed_quote, 0, 1, 1},
      {"\"a\"x,b", csv2::parse_errc::characters_after_closing_quote, 3, 1, 1},
      {"\"a\" \"b\"", csv2::parse_errc::invalid_doubled_quote, 4, 1, 1},
      {"a\rb", csv2::parse_errc::bare_carriage_return, 1, 1, 1},
      {"a,b\nc,\"d\"x", csv2::parse_errc::characters_after_closing_quote, 9, 2, 2},
  };

  for (const auto &test_case : invalid_inputs) {
    ReaderWithoutHeader reader;
    std::string input(test_case.input);
    REQUIRE(reader.parse(input));
    csv2::parse_error error;
    REQUIRE_FALSE(reader.validate(error));
    REQUIRE(error.code == test_case.code);
    REQUIRE(error.byte_offset == test_case.offset);
    REQUIRE(error.row == test_case.row);
    REQUIRE(error.column == test_case.column);
    REQUIRE(read_rows(reader).size() >= 1);
  }
}

TEST_CASE("Allow carriage returns inside a quoted field during validation" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("\"a\rb\",c\n");
  REQUIRE(reader.parse(input));
  csv2::parse_error error;
  REQUIRE(reader.validate(error));
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"\"a\rb\"", "c"}));
}

TEST_CASE("Validate structural characters before overlapping trim characters" *
          test_suite("Reader")) {
  using DelimiterTrimReader =
      csv2::Reader<csv2::delimiter<';'>, csv2::quote_character<'"'>,
                   csv2::first_row_is_header<false>, csv2::trim_policy::trim_characters<' ', ';'>>;
  DelimiterTrimReader delimiter_reader;
  std::string delimiter_input(";\"b\"x");
  REQUIRE(delimiter_reader.parse(delimiter_input));
  csv2::parse_error error;
  REQUIRE_FALSE(delimiter_reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  REQUIRE(error.byte_offset == 4);
  REQUIRE(error.row == 1);
  REQUIRE(error.column == 2);

  delimiter_input = "\"a\";\"b\"x";
  REQUIRE(delimiter_reader.parse(delimiter_input));
  REQUIRE_FALSE(delimiter_reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  REQUIRE(error.byte_offset == 7);
  REQUIRE(error.row == 1);
  REQUIRE(error.column == 2);

  using LineEndingTrimReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                            csv2::first_row_is_header<false>,
                                            csv2::trim_policy::trim_characters<' ', '\r', '\n'>>;
  LineEndingTrimReader line_reader;
  std::string line_input("\n\"b\"x");
  REQUIRE(line_reader.parse(line_input));
  REQUIRE_FALSE(line_reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  REQUIRE(error.byte_offset == 4);
  REQUIRE(error.row == 2);
  REQUIRE(error.column == 1);

  line_input = "\"a\"\r\n\"b\"x";
  REQUIRE(line_reader.parse(line_input));
  REQUIRE_FALSE(line_reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  REQUIRE(error.byte_offset == 8);
  REQUIRE(error.row == 2);
  REQUIRE(error.column == 1);

  line_input = "\rX";
  REQUIRE(line_reader.parse(line_input));
  REQUIRE_FALSE(line_reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
  REQUIRE(error.byte_offset == 0);
  REQUIRE(error.row == 1);
  REQUIRE(error.column == 1);

  line_input = "\"a\"\rX";
  REQUIRE(line_reader.parse(line_input));
  REQUIRE_FALSE(line_reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::bare_carriage_return);
  REQUIRE(error.byte_offset == 3);
  REQUIRE(error.row == 1);
  REQUIRE(error.column == 1);

  using SharedDelimiterQuoteReader = csv2::Reader<csv2::delimiter<'"'>, csv2::quote_character<'"'>,
                                                  csv2::first_row_is_header<false>>;
  SharedDelimiterQuoteReader shared_reader;
  std::string shared_input("\"a\"x");
  REQUIRE(shared_reader.parse(shared_input));
  REQUIRE_FALSE(shared_reader.validate(error));
  REQUIRE(error.code == csv2::parse_errc::characters_after_closing_quote);
  REQUIRE(error.byte_offset == 3);
  REQUIRE(error.row == 1);
  REQUIRE(error.column == 1);
}

TEST_CASE("Convert complete integer field content without modifying failures" *
          test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("42,-2147483648,2147483648,12x,+7,101,\"17\"");
  REQUIRE(reader.parse(input));
  auto cell = (*reader.begin()).begin();
  csv2::conversion_error error;

  int value = -1;
  REQUIRE((*cell).try_parse(value, error));
  REQUIRE(value == 42);
  REQUIRE(error.code == csv2::conversion_errc::none);

  ++cell;
  REQUIRE((*cell).try_parse(value, error));
  REQUIRE(value == (std::numeric_limits<int>::min)());

  ++cell;
  value = 9;
  REQUIRE_FALSE((*cell).try_parse(value, error));
  REQUIRE(value == 9);
  REQUIRE(error.code == csv2::conversion_errc::result_out_of_range);

  ++cell;
  REQUIRE_FALSE((*cell).try_parse(value, error));
  REQUIRE(error.code == csv2::conversion_errc::trailing_characters);
  REQUIRE(error.byte_offset == 2);

  ++cell;
  REQUIRE_FALSE((*cell).try_parse(value, error));
  REQUIRE(error.code == csv2::conversion_errc::invalid_argument);
  REQUIRE(error.byte_offset == 0);

  ++cell;
  REQUIRE((*cell).try_parse(value, error, 2));
  REQUIRE(value == 5);

  ++cell;
  REQUIRE((*cell).try_parse(value, error));
  REQUIRE(value == 17);

  value = 11;
  REQUIRE_FALSE((*cell).try_parse(value, error, 1));
  REQUIRE(value == 11);
  REQUIRE(error.code == csv2::conversion_errc::invalid_base);

  ReaderWithoutHeader sign_reader;
  std::string sign_input("-");
  REQUIRE(sign_reader.parse(sign_input));
  value = 12;
  REQUIRE_FALSE(sign_reader.begin()->begin()->try_parse(value, error));
  REQUIRE(value == 12);
  REQUIRE(error.code == csv2::conversion_errc::invalid_argument);
  REQUIRE(error.byte_offset == 0);
}

#if CSV2_HAS_EXPECTED
TEST_CASE("Expose C++23 expected adapters when the library provides them" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("42,invalid");
  REQUIRE(reader.parse(input));
  REQUIRE(reader.validate_expected().has_value());

  auto cell = (*reader.begin()).begin();
  const auto parsed = (*cell).template parse_expected<int>();
  REQUIRE(parsed == 42);
  ++cell;
  const auto failed = (*cell).template parse_expected<int>();
  REQUIRE_FALSE(failed.has_value());
  REQUIRE(failed.error().code == csv2::conversion_errc::invalid_argument);

#if CSV2_HAS_MMAP
  ReaderWithoutHeader mapped;
  REQUIRE(mapped.mmap_expected("inputs/test_01.csv").has_value());
  const auto missing = mapped.mmap_expected("inputs/this-file-does-not-exist.csv");
  REQUIRE_FALSE(missing.has_value());
  REQUIRE(missing.error());
#endif
}
#endif

TEST_CASE("Handle record terminators and quoted newlines" * test_suite("Reader")) {
  struct RecordCase {
    const char *input;
    std::vector<std::vector<std::string>> expected;
  };
  const RecordCase cases[] = {
      {"a,b\n1,2", {{"a", "b"}, {"1", "2"}}},
      {"a,b\n1,2\n", {{"a", "b"}, {"1", "2"}}},
      {"a,b\r\n1,2", {{"a", "b"}, {"1", "2"}}},
      {"a,b\r\n1,2\r\n", {{"a", "b"}, {"1", "2"}}},
      {"a,b\rstandalone", {{"a", "b\rstandalone"}}},
      {"a,\"b\nc\",d\r\n1,\"x\r\ny\",3\r\n", {{"a", "\"b\nc\"", "d"}, {"1", "\"x\r\ny\"", "3"}}},
      {"a,\"b\"\"c\nstill\",d\nx,y,z\n", {{"a", "\"b\"c\nstill\"", "d"}, {"x", "y", "z"}}},
      {"a,\"b\nc,d", {{"a", "\"b\nc,d"}}},
  };

  for (const auto &test_case : cases) {
    ReaderWithoutHeader reader;
    std::string input(test_case.input);
    REQUIRE(reader.parse(input));
    REQUIRE(read_rows(reader) == test_case.expected);
  }
}

TEST_CASE("Expose the address and length of each logical row" * test_suite("Reader")) {
  struct AddressCase {
    const char *input;
    std::vector<std::size_t> offsets;
    std::vector<std::string> records;
  };

  const AddressCase cases[] = {
      {"a,b\nc,d", {0, 4}, {"a,b", "c,d"}},
      {"a,b\r\nc,d", {0, 5}, {"a,b", "c,d"}},
      {"a,\"b\nc\"\nd,e", {0, 8}, {"a,\"b\nc\"", "d,e"}},
      {"a\n\nb", {0, 2, 3}, {"a", "", "b"}},
  };

  for (const auto &test_case : cases) {
    ReaderWithoutHeader reader;
    std::string input(test_case.input);
    REQUIRE(reader.parse(input));

    auto row = reader.begin();
    for (std::size_t i = 0; i < test_case.offsets.size(); ++i, ++row) {
      REQUIRE(row != reader.end());
      const auto value = *row;
      REQUIRE(value.address() == input.data() + test_case.offsets[i]);
      REQUIRE(std::string(value.address(), value.length()) == test_case.records[i]);
    }
    REQUIRE(row == reader.end());
  }

  ReaderWithoutHeader empty;
  REQUIRE(empty.header().address() == nullptr);
  REQUIRE(empty.header().length() == 0);
}

TEST_CASE("Preserve trailing empty fields and normalize empty records" * test_suite("Reader")) {
  struct FieldCase {
    const char *row;
    std::vector<std::string> expected;
  };
  const FieldCase field_cases[] = {
      {"a,", {"a", ""}}, {",", {"", ""}}, {",,", {"", "", ""}}, {"a,,", {"a", "", ""}}};
  const char *terminators[] = {"", "\n", "\r\n"};

  for (const auto &field_case : field_cases) {
    for (const auto terminator : terminators) {
      ReaderWithoutHeader reader;
      std::string input(field_case.row);
      input += terminator;
      REQUIRE(reader.parse(input));
      REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({field_case.expected}));
    }
  }

  const char *empty_record_inputs[] = {"a\n\nb\n", "a\r\n\r\nb\r\n"};
  for (const auto input_value : empty_record_inputs) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    REQUIRE(reader.parse(input));
    REQUIRE(reader.rows() == 3);
    REQUIRE(reader.rows(true) == 2);
    REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"a"}, {}, {"b"}}));
  }

  const char *single_empty_records[] = {"\n", "\r\n"};
  for (const auto input_value : single_empty_records) {
    ReaderWithoutHeader reader;
    std::string input(input_value);
    REQUIRE(reader.parse(input));
    REQUIRE(reader.rows() == 1);
    REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{}}));
  }

  ReaderWithHeader header_reader;
  std::string header_input("h1,h2,\r\nvalue1,value2,");
  REQUIRE(header_reader.parse(header_input));
  REQUIRE(read_cells(header_reader.header()) == std::vector<std::string>({"h1", "h2", ""}));
  REQUIRE(header_reader.cols() == 3);
  REQUIRE(read_rows(header_reader) ==
          std::vector<std::vector<std::string>>({{"value1", "value2", ""}}));
}

TEST_CASE("Read raw and decoded cell values by appending to the output" * test_suite("Reader")) {
  struct QuoteCase {
    const char *input;
    const char *expected;
  };
  const QuoteCase quote_cases[] = {{"\"\"", "\""},
                                   {"\"\"\"\"", "\"\""},
                                   {"\"a\"\"b\"", "\"a\"b\""},
                                   {"\"a\"\"b\"\"c\"", "\"a\"b\"c\""}};
  for (const auto &quote_case : quote_cases) {
    ReaderWithoutHeader reader;
    std::string input(quote_case.input);
    REQUIRE(reader.parse(input));
    REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({quote_case.expected}));
  }

  ReaderWithoutHeader reader;
  std::string input(" \t\"a\"\"b\"\t ");
  REQUIRE(reader.parse(input));
  const auto cell = *(*reader.begin()).begin();

  std::string raw("raw:");
  cell.read_raw_value(raw);
  REQUIRE(raw == "raw: \t\"a\"\"b\"\t ");

  std::string decoded("value:");
  cell.read_value(decoded);
  REQUIRE(decoded == "value:\"a\"b\"");
}

TEST_CASE("Do not reserve when reading an empty raw range" * test_suite("Reader")) {
  const PublicCell cell;
  RejectZeroReserveBuffer cell_output;
  cell.read_raw_value(cell_output);
  REQUIRE_FALSE(cell_output.reserve_called);

  const PublicRow row;
  RejectZeroReserveBuffer row_output;
  row.read_raw_value(row_output);
  REQUIRE_FALSE(row_output.reserve_called);
}

TEST_CASE("Copy fields to generic containers and output iterators" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input(" \t\"a\"\"b\"\t ");
  REQUIRE(reader.parse(input));
  const auto cell = *(*reader.begin()).begin();

  std::deque<char> raw;
  cell.read_raw_value(raw);
  REQUIRE(std::string(raw.begin(), raw.end()) == input);

  std::list<char> decoded;
  cell.read_value(decoded);
  REQUIRE(std::string(decoded.begin(), decoded.end()) == "\"a\"b\"");

  AppendOnlyBuffer appended;
  cell.read_value(appended);
  REQUIRE(appended.value == "\"a\"b\"");

  std::vector<char> copied;
  cell.copy_raw_to(std::back_inserter(copied));
  REQUIRE(std::string(copied.begin(), copied.end()) == input);

  char decoded_buffer[32] = {};
  char *const decoded_end = cell.decode_to(decoded_buffer);
  REQUIRE(std::string(decoded_buffer, decoded_end) == "\"a\"b\"");

  std::string content;
  cell.copy_content_to(std::back_inserter(content));
  REQUIRE(content == "a\"b");

#if CSV2_HAS_MEMORY_RESOURCE
  std::pmr::monotonic_buffer_resource resource;
  std::pmr::string pmr_value(&resource);
  cell.read_value(pmr_value);
  REQUIRE(pmr_value == "\"a\"b\"");
#endif
}

TEST_CASE("Batch contiguous raw and decoded field segments" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("plain,\"a\"\"b\"\"c\"");
  REQUIRE(reader.parse(input));
  const auto row = *reader.begin();

  AppendCountingBuffer raw_row;
  row.read_raw_value(raw_row);
  REQUIRE(raw_row.value == input);
  REQUIRE(raw_row.append_calls == 1);

  auto cell = row.begin();
  AppendCountingBuffer plain;
  (*cell).read_value(plain);
  REQUIRE(plain.value == "plain");
  REQUIRE(plain.append_calls == 1);

  ++cell;
  AppendCountingBuffer escaped;
  (*cell).read_value(escaped);
  REQUIRE(escaped.value == "\"a\"b\"c\"");
  REQUIRE(escaped.append_calls == 3);
}

TEST_CASE("Expose raw byte views and explicit source ownership" * test_suite("Reader")) {
  const char borrowed[] = "  \"a\"\"b\"  ,tail";
  ReaderWithoutHeader reader;
  REQUIRE(reader.parse_borrowed(borrowed, sizeof(borrowed) - 1));

  const auto row = *reader.begin();
  REQUIRE(row.raw_data() == borrowed);
  REQUIRE(row.raw_size() == sizeof(borrowed) - 1);
  REQUIRE(row.address() == row.raw_data());
  REQUIRE(row.length() == row.raw_size());

  const auto cell = *row.begin();
  REQUIRE(cell.raw_data() == borrowed);
  REQUIRE(cell.raw_size() == 10);
  REQUIRE(cell.has_escaped_quotes());
#if CSV2_HAS_STRING_VIEW
  REQUIRE(cell.raw_trimmed_view() == "\"a\"\"b\"");
#endif

  std::string owned("owned,value");
  REQUIRE(reader.parse_owned(owned));
  owned[0] = 'X';
  std::string owned_row;
  (*reader.begin()).read_raw_value(owned_row);
  REQUIRE(owned_row == "owned,value");
}

TEST_CASE("Reject an owned alias range that extends beyond its backing source" *
          test_suite("Reader")) {
  ReaderWithoutHeader reader;
  const std::string input("owned,value");
  REQUIRE(reader.parse_owned(input));
  const char *const source = (*reader.begin()).raw_data();

  REQUIRE_FALSE(reader.parse_borrowed(source + 1, input.size()));
  REQUIRE(reader.rows() == 0);
}

TEST_CASE("Preserve owned storage when parse_borrowed selects a cell range" *
          test_suite("Reader")) {
  ReaderWithoutHeader reader;
  const std::string first_cell(512, 'b');
  REQUIRE(reader.parse_owned(first_cell + ",discarded"));

  const auto cell = *(*reader.begin()).begin();
  const char *const data = cell.raw_data();
  const size_t size = cell.raw_size();
  REQUIRE(reader.parse_borrowed(data, size));
  REQUIRE((*reader.begin()).raw_data() == data);
  REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}

#if CSV2_HAS_MMAP
TEST_CASE("Preserve mapped storage when parse_borrowed selects a cell range" *
          test_suite("Reader")) {
  const std::string path = std::string(writer_output_path()) + ".parse-borrowed-mmap-source";
  ScopedFileRemoval cleanup(path);
  const std::string first_cell(512, 'p');
  write_binary_file(path, first_cell + ",discarded");

  ReaderWithoutHeader reader;
  REQUIRE(reader.mmap(path));
  const auto cell = *(*reader.begin()).begin();
  const char *const data = cell.raw_data();
  const size_t size = cell.raw_size();
  REQUIRE(reader.parse_borrowed(data, size));
  REQUIRE((*reader.begin()).raw_data() == data);
  REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}
#endif

#if CSV2_HAS_STRING_VIEW
TEST_CASE("Expose an empty view from a default cell" * test_suite("Reader")) {
  const PublicCell cell;
  REQUIRE(cell.raw_trimmed_view().empty());
  REQUIRE(cell.read_view().empty());
}
#endif

#if CSV2_HAS_SPAN
TEST_CASE("Borrow a span source without copying" * test_suite("Reader")) {
  char bytes[] = {'a', ',', 'b'};
  ReaderWithoutHeader reader;
  REQUIRE(reader.parse_borrowed(std::span<const char>(bytes)));
  REQUIRE((*reader.begin()).raw_data() == bytes);
  bytes[0] = 'x';
  std::string row;
  (*reader.begin()).read_raw_value(row);
  REQUIRE(row == "x,b");
}
#endif

TEST_CASE("Reacquire cursors and indexes after same-extent source mutation" *
          test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,b\nc,d");
  REQUIRE(reader.parse(input));
  REQUIRE(reader.index().size() == 2);

  input[3] = ',';
  REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"a", "b", "c", "d"}}));
  REQUIRE(reader.index().size() == 1);

  input[1] = ';';
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"a;b", "c", "d"}));

  std::string quoted("\"a,b\",c");
  REQUIRE(reader.parse(quoted));
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"\"a,b\"", "c"}));
  quoted[0] = 'x';
  quoted[4] = 'x';
  REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"xa", "bx", "c"}));
  REQUIRE(reader.index().size() == 1);
}

#if CSV2_HAS_RANGES
TEST_CASE("Pipe a temporary borrowed Row view" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,bb,ccc");
  REQUIRE(reader.parse(input));
  auto sizes = *reader.begin() |
               std::views::transform([](const PublicCell cell) { return cell.raw_size(); });
  REQUIRE(std::ranges::equal(sizes, std::vector<std::size_t>({1, 2, 3})));

#if CSV2_HAS_RANGES_TO_CONTAINER
  const auto collected = sizes | std::ranges::to<std::vector<std::size_t>>();
  REQUIRE(collected == std::vector<std::size_t>({1, 2, 3}));
#endif
}
#endif

TEST_CASE("Reserve for existing output when appending a raw row" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,b");
  REQUIRE(reader.parse(input));

  ReserveTrackingBuffer output("pre:");
  (*reader.begin()).read_raw_value(output);
  REQUIRE(output.last_reserve == 7);
  REQUIRE(output.value == "pre:a,b");
}

TEST_CASE("Append a raw row to a reserve-only output type" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,b");
  REQUIRE(reader.parse(input));

  ReserveOnlyBuffer output("pre:");
  (*reader.begin()).read_raw_value(output);
  REQUIRE(output.last_reserve == 3);
  REQUIRE(output.value == "pre:a,b");
}

TEST_CASE("Own rvalue input, borrow lvalue input, and preserve input across moves" *
          test_suite("Reader")) {
  ReaderWithoutHeader temporary_reader;
  const std::string first_cell(512, 'a');
  const std::string temporary_payload = first_cell + ",b\nc,d";
  REQUIRE(temporary_reader.parse(std::string(temporary_payload)));
  std::vector<std::string> heap_churn(512, std::string(temporary_payload.size(), 'x'));
  (void)heap_churn;
  REQUIRE(read_rows(temporary_reader) ==
          std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));

  ReaderWithoutHeader borrowed_reader;
  std::string borrowed_input("borrowed,data");
  REQUIRE(borrowed_reader.parse(borrowed_input));
  REQUIRE((*borrowed_reader.begin()).address() == borrowed_input.c_str());

  ReaderWithoutHeader string_like_reader;
  std::string string_like_input("generic,value");
  REQUIRE(string_like_reader.parse(
      StringLikeView(string_like_input.c_str(), string_like_input.size())));
  string_like_input.assign(string_like_input.size(), 'x');
  REQUIRE(read_rows(string_like_reader) ==
          std::vector<std::vector<std::string>>({{"generic", "value"}}));

  ReaderWithoutHeader moved(std::move(temporary_reader));
  REQUIRE(temporary_reader.rows() == 0);
  REQUIRE(read_rows(moved) ==
          std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));

  ReaderWithoutHeader assigned;
  assigned = std::move(moved);
  REQUIRE(moved.rows() == 0);
  REQUIRE(read_rows(assigned) ==
          std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));
}

TEST_CASE("Clear old input when replacing a source or a source fails" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  REQUIRE(reader.parse(std::string("owned,data")));

  std::string borrowed("borrowed,data");
  REQUIRE(reader.parse(borrowed));
  REQUIRE((*reader.begin()).address() == borrowed.c_str());

  REQUIRE_FALSE(reader.parse(std::string()));
  REQUIRE(reader.rows() == 0);

#if CSV2_HAS_MMAP
  REQUIRE(reader.parse(borrowed));
  REQUIRE_FALSE(reader.mmap("inputs/this-file-does-not-exist.csv"));
  REQUIRE(reader.rows() == 0);

  REQUIRE(reader.parse(borrowed));
  REQUIRE_FALSE(reader.mmap("inputs/empty.csv"));
  REQUIRE(reader.rows() == 0);
#endif
}

#if CSV2_HAS_MMAP
TEST_CASE("Report mmap errors and release handles after mapping failures" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::error_code error = std::make_error_code(std::errc::address_in_use);
  REQUIRE(reader.mmap("inputs/test_01.csv", error));
  REQUIRE_FALSE(error);

  REQUIRE_FALSE(reader.mmap("inputs/this-file-does-not-exist.csv", error));
  REQUIRE(error);
  REQUIRE(reader.rows() == 0);

  REQUIRE_FALSE(reader.mmap("inputs/empty.csv", error));
  REQUIRE(error);
#if defined(_WIN32)
  REQUIRE(error.value() == ERROR_FILE_INVALID);
#endif

#if defined(__linux__) || defined(_WIN32)
  const std::size_t warmup_handle_count = process_handle_count();
  REQUIRE(warmup_handle_count != (std::numeric_limits<std::size_t>::max)());
  const std::size_t handles_before = process_handle_count();
  REQUIRE(handles_before != (std::numeric_limits<std::size_t>::max)());
  for (int attempt = 0; attempt < 2048; ++attempt) {
    mio::mmap_source mapping;
    mapping.map("inputs/empty.csv", error);
    REQUIRE(error);
#if defined(_WIN32)
    REQUIRE(error.value() == ERROR_FILE_INVALID);
#endif
  }
  REQUIRE(process_handle_count() == handles_before);
#endif

  mio::mmap_source mapping;
  mapping.map("inputs/test_01.csv", (std::numeric_limits<std::size_t>::max)(), 2, error);
  REQUIRE(error);
  REQUIRE(error == std::errc::invalid_argument);
  REQUIRE(error.category() == std::generic_category());
}

TEST_CASE("Map a non-page-aligned offset beyond the first page" * test_suite("mio")) {
  const std::size_t page = mio::page_size();
  REQUIRE(page > 0);
  REQUIRE(page < (std::numeric_limits<std::size_t>::max)() - 3);

  const std::string path = std::string(writer_output_path()) + ".mmap-offset";
  ScopedFileRemoval cleanup(path);
  std::string contents(page + 3, 'x');
  contents[page + 1] = 'Z';
  {
    std::ofstream output(path.c_str(), std::ios::binary | std::ios::trunc);
    REQUIRE(output.is_open());
    output.write(contents.data(), static_cast<std::streamsize>(contents.size()));
    REQUIRE(output.good());
  }

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map(path, page + 1, 1, error);
  REQUIRE_FALSE(error);
  REQUIRE(mapping.size() == 1);
  REQUIRE(mapping[0] == 'Z');
  REQUIRE(mapping.mapping_offset() == 1);
  REQUIRE(mapping.mapped_length() == 2);
}

TEST_CASE("Preserve ownership when remapping through the mapping's own handle" *
          test_suite("mio")) {
  const std::string path = std::string(writer_output_path()) + ".mmap-remap-source";
  ScopedFileRemoval cleanup(path);
  write_binary_file(path, "a,b,c\n1,2,3\n4,5,6");

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map(path, error);
  REQUIRE_FALSE(error);

  const mio::file_handle_type handle = mapping.file_handle();
  mapping.map(handle, 6, 5, error);
  REQUIRE_FALSE(error);
  REQUIRE(std::string(mapping.data(), mapping.size()) == "1,2,3");

#if defined(__unix__) || defined(__APPLE__)
  errno = 0;
  REQUIRE(::fcntl(handle, F_GETFD) != -1);
#endif

  mapping.map(handle, 12, 5, error);
  REQUIRE_FALSE(error);
  REQUIRE(std::string(mapping.data(), mapping.size()) == "4,5,6");

  mapping.unmap();
#if defined(__unix__) || defined(__APPLE__)
  errno = 0;
  REQUIRE(::fcntl(handle, F_GETFD) == -1);
  REQUIRE(errno == EBADF);
#endif
}

TEST_CASE("Preserve ownership through shared and writable same-handle remaps" * test_suite("mio")) {
  const std::string source_path = std::string(writer_output_path()) + ".shared-mmap-remap-source";
  ScopedFileRemoval source_cleanup(source_path);
  write_binary_file(source_path, "a,b,c\n1,2,3\n4,5,6");

  std::error_code error;
  mio::shared_mmap_source shared;
  shared.map(source_path, error);
  REQUIRE_FALSE(error);
  const mio::file_handle_type shared_handle = shared.file_handle();
  shared.map(shared_handle, 6, 5, error);
  REQUIRE_FALSE(error);
  REQUIRE(std::string(shared.data(), shared.size()) == "1,2,3");
  shared.map(shared_handle, 12, 5, error);
  REQUIRE_FALSE(error);
  REQUIRE(std::string(shared.data(), shared.size()) == "4,5,6");
  shared.unmap();

  const std::string path = std::string(writer_output_path()) + ".mmap-sink";
  ScopedFileRemoval cleanup(path);
  {
    std::ofstream output(path.c_str(), std::ios::binary | std::ios::trunc);
    REQUIRE(output.is_open());
    output << "abcdef";
    REQUIRE(output.good());
  }

  mio::mmap_sink sink;
  sink.map(path, error);
  REQUIRE_FALSE(error);
  const mio::file_handle_type sink_handle = sink.file_handle();
  sink.map(sink_handle, 1, 1, error);
  REQUIRE_FALSE(error);
  sink[0] = 'Z';
  sink.sync(error);
  REQUIRE_FALSE(error);
  sink.map(sink_handle, 2, 1, error);
  REQUIRE_FALSE(error);
  REQUIRE(sink[0] == 'c');
  sink.unmap();

  std::ifstream input(path.c_str(), std::ios::binary);
  std::string persisted((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  REQUIRE(persisted == "aZcdef");
}

TEST_CASE("Reject mapped paths containing an embedded NUL" * test_suite("Reader")) {
  csv2::Reader<> reader;
  std::string path("inputs/test_01.csv");
  path.push_back('\0');
  path += "ignored-suffix";
  std::error_code error;

  REQUIRE_FALSE(reader.mmap(path, error));
  REQUIRE(error == std::make_error_code(std::errc::invalid_argument));
}

TEST_CASE("Validate sized character range paths before mapping" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::error_code error;

  std::vector<char> terminated_path;
  const std::string path("inputs/test_01.csv");
  terminated_path.assign(path.begin(), path.end());
  terminated_path.push_back('\0');
  REQUIRE(reader.mmap(terminated_path, error));
  REQUIRE_FALSE(error);

  std::vector<char> unterminated(path.begin(), path.end());
  REQUIRE_FALSE(reader.mmap(unterminated, error));
  REQUIRE(error == std::errc::invalid_argument);

  std::vector<char> embedded(terminated_path);
  embedded.insert(embedded.end(), {'x', '\0'});
  REQUIRE_FALSE(reader.mmap(embedded, error));
  REQUIRE(error == std::errc::invalid_argument);
}

#if defined(__unix__) || defined(__APPLE__)
TEST_CASE("Map a caller-owned file handle without closing it" * test_suite("Reader")) {
  const int handle = ::open("inputs/test_01.csv", O_RDONLY);
  REQUIRE(handle != -1);
  ReaderWithoutHeader reader;
  std::error_code error;
  REQUIRE(reader.mmap(handle, error));
  REQUIRE_FALSE(error);
  REQUIRE(reader.rows() > 0);
  reader = ReaderWithoutHeader();
  errno = 0;
  REQUIRE(::fcntl(handle, F_GETFD) != -1);
  REQUIRE(::close(handle) == 0);
}
#endif

TEST_CASE("Map a path stored in the Reader's current owned source" * test_suite("Reader")) {
  const std::string path = std::string(writer_output_path()) + ".owned-mmap-path-source";
  ScopedFileRemoval cleanup(path);
  write_binary_file(path, "mapped,data");

  ReaderWithoutHeader reader;
  REQUIRE(reader.parse_owned(path));
  const char *const borrowed_path = reader.header().raw_data();
  REQUIRE(reader.mmap(borrowed_path));
  REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"mapped", "data"}}));
}

TEST_CASE("Map a path stored in the Reader's current mapped source" * test_suite("Reader")) {
  const std::string target_path = std::string(writer_output_path()) + ".mapped-path-target";
  const std::string source_path = std::string(writer_output_path()) + ".mapped-path-source";
  ScopedFileRemoval target_cleanup(target_path);
  ScopedFileRemoval source_cleanup(source_path);
  write_binary_file(target_path, "target,data");
  write_binary_file(source_path, target_path + std::string(1, '\0'));

  ReaderWithoutHeader reader;
  REQUIRE(reader.mmap(source_path));
  const char *const borrowed_path = reader.header().raw_data();
  REQUIRE(reader.mmap(borrowed_path));
  REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"target", "data"}}));
}

#if CSV2_HAS_FILESYSTEM
TEST_CASE("Map a filesystem path" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::error_code error;
  REQUIRE(reader.mmap(std::filesystem::path("inputs/test_01.csv"), error));
  REQUIRE_FALSE(error);
  REQUIRE(reader.rows() > 0);
}
#endif
#endif

#if ((defined(_MSVC_LANG) && _MSVC_LANG >= 201703L) || __cplusplus >= 201703L)
TEST_CASE("Borrow storage passed through parse_view" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("view,data");
  REQUIRE(reader.parse_view(std::string_view(input)));
  REQUIRE((*reader.begin()).address() == input.data());
}

TEST_CASE("Preserve a complete owned source when parse_view aliases it" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  const std::string first_cell(512, 'f');
  const std::string input = first_cell + ",second\nthird,fourth";
  REQUIRE(reader.parse(std::string(input)));

  const char *const source_address = (*reader.begin()).address();
  REQUIRE(reader.parse_view(std::string_view(source_address, input.size())));
  REQUIRE((*reader.begin()).address() == source_address);
  REQUIRE(read_rows(reader) ==
          std::vector<std::vector<std::string>>({{first_cell, "second"}, {"third", "fourth"}}));
}

TEST_CASE("Preserve owned storage when parse_view selects a cell subview" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  const std::string first_cell(512, 'a');
  REQUIRE(reader.parse(std::string(first_cell + ",discarded")));

  const std::string_view view = (*(*reader.begin()).begin()).read_view();
  REQUIRE(reader.parse_view(view));
  REQUIRE((*reader.begin()).address() == view.data());
  REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}

#if CSV2_HAS_MMAP
TEST_CASE("Preserve mapped storage when parse_view selects a cell subview" * test_suite("Reader")) {
  const std::string path = std::string(writer_output_path()) + ".parse-view-mmap-source";
  ScopedFileRemoval cleanup(path);
  const std::string first_cell(512, 'm');
  write_binary_file(path, first_cell + ",discarded");

  ReaderWithoutHeader reader;
  REQUIRE(reader.mmap(path));
  const std::string_view view = (*(*reader.begin()).begin()).read_view();
  REQUIRE(reader.parse_view(view));
  REQUIRE((*reader.begin()).address() == view.data());
  REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}
#endif

TEST_CASE("Preserve destination-owned storage when move-assigning a view borrower" *
          test_suite("Reader")) {
  ReaderWithoutHeader owner;
  const std::string first_cell(512, 'o');
  REQUIRE(owner.parse(std::string(first_cell + ",discarded")));
  const std::string_view view = (*(*owner.begin()).begin()).read_view();

  ReaderWithoutHeader borrower;
  REQUIRE(borrower.parse_view(view));
  owner = std::move(borrower);

  REQUIRE(borrower.rows() == 0);
  REQUIRE((*owner.begin()).address() == view.data());
  REQUIRE(read_rows(owner) == std::vector<std::vector<std::string>>({{first_cell}}));
}
#endif

TEST_CASE("Compare const iterators and expose a trailing empty cell before end" *
          test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,b\nc,d");
  REQUIRE(reader.parse(input));

  const auto row_begin = reader.begin();
  const auto row_begin_copy = row_begin;
  const auto row_end = reader.end();
  static_assert(noexcept(row_begin == row_begin_copy), "RowIterator equality must be noexcept");
  static_assert(noexcept(row_begin != row_end), "RowIterator inequality must be noexcept");
  REQUIRE(row_begin == row_begin_copy);
  REQUIRE(row_begin != row_end);

  const auto row = *row_begin;
  auto cell_iterator = row.begin();
  const auto first_cell = cell_iterator;
  ++cell_iterator;
  const auto second_cell = cell_iterator;
  const auto cell_end = row.end();
  static_assert(noexcept(first_cell == second_cell), "CellIterator equality must be noexcept");
  static_assert(noexcept(first_cell != cell_end), "CellIterator inequality must be noexcept");
  REQUIRE(first_cell != second_cell);
  REQUIRE(second_cell != cell_end);

  ReaderWithoutHeader trailing_reader;
  std::string trailing_input("a,");
  REQUIRE(trailing_reader.parse(trailing_input));
  const auto trailing_row = *trailing_reader.begin();
  auto trailing_cell = trailing_row.begin();
  ++trailing_cell;
  const auto trailing_end = trailing_row.end();
  REQUIRE(trailing_cell != trailing_end);
  std::string trailing_value;
  (*trailing_cell).read_value(trailing_value);
  REQUIRE(trailing_value.empty());
  ++trailing_cell;
  REQUIRE(trailing_cell == trailing_end);
}

TEST_CASE("Use default and post-incremented iterators with classic algorithms" *
          test_suite("Reader")) {
  ReaderWithoutHeader::RowIterator default_row_a;
  ReaderWithoutHeader::RowIterator default_row_b;
  REQUIRE(default_row_a == default_row_b);

  ReaderWithoutHeader reader;
  std::string input("a,b\nc,d");
  REQUIRE(reader.parse(input));
  REQUIRE(std::distance(reader.begin(), reader.end()) == 2);
  REQUIRE(reader.begin()->raw_size() == 3);
  REQUIRE((*reader.begin()).begin()->raw_size() == 1);
  REQUIRE(reader.index().begin()->raw_size() == 3);

  auto row = reader.begin();
  const auto first_row = row++;
  REQUIRE(first_row != row);

  auto cells = (*first_row).begin();
  ReaderWithoutHeader::Row::CellIterator default_cell_a;
  ReaderWithoutHeader::Row::CellIterator default_cell_b;
  REQUIRE(default_cell_a == default_cell_b);
  const auto first_cell = cells++;
  REQUIRE(first_cell != cells);
  std::string value;
  (*first_cell).read_value(value);
  REQUIRE(value == "a");
}

TEST_CASE("Build an explicit random-access row index from logical record offsets" *
          test_suite("Reader")) {
  ReaderWithHeader reader;
  std::string input("h1,h2\n\n\"a\nb\",c\nx,y\n");
  REQUIRE(reader.parse(input));

  const auto all_rows = reader.index();
  REQUIRE(all_rows.size() == 3);
  REQUIRE(read_cells(all_rows[0]).empty());
  REQUIRE(read_cells(all_rows[1]) == std::vector<std::string>({"\"a\nb\"", "c"}));
  REQUIRE(read_cells(all_rows[2]) == std::vector<std::string>({"x", "y"}));
  REQUIRE(all_rows[1].raw_data() == input.data() + 7);

  const auto non_empty_rows = reader.index(true);
  REQUIRE(non_empty_rows.size() == 2);
  REQUIRE(non_empty_rows.end() - non_empty_rows.begin() == 2);
  REQUIRE(read_cells(*(non_empty_rows.begin() + 1)) == std::vector<std::string>({"x", "y"}));
  REQUIRE(read_cells(non_empty_rows.begin()[0]) == std::vector<std::string>({"\"a\nb\"", "c"}));

  const ReaderWithHeader::RowIndex invalid(nullptr, 4, 0, false);
  REQUIRE(invalid.empty());

#if CSV2_HAS_RANGES
  static_assert(std::ranges::random_access_range<ReaderWithHeader::RowIndex>);
  static_assert(std::ranges::sized_range<ReaderWithHeader::RowIndex>);
#endif
}

TEST_CASE("Write to streams with and without close" * test_suite("Writer")) {
  std::ostringstream memory_stream;
  {
    csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(memory_stream);
    writer.write_row(std::vector<std::string>({"a", "b"}));
  }
  REQUIRE(memory_stream.str() == "a,b\n");

  const char *const output_path = writer_output_path();
  std::remove(output_path);
  std::ofstream file_stream(output_path);
  REQUIRE(file_stream.is_open());
  {
    csv2::Writer<csv2::delimiter<','>, std::ofstream> writer(file_stream);
    writer.write_row(std::vector<std::string>({"1", "2"}));
  }
  REQUIRE_FALSE(file_stream.is_open());
  std::ifstream output(output_path);
  std::ostringstream output_contents;
  output_contents << output.rdbuf();
  REQUIRE(output_contents.str() == "1,2\n");
  output.close();
  std::remove(output_path);

  LvalueCloseStream lvalue_close_stream;
  {
    csv2::Writer<csv2::delimiter<','>, LvalueCloseStream> writer(lvalue_close_stream);
    writer.write_row(std::vector<std::string>({"x", "y"}));
  }
  REQUIRE(lvalue_close_stream.closed);
  REQUIRE(lvalue_close_stream.str() == "x,y\n");
}

TEST_CASE("Write empty and forward-iterable rows" * test_suite("Writer")) {
  std::ostringstream output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(output);

  writer.write_row(std::vector<std::string>());
  writer.write_row(std::vector<std::string>({""}));
  writer.write_row(std::list<std::string>({"a", "b"}));
  writer.write_row(std::forward_list<std::string>({"x", "y", "z"}));

  REQUIRE(output.str() == "\n\na,b\nx,y,z\n");
}

TEST_CASE("Write ADL ranges and contiguous character fields directly" * test_suite("Writer")) {
  DirectWriteTrackingStream output;
  csv2::basic_writer<csv2::delimiter<','>, DirectWriteTrackingStream> writer(output);
  const std::string row[] = {"alpha", "beta"};
  writer.write_row(row);

  REQUIRE(output.str() == "alpha,beta\n");
  REQUIRE(output.write_calls == 2);

  std::ostringstream numbers;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> number_writer(numbers);
  number_writer.write_row(std::vector<int>({1, 2}));
  REQUIRE(numbers.str() == "1,2\n");

  MinimalWriteStream minimal_stream;
  csv2::Writer<csv2::delimiter<','>, MinimalWriteStream> minimal_writer(minimal_stream);
  minimal_writer.write_row(std::vector<std::string>({"alpha", "beta"}));
  REQUIRE(minimal_stream.value == "alpha,beta\n");

  DecoratingStringStream decorating_stream;
  csv2::Writer<csv2::delimiter<','>, DecoratingStringStream> decorating_writer(decorating_stream);
  decorating_writer.write_row(std::vector<std::string>({"alpha", "beta"}));
  REQUIRE(decorating_stream.value == "<alpha>,<beta>\n");

  ChainedInsertionStream chained_stream;
  csv2::Writer<csv2::delimiter<','>, ChainedInsertionStream> chained_writer(chained_stream);
  chained_writer.write_row(std::vector<std::string>({"alpha", "beta"}));
  REQUIRE(chained_stream.value == "S{alpha},P{beta}\n");

  std::ostringstream const_range_output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> const_range_writer(const_range_output);
  ConstSelectingRow const_selecting_row;
  const_range_writer.write_row(const_selecting_row);
  REQUIRE(const_range_output.str() == "const\n");

#if CSV2_HAS_STRING_VIEW
  DecoratingStringStream view_stream;
  csv2::Writer<csv2::delimiter<','>, DecoratingStringStream> view_writer(view_stream);
  const std::string_view views[] = {"alpha", "beta"};
  view_writer.write_row(views);
  REQUIRE(view_stream.value == "[alpha],[beta]\n");
#endif

  MinimalWriteStream minimal_escaped_stream;
  csv2::EscapingWriter<csv2::delimiter<','>, MinimalWriteStream, csv2::stream_ownership::leave_open>
      minimal_escaped_writer(minimal_escaped_stream);
  minimal_escaped_writer.write_row(std::vector<std::string>({"a,b"}));
  REQUIRE(minimal_escaped_stream.value == "\"a,b\"\n");
}

TEST_CASE("Consume stream width on the next Writer field" * test_suite("Writer")) {
  std::ostringstream raw_output;
  raw_output << std::setfill('_') << std::left << std::setw(4);
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::none>
      raw(raw_output);
  raw.write_row(std::vector<std::string>({"x", "y"}));
  REQUIRE(raw_output.str() == "x___,y\n");
  REQUIRE(raw_output.width() == 0);

  std::ostringstream empty_output;
  empty_output << std::setfill('_') << std::right << std::setw(3);
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::none>
      empty(empty_output);
  empty.write_row(std::vector<std::string>({"", "y"}));
  REQUIRE(empty_output.str() == "___,y\n");
  REQUIRE(empty_output.width() == 0);

  std::ostringstream minimal_output;
  minimal_output << std::setfill('_') << std::left << std::setw(4);
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      minimal(minimal_output);
  minimal.write_row(std::vector<std::string>({"a,b", "z"}));
  REQUIRE(minimal_output.str() == "\"a,b_\",z\n");
  REQUIRE(minimal_output.width() == 0);

  std::ostringstream always_output;
  always_output << std::setfill('_') << std::right << std::setw(4);
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::always>
      always(always_output);
  always.write_row(std::vector<std::string>({"x", "z"}));
  REQUIRE(always_output.str() == "\"___x\",\"z\"\n");
  REQUIRE(always_output.width() == 0);

  DirectWriteTrackingStream direct_output;
  csv2::basic_writer<csv2::delimiter<','>, DirectWriteTrackingStream> direct(direct_output);
  direct.write_row(std::vector<std::string>({"alpha", "beta"}));
  REQUIRE(direct_output.write_calls == 2);

  std::ostringstream formatted_contiguous_output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> formatted_contiguous(
      formatted_contiguous_output);
  formatted_contiguous.write_row(std::vector<FormattedContiguousValue>(1));
  REQUIRE(formatted_contiguous_output.str() == "[formatted]\n");

  std::ostringstream raw_range_output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> raw_range(raw_range_output);
  raw_range.write_row(std::vector<std::vector<char>>(1, std::vector<char>({'r', 'a', 'w'})));
  REQUIRE(raw_range_output.str() == "raw\n");
}

TEST_CASE("Propagate formatted Writer state and preserve insertion exceptions" *
          test_suite("Writer")) {
  typedef csv2::EscapingWriter<csv2::delimiter<';'>, std::ostringstream,
                               csv2::stream_ownership::leave_open>
      EscapingSemicolonWriter;

  std::ostringstream fail_output;
  EscapingSemicolonWriter fail_writer(fail_output);
  fail_writer.write_row(
      std::vector<StatefulFormattedValue>(1, StatefulFormattedValue(std::ios_base::failbit)));
  REQUIRE(fail_output.str() == "a,b");
  REQUIRE(fail_output.fail());
  REQUIRE_FALSE(fail_output.bad());

  std::ostringstream bad_output;
  EscapingSemicolonWriter bad_writer(bad_output);
  bad_writer.write_row(
      std::vector<StatefulFormattedValue>(1, StatefulFormattedValue(std::ios_base::badbit)));
  REQUIRE(bad_output.str() == "a,b");
  REQUIRE(bad_output.bad());

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
  std::ostringstream throwing_output;
  throwing_output.exceptions(std::ios_base::failbit);
  EscapingSemicolonWriter throwing_writer(throwing_output);
  CHECK_THROWS_AS(throwing_writer.write_row(std::vector<StatefulFormattedValue>(
                      1, StatefulFormattedValue(std::ios_base::failbit))),
                  std::ios_base::failure);
  REQUIRE(throwing_output.str() == "a,b");
  REQUIRE(throwing_output.fail());

  std::ostringstream consuming_output;
  consuming_output << std::setw(4);
  EscapingSemicolonWriter consuming_writer(consuming_output);
  CHECK_THROWS_AS(consuming_writer.write_row(std::vector<ConsumingThrowValue>(1)), WriterUserError);
  REQUIRE(consuming_output.width() == 0);

  std::ostringstream unformatted_output;
  unformatted_output << std::setw(4);
  EscapingSemicolonWriter unformatted_writer(unformatted_output);
  CHECK_THROWS_AS(unformatted_writer.write_row(std::vector<UnformattedThrowValue>(1)),
                  WriterUserError);
  REQUIRE(unformatted_output.width() == 4);

  std::ostringstream stateful_throw_output;
  stateful_throw_output.exceptions(std::ios_base::failbit);
  EscapingSemicolonWriter stateful_throw_writer(stateful_throw_output);
  CHECK_THROWS_AS(stateful_throw_writer.write_row(std::vector<StatefulThrowValue>(1)),
                  WriterUserError);
  REQUIRE(stateful_throw_output.fail());
#endif
}

TEST_CASE("Escape CSV fields with explicit minimal and always quote policies" *
          test_suite("Writer")) {
  std::ostringstream minimal_output;
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      minimal(minimal_output);
  minimal.write_row(
      std::vector<std::string>({"plain", "a,b", "a\"b", "line\nbreak", "car\rriage", ""}));
  REQUIRE(minimal_output.str() == "plain,\"a,b\",\"a\"\"b\",\"line\nbreak\",\"car\rriage\",\n");

  std::ostringstream always_output;
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::always>
      always(always_output);
  always.write_row(std::vector<std::string>({"a", "\"b\"", ""}));
  REQUIRE(always_output.str() == "\"a\",\"\"\"b\"\"\",\"\"\n");

  std::ostringstream minimal_empty_output;
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      minimal_empty(minimal_empty_output);
  minimal_empty.write_row(std::vector<std::string>());
  minimal_empty.write_row(std::vector<std::string>(1));
  REQUIRE(minimal_empty_output.str() == "\n\n");

  std::ostringstream always_empty_output;
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     csv2::quote_policy::always>
      always_empty(always_empty_output);
  always_empty.write_row(std::vector<std::string>());
  always_empty.write_row(std::vector<std::string>(1));
  REQUIRE(always_empty_output.str() == "\n\"\"\n");

  std::ostringstream formatted_output;
  formatted_output << std::hex;
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      formatted(formatted_output);
  const std::vector<CommaFormattedValue> values = {{15, 16}};
  formatted.write_row(values);
  REQUIRE(formatted_output.str() == "\"f,10\"\n");

  DirectWriteTrackingStream direct_output;
  csv2::EscapingWriter<csv2::delimiter<','>, DirectWriteTrackingStream,
                       csv2::stream_ownership::leave_open>
      direct(direct_output);
  direct.write_row(std::vector<std::string>({"a,b"}));
  REQUIRE(direct_output.str() == "\"a,b\"\n");
  REQUIRE(direct_output.write_calls == 3);
}

TEST_CASE("Leave borrowed streams open unless close is explicit" * test_suite("Writer")) {
  CountingCloseStream implicit_stream;
  {
    csv2::basic_writer<csv2::delimiter<','>, CountingCloseStream,
                       csv2::stream_ownership::leave_open, csv2::quote_policy::none>
        writer(implicit_stream);
    writer.write_row(std::vector<std::string>({"a"}));
  }
  REQUIRE(implicit_stream.close_count == 0);
  REQUIRE(implicit_stream.str() == "a\n");

  CountingCloseStream explicit_stream;
  {
    csv2::basic_writer<csv2::delimiter<','>, CountingCloseStream,
                       csv2::stream_ownership::leave_open, csv2::quote_policy::none>
        writer(explicit_stream);
    writer.close();
  }
  REQUIRE(explicit_stream.close_count == 1);
}

#if CSV2_HAS_RANGES
TEST_CASE("Write C++20 view pipelines" * test_suite("Writer")) {
  std::ostringstream output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(output);
  const std::vector<std::string> fields = {"a", "skip", "b"};
  auto selected =
      fields | std::views::filter([](const std::string &field) { return field != "skip"; });
  writer.write_row(selected);

  const std::vector<std::string> counted_fields = {"x", "y", "ignored"};
  const auto counted = std::ranges::subrange(std::counted_iterator(counted_fields.begin(), 2),
                                             std::default_sentinel);
  writer.write_row(counted);
  REQUIRE(output.str() == "a,b\nx,y\n");
}
#endif

TEST_CASE("Write a forward-iterable collection of rows" * test_suite("Writer")) {
  std::ostringstream output;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> writer(output);
  const std::forward_list<std::vector<std::string>> rows = {{"a", "b"}, {}, {"c", "d", "e"}};

  writer.write_rows(rows);

  REQUIRE(output.str() == "a,b\n\nc,d,e\n");
}

TEST_CASE("Transfer and release Writer close responsibility exactly once" * test_suite("Writer")) {
  using CountingWriter = csv2::Writer<csv2::delimiter<','>, CountingCloseStream>;
  REQUIRE_FALSE(std::is_copy_constructible<CountingWriter>::value);
  REQUIRE_FALSE(std::is_copy_assignable<CountingWriter>::value);
  REQUIRE(std::is_nothrow_move_constructible<CountingWriter>::value);
  REQUIRE(std::is_nothrow_move_assignable<CountingWriter>::value);

  CountingCloseStream moved_stream;
  {
    CountingWriter source(moved_stream);
    CountingWriter destination(std::move(source));
    source.write_row(std::vector<std::string>({"ignored"}));
    destination.close();
    destination.write_row(std::vector<std::string>({"ignored"}));
  }
  REQUIRE(moved_stream.close_count == 1);
  REQUIRE(moved_stream.str().empty());

  CountingCloseStream source_stream;
  CountingCloseStream replaced_stream;
  {
    CountingWriter source(source_stream);
    CountingWriter destination(replaced_stream);
    destination = std::move(source);
    REQUIRE(replaced_stream.close_count == 1);
  }
  REQUIRE(source_stream.close_count == 1);
  REQUIRE(replaced_stream.close_count == 1);

  CountingCloseStream explicitly_closed_stream;
  {
    CountingWriter writer(explicitly_closed_stream);
    writer.close();
    writer.close();
  }
  REQUIRE(explicitly_closed_stream.close_count == 1);
}

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
TEST_CASE("Report explicit Writer close errors and suppress destructor close errors" *
          test_suite("Writer")) {
  using ThrowingWriter = csv2::Writer<csv2::delimiter<','>, ThrowingCloseStream>;

  ThrowingCloseStream explicit_stream;
  {
    ThrowingWriter writer(explicit_stream);
    REQUIRE_THROWS_AS(writer.close(), CloseError);
  }
  REQUIRE(explicit_stream.close_count == 1);

  ThrowingCloseStream destructor_stream;
  { ThrowingWriter writer(destructor_stream); }
  REQUIRE(destructor_stream.close_count == 1);
}
#endif

#endif
