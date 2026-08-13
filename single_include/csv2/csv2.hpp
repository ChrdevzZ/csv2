#pragma once

#include <cstring>
// #include <csv2/detail/config.hpp>

// Normalize the language mode. MSVC reports its selected standard through
// _MSVC_LANG unless /Zc:__cplusplus is enabled.
#if defined(_MSVC_LANG)
#define CSV2_CPLUSPLUS _MSVC_LANG
#else
#define CSV2_CPLUSPLUS __cplusplus
#endif

#define CSV2_DETAIL_HAS_VERSION_HEADER 0
#define CSV2_DETAIL_HAS_STRING_VIEW_HEADER 0

#if CSV2_CPLUSPLUS >= 201703L
#if defined(__has_include)
#if __has_include(<string_view>)
#undef CSV2_DETAIL_HAS_STRING_VIEW_HEADER
#define CSV2_DETAIL_HAS_STRING_VIEW_HEADER 1
#endif
#else
#undef CSV2_DETAIL_HAS_STRING_VIEW_HEADER
#define CSV2_DETAIL_HAS_STRING_VIEW_HEADER 1
#endif
#endif

#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS >= 202002L &&              \
    defined(__has_include) && !defined(CSV2_DETAIL_FORCE_HEADER_PROBES)
#if __has_include(<version>)
#undef CSV2_DETAIL_HAS_VERSION_HEADER
#define CSV2_DETAIL_HAS_VERSION_HEADER 1
#include <version>
#endif
#endif

// A conforming library can provide an SD-6 macro only from the facility's
// header, and a partial <version> may omit a facility that its own header
// supplies. Probe each missing macro independently and gate every API on the
// resulting macro value below.
#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS >= 201703L
#if defined(__has_include)
#if (!defined(__cpp_lib_string_view) || __cpp_lib_string_view < 201606L) &&                        \
    CSV2_DETAIL_HAS_STRING_VIEW_HEADER
#include <string_view>
#endif
#if (!defined(__cpp_lib_filesystem) || __cpp_lib_filesystem < 201703L) && __has_include(<filesystem>)
#include <filesystem>
#endif
#if (!defined(__cpp_lib_to_chars) || __cpp_lib_to_chars < 201611L) && __has_include(<charconv>)
#include <charconv>
#endif
#if (!defined(__cpp_lib_memory_resource) || __cpp_lib_memory_resource < 201603L) &&                \
    __has_include(<memory_resource>)
#include <memory_resource>
#endif
#else
#include <charconv>
#include <filesystem>
#include <memory_resource>
#include <string_view>
#endif
#endif

#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS >= 202002L
#if defined(__has_include)
#if (!defined(__cpp_lib_span) || __cpp_lib_span < 202002L) && __has_include(<span>)
#include <span>
#endif
#if (!defined(__cpp_lib_ranges) || __cpp_lib_ranges < 201911L ||                                   \
     !defined(__cpp_lib_ranges_to_container)) &&                                                   \
    __has_include(<ranges>)
#include <ranges>
#endif
#else
#include <ranges>
#include <span>
#endif
#endif

#if !defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES) && CSV2_CPLUSPLUS > 202002L
#if defined(__has_include)
#if (!defined(__cpp_lib_expected) || __cpp_lib_expected < 202202L) && __has_include(<expected>)
#include <expected>
#endif
#else
#include <expected>
#endif
#endif

#if defined(__has_cpp_attribute)
#if CSV2_CPLUSPLUS >= 201703L && __has_cpp_attribute(nodiscard)
#define CSV2_NODISCARD [[nodiscard]]
#else
#define CSV2_NODISCARD
#endif
#else
#define CSV2_NODISCARD
#endif

#if CSV2_CPLUSPLUS >= 201402L
#define CSV2_CONSTEXPR14 constexpr
#else
#define CSV2_CONSTEXPR14
#endif

#if CSV2_CPLUSPLUS >= 201703L
#define CSV2_CONSTEXPR17 constexpr
#else
#define CSV2_CONSTEXPR17
#endif

#if defined(_MSC_VER)
#define CSV2_FORCE_INLINE __forceinline
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__OPTIMIZE__)
#define CSV2_FORCE_INLINE inline __attribute__((always_inline))
#else
#define CSV2_FORCE_INLINE inline
#endif

#if defined(CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES)
#define CSV2_HAS_STRING_VIEW 0
#define CSV2_HAS_FILESYSTEM 0
#define CSV2_HAS_CHARCONV 0
#define CSV2_HAS_MEMORY_RESOURCE 0
#define CSV2_HAS_SPAN 0
#define CSV2_HAS_RANGES 0
#define CSV2_HAS_EXPECTED 0
#define CSV2_HAS_RANGES_TO_CONTAINER 0
#else
#if defined(__cpp_lib_string_view) && __cpp_lib_string_view >= 201606L
#define CSV2_HAS_STRING_VIEW 1
#else
#define CSV2_HAS_STRING_VIEW 0
#endif

#if defined(__cpp_lib_filesystem) && __cpp_lib_filesystem >= 201703L
#define CSV2_HAS_FILESYSTEM 1
#else
#define CSV2_HAS_FILESYSTEM 0
#endif

#if defined(__cpp_lib_to_chars) && __cpp_lib_to_chars >= 201611L
#define CSV2_HAS_CHARCONV 1
#else
#define CSV2_HAS_CHARCONV 0
#endif

#if defined(__cpp_lib_memory_resource) && __cpp_lib_memory_resource >= 201603L
#define CSV2_HAS_MEMORY_RESOURCE 1
#else
#define CSV2_HAS_MEMORY_RESOURCE 0
#endif

#if defined(__cpp_lib_span) && __cpp_lib_span >= 202002L
#define CSV2_HAS_SPAN 1
#else
#define CSV2_HAS_SPAN 0
#endif

#if defined(__cpp_lib_ranges) && __cpp_lib_ranges >= 201911L
#define CSV2_HAS_RANGES 1
#else
#define CSV2_HAS_RANGES 0
#endif

#if defined(__cpp_lib_expected) && __cpp_lib_expected >= 202202L
#define CSV2_HAS_EXPECTED 1
#else
#define CSV2_HAS_EXPECTED 0
#endif

#if defined(__cpp_lib_ranges_to_container) && __cpp_lib_ranges_to_container >= 202202L
#define CSV2_HAS_RANGES_TO_CONTAINER 1
#else
#define CSV2_HAS_RANGES_TO_CONTAINER 0
#endif
#endif

#ifndef CSV2_HAS_MMAP
#if defined(__has_include)
#if defined(_WIN32)
#if __has_include(<windows.h>)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#elif __has_include(<sys/mman.h>) && __has_include(<fcntl.h>) &&                                 \
    __has_include(<sys/stat.h>) && __has_include(<unistd.h>)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#elif defined(_WIN32) || defined(__unix__) || defined(__unix) || defined(__APPLE__)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#endif

// #include <csv2/detail/conversion.hpp>

// #include <csv2/detail/config.hpp>
// #include <csv2/errors.hpp>

#include <cstddef>

namespace csv2 {

enum class parse_errc {
  none,
  unexpected_quote,
  unclosed_quote,
  invalid_doubled_quote,
  characters_after_closing_quote,
  bare_carriage_return
};

struct parse_error {
  parse_errc code{parse_errc::none};
  std::size_t byte_offset{0};
  std::size_t row{0};
  std::size_t column{0};
};

enum class conversion_errc {
  none,
  invalid_argument,
  invalid_base,
  result_out_of_range,
  trailing_characters
};

struct conversion_error {
  conversion_errc code{conversion_errc::none};
  std::size_t byte_offset{0};
};

} // namespace csv2


#if CSV2_HAS_CHARCONV
#include <charconv>
#endif

#include <cstddef>
#include <limits>
#include <system_error>
#include <type_traits>

namespace csv2 {
namespace detail {

template <class T>
struct is_csv_integer
    : std::integral_constant<
          bool, std::is_integral<T>::value && !std::is_same<T, bool>::value &&
                    !std::is_same<T, char>::value && !std::is_same<T, signed char>::value &&
                    !std::is_same<T, unsigned char>::value && !std::is_same<T, wchar_t>::value &&
                    !std::is_same<T, char16_t>::value && !std::is_same<T, char32_t>::value
#if defined(__cpp_char8_t)
                    && !std::is_same<T, char8_t>::value
#endif
          > {
};

inline int integer_digit(char character) noexcept {
  if (character >= '0' && character <= '9')
    return character - '0';
  if (character >= 'a' && character <= 'z')
    return character - 'a' + 10;
  if (character >= 'A' && character <= 'Z')
    return character - 'A' + 10;
  return -1;
}

inline bool conversion_failure(conversion_error &error, conversion_errc code,
                               std::size_t offset) noexcept {
  error.code = code;
  error.byte_offset = offset;
  return false;
}

template <class Integer>
bool parse_integer_fallback(const char *first, const char *last, Integer &output,
                            conversion_error &error, int base) noexcept {
  typedef typename std::make_unsigned<Integer>::type unsigned_type;
  if (first == last)
    return conversion_failure(error, conversion_errc::invalid_argument, 0);

  const char *cursor = first;
  bool negative = false;
  if (*cursor == '-') {
    if (!std::is_signed<Integer>::value)
      return conversion_failure(error, conversion_errc::invalid_argument, 0);
    negative = true;
    ++cursor;
  } else if (*cursor == '+') {
    return conversion_failure(error, conversion_errc::invalid_argument, 0);
  }
  if (cursor == last)
    return conversion_failure(error, conversion_errc::invalid_argument, 0);

  const unsigned_type maximum = static_cast<unsigned_type>((std::numeric_limits<Integer>::max)());
  const unsigned_type limit = negative ? static_cast<unsigned_type>(maximum + 1) : maximum;
  unsigned_type magnitude = 0;
  bool overflow = false;
  const char *digits_begin = cursor;
  for (; cursor != last; ++cursor) {
    const int digit = integer_digit(*cursor);
    if (digit < 0 || digit >= base)
      break;
    const unsigned_type unsigned_digit = static_cast<unsigned_type>(digit);
    if (!overflow && magnitude > static_cast<unsigned_type>((limit - unsigned_digit) /
                                                            static_cast<unsigned_type>(base))) {
      overflow = true;
    } else if (!overflow) {
      magnitude =
          static_cast<unsigned_type>(magnitude * static_cast<unsigned_type>(base) + unsigned_digit);
    }
  }

  if (cursor == digits_begin)
    return conversion_failure(error, conversion_errc::invalid_argument, 0);
  if (overflow)
    return conversion_failure(error, conversion_errc::result_out_of_range,
                              static_cast<std::size_t>(cursor - first));
  if (cursor != last)
    return conversion_failure(error, conversion_errc::trailing_characters,
                              static_cast<std::size_t>(cursor - first));

  Integer converted;
  if (negative) {
    converted = magnitude == limit ? (std::numeric_limits<Integer>::min)()
                                   : static_cast<Integer>(-static_cast<Integer>(magnitude));
  } else {
    converted = static_cast<Integer>(magnitude);
  }
  output = converted;
  error = conversion_error();
  return true;
}

template <class Integer>
bool parse_integer(const char *first, const char *last, Integer &output, conversion_error &error,
                   int base) noexcept {
  if (base < 2 || base > 36)
    return conversion_failure(error, conversion_errc::invalid_base, 0);

#if CSV2_HAS_CHARCONV
  Integer converted{};
  const std::from_chars_result result = std::from_chars(first, last, converted, base);
  const std::size_t offset = static_cast<std::size_t>(result.ptr - first);
  if (result.ec == std::errc::invalid_argument)
    return conversion_failure(error, conversion_errc::invalid_argument, offset);
  if (result.ec == std::errc::result_out_of_range)
    return conversion_failure(error, conversion_errc::result_out_of_range, offset);
  if (result.ptr != last)
    return conversion_failure(error, conversion_errc::trailing_characters, offset);
  output = converted;
  error = conversion_error();
  return true;
#else
  return parse_integer_fallback(first, last, output, error, base);
#endif
}

} // namespace detail
} // namespace csv2

// #include <csv2/detail/output.hpp>

// #include <csv2/detail/config.hpp>

#include <cstddef>
#include <iterator>
#include <type_traits>
#include <utility>

namespace csv2 {
namespace detail {

template <unsigned Priority> struct output_priority : output_priority<Priority - 1> {};
template <> struct output_priority<0> {};

template <typename Container>
CSV2_FORCE_INLINE auto reserve_for_append_impl(Container &output, std::size_t additional,
                                               output_priority<2>)
    -> decltype(output.reserve(output.size() + additional), void()) {
  output.reserve(output.size() + additional);
}

template <typename Container>
CSV2_FORCE_INLINE auto
reserve_for_append_impl(Container &output, std::size_t additional,
                        output_priority<1>) -> decltype(output.reserve(additional), void()) {
  output.reserve(additional);
}

template <typename Container>
CSV2_FORCE_INLINE void reserve_for_append_impl(Container &, std::size_t, output_priority<0>) {}

template <typename Container>
CSV2_FORCE_INLINE void reserve_for_append(Container &output, std::size_t additional) {
  reserve_for_append_impl(output, additional, output_priority<2>());
}

template <typename Container>
CSV2_FORCE_INLINE auto append_range_impl(Container &output, const char *first, const char *last,
                                         output_priority<3>)
    -> decltype(output.append(first, static_cast<std::size_t>(last - first)), void()) {
  output.append(first, static_cast<std::size_t>(last - first));
}

template <typename Container>
CSV2_FORCE_INLINE auto append_range_impl(Container &output, const char *first, const char *last,
                                         output_priority<2>)
    -> decltype(output.insert(output.end(), first, last), void()) {
  output.insert(output.end(), first, last);
}

template <typename Container>
CSV2_FORCE_INLINE auto append_range_impl(Container &output, const char *first, const char *last,
                                         output_priority<1>) -> decltype(output.push_back(*first),
                                                                         void()) {
  while (first != last) {
    output.push_back(*first);
    ++first;
  }
}

template <typename Container>
CSV2_FORCE_INLINE void append_range(Container &output, const char *first, const char *last) {
  append_range_impl(output, first, last, output_priority<3>());
}

template <typename Container> class supports_push_back {
  template <typename Type>
  static auto check(int) -> decltype(std::declval<Type &>().push_back(char()), std::true_type());
  template <typename> static std::false_type check(...);

public:
  static const bool value = decltype(check<Container>(0))::value;
};

template <typename Container>
CSV2_FORCE_INLINE void append_optimized_range_impl(Container &output, const char *first,
                                                   const char *last, std::true_type) {
  if (last - first < 64) {
    while (first != last) {
      output.push_back(*first);
      ++first;
    }
    return;
  }
  append_range(output, first, last);
}

template <typename Container>
CSV2_FORCE_INLINE void append_optimized_range_impl(Container &output, const char *first,
                                                   const char *last, std::false_type) {
  append_range(output, first, last);
}

template <typename Container>
CSV2_FORCE_INLINE void append_optimized_range(Container &output, const char *first,
                                              const char *last) {
  append_optimized_range_impl(output, first, last,
                              std::integral_constant<bool, supports_push_back<Container>::value>());
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded_segments(Container &output, const char *buffer,
                                               std::size_t first, std::size_t last, char quote) {
  std::size_t segment_start = first;
  for (std::size_t i = first; i < last; ++i) {
    if (buffer[i] == quote && i + 1 < last && buffer[i + 1] == quote) {
      append_range(output, buffer + segment_start, buffer + i + 1);
      ++i;
      segment_start = i + 1;
    }
  }
  if (segment_start < last)
    append_range(output, buffer + segment_start, buffer + last);
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded_impl(Container &output, const char *buffer, std::size_t first,
                                           std::size_t last, char quote, std::true_type) {
  if (last - first < 64) {
    for (std::size_t i = first; i < last; ++i) {
      output.push_back(buffer[i]);
      if (buffer[i] == quote && i + 1 < last && buffer[i + 1] == quote)
        ++i;
    }
    return;
  }
  append_decoded_segments(output, buffer, first, last, quote);
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded_impl(Container &output, const char *buffer, std::size_t first,
                                           std::size_t last, char quote, std::false_type) {
  append_decoded_segments(output, buffer, first, last, quote);
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded(Container &output, const char *buffer, std::size_t first,
                                      std::size_t last, char quote) {
  append_decoded_impl(output, buffer, first, last, quote,
                      std::integral_constant<bool, supports_push_back<Container>::value>());
}

template <typename Container> class container_output_iterator {
public:
  using iterator_category = std::output_iterator_tag;
  using value_type = void;
  using difference_type = void;
  using pointer = void;
  using reference = void;

  explicit container_output_iterator(Container &output) : output_(&output) {}

  container_output_iterator &operator=(char value) {
    append_range(*output_, &value, &value + 1);
    return *this;
  }
  container_output_iterator &operator*() { return *this; }
  container_output_iterator &operator++() { return *this; }
  container_output_iterator operator++(int) { return *this; }

private:
  Container *output_;
};

template <typename Container>
container_output_iterator<Container> container_inserter(Container &output) {
  return container_output_iterator<Container>(output);
}

template <typename OutputIt>
OutputIt copy_chars(const char *first, const char *last, OutputIt output) {
  while (first != last) {
    *output = *first;
    ++output;
    ++first;
  }
  return output;
}

} // namespace detail
} // namespace csv2

// #include <csv2/detail/scanner.hpp>

// #include <csv2/detail/config.hpp>

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

template <class Delimiter, class QuoteCharacter>
CSV2_FORCE_INLINE cell_bounds find_cell_bounds_scalar(const char *buffer, std::size_t current,
                                                      std::size_t end) noexcept {
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
      if (quote_opened) {
        if (i + 1 == end)
          return {end, escaped};
        if (buffer[i + 1] == Delimiter::value)
          return {i + 1, escaped};
      }
      quote_opened = !quote_opened;
    } else if (buffer[i] == Delimiter::value && !quote_opened) {
      return {i, escaped};
    }
  }
  return {end, escaped};
}

template <class Delimiter, class QuoteCharacter>
CSV2_FORCE_INLINE cell_bounds find_quoted_cell_bounds_scalar(const char *buffer,
                                                             std::size_t current,
                                                             std::size_t end) noexcept {
  bool quote_opened = true;
  bool escaped = current + 1 < end && buffer[current + 1] == QuoteCharacter::value;
  for (std::size_t i = current + 1; i < end; ++i) {
    if (buffer[i] == QuoteCharacter::value) {
      const bool adjacent_quote = i + 1 < end && buffer[i + 1] == QuoteCharacter::value;
      if (adjacent_quote)
        escaped = true;
      if (quote_opened && adjacent_quote) {
        ++i;
        continue;
      }
      if (quote_opened) {
        if (i + 1 == end)
          return {end, escaped};
        if (buffer[i + 1] == Delimiter::value)
          return {i + 1, escaped};
      }
      quote_opened = !quote_opened;
    } else if (buffer[i] == Delimiter::value && !quote_opened) {
      return {i, escaped};
    }
  }
  return {end, escaped};
}

template <class QuoteCharacter>
record_bounds find_record_bounds(const char *buffer, std::size_t buffer_size,
                                 std::size_t start) noexcept {
  if (!buffer || start >= buffer_size)
    return {buffer_size, buffer_size};

  const char *const record_start = buffer + start;
  const std::size_t remaining = buffer_size - start;
  const char *const newline = static_cast<const char *>(std::memchr(record_start, '\n', remaining));
  const std::size_t candidate_length =
      newline ? static_cast<std::size_t>(newline - record_start) : remaining;
  // Include the record-separator candidate so a newline quote policy takes
  // the same quote-first path as the scalar state machine below.
  const std::size_t quote_length = candidate_length + (newline ? std::size_t{1} : 0);
  const char *const quote =
      static_cast<const char *>(std::memchr(record_start, QuoteCharacter::value, quote_length));

  if (!quote) {
    if (!newline)
      return {buffer_size, buffer_size};
    const std::size_t newline_index = start + static_cast<std::size_t>(newline - record_start);
    const std::size_t content_end = newline_index > start && buffer[newline_index - 1] == '\r'
                                        ? newline_index - 1
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
      // A carriage return that also served as the closing quote belongs to
      // the record; only an ordinary CRLF terminator drops the CR byte.
      const bool strip_carriage_return =
          QuoteCharacter::value != '\r' && i > start && buffer[i - 1] == '\r';
      const std::size_t content_end = strip_carriage_return ? i - 1 : i;
      return {content_end, i + 1};
    }
  }

  return {buffer_size, buffer_size};
}

template <class Delimiter, class QuoteCharacter>
CSV2_FORCE_INLINE cell_bounds find_cell_bounds(const char *buffer, std::size_t current,
                                               std::size_t end) noexcept {
  if (!buffer || current >= end)
    return {end, false};

  const std::size_t remaining = end - current;
  // Scan a small prefix once. This preserves the low overhead of the scalar
  // path for ordinary short fields and only selects memchr after proving that
  // the field has a long delimiter/quote-free prefix.
  const std::size_t prefix_end = current + (remaining < 64 ? remaining : 64);
  if (buffer[current] == QuoteCharacter::value)
    return find_quoted_cell_bounds_scalar<Delimiter, QuoteCharacter>(buffer, current, end);
  for (std::size_t i = current; i < prefix_end; ++i) {
    if (buffer[i] == QuoteCharacter::value)
      return find_cell_bounds_scalar<Delimiter, QuoteCharacter>(buffer, current, end);
    if (buffer[i] == Delimiter::value)
      return {i, false};
  }
  if (prefix_end == end)
    return {end, false};

  const char *const first = buffer + prefix_end;
  const std::size_t tail_size = end - prefix_end;
  const char *const delimiter =
      static_cast<const char *>(std::memchr(first, Delimiter::value, tail_size));
  const std::size_t candidate_length =
      delimiter ? static_cast<std::size_t>(delimiter - first) : tail_size;
  // Include the delimiter candidate itself in the quote probe. This matters
  // when a supported policy deliberately assigns the same character to both
  // roles: the scalar path gives quote handling precedence, so the fast path
  // must fall back instead of accepting that byte as an unquoted delimiter.
  const std::size_t quote_length = candidate_length + (delimiter ? std::size_t{1} : 0);
  const char *const quote =
      static_cast<const char *>(std::memchr(first, QuoteCharacter::value, quote_length));

  if (!quote)
    return {delimiter ? static_cast<std::size_t>(delimiter - buffer) : end, false};
  return find_cell_bounds_scalar<Delimiter, QuoteCharacter>(buffer, current, end);
}

} // namespace detail
} // namespace csv2

// #include <csv2/detail/validation.hpp>

// #include <csv2/detail/scanner.hpp>
// #include <csv2/errors.hpp>

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


#if CSV2_HAS_MMAP
// #include <csv2/mio.hpp>

// #include <csv2/detail/config.hpp>

#if CSV2_HAS_MMAP

/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_MMAP_HEADER
#define MIO_MMAP_HEADER

// #include "mio/page.hpp"
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_PAGE_HEADER
#define MIO_PAGE_HEADER

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace mio {

/**
 * This is used by `basic_mmap` to determine whether to create a read-only or
 * a read-write memory mapping.
 */
enum class access_mode { read, write };

/**
 * Determines the operating system's page allocation granularity.
 *
 * On the first call to this function, it invokes the operating system specific syscall
 * to determine the page size, caches the value, and returns it. Any subsequent call to
 * this function serves the cached value, so no further syscalls are made.
 */
inline size_t page_size() {
  static const size_t page_size = [] {
#ifdef _WIN32
    SYSTEM_INFO SystemInfo;
    GetSystemInfo(&SystemInfo);
    return SystemInfo.dwAllocationGranularity;
#else
    return sysconf(_SC_PAGE_SIZE);
#endif
  }();
  return page_size;
}

/**
 * Alligns `offset` to the operating's system page size such that it subtracts the
 * difference until the nearest page boundary before `offset`, or does nothing if
 * `offset` is already page aligned.
 */
inline size_t make_offset_page_aligned(size_t offset) noexcept {
  const size_t page_size_ = page_size();
  // Use integer division to round down to the nearest page alignment.
  return offset / page_size_ * page_size_;
}

} // namespace mio

#endif // MIO_PAGE_HEADER

#include <cstdint>
// #include <csv2/detail/config.hpp>
#include <iterator>
#include <limits>
#include <string>
#if CSV2_DETAIL_HAS_STRING_VIEW_HEADER
#include <string_view>
#endif
#include <system_error>
#if CSV2_HAS_FILESYSTEM
#include <filesystem>
#endif

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif // WIN32_LEAN_AND_MEAN
#include <windows.h>
#else // ifdef _WIN32
#define INVALID_HANDLE_VALUE -1
#endif // ifdef _WIN32

namespace mio {

// This value may be provided as the `length` parameter to the constructor or
// `map`, in which case a memory mapping of the entire file is created.
enum { map_entire_file = 0 };

#ifdef _WIN32
using file_handle_type = HANDLE;
#else
using file_handle_type = int;
#endif

// This value represents an invalid file handle type. This can be used to
// determine whether `basic_mmap::file_handle` is valid, for example.
const static file_handle_type invalid_handle = INVALID_HANDLE_VALUE;

// Windows file-mapping APIs use nullptr rather than INVALID_HANDLE_VALUE.
#ifdef _WIN32
const static file_handle_type invalid_mapping_handle = nullptr;
#else
const static file_handle_type invalid_mapping_handle = invalid_handle;
#endif

template <access_mode AccessMode, typename ByteT> struct basic_mmap {
  using value_type = ByteT;
  using size_type = size_t;
  using reference = value_type &;
  using const_reference = const value_type &;
  using pointer = value_type *;
  using const_pointer = const value_type *;
  using difference_type = std::ptrdiff_t;
  using iterator = pointer;
  using const_iterator = const_pointer;
  using reverse_iterator = std::reverse_iterator<iterator>;
  using const_reverse_iterator = std::reverse_iterator<const_iterator>;
  using iterator_category = std::random_access_iterator_tag;
  using handle_type = file_handle_type;

  static_assert(sizeof(ByteT) == sizeof(char), "ByteT must be the same size as char.");

private:
  // Points to the first requested byte, and not to the actual start of the mapping.
  pointer data_ = nullptr;

  // Length--in bytes--requested by user (which may not be the length of the
  // full mapping) and the length of the full mapping.
  size_type length_ = 0;
  size_type mapped_length_ = 0;

  // Letting user map a file using both an existing file handle and a path
  // introcudes some complexity (see `is_handle_internal_`).
  // On POSIX, we only need a file handle to create a mapping, while on
  // Windows systems the file handle is necessary to retrieve a file mapping
  // handle, but any subsequent operations on the mapped region must be done
  // through the latter.
  handle_type file_handle_ = INVALID_HANDLE_VALUE;
#ifdef _WIN32
  handle_type file_mapping_handle_ = invalid_mapping_handle;
#endif

  // Letting user map a file using both an existing file handle and a path
  // introcudes some complexity in that we must not close the file handle if
  // user provided it, but we must close it if we obtained it using the
  // provided path. For this reason, this flag is used to determine when to
  // close `file_handle_`.
  bool is_handle_internal_ = false;

public:
  /**
   * The default constructed mmap object is in a non-mapped state, that is,
   * any operation that attempts to access nonexistent underlying data will
   * result in undefined behaviour/segmentation faults.
   */
  basic_mmap() = default;

#ifdef __cpp_exceptions
  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  template <typename String>
  basic_mmap(const String &path, const size_type offset = 0,
             const size_type length = map_entire_file) {
    std::error_code error;
    map(path, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }

  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  basic_mmap(const handle_type handle, const size_type offset = 0,
             const size_type length = map_entire_file) {
    std::error_code error;
    map(handle, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }
#endif // __cpp_exceptions

  /**
   * `basic_mmap` has single-ownership semantics, so transferring ownership
   * may only be accomplished by moving the object.
   */
  basic_mmap(const basic_mmap &) = delete;
  basic_mmap(basic_mmap &&);
  basic_mmap &operator=(const basic_mmap &) = delete;
  basic_mmap &operator=(basic_mmap &&);

  /**
   * If this is a read-write mapping, the destructor invokes sync. Regardless
   * of the access mode, unmap is invoked as a final step.
   */
  ~basic_mmap();

  /**
   * On UNIX systems 'file_handle' and 'mapping_handle' are the same. On Windows,
   * however, a mapped region of a file gets its own handle, which is returned by
   * 'mapping_handle'.
   */
  handle_type file_handle() const noexcept { return file_handle_; }
  handle_type mapping_handle() const noexcept;

  /** Returns whether a valid memory mapping has been created. */
  bool is_open() const noexcept { return file_handle_ != invalid_handle; }

  /**
   * Returns true if no mapping was established, that is, conceptually the
   * same as though the length that was mapped was 0. This function is
   * provided so that this class has Container semantics.
   */
  bool empty() const noexcept { return length() == 0; }

  /** Returns true if a mapping was established. */
  bool is_mapped() const noexcept;

  /**
   * `size` and `length` both return the logical length, i.e. the number of bytes
   * user requested to be mapped, while `mapped_length` returns the actual number of
   * bytes that were mapped which is a multiple of the underlying operating system's
   * page allocation granularity.
   */
  size_type size() const noexcept { return length(); }
  size_type length() const noexcept { return length_; }
  size_type mapped_length() const noexcept { return mapped_length_; }

  /** Returns the offset relative to the start of the mapping. */
  size_type mapping_offset() const noexcept { return mapped_length_ - length_; }

  /**
   * Returns a pointer to the first requested byte, or `nullptr` if no memory mapping
   * exists.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  pointer data() noexcept {
    return data_;
  }
  const_pointer data() const noexcept { return data_; }

  /**
   * Returns an iterator to the first requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  iterator begin() noexcept {
    return data();
  }
  const_iterator begin() const noexcept { return data(); }
  const_iterator cbegin() const noexcept { return data(); }

  /**
   * Returns an iterator one past the last requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  iterator end() noexcept {
    return data() + length();
  }
  const_iterator end() const noexcept { return data() + length(); }
  const_iterator cend() const noexcept { return data() + length(); }

  /**
   * Returns a reverse iterator to the last memory mapped byte, if a valid
   * memory mapping exists, otherwise this function call is undefined
   * behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rbegin() noexcept {
    return reverse_iterator(end());
  }
  const_reverse_iterator rbegin() const noexcept { return const_reverse_iterator(end()); }
  const_reverse_iterator crbegin() const noexcept { return const_reverse_iterator(end()); }

  /**
   * Returns a reverse iterator past the first mapped byte, if a valid memory
   * mapping exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rend() noexcept {
    return reverse_iterator(begin());
  }
  const_reverse_iterator rend() const noexcept { return const_reverse_iterator(begin()); }
  const_reverse_iterator crend() const noexcept { return const_reverse_iterator(begin()); }

  /**
   * Returns a reference to the `i`th byte from the first requested byte (as returned
   * by `data`). If this is invoked when no valid memory mapping has been created
   * prior to this call, undefined behaviour ensues.
   */
  reference operator[](const size_type i) noexcept { return data_[i]; }
  const_reference operator[](const size_type i) const noexcept { return data_[i]; }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  template <typename String>
  void map(const String &path, const size_type offset, const size_type length,
           std::error_code &error);

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  template <typename String> void map(const String &path, std::error_code &error) {
    map(path, 0, map_entire_file, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is
   * unsuccesful, the reason is reported via `error` and the object remains in
   * a state as if this function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  void map(const handle_type handle, const size_type offset, const size_type length,
           std::error_code &error);

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is
   * unsuccesful, the reason is reported via `error` and the object remains in
   * a state as if this function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  void map(const handle_type handle, std::error_code &error) {
    map(handle, 0, map_entire_file, error);
  }

  /**
   * If a valid memory mapping has been created prior to this call, this call
   * instructs the kernel to unmap the memory region and disassociate this object
   * from the file.
   *
   * The file handle associated with the file that is mapped is only closed if the
   * mapping was created using a file path. If, on the other hand, an existing
   * file handle was used to create the mapping, the file handle is not closed.
   */
  void unmap();

  void swap(basic_mmap &other);

  /** Flushes the memory mapped page to disk. Errors are reported via `error`. */
  template <access_mode A = AccessMode>
  typename std::enable_if<A == access_mode::write, void>::type sync(std::error_code &error);

  /**
   * All operators compare the address of the first byte and size of the two mapped
   * regions.
   */

private:
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  pointer get_mapping_start() noexcept {
    return !data() ? nullptr : data() - mapping_offset();
  }

  const_pointer get_mapping_start() const noexcept {
    return !data() ? nullptr : data() - mapping_offset();
  }

  /**
   * The destructor syncs changes to disk if `AccessMode` is `write`, but not
   * if it's `read`, but since the destructor cannot be templated, we need to
   * do SFINAE in a dedicated function, where one syncs and the other is a noop.
   */
  template <access_mode A = AccessMode>
  typename std::enable_if<A == access_mode::write, void>::type conditional_sync();
  template <access_mode A = AccessMode>
  typename std::enable_if<A == access_mode::read, void>::type conditional_sync();
};

template <access_mode AccessMode, typename ByteT>
bool operator==(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator!=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator<(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator<=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator>(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator>=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

/**
 * This is the basis for all read-only mmap objects and should be preferred over
 * directly using `basic_mmap`.
 */
template <typename ByteT> using basic_mmap_source = basic_mmap<access_mode::read, ByteT>;

/**
 * This is the basis for all read-write mmap objects and should be preferred over
 * directly using `basic_mmap`.
 */
template <typename ByteT> using basic_mmap_sink = basic_mmap<access_mode::write, ByteT>;

/**
 * These aliases cover the most common use cases, both representing a raw byte stream
 * (either with a char or an unsigned char/uint8_t).
 */
using mmap_source = basic_mmap_source<char>;
using ummap_source = basic_mmap_source<unsigned char>;

using mmap_sink = basic_mmap_sink<char>;
using ummap_sink = basic_mmap_sink<unsigned char>;

/**
 * Convenience factory method that constructs a mapping for any `basic_mmap` or
 * `basic_mmap` type.
 */
template <typename MMap, typename MappingToken>
MMap make_mmap(const MappingToken &token, int64_t offset, int64_t length, std::error_code &error) {
  MMap mmap;
  mmap.map(token, offset, length, error);
  return mmap;
}

/**
 * Convenience factory method.
 *
 * MappingToken may be a supported NUL-terminated path (`std::string`, `const char*`,
 * and, in C++17, `std::filesystem::path`) or a `mmap_source::handle_type`.
 */
template <typename MappingToken>
mmap_source make_mmap_source(const MappingToken &token, mmap_source::size_type offset,
                             mmap_source::size_type length, std::error_code &error) {
  return make_mmap<mmap_source>(token, offset, length, error);
}

template <typename MappingToken>
mmap_source make_mmap_source(const MappingToken &token, std::error_code &error) {
  return make_mmap_source(token, 0, map_entire_file, error);
}

/**
 * Convenience factory method.
 *
 * MappingToken may be a supported NUL-terminated path (`std::string`, `const char*`,
 * and, in C++17, `std::filesystem::path`) or a `mmap_sink::handle_type`.
 */
template <typename MappingToken>
mmap_sink make_mmap_sink(const MappingToken &token, mmap_sink::size_type offset,
                         mmap_sink::size_type length, std::error_code &error) {
  return make_mmap<mmap_sink>(token, offset, length, error);
}

template <typename MappingToken>
mmap_sink make_mmap_sink(const MappingToken &token, std::error_code &error) {
  return make_mmap_sink(token, 0, map_entire_file, error);
}

} // namespace mio

// #include "detail/mmap.ipp"
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_BASIC_MMAP_IMPL
#define MIO_BASIC_MMAP_IMPL

// #include "mio/mmap.hpp"

// #include "mio/page.hpp"

// #include "mio/detail/string_util.hpp"
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_STRING_UTIL_HEADER
#define MIO_STRING_UTIL_HEADER

#include <type_traits>

namespace mio {
namespace detail {

template <typename S, typename C = typename std::decay<S>::type,
          typename = decltype(std::declval<C>().data()),
          typename = typename std::enable_if<std::is_same<typename C::value_type, char>::value
#ifdef _WIN32
                                             || std::is_same<typename C::value_type, wchar_t>::value
#endif
                                             >::type>
struct char_type_helper {
  using type = typename C::value_type;
};

template <class T> struct char_type {
  using type = typename char_type_helper<T>::type;
};

// TODO: can we avoid this brute force approach?
template <> struct char_type<char *> {
  using type = char;
};

template <> struct char_type<const char *> {
  using type = char;
};

template <size_t N> struct char_type<char[N]> {
  using type = char;
};

template <size_t N> struct char_type<const char[N]> {
  using type = char;
};

#ifdef _WIN32
template <> struct char_type<wchar_t *> {
  using type = wchar_t;
};

template <> struct char_type<const wchar_t *> {
  using type = wchar_t;
};

template <size_t N> struct char_type<wchar_t[N]> {
  using type = wchar_t;
};

template <size_t N> struct char_type<const wchar_t[N]> {
  using type = wchar_t;
};
#endif // _WIN32

template <typename CharT, typename S> struct is_c_str_helper {
  using decayed_type = typename std::decay<S>::type;
  static constexpr bool value = std::is_pointer<decayed_type>::value &&
                                std::is_convertible<decayed_type, const CharT *>::value;
};

template <typename S> struct is_c_str {
  static constexpr bool value = is_c_str_helper<char, S>::value;
};

#ifdef _WIN32
template <typename S> struct is_c_wstr {
  static constexpr bool value = is_c_str_helper<wchar_t, S>::value;
};
#endif // _WIN32

template <typename S> struct is_c_str_or_c_wstr {
  static constexpr bool value = is_c_str<S>::value
#ifdef _WIN32
                                || is_c_wstr<S>::value
#endif
      ;
};

template <typename T> struct is_basic_string : std::false_type {};

template <typename CharT, typename Traits, typename Allocator>
struct is_basic_string<std::basic_string<CharT, Traits, Allocator>>
    : std::integral_constant<bool, std::is_same<CharT, char>::value
#ifdef _WIN32
                                       || std::is_same<CharT, wchar_t>::value
#endif
                             > {
};

template <typename T, typename = void> struct is_sized_char_range : std::false_type {};

template <typename T>
struct is_sized_char_range<
    T,
    typename std::enable_if<
        (std::is_same<typename std::decay<T>::type::value_type, char>::value
#ifdef _WIN32
         || std::is_same<typename std::decay<T>::type::value_type, wchar_t>::value
#endif
         ) &&
        std::is_convertible<decltype(std::declval<const typename std::decay<T>::type &>().data()),
                            const typename std::decay<T>::type::value_type *>::value &&
        std::is_convertible<decltype(std::declval<const typename std::decay<T>::type &>().size()),
                            size_t>::value>::type> : std::true_type {
};

#if CSV2_DETAIL_HAS_STRING_VIEW_HEADER
template <typename T> struct is_basic_string_view : std::false_type {};

template <typename CharT, typename Traits>
struct is_basic_string_view<std::basic_string_view<CharT, Traits>> : std::true_type {};
#endif

template <typename S> struct is_object_path {
  using type = typename std::decay<S>::type;
  static constexpr bool value = is_basic_string<type>::value
#if CSV2_HAS_FILESYSTEM
                                || std::is_same<type, std::filesystem::path>::value
#endif
      ;
};

template <typename S> struct is_path {
  static constexpr bool value = is_c_str_or_c_wstr<S>::value || is_object_path<S>::value;
};

template <typename S> struct is_range_path {
  using type = typename std::decay<S>::type;
  static constexpr bool value = is_sized_char_range<type>::value && !is_object_path<type>::value
#if CSV2_DETAIL_HAS_STRING_VIEW_HEADER
                                && !is_basic_string_view<type>::value
#endif
      ;
};

template <typename S> struct is_mapping_token {
  using type = typename std::decay<S>::type;
  static constexpr bool value = is_path<S>::value || is_range_path<S>::value
#ifdef _WIN32
                                || std::is_same<type, file_handle_type>::value
#endif
      ;
};

#if CSV2_HAS_FILESYSTEM
template <> struct char_type<std::filesystem::path> {
  using type = std::filesystem::path::value_type;
};
#endif

template <typename String, typename = typename std::enable_if<is_object_path<String>::value>::type>
auto c_str(const String &path) -> decltype(path.c_str()) {
  return path.c_str();
}

template <typename String>
typename std::enable_if<is_object_path<String>::value, bool>::type empty(const String &path) {
  return path.empty();
}

template <typename Range, typename = typename std::enable_if<is_range_path<Range>::value>::type>
auto c_str(const Range &path) -> decltype(path.data()) {
  return path.data();
}

template <typename Range>
typename std::enable_if<is_range_path<Range>::value, bool>::type empty(const Range &path) {
  return path.size() <= 1 || path.data() == nullptr || path.data()[0] == 0;
}

template <typename String,
          typename = typename std::enable_if<is_c_str_or_c_wstr<String>::value>::type>
const typename char_type<String>::type *c_str(String path) {
  return path;
}

template <typename String>
typename std::enable_if<is_c_str_or_c_wstr<String>::value, bool>::type empty(String path) {
  return !path || (*path == 0);
}

template <typename CharT, typename Traits, typename Allocator>
size_t path_size(const std::basic_string<CharT, Traits, Allocator> &path) {
  return path.size();
}

template <typename String>
typename std::enable_if<is_basic_string<typename std::decay<String>::type>::value, bool>::type
has_embedded_null(const String &path) {
  typedef typename char_type<String>::type char_type;
  return std::char_traits<char_type>::length(c_str(path)) != path_size(path);
}

#if CSV2_HAS_FILESYSTEM
inline size_t path_size(const std::filesystem::path &path) { return path.native().size(); }
#endif

template <typename String>
typename std::enable_if<is_object_path<String>::value &&
                            !is_basic_string<typename std::decay<String>::type>::value,
                        bool>::type
has_embedded_null(const String &path) {
  typedef typename char_type<String>::type char_type;
  return std::char_traits<char_type>::length(c_str(path)) != path_size(path);
}

template <typename String>
typename std::enable_if<is_c_str_or_c_wstr<String>::value, bool>::type has_embedded_null(String) {
  return false;
}

template <typename Range>
typename std::enable_if<is_range_path<Range>::value, bool>::type
has_embedded_null(const Range &path) {
  typedef typename std::decay<Range>::type range_type;
  typedef typename range_type::value_type char_type;
  const size_t size = static_cast<size_t>(path.size());
  const char_type *const data = path.data();
  if (!data || size == 0 || data[size - 1] != char_type())
    return true;
  return std::char_traits<char_type>::length(data) != size - 1;
}

} // namespace detail
} // namespace mio

#endif // MIO_STRING_UTIL_HEADER

#include <algorithm>

#ifndef _WIN32
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace mio {
namespace detail {

#ifdef _WIN32
namespace win {

/** Returns the 4 upper bytes of an 8-byte integer. */
inline DWORD int64_high(int64_t n) noexcept { return n >> 32; }

/** Returns the 4 lower bytes of an 8-byte integer. */
inline DWORD int64_low(int64_t n) noexcept { return n & 0xffffffff; }

template <typename String, typename = typename std::enable_if<
                               std::is_same<typename char_type<String>::type, char>::value>::type>
file_handle_type open_file_helper(const String &path, const access_mode mode) {
  return ::CreateFileA(
      c_str(path), mode == access_mode::read ? GENERIC_READ : GENERIC_READ | GENERIC_WRITE,
      FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
}

template <typename String>
typename std::enable_if<std::is_same<typename char_type<String>::type, wchar_t>::value,
                        file_handle_type>::type
open_file_helper(const String &path, const access_mode mode) {
  return ::CreateFileW(
      c_str(path), mode == access_mode::read ? GENERIC_READ : GENERIC_READ | GENERIC_WRITE,
      FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
}

} // namespace win
#endif // _WIN32

/**
 * Returns the last platform specific system error (errno on POSIX and
 * GetLastError on Win) as a `std::error_code`.
 */
inline std::error_code last_error() noexcept {
  std::error_code error;
#ifdef _WIN32
  error.assign(GetLastError(), std::system_category());
#else
  error.assign(errno, std::system_category());
#endif
  return error;
}

template <typename String>
file_handle_type open_file(const String &path, const access_mode mode, std::error_code &error) {
  error.clear();
  if (detail::empty(path) || detail::has_embedded_null(path)) {
    error = std::make_error_code(std::errc::invalid_argument);
    return invalid_handle;
  }
#ifdef _WIN32
  const auto handle = win::open_file_helper(path, mode);
#else // POSIX
  const auto handle = ::open(c_str(path), mode == access_mode::read ? O_RDONLY : O_RDWR);
#endif
  if (handle == invalid_handle) {
    error = detail::last_error();
  }
  return handle;
}

inline void close_file(const file_handle_type handle) noexcept {
  if (handle == invalid_handle)
    return;
#ifdef _WIN32
  ::CloseHandle(handle);
#else
  ::close(handle);
#endif
}

class file_handle_guard {
public:
  explicit file_handle_guard(const file_handle_type handle) noexcept : handle_(handle) {}
  ~file_handle_guard() { close_file(handle_); }

  file_handle_guard(const file_handle_guard &) = delete;
  file_handle_guard &operator=(const file_handle_guard &) = delete;

  void release() noexcept { handle_ = invalid_handle; }

private:
  file_handle_type handle_;
};

inline size_t query_file_size(file_handle_type handle, std::error_code &error) {
  error.clear();
#ifdef _WIN32
  LARGE_INTEGER file_size;
  if (::GetFileSizeEx(handle, &file_size) == 0) {
    error = detail::last_error();
    return 0;
  }
  const int64_t file_size_value = file_size.QuadPart;
#else // POSIX
  struct stat sbuf;
  if (::fstat(handle, &sbuf) == -1) {
    error = detail::last_error();
    return 0;
  }
  const int64_t file_size_value = sbuf.st_size;
#endif
  if (file_size_value < 0 ||
      static_cast<std::uintmax_t>(file_size_value) > (std::numeric_limits<size_t>::max)()) {
    error = std::make_error_code(std::errc::value_too_large);
    return 0;
  }
  return static_cast<size_t>(file_size_value);
}

struct mmap_context {
  char *data;
  int64_t length;
  int64_t mapped_length;
#ifdef _WIN32
  file_handle_type file_mapping_handle;
#endif
};

inline mmap_context memory_map(const file_handle_type file_handle, const int64_t offset,
                               const int64_t length, const access_mode mode,
                               std::error_code &error) {
  const int64_t aligned_offset = make_offset_page_aligned(offset);
  const int64_t length_to_map = offset - aligned_offset + length;
#ifdef _WIN32
  const int64_t max_file_size = offset + length;
  const auto file_mapping_handle = ::CreateFileMapping(
      file_handle, 0, mode == access_mode::read ? PAGE_READONLY : PAGE_READWRITE,
      win::int64_high(max_file_size), win::int64_low(max_file_size), 0);
  if (file_mapping_handle == invalid_mapping_handle) {
    error = detail::last_error();
    return {};
  }
  char *mapping_start = static_cast<char *>(::MapViewOfFile(
      file_mapping_handle, mode == access_mode::read ? FILE_MAP_READ : FILE_MAP_WRITE,
      win::int64_high(aligned_offset), win::int64_low(aligned_offset), length_to_map));
  if (mapping_start == nullptr) {
    const std::error_code mapping_error = detail::last_error();
    ::CloseHandle(file_mapping_handle);
    error = mapping_error;
    return {};
  }
#else // POSIX
  char *mapping_start =
      static_cast<char *>(::mmap(0, // Don't give hint as to where to map.
                                 length_to_map, mode == access_mode::read ? PROT_READ : PROT_WRITE,
                                 MAP_SHARED, file_handle, aligned_offset));
  if (mapping_start == MAP_FAILED) {
    error = detail::last_error();
    return {};
  }
#endif
  mmap_context ctx;
  ctx.data = mapping_start + (offset - aligned_offset);
  ctx.length = length;
  ctx.mapped_length = length_to_map;
#ifdef _WIN32
  ctx.file_mapping_handle = file_mapping_handle;
#endif
  return ctx;
}

} // namespace detail

// -- basic_mmap --

template <access_mode AccessMode, typename ByteT> basic_mmap<AccessMode, ByteT>::~basic_mmap() {
  conditional_sync();
  unmap();
}

template <access_mode AccessMode, typename ByteT>
basic_mmap<AccessMode, ByteT>::basic_mmap(basic_mmap &&other)
    : data_(std::move(other.data_)), length_(std::move(other.length_)),
      mapped_length_(std::move(other.mapped_length_)), file_handle_(std::move(other.file_handle_))
#ifdef _WIN32
      ,
      file_mapping_handle_(std::move(other.file_mapping_handle_))
#endif
      ,
      is_handle_internal_(std::move(other.is_handle_internal_)) {
  other.data_ = nullptr;
  other.length_ = other.mapped_length_ = 0;
  other.file_handle_ = invalid_handle;
#ifdef _WIN32
  other.file_mapping_handle_ = invalid_mapping_handle;
#endif
  other.is_handle_internal_ = false;
}

template <access_mode AccessMode, typename ByteT>
basic_mmap<AccessMode, ByteT> &basic_mmap<AccessMode, ByteT>::operator=(basic_mmap &&other) {
  if (this != &other) {
    // First the existing mapping needs to be removed.
    unmap();
    data_ = std::move(other.data_);
    length_ = std::move(other.length_);
    mapped_length_ = std::move(other.mapped_length_);
    file_handle_ = std::move(other.file_handle_);
#ifdef _WIN32
    file_mapping_handle_ = std::move(other.file_mapping_handle_);
#endif
    is_handle_internal_ = std::move(other.is_handle_internal_);

    // The moved from basic_mmap's fields need to be reset, because
    // otherwise other's destructor will unmap the same mapping that was
    // just moved into this.
    other.data_ = nullptr;
    other.length_ = other.mapped_length_ = 0;
    other.file_handle_ = invalid_handle;
#ifdef _WIN32
    other.file_mapping_handle_ = invalid_mapping_handle;
#endif
    other.is_handle_internal_ = false;
  }
  return *this;
}

template <access_mode AccessMode, typename ByteT>
typename basic_mmap<AccessMode, ByteT>::handle_type
basic_mmap<AccessMode, ByteT>::mapping_handle() const noexcept {
#ifdef _WIN32
  return file_mapping_handle_;
#else
  return file_handle_;
#endif
}

template <access_mode AccessMode, typename ByteT>
template <typename String>
void basic_mmap<AccessMode, ByteT>::map(const String &path, const size_type offset,
                                        const size_type length, std::error_code &error) {
  error.clear();
  if (detail::empty(path)) {
    error = std::make_error_code(std::errc::invalid_argument);
    return;
  }
  const auto handle = detail::open_file(path, AccessMode, error);
  if (error) {
    return;
  }

  detail::file_handle_guard handle_guard(handle);
  map(handle, offset, length, error);
  if (error)
    return;

  is_handle_internal_ = true;
  handle_guard.release();
}

template <access_mode AccessMode, typename ByteT>
void basic_mmap<AccessMode, ByteT>::map(const handle_type handle, const size_type offset,
                                        const size_type length, std::error_code &error) {
  error.clear();
  if (handle == invalid_handle) {
    error = std::make_error_code(std::errc::bad_file_descriptor);
    return;
  }

  const auto file_size = detail::query_file_size(handle, error);
  if (error) {
    return;
  }

  if (offset > file_size || length > file_size - offset) {
    error = std::make_error_code(std::errc::invalid_argument);
    return;
  }

  const bool remapping_internal_handle = is_handle_internal_ && handle == file_handle_;
  const auto ctx = detail::memory_map(
      handle, offset, length == map_entire_file ? (file_size - offset) : length, AccessMode, error);
  if (!error) {
    // We must unmap the previous mapping that may have existed prior to this call.
    // Note that this must only be invoked after a new mapping has been created in
    // order to provide the strong guarantee that, should the new mapping fail, the
    // `map` function leaves this instance in a state as though the function had
    // never been invoked.
    if (remapping_internal_handle)
      is_handle_internal_ = false;
    unmap();
    file_handle_ = handle;
    is_handle_internal_ = remapping_internal_handle;
    data_ = reinterpret_cast<pointer>(ctx.data);
    length_ = ctx.length;
    mapped_length_ = ctx.mapped_length;
#ifdef _WIN32
    file_mapping_handle_ = ctx.file_mapping_handle;
#endif
  }
}

template <access_mode AccessMode, typename ByteT>
template <access_mode A>
typename std::enable_if<A == access_mode::write, void>::type
basic_mmap<AccessMode, ByteT>::sync(std::error_code &error) {
  error.clear();
  if (!is_open()) {
    error = std::make_error_code(std::errc::bad_file_descriptor);
    return;
  }

  if (data()) {
#ifdef _WIN32
    if (::FlushViewOfFile(get_mapping_start(), mapped_length_) == 0)
#else // POSIX
    if (::msync(get_mapping_start(), mapped_length_, MS_SYNC) != 0)
#endif
    {
      error = detail::last_error();
      return;
    }
  }
#ifdef _WIN32
  if (::FlushFileBuffers(file_handle_) == 0) {
    error = detail::last_error();
  }
#endif
}

template <access_mode AccessMode, typename ByteT> void basic_mmap<AccessMode, ByteT>::unmap() {
  if (!is_open()) {
    return;
  }
  // TODO do we care about errors here?
#ifdef _WIN32
  if (is_mapped()) {
    ::UnmapViewOfFile(get_mapping_start());
    ::CloseHandle(file_mapping_handle_);
  }
#else // POSIX
  if (data_) {
    ::munmap(const_cast<pointer>(get_mapping_start()), mapped_length_);
  }
#endif

  // If `file_handle_` was obtained by our opening it (when map is called with
  // a path, rather than an existing file handle), we need to close it,
  // otherwise it must not be closed as it may still be used outside this
  // instance.
  if (is_handle_internal_) {
#ifdef _WIN32
    ::CloseHandle(file_handle_);
#else // POSIX
    ::close(file_handle_);
#endif
  }

  // Reset fields to their default values.
  data_ = nullptr;
  length_ = mapped_length_ = 0;
  file_handle_ = invalid_handle;
#ifdef _WIN32
  file_mapping_handle_ = invalid_mapping_handle;
#endif
  is_handle_internal_ = false;
}

template <access_mode AccessMode, typename ByteT>
bool basic_mmap<AccessMode, ByteT>::is_mapped() const noexcept {
#ifdef _WIN32
  return file_mapping_handle_ != invalid_mapping_handle;
#else // POSIX
  return is_open();
#endif
}

template <access_mode AccessMode, typename ByteT>
void basic_mmap<AccessMode, ByteT>::swap(basic_mmap &other) {
  if (this != &other) {
    using std::swap;
    swap(data_, other.data_);
    swap(file_handle_, other.file_handle_);
#ifdef _WIN32
    swap(file_mapping_handle_, other.file_mapping_handle_);
#endif
    swap(length_, other.length_);
    swap(mapped_length_, other.mapped_length_);
    swap(is_handle_internal_, other.is_handle_internal_);
  }
}

template <access_mode AccessMode, typename ByteT>
template <access_mode A>
typename std::enable_if<A == access_mode::write, void>::type
basic_mmap<AccessMode, ByteT>::conditional_sync() {
  // This is invoked from the destructor, so not much we can do about
  // failures here.
  std::error_code ec;
  sync(ec);
}

template <access_mode AccessMode, typename ByteT>
template <access_mode A>
typename std::enable_if<A == access_mode::read, void>::type
basic_mmap<AccessMode, ByteT>::conditional_sync() {
  // noop
}

template <access_mode AccessMode, typename ByteT>
bool operator==(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return a.data() == b.data() && a.size() == b.size();
}

template <access_mode AccessMode, typename ByteT>
bool operator!=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return !(a == b);
}

template <access_mode AccessMode, typename ByteT>
bool operator<(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  if (a.data() == b.data()) {
    return a.size() < b.size();
  }
  return a.data() < b.data();
}

template <access_mode AccessMode, typename ByteT>
bool operator<=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return !(a > b);
}

template <access_mode AccessMode, typename ByteT>
bool operator>(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  if (a.data() == b.data()) {
    return a.size() > b.size();
  }
  return a.data() > b.data();
}

template <access_mode AccessMode, typename ByteT>
bool operator>=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return !(a < b);
}

} // namespace mio

#endif // MIO_BASIC_MMAP_IMPL

#endif // MIO_MMAP_HEADER
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_PAGE_HEADER
#define MIO_PAGE_HEADER

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace mio {

/**
 * This is used by `basic_mmap` to determine whether to create a read-only or
 * a read-write memory mapping.
 */
enum class access_mode { read, write };

/**
 * Determines the operating system's page allocation granularity.
 *
 * On the first call to this function, it invokes the operating system specific syscall
 * to determine the page size, caches the value, and returns it. Any subsequent call to
 * this function serves the cached value, so no further syscalls are made.
 */
inline size_t page_size() {
  static const size_t page_size = [] {
#ifdef _WIN32
    SYSTEM_INFO SystemInfo;
    GetSystemInfo(&SystemInfo);
    return SystemInfo.dwAllocationGranularity;
#else
    return sysconf(_SC_PAGE_SIZE);
#endif
  }();
  return page_size;
}

/**
 * Alligns `offset` to the operating's system page size such that it subtracts the
 * difference until the nearest page boundary before `offset`, or does nothing if
 * `offset` is already page aligned.
 */
inline size_t make_offset_page_aligned(size_t offset) noexcept {
  const size_t page_size_ = page_size();
  // Use integer division to round down to the nearest page alignment.
  return offset / page_size_ * page_size_;
}

} // namespace mio

#endif // MIO_PAGE_HEADER
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_SHARED_MMAP_HEADER
#define MIO_SHARED_MMAP_HEADER

// #include "mio/mmap.hpp"

#include <memory>       // std::shared_ptr
#include <system_error> // std::error_code

namespace mio {

/**
 * Exposes (nearly) the same interface as `basic_mmap`, but endowes it with
 * `std::shared_ptr` semantics.
 *
 * This is not the default behaviour of `basic_mmap` to avoid allocating on the heap if
 * shared semantics are not required.
 */
template <access_mode AccessMode, typename ByteT> class basic_shared_mmap {
  using impl_type = basic_mmap<AccessMode, ByteT>;
  std::shared_ptr<impl_type> pimpl_;

public:
  using value_type = typename impl_type::value_type;
  using size_type = typename impl_type::size_type;
  using reference = typename impl_type::reference;
  using const_reference = typename impl_type::const_reference;
  using pointer = typename impl_type::pointer;
  using const_pointer = typename impl_type::const_pointer;
  using difference_type = typename impl_type::difference_type;
  using iterator = typename impl_type::iterator;
  using const_iterator = typename impl_type::const_iterator;
  using reverse_iterator = typename impl_type::reverse_iterator;
  using const_reverse_iterator = typename impl_type::const_reverse_iterator;
  using iterator_category = typename impl_type::iterator_category;
  using handle_type = typename impl_type::handle_type;
  using mmap_type = impl_type;

  basic_shared_mmap() = default;
  basic_shared_mmap(const basic_shared_mmap &) = default;
  basic_shared_mmap &operator=(const basic_shared_mmap &) = default;
  basic_shared_mmap(basic_shared_mmap &&) = default;
  basic_shared_mmap &operator=(basic_shared_mmap &&) = default;

  /** Takes ownership of an existing mmap object. */
  basic_shared_mmap(mmap_type &&mmap) : pimpl_(std::make_shared<mmap_type>(std::move(mmap))) {}

  /** Takes ownership of an existing mmap object. */
  basic_shared_mmap &operator=(mmap_type &&mmap) {
    pimpl_ = std::make_shared<mmap_type>(std::move(mmap));
    return *this;
  }

  /** Initializes this object with an already established shared mmap. */
  basic_shared_mmap(std::shared_ptr<mmap_type> mmap) : pimpl_(std::move(mmap)) {}

  /** Initializes this object with an already established shared mmap. */
  basic_shared_mmap &operator=(std::shared_ptr<mmap_type> mmap) {
    pimpl_ = std::move(mmap);
    return *this;
  }

#ifdef __cpp_exceptions
  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  template <typename String>
  basic_shared_mmap(const String &path, const size_type offset = 0,
                    const size_type length = map_entire_file) {
    std::error_code error;
    map(path, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }

  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  basic_shared_mmap(const handle_type handle, const size_type offset = 0,
                    const size_type length = map_entire_file) {
    std::error_code error;
    map(handle, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }
#endif // __cpp_exceptions

  /**
   * If this is a read-write mapping and the last reference to the mapping,
   * the destructor invokes sync. Regardless of the access mode, unmap is
   * invoked as a final step.
   */
  ~basic_shared_mmap() = default;

  /** Returns the underlying `std::shared_ptr` instance that holds the mmap. */
  std::shared_ptr<mmap_type> get_shared_ptr() { return pimpl_; }

  /**
   * On UNIX systems 'file_handle' and 'mapping_handle' are the same. On Windows,
   * however, a mapped region of a file gets its own handle, which is returned by
   * 'mapping_handle'.
   */
  handle_type file_handle() const noexcept {
    return pimpl_ ? pimpl_->file_handle() : invalid_handle;
  }

  handle_type mapping_handle() const noexcept {
    return pimpl_ ? pimpl_->mapping_handle() : invalid_mapping_handle;
  }

  /** Returns whether a valid memory mapping has been created. */
  bool is_open() const noexcept { return pimpl_ && pimpl_->is_open(); }

  /**
   * Returns true if no mapping was established, that is, conceptually the
   * same as though the length that was mapped was 0. This function is
   * provided so that this class has Container semantics.
   */
  bool empty() const noexcept { return !pimpl_ || pimpl_->empty(); }

  /**
   * `size` and `length` both return the logical length, i.e. the number of bytes
   * user requested to be mapped, while `mapped_length` returns the actual number of
   * bytes that were mapped which is a multiple of the underlying operating system's
   * page allocation granularity.
   */
  size_type size() const noexcept { return pimpl_ ? pimpl_->length() : 0; }
  size_type length() const noexcept { return pimpl_ ? pimpl_->length() : 0; }
  size_type mapped_length() const noexcept { return pimpl_ ? pimpl_->mapped_length() : 0; }

  /**
   * Returns a pointer to the first requested byte, or `nullptr` if no memory mapping
   * exists.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  pointer data() noexcept {
    return pimpl_->data();
  }
  const_pointer data() const noexcept { return pimpl_ ? pimpl_->data() : nullptr; }

  /**
   * Returns an iterator to the first requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  iterator begin() noexcept { return pimpl_->begin(); }
  const_iterator begin() const noexcept { return pimpl_->begin(); }
  const_iterator cbegin() const noexcept { return pimpl_->cbegin(); }

  /**
   * Returns an iterator one past the last requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  iterator end() noexcept {
    return pimpl_->end();
  }
  const_iterator end() const noexcept { return pimpl_->end(); }
  const_iterator cend() const noexcept { return pimpl_->cend(); }

  /**
   * Returns a reverse iterator to the last memory mapped byte, if a valid
   * memory mapping exists, otherwise this function call is undefined
   * behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rbegin() noexcept {
    return pimpl_->rbegin();
  }
  const_reverse_iterator rbegin() const noexcept { return pimpl_->rbegin(); }
  const_reverse_iterator crbegin() const noexcept { return pimpl_->crbegin(); }

  /**
   * Returns a reverse iterator past the first mapped byte, if a valid memory
   * mapping exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rend() noexcept {
    return pimpl_->rend();
  }
  const_reverse_iterator rend() const noexcept { return pimpl_->rend(); }
  const_reverse_iterator crend() const noexcept { return pimpl_->crend(); }

  /**
   * Returns a reference to the `i`th byte from the first requested byte (as returned
   * by `data`). If this is invoked when no valid memory mapping has been created
   * prior to this call, undefined behaviour ensues.
   */
  reference operator[](const size_type i) noexcept { return (*pimpl_)[i]; }
  const_reference operator[](const size_type i) const noexcept { return (*pimpl_)[i]; }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  template <typename String>
  void map(const String &path, const size_type offset, const size_type length,
           std::error_code &error) {
    map_impl(path, offset, length, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  template <typename String> void map(const String &path, std::error_code &error) {
    map_impl(path, 0, map_entire_file, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  void map(const handle_type handle, const size_type offset, const size_type length,
           std::error_code &error) {
    map_impl(handle, offset, length, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  void map(const handle_type handle, std::error_code &error) {
    map_impl(handle, 0, map_entire_file, error);
  }

  /**
   * If a valid memory mapping has been created prior to this call, this call
   * instructs the kernel to unmap the memory region and disassociate this object
   * from the file.
   *
   * The file handle associated with the file that is mapped is only closed if the
   * mapping was created using a file path. If, on the other hand, an existing
   * file handle was used to create the mapping, the file handle is not closed.
   */
  void unmap() {
    if (pimpl_)
      pimpl_->unmap();
  }

  void swap(basic_shared_mmap &other) { pimpl_.swap(other.pimpl_); }

  /** Flushes the memory mapped page to disk. Errors are reported via `error`. */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  void sync(std::error_code &error) {
    if (pimpl_)
      pimpl_->sync(error);
  }

  /** All operators compare the underlying `basic_mmap`'s addresses. */

  friend bool operator==(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ == b.pimpl_;
  }

  friend bool operator!=(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return !(a == b);
  }

  friend bool operator<(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ < b.pimpl_;
  }

  friend bool operator<=(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ <= b.pimpl_;
  }

  friend bool operator>(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ > b.pimpl_;
  }

  friend bool operator>=(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ >= b.pimpl_;
  }

private:
  template <typename MappingToken>
  void map_impl(const MappingToken &token, const size_type offset, const size_type length,
                std::error_code &error) {
    if (!pimpl_) {
      mmap_type mmap = make_mmap<mmap_type>(token, offset, length, error);
      if (error) {
        return;
      }
      pimpl_ = std::make_shared<mmap_type>(std::move(mmap));
    } else {
      pimpl_->map(token, offset, length, error);
    }
  }
};

/**
 * This is the basis for all read-only mmap objects and should be preferred over
 * directly using basic_shared_mmap.
 */
template <typename ByteT>
using basic_shared_mmap_source = basic_shared_mmap<access_mode::read, ByteT>;

/**
 * This is the basis for all read-write mmap objects and should be preferred over
 * directly using basic_shared_mmap.
 */
template <typename ByteT>
using basic_shared_mmap_sink = basic_shared_mmap<access_mode::write, ByteT>;

/**
 * These aliases cover the most common use cases, both representing a raw byte stream
 * (either with a char or an unsigned char/uint8_t).
 */
using shared_mmap_source = basic_shared_mmap_source<char>;
using shared_ummap_source = basic_shared_mmap_source<unsigned char>;

using shared_mmap_sink = basic_shared_mmap_sink<char>;
using shared_ummap_sink = basic_shared_mmap_sink<unsigned char>;

} // namespace mio

#endif // MIO_SHARED_MMAP_HEADER

#endif // CSV2_HAS_MMAP

#endif
// #include <csv2/parameters.hpp>

// #include <csv2/detail/config.hpp>

#include <cstddef>
#include <utility>

namespace csv2 {

namespace trim_policy {
struct no_trimming {
public:
  static std::pair<std::size_t, std::size_t> trim(const char *buffer, std::size_t start,
                                                  std::size_t end) noexcept {
    (void)(buffer); // to silence unused parameter warning
    return {start, end};
  }
};

template <char... character_list> struct trim_characters {
private:
  constexpr static bool is_trim_char(char) { return false; }

  template <class... Tail> constexpr static bool is_trim_char(char c, char head, Tail... tail) {
    return c == head || is_trim_char(c, tail...);
  }

public:
  static std::pair<std::size_t, std::size_t> trim(const char *buffer, std::size_t start,
                                                  std::size_t end) noexcept {
    std::size_t new_start = start, new_end = end;
    while (new_start != new_end && is_trim_char(buffer[new_start], character_list...))
      ++new_start;
    while (new_start != new_end && is_trim_char(buffer[new_end - 1], character_list...))
      --new_end;
    return {new_start, new_end};
  }
};

using trim_whitespace = trim_characters<' ', '\t'>;
} // namespace trim_policy

template <char character> struct delimiter {
  constexpr static char value = character;
};

template <char character> struct quote_character {
  constexpr static char value = character;
};

template <bool flag> struct first_row_is_header {
  constexpr static bool value = flag;
};

} // namespace csv2


#include <cstdint>
#include <iterator>
#include <limits>
#include <memory>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>
#include <vector>
#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif
#if CSV2_HAS_SPAN
#include <span>
#endif
#if CSV2_HAS_RANGES
#include <ranges>
#endif
#if CSV2_HAS_EXPECTED
#include <expected>
#endif

namespace csv2 {

namespace detail {

#if CSV2_HAS_RANGES
template <class T>
concept marked_row_view = requires {
  typename std::remove_cv_t<T>::csv2_row_view_marker;
  requires std::is_same_v<typename std::remove_cv_t<T>::csv2_row_view_marker, std::remove_cv_t<T>>;
};
#endif

template <class T> class arrow_proxy {
  T value_;

public:
  explicit arrow_proxy(T value) : value_(std::move(value)) {}
  const T *operator->() const noexcept { return std::addressof(value_); }
};

template <class Delimiter>
struct is_record_compatible_delimiter
    : std::integral_constant<bool, Delimiter::value != '\r' && Delimiter::value != '\n'> {};

} // namespace detail

template <class quote_character, class trim_policy> class basic_cell {
  const char *buffer_{nullptr};
  size_t start_{0};
  size_t end_{0};
  bool escaped_{false};

  std::pair<size_t, size_t> content_bounds_() const
      noexcept(noexcept(trim_policy::trim(buffer_, start_, end_))) {
    std::pair<size_t, size_t> bounds = trim_policy::trim(buffer_, start_, end_);
    if (bounds.second - bounds.first >= 2 && buffer_[bounds.first] == quote_character::value &&
        buffer_[bounds.second - 1] == quote_character::value) {
      ++bounds.first;
      --bounds.second;
    }
    return bounds;
  }

public:
  basic_cell() = default;
  basic_cell(const char *buffer, size_t start, size_t end, bool escaped) noexcept
      : buffer_(buffer), start_(start), end_(end), escaped_(escaped) {}

  const char *raw_data() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
  size_t raw_size() const noexcept { return end_ - start_; }
  bool has_escaped_quotes() const noexcept { return escaped_; }

#if CSV2_HAS_STRING_VIEW
  std::string_view raw_trimmed_view() const
      noexcept(noexcept(trim_policy::trim(buffer_, start_, end_))) {
    if (!buffer_)
      return std::string_view();
    const auto bounds = trim_policy::trim(buffer_, start_, end_);
    return std::string_view(buffer_ + bounds.first, bounds.second - bounds.first);
  }

  std::string_view read_view() const noexcept(noexcept(raw_trimmed_view())) {
    return raw_trimmed_view();
  }
#endif

  template <typename Container> void read_raw_value(Container &result) const {
    if (start_ >= end_)
      return;
    detail::reserve_for_append(result, raw_size());
    detail::append_optimized_range(result, buffer_ + start_, buffer_ + end_);
  }

  template <typename Container> void read_value(Container &result) const {
    if (start_ >= end_)
      return;
    const auto bounds = trim_policy::trim(buffer_, start_, end_);
    detail::reserve_for_append(result, bounds.second - bounds.first);
    if (!escaped_) {
      if (bounds.first < bounds.second)
        detail::append_optimized_range(result, buffer_ + bounds.first, buffer_ + bounds.second);
      return;
    }
    detail::append_decoded(result, buffer_, bounds.first, bounds.second, quote_character::value);
  }

  template <typename OutputIt> OutputIt copy_raw_to(OutputIt output) const {
    if (start_ >= end_)
      return output;
    return detail::copy_chars(buffer_ + start_, buffer_ + end_, output);
  }

  template <typename OutputIt> OutputIt decode_to(OutputIt output) const {
    if (start_ >= end_)
      return output;
    const auto bounds = trim_policy::trim(buffer_, start_, end_);
    for (size_t i = bounds.first; i < bounds.second; ++i) {
      *output = buffer_[i];
      ++output;
      if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
          buffer_[i + 1] == quote_character::value)
        ++i;
    }
    return output;
  }

  template <typename OutputIt> OutputIt copy_content_to(OutputIt output) const {
    if (start_ >= end_)
      return output;
    auto bounds = trim_policy::trim(buffer_, start_, end_);
    if (bounds.second - bounds.first >= 2 && buffer_[bounds.first] == quote_character::value &&
        buffer_[bounds.second - 1] == quote_character::value) {
      ++bounds.first;
      --bounds.second;
    }
    for (size_t i = bounds.first; i < bounds.second; ++i) {
      *output = buffer_[i];
      ++output;
      if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
          buffer_[i + 1] == quote_character::value)
        ++i;
    }
    return output;
  }

  template <class Integer>
  typename std::enable_if<detail::is_csv_integer<Integer>::value, bool>::type
  try_parse(Integer &output, conversion_error &error, int base = 10) const
      noexcept(noexcept(trim_policy::trim(buffer_, start_, end_))) {
    if (!buffer_ || escaped_)
      return detail::conversion_failure(error, conversion_errc::invalid_argument, 0);
    const std::pair<size_t, size_t> bounds = content_bounds_();
    return detail::parse_integer(buffer_ + bounds.first, buffer_ + bounds.second, output, error,
                                 base);
  }

#if CSV2_HAS_EXPECTED
  template <class Integer>
  typename std::enable_if<detail::is_csv_integer<Integer>::value,
                          std::expected<Integer, conversion_error>>::type
  parse_expected(int base = 10) const noexcept(noexcept(trim_policy::trim(buffer_, start_, end_))) {
    Integer result{};
    conversion_error error;
    if (try_parse(result, error, base))
      return result;
    return std::unexpected(error);
  }
#endif
};

template <class delimiter, class quote_character, class trim_policy> class basic_row {
  const char *buffer_{nullptr};
  size_t start_{0};
  size_t end_{0};

public:
  using Cell = basic_cell<quote_character, trim_policy>;

  basic_row() = default;
  basic_row(const char *buffer, size_t start, size_t end) noexcept
      : buffer_(buffer), start_(start), end_(end) {}

  const char *raw_data() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
  size_t raw_size() const noexcept { return end_ - start_; }
  const char *address() const noexcept { return raw_data(); }
  size_t length() const noexcept { return raw_size(); }

  template <typename Container> void read_raw_value(Container &result) const {
    if (start_ >= end_)
      return;
    detail::reserve_for_append(result, raw_size());
    detail::append_optimized_range(result, buffer_ + start_, buffer_ + end_);
  }

  class CellIterator {
    const char *buffer_{nullptr};
    size_t current_{0};
    size_t end_{0};
    size_t content_end_{0};
    bool escaped_{false};
    bool at_end_{true};

    void update_bounds_() noexcept {
      if (!at_end_) {
        const detail::cell_bounds bounds =
            detail::find_cell_bounds<delimiter, quote_character>(buffer_, current_, end_);
        content_end_ = bounds.content_end;
        escaped_ = bounds.escaped;
      } else {
        content_end_ = end_;
        escaped_ = false;
      }
    }

  public:
    using value_type = Cell;
    using difference_type = std::ptrdiff_t;
    using reference = Cell;
    using pointer = detail::arrow_proxy<Cell>;
    using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
    using iterator_concept = std::forward_iterator_tag;
#endif

    CellIterator() = default;

    CellIterator(const char *buffer, size_t start, size_t end)
        : buffer_(buffer), current_(start), end_(end), content_end_(end), escaped_(false),
          at_end_(start >= end) {
      update_bounds_();
    }

    CellIterator(const char *buffer, size_t buffer_size, size_t start, size_t end)
        : CellIterator(buffer, start, end) {
      (void)buffer_size;
    }

    CellIterator &operator++() {
      if (!at_end_) {
        if (content_end_ < end_) {
          current_ = content_end_ + 1;
        } else {
          current_ = end_;
          at_end_ = true;
        }
        update_bounds_();
      }
      return *this;
    }

    CellIterator operator++(int) {
      CellIterator previous(*this);
      ++(*this);
      return previous;
    }

    Cell operator*() const { return Cell(buffer_, current_, content_end_, escaped_); }
    pointer operator->() const { return pointer(operator*()); }

    bool operator==(const CellIterator &rhs) const noexcept {
      return buffer_ == rhs.buffer_ && current_ == rhs.current_ && end_ == rhs.end_ &&
             at_end_ == rhs.at_end_;
    }

    bool operator!=(const CellIterator &rhs) const noexcept { return !(*this == rhs); }
  };

  CellIterator begin() const { return CellIterator(buffer_, start_, end_); }
  CellIterator end() const { return CellIterator(buffer_, end_, end_); }
};

template <class delimiter_type, class quote_character_type, class trim_policy_type,
          class row_type = basic_row<delimiter_type, quote_character_type, trim_policy_type>>
class RowIndex {
  static_assert(detail::is_record_compatible_delimiter<delimiter_type>::value,
                "csv2 record separators cannot also be field delimiters");

public:
  using Row = row_type;

private:
  struct row_bounds {
    size_t start;
    size_t end;
  };

  const char *buffer_{nullptr};
  std::vector<row_bounds> rows_;

  Row row_at_(size_t position) const noexcept {
    const row_bounds bounds = rows_[position];
    return Row(buffer_, bounds.start, bounds.end);
  }

public:
  RowIndex() = default;

  RowIndex(const char *buffer, size_t buffer_size, size_t start, bool ignore_empty_lines)
      : buffer_(buffer) {
    if (!buffer_)
      return;
    while (start < buffer_size) {
      const detail::record_bounds bounds =
          detail::find_record_bounds<quote_character_type>(buffer_, buffer_size, start);
      if (!ignore_empty_lines || bounds.content_end != start)
        rows_.push_back({start, bounds.content_end});
      start = bounds.next_start;
    }
  }

  size_t size() const noexcept { return rows_.size(); }
  bool empty() const noexcept { return rows_.empty(); }
  Row operator[](size_t position) const noexcept { return row_at_(position); }

  class iterator {
    const RowIndex *index_{nullptr};
    size_t position_{0};

  public:
    using value_type = Row;
    using difference_type = std::ptrdiff_t;
    using reference = Row;
    using pointer = detail::arrow_proxy<Row>;
    using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
    using iterator_concept = std::random_access_iterator_tag;
#endif

    iterator() = default;
    iterator(const RowIndex *index, size_t position) noexcept
        : index_(index), position_(position) {}

    Row operator*() const noexcept { return (*index_)[position_]; }
    pointer operator->() const { return pointer(operator*()); }
    Row operator[](difference_type offset) const noexcept {
      return (*index_)[static_cast<size_t>(static_cast<difference_type>(position_) + offset)];
    }

    iterator &operator++() noexcept {
      ++position_;
      return *this;
    }
    iterator operator++(int) noexcept {
      iterator previous(*this);
      ++(*this);
      return previous;
    }
    iterator &operator--() noexcept {
      --position_;
      return *this;
    }
    iterator operator--(int) noexcept {
      iterator previous(*this);
      --(*this);
      return previous;
    }
    iterator &operator+=(difference_type offset) noexcept {
      position_ = static_cast<size_t>(static_cast<difference_type>(position_) + offset);
      return *this;
    }
    iterator &operator-=(difference_type offset) noexcept { return *this += -offset; }

    friend iterator operator+(iterator value, difference_type offset) noexcept {
      value += offset;
      return value;
    }
    friend iterator operator+(difference_type offset, iterator value) noexcept {
      value += offset;
      return value;
    }
    friend iterator operator-(iterator value, difference_type offset) noexcept {
      value -= offset;
      return value;
    }
    friend difference_type operator-(const iterator &left, const iterator &right) noexcept {
      return static_cast<difference_type>(left.position_) -
             static_cast<difference_type>(right.position_);
    }

    friend bool operator==(const iterator &left, const iterator &right) noexcept {
      return left.index_ == right.index_ && left.position_ == right.position_;
    }
    friend bool operator!=(const iterator &left, const iterator &right) noexcept {
      return !(left == right);
    }
    friend bool operator<(const iterator &left, const iterator &right) noexcept {
      return left.position_ < right.position_;
    }
    friend bool operator>(const iterator &left, const iterator &right) noexcept {
      return right < left;
    }
    friend bool operator<=(const iterator &left, const iterator &right) noexcept {
      return !(right < left);
    }
    friend bool operator>=(const iterator &left, const iterator &right) noexcept {
      return !(left < right);
    }
  };

  iterator begin() const noexcept { return iterator(this, 0); }
  iterator end() const noexcept { return iterator(this, size()); }
};

#if CSV2_HAS_RANGES
} // namespace csv2
namespace std {
namespace ranges {
template <class delimiter, class quote_character, class trim_policy>
inline constexpr bool enable_view<csv2::basic_row<delimiter, quote_character, trim_policy>> = true;
template <class delimiter, class quote_character, class trim_policy>
inline constexpr bool
    enable_borrowed_range<csv2::basic_row<delimiter, quote_character, trim_policy>> = true;
template <class T>
  requires csv2::detail::marked_row_view<T>
inline constexpr bool enable_view<T> = true;
template <class T>
  requires csv2::detail::marked_row_view<T>
inline constexpr bool enable_borrowed_range<T> = true;
} // namespace ranges
} // namespace std

namespace csv2 {
#endif

template <class delimiter = delimiter<','>, class quote_character = quote_character<'"'>,
          class first_row_is_header = first_row_is_header<true>,
          class trim_policy = trim_policy::trim_whitespace>
class Reader {
  static_assert(detail::is_record_compatible_delimiter<delimiter>::value,
                "csv2 record separators cannot also be field delimiters");

#if CSV2_HAS_MMAP
  mio::mmap_source mmap_;
#endif
  std::unique_ptr<std::string> owned_buffer_;
  const char *buffer_{nullptr};
  size_t buffer_size_{0};

  void clear_buffer_() noexcept {
    buffer_ = nullptr;
    buffer_size_ = 0;
  }

  void reset_source_() {
    clear_buffer_();
    owned_buffer_.reset();
#if CSV2_HAS_MMAP
    mmap_.unmap();
#endif
  }

  static bool contains_range_(const char *source, size_t source_size, const char *data,
                              size_t size) noexcept {
    if (!source || !data || size > source_size)
      return false;

    const std::uintptr_t source_begin = reinterpret_cast<std::uintptr_t>(source);
    const std::uintptr_t data_begin = reinterpret_cast<std::uintptr_t>(data);
    if (source_size > (std::numeric_limits<std::uintptr_t>::max)() - source_begin)
      return false;
    const std::uintptr_t source_end = source_begin + source_size;
    return data_begin >= source_begin && data_begin <= source_end &&
           size <= source_end - data_begin;
  }

  static bool contains_address_(const char *source, size_t source_size, const char *data) noexcept {
    if (!source || !data)
      return false;
    const std::uintptr_t source_begin = reinterpret_cast<std::uintptr_t>(source);
    const std::uintptr_t data_begin = reinterpret_cast<std::uintptr_t>(data);
    if (source_size > (std::numeric_limits<std::uintptr_t>::max)() - source_begin)
      return false;
    return data_begin >= source_begin && data_begin <= source_begin + source_size;
  }

  bool owns_range_(const char *data, size_t size) const noexcept {
    if (owned_buffer_ && contains_range_(owned_buffer_->c_str(), owned_buffer_->size(), data, size))
      return true;
#if CSV2_HAS_MMAP
    if (mmap_.is_mapped() && contains_range_(mmap_.data(), mmap_.size(), data, size))
      return true;
#endif
    return false;
  }

  bool aliases_source_(const char *data) const noexcept {
    if (owned_buffer_ && contains_address_(owned_buffer_->c_str(), owned_buffer_->size(), data))
      return true;
#if CSV2_HAS_MMAP
    if (mmap_.is_mapped() && contains_address_(mmap_.data(), mmap_.size(), data))
      return true;
#endif
    return false;
  }

  template <typename StringType> bool parse_dispatch_(StringType &&contents, std::true_type) {
    const char *const data = contents.c_str();
    const size_t size = contents.size();
    return parse_borrowed(data, size);
  }

  template <typename StringType> bool parse_owned_(StringType &&contents, std::true_type) {
    std::unique_ptr<std::string> new_buffer(new std::string(std::forward<StringType>(contents)));
    reset_source_();
    if (new_buffer->empty())
      return false;
    owned_buffer_ = std::move(new_buffer);
    buffer_ = owned_buffer_->c_str();
    buffer_size_ = owned_buffer_->size();
    return true;
  }

  template <typename StringType> bool parse_owned_(StringType &&contents, std::false_type) {
    std::unique_ptr<std::string> new_buffer(new std::string(contents.c_str(), contents.size()));
    reset_source_();
    if (new_buffer->empty())
      return false;
    owned_buffer_ = std::move(new_buffer);
    buffer_ = owned_buffer_->c_str();
    buffer_size_ = owned_buffer_->size();
    return true;
  }

  template <typename StringType> bool parse_dispatch_(StringType &&contents, std::false_type) {
    typedef typename std::decay<StringType>::type DecayedString;
    return parse_owned_(std::forward<StringType>(contents),
                        typename std::is_same<DecayedString, std::string>::type());
  }

public:
  class Cell : public basic_cell<quote_character, trim_policy> {
    using base_type = basic_cell<quote_character, trim_policy>;

  public:
    Cell() = default;
    explicit Cell(const base_type &cell) noexcept : base_type(cell) {}
    Cell(const char *buffer, size_t start, size_t end, bool escaped) noexcept
        : base_type(buffer, start, end, escaped) {}

#if CSV2_HAS_STRING_VIEW
    std::string_view read_view() const { return base_type::read_view(); }
#endif

    template <typename Container> void read_raw_value(Container &result) const {
      base_type::read_raw_value(result);
    }

    template <typename Container> void read_value(Container &result) const {
      base_type::read_value(result);
    }
  };

  class Row : public basic_row<delimiter, quote_character, trim_policy> {
    using base_type = basic_row<delimiter, quote_character, trim_policy>;

  public:
    using csv2_row_view_marker = Row;
    using Cell = typename Reader::Cell;
    Row() = default;
    Row(const char *buffer, size_t start, size_t end) noexcept : base_type(buffer, start, end) {}

    const char *address() const noexcept { return base_type::address(); }
    size_t length() const { return base_type::length(); }

    template <typename Container> void read_raw_value(Container &result) const {
      base_type::read_raw_value(result);
    }

    class CellIterator {
      typename base_type::CellIterator iterator_;

    public:
      using value_type = Cell;
      using difference_type = std::ptrdiff_t;
      using reference = Cell;
      using pointer = detail::arrow_proxy<Cell>;
      using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
      using iterator_concept = std::forward_iterator_tag;
#endif

      CellIterator() = default;
      explicit CellIterator(typename base_type::CellIterator iterator) : iterator_(iterator) {}
      CellIterator(const char *buffer, size_t start, size_t end) : iterator_(buffer, start, end) {}
      CellIterator(const char *buffer, size_t buffer_size, size_t start, size_t end)
          : iterator_(buffer, buffer_size, start, end) {}

      CellIterator &operator++() {
        ++iterator_;
        return *this;
      }
      CellIterator operator++(int) {
        CellIterator previous(*this);
        ++(*this);
        return previous;
      }

      Cell operator*() const { return Cell(*iterator_); }
      pointer operator->() const { return pointer(operator*()); }

      bool operator==(const CellIterator &other) const noexcept {
        return iterator_ == other.iterator_;
      }
      bool operator!=(const CellIterator &other) const noexcept { return !(*this == other); }
    };

    CellIterator begin() const { return CellIterator(base_type::begin()); }
    CellIterator end() const { return CellIterator(base_type::end()); }
  };

  Reader() = default;
  Reader(const Reader &) = delete;
  Reader &operator=(const Reader &) = delete;

  Reader(Reader &&other)
      :
#if CSV2_HAS_MMAP
        mmap_(std::move(other.mmap_)),
#endif
        owned_buffer_(std::move(other.owned_buffer_)), buffer_(other.buffer_),
        buffer_size_(other.buffer_size_) {
    other.clear_buffer_();
  }

  Reader &operator=(Reader &&other) {
    if (this != &other) {
      // The borrowed source may be a view into storage currently owned by this Reader.
      if (owns_range_(other.buffer_, other.buffer_size_)) {
        buffer_ = other.buffer_;
        buffer_size_ = other.buffer_size_;
        other.clear_buffer_();
        return *this;
      }
      reset_source_();
#if CSV2_HAS_MMAP
      mmap_ = std::move(other.mmap_);
#endif
      owned_buffer_ = std::move(other.owned_buffer_);
      buffer_ = other.buffer_;
      buffer_size_ = other.buffer_size_;
      other.clear_buffer_();
    }
    return *this;
  }

#if CSV2_HAS_MMAP
  // Memory-map a file. A failed mapping clears any previous source.
  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value ||
                              mio::detail::is_range_path<StringType>::value,
                          bool>::type
  mmap(StringType &&filename, std::error_code &error) {
    // Map through a temporary so a C-string path may safely point into this
    // Reader's current owned or mapped source until the OS consumes it.
    mio::mmap_source new_mapping;
    new_mapping.map(std::forward<StringType>(filename), error);
    reset_source_();
    if (error || !new_mapping.is_open() || !new_mapping.is_mapped() || new_mapping.size() == 0) {
      if (!error)
        error = std::make_error_code(std::errc::invalid_argument);
      new_mapping.unmap();
      return false;
    }
    mmap_ = std::move(new_mapping);
    buffer_ = mmap_.data();
    buffer_size_ = mmap_.size();
    return true;
  }

  template <typename Handle>
  typename std::enable_if<std::is_same<typename std::decay<Handle>::type,
                                       typename mio::mmap_source::handle_type>::value,
                          bool>::type
  mmap(Handle handle, std::error_code &error) {
    mio::mmap_source new_mapping;
    new_mapping.map(handle, 0, mio::map_entire_file, error);
    reset_source_();
    if (error || !new_mapping.is_open() || !new_mapping.is_mapped() || new_mapping.size() == 0) {
      if (!error)
        error = std::make_error_code(std::errc::invalid_argument);
      new_mapping.unmap();
      return false;
    }
    mmap_ = std::move(new_mapping);
    buffer_ = mmap_.data();
    buffer_size_ = mmap_.size();
    return true;
  }

  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value ||
                              mio::detail::is_range_path<StringType>::value,
                          bool>::type
  mmap(StringType &&filename) {
    std::error_code error;
    return mmap(std::forward<StringType>(filename), error);
  }

  template <typename Handle>
  typename std::enable_if<std::is_same<typename std::decay<Handle>::type,
                                       typename mio::mmap_source::handle_type>::value,
                          bool>::type
  mmap(Handle handle) {
    std::error_code error;
    return mmap(handle, error);
  }

#if CSV2_HAS_EXPECTED
  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value ||
                              mio::detail::is_range_path<StringType>::value,
                          std::expected<void, std::error_code>>::type
  mmap_expected(StringType &&filename) {
    std::error_code error;
    if (mmap(std::forward<StringType>(filename), error))
      return {};
    return std::unexpected(error);
  }

  template <typename Handle>
  typename std::enable_if<std::is_same<typename std::decay<Handle>::type,
                                       typename mio::mmap_source::handle_type>::value,
                          std::expected<void, std::error_code>>::type
  mmap_expected(Handle handle) {
    std::error_code error;
    if (mmap(handle, error))
      return {};
    return std::unexpected(error);
  }
#endif
#endif

  // Lvalue strings are borrowed; rvalues are owned. Borrowed address and extent
  // must remain valid. Any mutation invalidates previously acquired views and
  // cursors, which must be discarded and reacquired from this Reader.
  template <typename StringType> bool parse(StringType &&contents) {
    return parse_dispatch_(std::forward<StringType>(contents),
                           typename std::is_lvalue_reference<StringType &&>::type());
  }

  // Borrow exactly size bytes under the lifetime and mutation contract above.
  bool parse_borrowed(const char *data, size_t size) noexcept {
    if (!data || size == 0) {
      reset_source_();
      return false;
    }
    const bool owned_range = owns_range_(data, size);
    if (aliases_source_(data) && !owned_range) {
      reset_source_();
      return false;
    }
    if (!owned_range)
      reset_source_();
    buffer_ = data;
    buffer_size_ = size;
    return true;
  }

  // Own an independent copy (or moved value) of the input string.
  bool parse_owned(std::string contents) {
    return parse_owned_(std::move(contents), std::true_type());
  }

#if CSV2_HAS_SPAN
  bool parse_borrowed(std::span<const char> contents) noexcept {
    return parse_borrowed(contents.data(), contents.size());
  }
#endif

#if CSV2_HAS_STRING_VIEW
  // Borrow a string_view under the lifetime and mutation contract above.
  bool parse_view(std::string_view sv) {
    const char *const data = sv.data();
    const size_t size = sv.size();
    if (size == 0) {
      reset_source_();
      return false;
    }
    const bool owned_range = owns_range_(data, size);
    if (aliases_source_(data) && !owned_range) {
      reset_source_();
      return false;
    }
    if (!owned_range)
      reset_source_();
    buffer_ = data;
    buffer_size_ = size;
    return true;
  }
#endif

  bool validate(parse_error &error) const
      noexcept(noexcept(trim_policy::trim(buffer_, size_t(), size_t()))) {
    return detail::validate_csv<delimiter, quote_character, trim_policy>(buffer_, buffer_size_,
                                                                         error);
  }

#if CSV2_HAS_EXPECTED
  std::expected<void, parse_error> validate_expected() const
      noexcept(noexcept(trim_policy::trim(buffer_, size_t(), size_t()))) {
    parse_error error;
    if (validate(error))
      return {};
    return std::unexpected(error);
  }
#endif

  using RowIndex = csv2::RowIndex<delimiter, quote_character, trim_policy, Row>;
  class RowIterator;

  class RowIterator {
    const char *buffer_{nullptr};
    size_t buffer_size_{0};
    size_t start_{0};
    size_t content_end_{0};
    size_t next_start_{0};
    friend class Reader;

  public:
    using value_type = Row;
    using difference_type = std::ptrdiff_t;
    using reference = Row;
    using pointer = detail::arrow_proxy<Row>;
    using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
    using iterator_concept = std::forward_iterator_tag;
#endif

    RowIterator() = default;

    RowIterator(const char *buffer, size_t buffer_size, size_t start)
        : buffer_(buffer), buffer_size_(buffer_size),
          start_(start < buffer_size ? start : buffer_size), content_end_(buffer_size),
          next_start_(buffer_size) {
      if (start_ < buffer_size_) {
        const detail::record_bounds bounds =
            detail::find_record_bounds<quote_character>(buffer_, buffer_size_, start_);
        content_end_ = bounds.content_end;
        next_start_ = bounds.next_start;
      }
    }

    RowIterator &operator++() {
      start_ = next_start_;
      if (start_ < buffer_size_) {
        const detail::record_bounds bounds =
            detail::find_record_bounds<quote_character>(buffer_, buffer_size_, start_);
        content_end_ = bounds.content_end;
        next_start_ = bounds.next_start;
      } else {
        start_ = buffer_size_;
        content_end_ = buffer_size_;
        next_start_ = buffer_size_;
      }
      return *this;
    }

    RowIterator operator++(int) {
      RowIterator previous(*this);
      ++(*this);
      return previous;
    }

    Row operator*() const { return Row(buffer_, start_, content_end_); }
    pointer operator->() const { return pointer(operator*()); }

    bool operator==(const RowIterator &rhs) const noexcept {
      return buffer_ == rhs.buffer_ && buffer_size_ == rhs.buffer_size_ && start_ == rhs.start_ &&
             content_end_ == rhs.content_end_ && next_start_ == rhs.next_start_;
    }

    bool operator!=(const RowIterator &rhs) const noexcept { return !(*this == rhs); }
  };

  RowIterator begin() const {
    if (!buffer_ || buffer_size_ == 0)
      return end();
    if (first_row_is_header::value) {
      const detail::record_bounds header =
          detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0);
      return RowIterator(buffer_, buffer_size_, header.next_start);
    }
    return RowIterator(buffer_, buffer_size_, 0);
  }

  RowIterator end() const { return RowIterator(buffer_, buffer_size_, buffer_size_); }

  Row header() const {
    if (!buffer_ || buffer_size_ == 0)
      return Row();
    const detail::record_bounds bounds =
        detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0);
    return Row(buffer_, 0, bounds.content_end);
  }

  /** Returns the number of records, excluding the header when configured. */
  size_t rows(bool ignore_empty_lines = false) const {
    if (!buffer_ || buffer_size_ == 0)
      return 0;

    size_t start = 0;
    if (first_row_is_header::value)
      start = detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0).next_start;

    size_t result = 0;
    while (start < buffer_size_) {
      const detail::record_bounds bounds =
          detail::find_record_bounds<quote_character>(buffer_, buffer_size_, start);
      if (!ignore_empty_lines || bounds.content_end != start)
        ++result;
      start = bounds.next_start;
    }
    return result;
  }

  size_t cols() const {
    size_t result = 0;
    for (const auto cell : header()) {
      (void)cell;
      ++result;
    }
    return result;
  }

  RowIndex index(bool ignore_empty_lines = false) const {
    size_t start = 0;
    if (buffer_ && first_row_is_header::value)
      start = detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0).next_start;
    return RowIndex(buffer_, buffer_size_, start, ignore_empty_lines);
  }
};

} // namespace csv2
#pragma once

#include <cstring>
// #include <csv2/detail/config.hpp>
// #include <csv2/parameters.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <type_traits>
#include <utility>
#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif

namespace csv2 {

namespace stream_ownership {
struct close_on_destroy {};
struct leave_open {};
} // namespace stream_ownership

namespace quote_policy {
struct none {};
struct minimal {};
struct always {};
} // namespace quote_policy

namespace detail {

struct direct_character_fields {};

using std::begin;
using std::end;

template <typename Range>
auto adl_begin(Range &&range) -> decltype(begin(std::forward<Range>(range))) {
  return begin(std::forward<Range>(range));
}

template <typename Range> auto adl_end(Range &&range) -> decltype(end(std::forward<Range>(range))) {
  return end(std::forward<Range>(range));
}

template <typename T> struct is_direct_character_field : std::false_type {};

template <typename Traits, typename Allocator>
struct is_direct_character_field<std::basic_string<char, Traits, Allocator>> : std::true_type {};

#if CSV2_HAS_STRING_VIEW
template <typename Traits>
struct is_direct_character_field<std::basic_string_view<char, Traits>> : std::true_type {};
#endif

} // namespace detail

template <typename, typename T> struct has_close : std::false_type {};

template <typename C, typename Ret, typename... Args> struct has_close<C, Ret(Args...)> {
private:
  template <typename T>
  static constexpr auto check(T *) ->
      typename std::is_same<decltype(std::declval<T &>().close(std::declval<Args>()...)),
                            Ret>::type;

  template <typename> static constexpr std::false_type check(...);

public:
  static constexpr bool value = decltype(check<C>(0))::value;
};

template <class delimiter = delimiter<','>, typename Stream = std::ofstream,
          typename Ownership = stream_ownership::close_on_destroy,
          typename QuotePolicy = quote_policy::none>
class basic_writer {
  static_assert(std::is_same<Ownership, stream_ownership::close_on_destroy>::value ||
                    std::is_same<Ownership, stream_ownership::leave_open>::value,
                "csv2 writer ownership policy is not supported");
  static_assert(std::is_same<QuotePolicy, quote_policy::none>::value ||
                    std::is_same<QuotePolicy, quote_policy::minimal>::value ||
                    std::is_same<QuotePolicy, quote_policy::always>::value,
                "csv2 writer quote policy is not supported");

  Stream *stream_; // output stream for the writer
  bool active_;

  static void close_stream_(Stream &stream, std::true_type) { stream.close(); }

  static void close_stream_(Stream &, std::false_type) {}

  void close_noexcept_() noexcept {
    if (!active_)
      return;
    active_ = false;
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
    try {
      close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
    } catch (...) {
    }
#else
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
#endif
  }

  void release_noexcept_(std::true_type) noexcept { close_noexcept_(); }

  void release_noexcept_(std::false_type) noexcept { active_ = false; }

  void release_noexcept_() noexcept {
    release_noexcept_(typename std::is_same<Ownership, stream_ownership::close_on_destroy>::type());
  }

  template <typename Field, typename CandidateStream = Stream>
  auto write_raw_contiguous_(const Field &field, int)
      -> decltype(std::declval<CandidateStream &>().width(),
                  std::declval<CandidateStream &>()
                      << std::string(static_cast<const char *>(field.data()),
                                     static_cast<size_t>(field.size())),
                  void()) {
    if (stream_->width() != 0) {
      *stream_ << std::string(static_cast<const char *>(field.data()),
                              static_cast<size_t>(field.size()));
      return;
    }
    stream_->write(static_cast<const char *>(field.data()),
                   static_cast<std::streamsize>(field.size()));
  }

  template <typename Field> void write_raw_contiguous_(const Field &field, long) {
    stream_->write(static_cast<const char *>(field.data()),
                   static_cast<std::streamsize>(field.size()));
  }

  template <typename Field> void write_raw_field_(const Field &field, std::true_type) {
    write_raw_contiguous_(field, 0);
  }

  template <typename Field>
  auto write_raw_fallback_(const Field &field, int) -> decltype(*stream_ << field, void()) {
    *stream_ << field;
  }

  template <typename Field> void write_raw_fallback_(const Field &field, long) {
    write_raw_contiguous_(field, 0);
  }

  template <typename Field> void write_raw_field_(const Field &field, std::false_type) {
    write_raw_fallback_(field, 0);
  }

  static bool should_quote_(const char *, size_t, quote_policy::always) noexcept { return true; }

  static bool should_quote_(const char *data, size_t size, quote_policy::minimal) noexcept {
    for (size_t i = 0; i < size; ++i) {
      if (data[i] == delimiter::value || data[i] == '"' || data[i] == '\r' || data[i] == '\n')
        return true;
    }
    return false;
  }

  template <class Policy> void write_escaped_chars_(const char *data, size_t size, Policy policy) {
    if (!should_quote_(data, size, policy)) {
      if (size != 0)
        stream_->write(data, static_cast<std::streamsize>(size));
      return;
    }

    stream_->write("\"", 1);
    size_t segment = 0;
    for (size_t i = 0; i < size; ++i) {
      if (data[i] != '"')
        continue;
      if (segment < i)
        stream_->write(data + segment, static_cast<std::streamsize>(i - segment));
      stream_->write("\"\"", 2);
      segment = i + 1;
    }
    if (segment < size)
      stream_->write(data + segment, static_cast<std::streamsize>(size - segment));
    stream_->write("\"", 1);
  }

  template <typename Field> void write_formatted_field_(const Field &field) {
    std::ostringstream formatted;
    formatted.copyfmt(*stream_);
    formatted.exceptions(std::ios_base::goodbit);
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
    struct formatted_state_guard {
      Stream *target;
      std::ostringstream *source;
      bool active;

      formatted_state_guard(Stream &target_stream, std::ostringstream &source_stream) noexcept
          : target(&target_stream), source(&source_stream), active(true) {}

      ~formatted_state_guard() noexcept {
        if (!active)
          return;
        try {
          target->width(source->width());
          if (source->rdstate() != std::ios_base::goodbit)
            target->setstate(source->rdstate());
        } catch (...) {
        }
      }

      void release() noexcept { active = false; }
    } guard(*stream_, formatted);

    formatted << field;
    guard.release();
#else
    formatted << field;
#endif

    stream_->width(formatted.width());
    const std::ios_base::iostate state = formatted.rdstate();
    const std::string value = formatted.str();
    write_escaped_chars_(value.data(), value.size(), QuotePolicy());
    if (state != std::ios_base::goodbit)
      stream_->setstate(state);
  }

  void write_formatted_field_(const char *data, size_t size) {
    write_formatted_field_(std::string(data, size));
  }

  template <typename Field, typename CandidateStream = Stream>
  auto write_escaped_contiguous_(const Field &field, int)
      -> decltype(std::declval<CandidateStream &>().width(),
                  std::declval<std::ostringstream &>().copyfmt(std::declval<CandidateStream &>()),
                  std::declval<CandidateStream &>()
                      << std::string(static_cast<const char *>(field.data()),
                                     static_cast<size_t>(field.size())),
                  void()) {
    const char *const data = static_cast<const char *>(field.data());
    const size_t size = static_cast<size_t>(field.size());
    if (stream_->width() == 0) {
      write_escaped_chars_(data, size, QuotePolicy());
      return;
    }
    write_formatted_field_(data, size);
  }

  template <typename Field> void write_escaped_contiguous_(const Field &field, long) {
    write_escaped_chars_(static_cast<const char *>(field.data()), static_cast<size_t>(field.size()),
                         QuotePolicy());
  }

  template <typename Field> void write_escaped_field_(const Field &field, std::true_type) {
    write_escaped_contiguous_(field, 0);
  }

  template <typename Field>
  auto write_escaped_fallback_(const Field &field,
                               int) -> decltype(std::declval<std::ostringstream &>() << field,
                                                void()) {
    write_formatted_field_(field);
  }

  template <typename Field> void write_escaped_fallback_(const Field &field, long) {
    write_escaped_contiguous_(field, 0);
  }

  template <typename Field> void write_escaped_field_(const Field &field, std::false_type) {
    write_escaped_fallback_(field, 0);
  }

  template <typename Field> void write_field_(const Field &field, std::true_type) {
    typedef typename std::decay<Field>::type field_type;
    write_raw_field_(field, typename detail::is_direct_character_field<field_type>::type());
  }

  template <typename Field> void write_field_(const Field &field, std::false_type) {
    typedef typename std::decay<Field>::type field_type;
    write_escaped_field_(field, typename detail::is_direct_character_field<field_type>::type());
  }

  template <typename Field>
  void write_field_(const Field &field, std::true_type, detail::direct_character_fields) {
    write_field_(field, std::true_type());
  }

  template <typename Field>
  void write_field_(const Field &field, std::false_type, detail::direct_character_fields) {
    write_field_(field, std::false_type());
  }

protected:
  template <typename Field>
  auto write_legacy_next_field_(char separator, const Field &field,
                                int) -> decltype((*stream_ << separator) << field, void()) {
    (*stream_ << separator) << field;
  }

  template <typename Field>
  void write_legacy_next_field_(char separator, const Field &field, long) {
    *stream_ << separator;
    write_raw_fallback_(field, 0);
  }

  template <typename Range> void write_legacy_iterable_row_(Range &strings) {
    auto current = detail::adl_begin(strings);
    const auto last = detail::adl_end(strings);
    if (current != last) {
      write_raw_fallback_(*current, 0);
      const char separator = delimiter::value;
      while (++current != last)
        write_legacy_next_field_(separator, *current, 0);
    }
    *stream_ << '\n';
  }

  template <typename Container>
  auto write_legacy_row_dispatch_(Container &&row, int)
      -> decltype(detail::adl_begin(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  detail::adl_end(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  void()) {
    const auto &strings = row;
    write_legacy_iterable_row_(strings);
  }

  template <typename Container> void write_legacy_row_dispatch_(Container &&row, long) {
    auto &&strings = std::forward<Container>(row);
    write_legacy_iterable_row_(strings);
  }

  template <typename Container> void write_legacy_row_(Container &&row) {
    if (!active_)
      return;
    write_legacy_row_dispatch_(std::forward<Container>(row), 0);
  }

  template <typename Range> void write_legacy_iterable_rows_(Range &container_of_rows) {
    auto current = detail::adl_begin(container_of_rows);
    const auto last = detail::adl_end(container_of_rows);
    while (current != last) {
      write_legacy_row_(*current);
      ++current;
    }
  }

  template <typename Container>
  auto write_legacy_rows_dispatch_(Container &&rows, int)
      -> decltype(detail::adl_begin(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  detail::adl_end(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  void()) {
    const auto &container_of_rows = rows;
    write_legacy_iterable_rows_(container_of_rows);
  }

  template <typename Container> void write_legacy_rows_dispatch_(Container &&rows, long) {
    auto &&container_of_rows = std::forward<Container>(rows);
    write_legacy_iterable_rows_(container_of_rows);
  }

  template <typename Container> void write_legacy_rows_(Container &&rows) {
    if (!active_)
      return;
    write_legacy_rows_dispatch_(std::forward<Container>(rows), 0);
  }

  template <typename Container, typename FieldPolicy>
  void write_row_with_policy_(Container &&row, FieldPolicy field_policy) {
    if (!active_)
      return;
    auto &&strings = std::forward<Container>(row);
    using std::begin;
    using std::end;
    auto current = begin(strings);
    const auto last = end(strings);
    if (current != last) {
      write_field_(*current, typename std::is_same<QuotePolicy, quote_policy::none>::type(),
                   field_policy);
      const char separator = delimiter::value;
      while (++current != last) {
        *stream_ << separator;
        write_field_(*current, typename std::is_same<QuotePolicy, quote_policy::none>::type(),
                     field_policy);
      }
    }
    *stream_ << '\n';
  }

  template <typename Container, typename FieldPolicy>
  void write_rows_with_policy_(Container &&rows, FieldPolicy field_policy) {
    if (!active_)
      return;
    auto &&container_of_rows = std::forward<Container>(rows);
    using std::begin;
    using std::end;
    auto current = begin(container_of_rows);
    const auto last = end(container_of_rows);
    while (current != last) {
      write_row_with_policy_(*current, field_policy);
      ++current;
    }
  }

public:
  basic_writer(Stream &stream) noexcept : stream_(&stream), active_(true) {}

  basic_writer(const basic_writer &) = delete;
  basic_writer &operator=(const basic_writer &) = delete;

  basic_writer(basic_writer &&other) noexcept : stream_(other.stream_), active_(other.active_) {
    other.stream_ = nullptr;
    other.active_ = false;
  }

  basic_writer &operator=(basic_writer &&other) noexcept {
    if (this != &other) {
      release_noexcept_();
      stream_ = other.stream_;
      active_ = other.active_;
      other.stream_ = nullptr;
      other.active_ = false;
    }
    return *this;
  }

  ~basic_writer() noexcept { release_noexcept_(); }

  void close() {
    if (!active_)
      return;
    active_ = false;
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
  }

  template <typename Container> void write_row(Container &&row) {
    write_row_with_policy_(std::forward<Container>(row), detail::direct_character_fields());
  }

  template <typename Container> void write_rows(Container &&rows) {
    write_rows_with_policy_(std::forward<Container>(rows), detail::direct_character_fields());
  }
};

// Keep the historical two-parameter class template intact. Configurable
// ownership and quoting live on basic_writer so C++11/14 code can continue to
// pass csv2::Writer to a template-template parameter expecting two arguments.
template <class delimiter = delimiter<','>, typename Stream = std::ofstream>
class Writer : public basic_writer<delimiter, Stream, stream_ownership::close_on_destroy,
                                   quote_policy::none> {
  using base_type =
      basic_writer<delimiter, Stream, stream_ownership::close_on_destroy, quote_policy::none>;

public:
  Writer(Stream &stream) noexcept : base_type(stream) {}

  void close() { base_type::close(); }

  template <typename Container> void write_row(Container &&row) {
    this->write_legacy_row_(std::forward<Container>(row));
  }

  template <typename Container> void write_rows(Container &&rows) {
    this->write_legacy_rows_(std::forward<Container>(rows));
  }
};

template <class delimiter = delimiter<','>, typename Stream = std::ofstream,
          typename Ownership = stream_ownership::close_on_destroy>
using EscapingWriter = basic_writer<delimiter, Stream, Ownership, quote_policy::minimal>;

} // namespace csv2
