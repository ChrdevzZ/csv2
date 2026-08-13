#include <csv2/reader.hpp>

#include <cstddef>
#include <cstdint>
#include <iterator>
#include <string>
#include <vector>

template <class Reader> void exercise_reader(Reader &reader) {
  csv2::parse_error parse_error;
  (void)reader.validate(parse_error);
  for (const auto row : reader) {
    std::string raw_row;
    row.read_raw_value(raw_row);
    for (const auto cell : row) {
      std::string raw;
      std::vector<char> decoded;
      cell.read_raw_value(raw);
      cell.read_value(decoded);
      std::string content;
      cell.copy_content_to(std::back_inserter(content));
      long long integer = 0;
      csv2::conversion_error conversion_error;
      (void)cell.try_parse(integer, conversion_error);
    }
  }
  (void)reader.index();
  (void)reader.index(true);
}

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *data, std::size_t size) {
  const char *const bytes = reinterpret_cast<const char *>(data);
  csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>, csv2::first_row_is_header<false>>
      reader;
  if (reader.parse_borrowed(bytes, size))
    exercise_reader(reader);

  // Exercise non-default policies, including the supported case where the
  // delimiter and quote byte are identical. This reaches scanner fallbacks
  // that the default comma/double-quote policy cannot cover.
  csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'\''>, csv2::first_row_is_header<false>,
               csv2::trim_policy::no_trimming>
      alternate_reader;
  if (alternate_reader.parse_borrowed(bytes, size))
    exercise_reader(alternate_reader);

  csv2::Reader<csv2::delimiter<'"'>, csv2::quote_character<'"'>, csv2::first_row_is_header<false>>
      shared_policy_reader;
  if (shared_policy_reader.parse_borrowed(bytes, size))
    exercise_reader(shared_policy_reader);
  return 0;
}

#if defined(CSV2_FUZZ_STANDALONE)
int main() {
  const char *const seeds[] = {"a,b\n1,2", "a,\"b\nc\",d", "\"a\"\"b\",", "\r\n", "\""};
  for (const char *seed : seeds)
    LLVMFuzzerTestOneInput(reinterpret_cast<const std::uint8_t *>(seed),
                           std::char_traits<char>::length(seed));

  std::vector<std::uint8_t> generated(512);
  std::uint32_t state = 0x43535632u;
  for (std::size_t run = 0; run < 512; ++run) {
    const std::size_t length = run % (generated.size() + 1);
    for (std::size_t i = 0; i < length; ++i) {
      state = state * 1664525u + 1013904223u;
      generated[i] = static_cast<std::uint8_t>(state >> 24);
    }
    LLVMFuzzerTestOneInput(generated.data(), length);
  }
  return 0;
}
#endif
