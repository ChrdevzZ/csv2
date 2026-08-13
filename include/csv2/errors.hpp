#pragma once

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
