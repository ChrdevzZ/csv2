#include <csv2/reader.hpp>
#include <csv2/writer.hpp>

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iterator>
#include <sstream>
#include <string>
#include <vector>

namespace {

typedef csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                     csv2::first_row_is_header<false>, csv2::trim_policy::no_trimming>
    fuzz_reader;

std::vector<std::string> split_fields(const std::uint8_t *data, std::size_t size) {
  std::vector<std::string> fields(1);
  // A blank CSV record cannot distinguish zero fields from one empty field.
  // Map the empty fuzz input to two empty fields so minimal quoting remains a
  // bijection for every generated case.
  if (size == 0)
    fields.push_back(std::string());
  for (std::size_t index = 0; index < size; ++index) {
    if (data[index] == 0) {
      fields.push_back(std::string());
    } else {
      fields.back().push_back(static_cast<char>(data[index]));
    }
  }
  return fields;
}

bool decodes_as_exactly_one_row(const std::string &encoded,
                                const std::vector<std::string> &expected) {
  fuzz_reader reader;
  if (!reader.parse_borrowed(encoded.data(), encoded.size()))
    return false;
  csv2::parse_error error;
  if (!reader.validate(error))
    return false;

  fuzz_reader::RowIterator row = reader.begin();
  if (row == reader.end())
    return false;
  std::vector<std::string> actual;
  for (const fuzz_reader::Cell cell : *row) {
    std::string value;
    cell.copy_content_to(std::back_inserter(value));
    actual.push_back(value);
  }
  ++row;
  return row == reader.end() && actual == expected;
}

bool roundtrip(const std::vector<std::string> &expected) {
  std::ostringstream output;
  csv2::EscapingWriter<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open>
      writer(output);
  writer.write_row(expected);
  return decodes_as_exactly_one_row(output.str(), expected);
}

} // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *data, std::size_t size) {
  if (!roundtrip(split_fields(data, size))) {
#if defined(CSV2_FUZZ_STANDALONE)
    return 1;
#else
    std::abort();
#endif
  }
  return 0;
}

#if defined(CSV2_FUZZ_STANDALONE)
int main() {
  const char *const seeds[] = {"plain", "a,b", "a\"b", "line\nbreak", "a\0b\0"};
  const std::size_t lengths[] = {5, 3, 3, 10, 4};
  for (std::size_t index = 0; index < sizeof(seeds) / sizeof(seeds[0]); ++index) {
    if (LLVMFuzzerTestOneInput(reinterpret_cast<const std::uint8_t *>(seeds[index]),
                               lengths[index]) != 0)
      return 1;
  }

  std::vector<std::string> one_row(1, "first");
  if (decodes_as_exactly_one_row("first\nsecond\n", one_row))
    return 1;

  std::vector<std::uint8_t> generated(512);
  std::uint32_t state = 0x57525452u;
  for (std::size_t run = 0; run < 512; ++run) {
    const std::size_t length = run % (generated.size() + 1);
    for (std::size_t index = 0; index < length; ++index) {
      state = state * 1664525u + 1013904223u;
      generated[index] = static_cast<std::uint8_t>(state >> 24);
    }
    if (LLVMFuzzerTestOneInput(generated.data(), length) != 0)
      return 1;
  }
  return 0;
}
#endif
