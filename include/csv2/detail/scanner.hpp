#pragma once

#include <cstddef>
#include <cstring>

namespace csv2 {
namespace detail {

struct record_bounds {
  std::size_t content_end;
  std::size_t next_start;
};

struct cell_bounds {
  std::size_t content_end;
  bool escaped;
};

template <class QuoteCharacter>
record_bounds find_record_bounds(const char *buffer, std::size_t buffer_size,
                                 std::size_t start) noexcept {
  if (!buffer || start >= buffer_size)
    return {buffer_size, buffer_size};

  const char *const record_start = buffer + start;
  const std::size_t remaining = buffer_size - start;
  const char *const newline =
      static_cast<const char *>(std::memchr(record_start, '\n', remaining));
  const std::size_t candidate_length =
      newline ? static_cast<std::size_t>(newline - record_start) : remaining;
  const char *const quote = static_cast<const char *>(
      std::memchr(record_start, QuoteCharacter::value, candidate_length));

  if (!quote) {
    if (!newline)
      return {buffer_size, buffer_size};
    const std::size_t newline_index =
        start + static_cast<std::size_t>(newline - record_start);
    const std::size_t content_end =
        newline_index > start && buffer[newline_index - 1] == '\r' ? newline_index - 1
                                                                    : newline_index;
    return {content_end, newline_index + 1};
  }

  bool quote_opened = false;
  for (std::size_t i = start; i < buffer_size; ++i) {
    if (buffer[i] == QuoteCharacter::value) {
      if (quote_opened && i + 1 < buffer_size && buffer[i + 1] == QuoteCharacter::value) {
        ++i;
        continue;
      }
      quote_opened = !quote_opened;
    } else if (buffer[i] == '\n' && !quote_opened) {
      const std::size_t content_end = i > start && buffer[i - 1] == '\r' ? i - 1 : i;
      return {content_end, i + 1};
    }
  }

  return {buffer_size, buffer_size};
}

template <class Delimiter, class QuoteCharacter>
cell_bounds find_cell_bounds(const char *buffer, std::size_t current,
                             std::size_t end) noexcept {
  if (!buffer || current >= end)
    return {end, false};

  const char *const first = buffer + current;
  const std::size_t remaining = end - current;
  const char *const delimiter =
      static_cast<const char *>(std::memchr(first, Delimiter::value, remaining));
  const char *const quote =
      static_cast<const char *>(std::memchr(first, QuoteCharacter::value, remaining));

  if (!quote || (delimiter && delimiter < quote))
    return {delimiter ? static_cast<std::size_t>(delimiter - buffer) : end, false};

  bool quote_opened = false;
  bool escaped = false;
  for (std::size_t i = current; i < end; ++i) {
    if (buffer[i] == QuoteCharacter::value) {
      const bool adjacent_quote = i + 1 < end && buffer[i + 1] == QuoteCharacter::value;
      if (adjacent_quote)
        escaped = true;
      if (quote_opened && adjacent_quote) {
        ++i;
        continue;
      }
      quote_opened = !quote_opened;
    } else if (buffer[i] == Delimiter::value && !quote_opened) {
      return {i, escaped};
    }
  }
  return {end, escaped};
}

} // namespace detail
} // namespace csv2
