#pragma once

#include <csv2/detail/config.hpp>
#include <csv2/errors.hpp>

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
