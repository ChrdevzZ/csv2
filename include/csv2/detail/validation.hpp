#pragma once

#include <csv2/detail/scanner.hpp>
#include <csv2/errors.hpp>

#include <cstddef>
#include <utility>

namespace csv2 {
namespace detail {

inline bool validation_failure(parse_error &error, parse_errc code, std::size_t offset,
                               std::size_t row, std::size_t column) noexcept {
  error.code = code;
  error.byte_offset = offset;
  error.row = row;
  error.column = column;
  return false;
}

struct validation_trim_bounds {
  std::size_t first;
  std::size_t second;
  bool valid;
};

template <class Delimiter, class QuoteCharacter, class TrimPolicy>
validation_trim_bounds trim_preserving_structure(
    const char *buffer, std::size_t start,
    std::size_t end) noexcept(noexcept(TrimPolicy::trim(buffer, start, end))) {
  const std::pair<std::size_t, std::size_t> trimmed = TrimPolicy::trim(buffer, start, end);
  if (trimmed.first > trimmed.second || trimmed.first < start || trimmed.second > end)
    return {start, end, false};

  std::size_t first = trimmed.first;
  for (std::size_t i = start; i < trimmed.first; ++i) {
    const char character = buffer[i];
    if (character == Delimiter::value || character == QuoteCharacter::value || character == '\r' ||
        character == '\n') {
      first = i;
      break;
    }
  }

  std::size_t second = trimmed.second;
  for (std::size_t i = trimmed.second; i < end; ++i) {
    const char character = buffer[i];
    if (character == Delimiter::value || character == QuoteCharacter::value || character == '\r' ||
        character == '\n')
      second = i + 1;
  }
  return {first, second, true};
}

template <class Delimiter, class QuoteCharacter, class TrimPolicy>
bool validate_cell(const char *buffer, std::size_t start, std::size_t end, parse_error &error,
                   std::size_t row,
                   std::size_t column) noexcept(noexcept(TrimPolicy::trim(buffer, start, end))) {
  const validation_trim_bounds bounds =
      trim_preserving_structure<Delimiter, QuoteCharacter, TrimPolicy>(buffer, start, end);
  if (!bounds.valid)
    return validation_failure(error, parse_errc::characters_after_closing_quote, start, row,
                              column);
  if (bounds.first == bounds.second)
    return true;

  if (buffer[bounds.first] != QuoteCharacter::value) {
    for (std::size_t i = start; i < end; ++i) {
      if (buffer[i] == QuoteCharacter::value)
        return validation_failure(error, parse_errc::unexpected_quote, i, row, column);
      if (buffer[i] == '\r' &&
          (QuoteCharacter::value == '\n' || i + 1 >= end || buffer[i + 1] != '\n'))
        return validation_failure(error, parse_errc::bare_carriage_return, i, row, column);
    }
    return true;
  }

  std::size_t closing_quote = bounds.first + 1;
  while (closing_quote < bounds.second) {
    if (buffer[closing_quote] != QuoteCharacter::value) {
      ++closing_quote;
      continue;
    }
    if (closing_quote + 1 < bounds.second && buffer[closing_quote + 1] == QuoteCharacter::value) {
      closing_quote += 2;
      continue;
    }
    break;
  }
  if (closing_quote == bounds.second)
    return validation_failure(error, parse_errc::unclosed_quote, bounds.first, row, column);

  if (closing_quote + 1 < bounds.second) {
    const std::size_t first_suffix = closing_quote + 1;
    std::size_t offending = first_suffix;
    const validation_trim_bounds suffix =
        trim_preserving_structure<Delimiter, QuoteCharacter, TrimPolicy>(buffer, offending,
                                                                         bounds.second);
    if (suffix.valid && suffix.first < suffix.second)
      offending = suffix.first;
    if (buffer[offending] == '\r' && QuoteCharacter::value != '\r' &&
        (offending + 1 >= bounds.second || buffer[offending + 1] != '\n'))
      return validation_failure(error, parse_errc::bare_carriage_return, offending, row, column);
    const parse_errc code = offending != first_suffix && buffer[offending] == QuoteCharacter::value
                                ? parse_errc::invalid_doubled_quote
                                : parse_errc::characters_after_closing_quote;
    return validation_failure(error, code, offending, row, column);
  }
  return true;
}

template <class Delimiter, class QuoteCharacter, class TrimPolicy>
bool validate_csv(const char *buffer, std::size_t size,
                  parse_error &error) noexcept(noexcept(TrimPolicy::trim(buffer, std::size_t(),
                                                                         std::size_t()))) {
  error = parse_error();
  if (!buffer || size == 0)
    return true;

  std::size_t row = 1;
  std::size_t record_start = 0;
  while (record_start < size) {
    const record_bounds record = find_record_bounds<QuoteCharacter>(buffer, size, record_start);
    std::size_t column = 1;
    std::size_t cell_start = record_start;
    while (cell_start <= record.content_end) {
      const cell_bounds cell =
          find_cell_bounds<Delimiter, QuoteCharacter>(buffer, cell_start, record.content_end);
      if (!validate_cell<Delimiter, QuoteCharacter, TrimPolicy>(
              buffer, cell_start, cell.content_end, error, row, column))
        return false;
      if (cell.content_end >= record.content_end)
        break;
      cell_start = cell.content_end + 1;
      ++column;
    }
    if (record.next_start >= size)
      break;
    record_start = record.next_start;
    ++row;
  }
  return true;
}

} // namespace detail
} // namespace csv2
