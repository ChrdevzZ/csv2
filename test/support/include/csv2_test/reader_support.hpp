#ifndef CSV2_TEST_READER_SUPPORT_HPP
#define CSV2_TEST_READER_SUPPORT_HPP

#include <csv2_test/csv2_headers.hpp>

#include <cstddef>
#include <iterator>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#if CSV2_HAS_RANGES
#include <concepts>
#include <ranges>
#endif

namespace csv2_test {

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
#if CSV2_HAS_MMAP && !defined(_WIN32)
static_assert(mio::detail::mmap_protection(mio::access_mode::read) == PROT_READ,
              "read mappings must request read access");
static_assert(mio::detail::mmap_protection(mio::access_mode::write) == (PROT_READ | PROT_WRITE),
              "writable mappings must also remain readable");
#endif
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

struct AbsoluteOffsetTrim {
  static const char *&expected_buffer() {
    static const char *value = nullptr;
    return value;
  }

  static std::pair<std::size_t, std::size_t> trim(const char *buffer, std::size_t start,
                                                  std::size_t end) {
    if (buffer == expected_buffer() && start == 2 && start < end)
      ++start;
    return std::make_pair(start, end);
  }
};

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
  static bool &enabled() {
    static bool value = true;
    return value;
  }
  static std::pair<std::size_t, std::size_t> trim(const char *, std::size_t start,
                                                  std::size_t end) {
    if (enabled())
      throw std::runtime_error("trim failure");
    return std::make_pair(start, end);
  }
};
#endif

} // namespace csv2_test

#endif
