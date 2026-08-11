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

#define max(left, right) ((left) > (right) ? (left) : (right))

#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/mio.hpp>
#endif

#undef max
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
#include <limits>
#include <list>
#include <iterator>
#include <sstream>
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
using PublicCell =
    csv2::basic_cell<csv2::quote_character<'"'>, csv2::trim_policy::trim_whitespace>;
static_assert(std::is_same<ReaderWithoutHeader::Row, PublicRow>::value,
              "Reader::Row must remain a source-compatible alias");
static_assert(std::is_same<ReaderWithoutHeader::Cell, PublicCell>::value,
              "Reader::Cell must remain a source-compatible alias");
static_assert(sizeof(ReaderWithoutHeader::RowIterator) <= 5 * sizeof(void *),
              "RowIterator must remain a five-word cursor");
static_assert(sizeof(PublicRow::CellIterator) <= 5 * sizeof(void *),
              "CellIterator must not retain redundant range state");

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

class LvalueCloseStream : public std::ostringstream {
public:
  LvalueCloseStream() : closed(false) {}

  void close() & { closed = true; }

  bool closed;
};

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

TEST_CASE("Scan cell boundaries through the shared fast path" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("plain,\"quoted,field\",\"a\"\"b\",tail,");
  REQUIRE(reader.parse(input));
  REQUIRE(read_cells(*reader.begin()) ==
          std::vector<std::string>({"plain", "\"quoted,field\"", "\"a\"b\"", "tail", ""}));
}

TEST_CASE("Validate strict CSV syntax without changing permissive traversal" *
          test_suite("Reader")) {
  const char *valid_inputs[] = {"a,b\n1,2", " \t\"a\"\"b\" \t,c", "a,\"b\nc\",d",
                                "a,\"b\r\nc\",d", "a,\"b\rc\",d", "a,b\n1\n2,3,4"};
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
}

#if CSV2_HAS_EXPECTED
TEST_CASE("Expose C++23 expected adapters when the library provides them" *
          test_suite("Reader")) {
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

TEST_CASE("Expose stable raw byte views and explicit source ownership" * test_suite("Reader")) {
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

#if CSV2_HAS_RANGES
TEST_CASE("Pipe a temporary borrowed Row view" * test_suite("Reader")) {
  ReaderWithoutHeader reader;
  std::string input("a,bb,ccc");
  REQUIRE(reader.parse(input));
  auto sizes = *reader.begin() | std::views::transform([](const PublicCell cell) {
                 return cell.raw_size();
               });
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
  csv2::Writer<csv2::delimiter<','>, DirectWriteTrackingStream> writer(output);
  const std::string row[] = {"alpha", "beta"};
  writer.write_row(row);

  REQUIRE(output.str() == "alpha,beta\n");
  REQUIRE(output.write_calls == 2);

  std::ostringstream numbers;
  csv2::Writer<csv2::delimiter<','>, std::ostringstream> number_writer(numbers);
  number_writer.write_row(std::vector<int>({1, 2}));
  REQUIRE(numbers.str() == "1,2\n");
}

TEST_CASE("Leave borrowed streams open unless close is explicit" * test_suite("Writer")) {
  CountingCloseStream implicit_stream;
  {
    csv2::Writer<csv2::delimiter<','>, CountingCloseStream,
                 csv2::stream_ownership::leave_open>
        writer(implicit_stream);
    writer.write_row(std::vector<std::string>({"a"}));
  }
  REQUIRE(implicit_stream.close_count == 0);
  REQUIRE(implicit_stream.str() == "a\n");

  CountingCloseStream explicit_stream;
  {
    csv2::Writer<csv2::delimiter<','>, CountingCloseStream,
                 csv2::stream_ownership::leave_open>
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
  auto selected = fields | std::views::filter([](const std::string &field) {
                    return field != "skip";
                  });
  writer.write_row(selected);

  const std::vector<std::string> counted_fields = {"x", "y", "ignored"};
  const auto counted = std::ranges::subrange(
      std::counted_iterator(counted_fields.begin(), 2), std::default_sentinel);
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
