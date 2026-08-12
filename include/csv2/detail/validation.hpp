#pragma once

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

template <class TrimPolicy>
bool is_trim_character(const char *buffer, std::size_t offset) noexcept {
  const std::pair<std::size_t, std::size_t> bounds = TrimPolicy::trim(buffer, offset, offset + 1);
  return bounds.first == bounds.second;
}

template <class Delimiter, class QuoteCharacter, class TrimPolicy>
bool validate_csv(const char *buffer, std::size_t size, parse_error &error) noexcept {
  enum state { field_start, unquoted, quoted, after_quote } current = field_start;
  std::size_t row = 1;
  std::size_t column = 1;
  std::size_t opening_quote = 0;

  error = parse_error();
  for (std::size_t i = 0; i < size;) {
    const char character = buffer[i];
    if (current == quoted) {
      if (character == QuoteCharacter::value) {
        if (i + 1 < size && buffer[i + 1] == QuoteCharacter::value) {
          i += 2;
          continue;
        }
        current = after_quote;
      }
      ++i;
      continue;
    }

    if (current == field_start && character == QuoteCharacter::value) {
      current = quoted;
      opening_quote = i;
      ++i;
      continue;
    }
    if (current == after_quote && character == QuoteCharacter::value)
      return validation_failure(error, parse_errc::invalid_doubled_quote, i, row, column);

    if (character == Delimiter::value) {
      ++column;
      current = field_start;
      ++i;
      continue;
    }
    if (character == '\r') {
      if (i + 1 >= size || buffer[i + 1] != '\n')
        return validation_failure(error, parse_errc::bare_carriage_return, i, row, column);
      ++row;
      column = 1;
      current = field_start;
      i += 2;
      continue;
    }
    if (character == '\n') {
      ++row;
      column = 1;
      current = field_start;
      ++i;
      continue;
    }

    if (current == field_start && is_trim_character<TrimPolicy>(buffer, i)) {
      ++i;
      continue;
    }

    if (current == unquoted && character == QuoteCharacter::value)
      return validation_failure(error, parse_errc::unexpected_quote, i, row, column);
    if (current == after_quote && is_trim_character<TrimPolicy>(buffer, i)) {
      ++i;
      continue;
    }
    if (current == after_quote)
      return validation_failure(error, parse_errc::characters_after_closing_quote, i, row, column);
    current = unquoted;
    ++i;
  }

  if (current == quoted)
    return validation_failure(error, parse_errc::unclosed_quote, opening_quote, row, column);
  return true;
}

} // namespace detail
} // namespace csv2
