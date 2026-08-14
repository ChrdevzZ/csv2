#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

#include <cstdint>

using namespace csv2_test;

namespace {

typedef csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                     csv2::first_row_is_header<false>, csv2::trim_policy::no_trimming>
    roundtrip_reader;

std::vector<std::vector<std::string>> make_rows() {
  std::vector<std::vector<std::string>> rows;
  rows.push_back(std::vector<std::string>(
      {"plain", "a,b", "a\"b", "line\nbreak", "car\rriage", "", "caf\xc3\xa9"}));

  const unsigned char alphabet[] = {'a', 'Z', '0', ',', '"', '\r', '\n', ' ', '\t', 0xc3, 0xa9};
  std::uint32_t state = 0x43535632u;
  for (std::size_t row_index = 0; row_index < 256; ++row_index) {
    const std::size_t field_count = 1 + row_index % 8;
    std::vector<std::string> row;
    for (std::size_t field_index = 0; field_index < field_count; ++field_index) {
      state = state * 1664525u + 1013904223u;
      const std::size_t length = (state >> 24) % 65;
      std::string field;
      field.reserve(length);
      for (std::size_t byte_index = 0; byte_index < length; ++byte_index) {
        state = state * 1664525u + 1013904223u;
        field.push_back(static_cast<char>(alphabet[(state >> 24) % sizeof(alphabet)]));
      }
      row.push_back(field);
    }
    rows.push_back(row);
  }
  return rows;
}

std::vector<std::vector<std::string>> decode_rows(const std::string &encoded) {
  roundtrip_reader reader;
  if (!reader.parse_borrowed(encoded.data(), encoded.size())) {
    CSV2_CHECK(false);
    return std::vector<std::vector<std::string>>();
  }
  csv2::parse_error error;
  if (!reader.validate(error)) {
    CSV2_CHECK(false);
    return std::vector<std::vector<std::string>>();
  }

  std::vector<std::vector<std::string>> rows;
  for (const roundtrip_reader::Row row : reader) {
    std::vector<std::string> fields;
    for (const roundtrip_reader::Cell cell : row) {
      std::string field;
      cell.copy_content_to(std::back_inserter(field));
      fields.push_back(field);
    }
    rows.push_back(fields);
  }
  return rows;
}

template <typename QuotePolicy>
void check_roundtrip(const std::vector<std::vector<std::string>> &rows) {
  std::ostringstream output;
  csv2::basic_writer<csv2::delimiter<','>, std::ostringstream, csv2::stream_ownership::leave_open,
                     QuotePolicy>
      writer(output);
  writer.write_rows(rows);
  CSV2_CHECK_EQ(decode_rows(output.str()), rows);
}

} // namespace

CSV2_TEST_CASE("property.roundtrip.deterministic-minimal-always", "property.roundtrip") {
  const std::vector<std::vector<std::string>> rows = make_rows();
  check_roundtrip<csv2::quote_policy::minimal>(rows);
  check_roundtrip<csv2::quote_policy::always>(rows);
}
