#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <streambuf>
#include <string>
#include <vector>

#ifndef CSV2_BENCHMARK_REVISION
#define CSV2_BENCHMARK_REVISION "unstamped"
#endif

namespace {

using CommonReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::first_row_is_header<false>>;

const char protocol[] = "csv2-common-v3";
volatile std::uint64_t benchmark_sink = 0;
bool timed_phase = false;
std::uint64_t timed_checksum_mix_calls = 0;
std::uint64_t timed_reader_steps = 0;

struct Options {
  std::string operation;
  std::string input;
  std::string source;
  std::size_t iterations{1};
};

struct Observation {
  std::uint64_t rows{0};
  std::uint64_t cells{0};
  std::uint64_t row_bytes{0};
};

void mix(std::uint64_t &checksum, std::uint64_t value) noexcept {
  if (timed_phase)
    ++timed_checksum_mix_calls;
  checksum ^= value + 0x9e3779b97f4a7c15ull + (checksum << 6) + (checksum >> 2);
}

class FixedOutputBuffer : public std::streambuf {
  std::vector<char> storage_;

public:
  explicit FixedOutputBuffer(std::size_t capacity) : storage_(capacity) { reset(); }

  void reset() {
    char *const first = storage_.empty() ? 0 : &storage_[0];
    setp(first, first == 0 ? 0 : first + storage_.size());
  }

  const char *data() const { return storage_.empty() ? 0 : &storage_[0]; }
  std::size_t size() const { return pbase() == 0 ? 0 : static_cast<std::size_t>(pptr() - pbase()); }

protected:
  std::streamsize xsputn(const char *data, std::streamsize size) override {
    if (size <= 0)
      return 0;
    const std::streamsize available = pptr() == 0 ? 0 : epptr() - pptr();
    const std::streamsize written = (std::min)(available, size);
    if (written > 0) {
      std::copy(data, data + written, pptr());
      std::streamsize remaining = written;
      while (remaining > 0) {
        const int step = static_cast<int>(
            (std::min)(remaining, static_cast<std::streamsize>((std::numeric_limits<int>::max)())));
        pbump(step);
        remaining -= step;
      }
    }
    return written;
  }

  int_type overflow(int_type character) override {
    if (traits_type::eq_int_type(character, traits_type::eof()) || pptr() == epptr())
      return traits_type::eof();
    *pptr() = traits_type::to_char_type(character);
    pbump(1);
    return character;
  }
};

std::uint64_t output_checksum(const FixedOutputBuffer &buffer) {
  std::uint64_t checksum = 1469598103934665603ull;
  for (std::size_t index = 0; index < buffer.size(); ++index)
    mix(checksum, static_cast<unsigned char>(buffer.data()[index]));
  return checksum;
}

bool writer_capacity(std::uint64_t input_bytes, const Observation &sample, std::size_t &capacity) {
  const std::uint64_t maximum = (std::numeric_limits<std::size_t>::max)();
  if (input_bytes > (maximum - 64) / 3 || sample.cells > (maximum - 64) / 3 ||
      sample.rows > maximum - 64)
    return false;
  const std::uint64_t input_capacity = input_bytes * 3;
  const std::uint64_t cell_capacity = sample.cells * 3;
  if (input_capacity > maximum - cell_capacity - 64)
    return false;
  const std::uint64_t partial = input_capacity + cell_capacity + 64;
  if (sample.rows > maximum - partial)
    return false;
  capacity = static_cast<std::size_t>(partial + sample.rows);
  return true;
}

bool parse_size(const char *text, std::size_t &value) {
  if (!text || *text == '\0')
    return false;

  std::size_t parsed = 0;
  const std::size_t maximum = (std::numeric_limits<std::size_t>::max)();
  for (const char *current = text; *current != '\0'; ++current) {
    if (*current < '0' || *current > '9')
      return false;
    const std::size_t digit = static_cast<std::size_t>(*current - '0');
    if (parsed > (maximum - digit) / std::size_t(10))
      return false;
    parsed = parsed * std::size_t(10) + digit;
  }
  if (parsed == 0)
    return false;
  value = parsed;
  return true;
}

bool parse_options(int argc, char **argv, Options &options) {
  for (int argument = 1; argument < argc; ++argument) {
    if (argument + 1 >= argc)
      return false;
    const std::string name(argv[argument]);
    const char *const value = argv[++argument];
    if (name == "--operation")
      options.operation = value;
    else if (name == "--input")
      options.input = value;
    else if (name == "--source")
      options.source = value;
    else if (name == "--iterations") {
      if (!parse_size(value, options.iterations))
        return false;
    } else {
      return false;
    }
  }
  return !options.operation.empty() && !options.input.empty() && !options.source.empty();
}

bool read_file(const std::string &path, std::string &contents) {
  std::ifstream input(path.c_str(), std::ios::binary);
  if (!input)
    return false;
  contents.assign(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
  return (input.good() || input.eof()) && !contents.empty();
}

std::uint64_t file_size(const std::string &path) {
  std::ifstream input(path.c_str(), std::ios::binary | std::ios::ate);
  if (!input)
    return 0;
  const std::ifstream::pos_type end = input.tellg();
  return end > 0 ? static_cast<std::uint64_t>(end) : 0;
}

Observation traverse(const CommonReader &reader) {
  Observation result;
  for (const auto row : reader) {
    if (timed_phase)
      ++timed_reader_steps;
    ++result.rows;
    result.row_bytes += static_cast<std::uint64_t>(row.length());
    for (const auto cell : row) {
      if (timed_phase)
        ++timed_reader_steps;
      (void)cell;
      ++result.cells;
    }
  }
  return result;
}

std::uint64_t semantic_checksum(const CommonReader &reader) {
  std::uint64_t checksum = 1469598103934665603ull;
  for (const auto row : reader) {
    mix(checksum, static_cast<std::uint64_t>(row.length()));
    for (const auto cell : row) {
      std::string raw;
      cell.read_raw_value(raw);
      mix(checksum, static_cast<std::uint64_t>(raw.size()));
      for (std::string::const_iterator current = raw.begin(); current != raw.end(); ++current)
        mix(checksum, static_cast<unsigned char>(*current));
    }
  }
  return checksum;
}

typedef std::vector<std::vector<std::string>> StringRows;

void extract_raw_rows(const CommonReader &reader, StringRows &rows) {
  rows.clear();
  for (const auto row : reader) {
    rows.push_back(std::vector<std::string>());
    std::vector<std::string> &result_row = rows.back();
    for (const auto cell : row) {
      result_row.push_back(std::string());
      cell.read_raw_value(result_row.back());
    }
  }
}

#if defined(CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS)
struct RawFieldReference {
  const char *bytes;
  std::size_t length;
};

typedef std::vector<std::vector<RawFieldReference>> RawRows;

struct RawDirectField {
  const RawFieldReference *field;
  const char *data() const noexcept { return field->bytes; }
  std::size_t size() const noexcept { return field->length; }
};

struct RawStreamableField {
  const RawFieldReference *field;
};

std::ostream &operator<<(std::ostream &output, const RawStreamableField &field) {
  return output.write(field.field->bytes, static_cast<std::streamsize>(field.field->length));
}

template <class Field> class PreparedRawRow {
  const std::vector<RawFieldReference> *row_;

public:
  explicit PreparedRawRow(const std::vector<RawFieldReference> &row) : row_(&row) {}

  class iterator {
    std::vector<RawFieldReference>::const_iterator current_;

  public:
    typedef Field value_type;
    typedef std::ptrdiff_t difference_type;
    typedef Field reference;
    typedef void pointer;
    typedef std::input_iterator_tag iterator_category;

    iterator() {}
    explicit iterator(std::vector<RawFieldReference>::const_iterator current) : current_(current) {}
    Field operator*() const {
      Field field = {&*current_};
      return field;
    }
    iterator &operator++() {
      ++current_;
      return *this;
    }
    bool operator==(const iterator &other) const { return current_ == other.current_; }
    bool operator!=(const iterator &other) const { return !(*this == other); }
  };

  iterator begin() const { return iterator(row_->begin()); }
  iterator end() const { return iterator(row_->end()); }
};

void extract_raw_references(const CommonReader &reader, RawRows &rows) {
  rows.clear();
  for (const auto row : reader) {
    rows.push_back(std::vector<RawFieldReference>());
    std::vector<RawFieldReference> &result_row = rows.back();
    for (const auto cell : row) {
      RawFieldReference reference = {cell.raw_data(), cell.raw_size()};
      result_row.push_back(reference);
    }
  }
}

struct StreamableStringField {
  const std::string &value;
};

std::ostream &operator<<(std::ostream &output, const StreamableStringField &field) {
  return output.write(field.value.data(), static_cast<std::streamsize>(field.value.size()));
}

class StreamableStringRow {
  const std::vector<std::string> &row_;

public:
  explicit StreamableStringRow(const std::vector<std::string> &row) : row_(row) {}

  class iterator {
    std::vector<std::string>::const_iterator current_;

  public:
    typedef StreamableStringField value_type;
    typedef std::ptrdiff_t difference_type;
    typedef value_type reference;
    typedef void pointer;
    typedef std::input_iterator_tag iterator_category;

    iterator() {}
    explicit iterator(std::vector<std::string>::const_iterator current) : current_(current) {}
    value_type operator*() const {
      value_type field = {*current_};
      return field;
    }
    iterator &operator++() {
      ++current_;
      return *this;
    }
    bool operator==(const iterator &other) const { return current_ == other.current_; }
    bool operator!=(const iterator &other) const { return !(*this == other); }
  };

  iterator begin() const { return iterator(row_.begin()); }
  iterator end() const { return iterator(row_.end()); }
};

bool is_modern_writer_operation(const std::string &operation) {
  return operation == "writer_raw_direct" || operation == "writer_raw_streamable" ||
         operation == "writer_escaped_direct" || operation == "writer_escaped_streamable";
}

bool is_escaped_writer_operation(const std::string &operation) {
  return operation == "writer_escaped_direct" || operation == "writer_escaped_streamable";
}

void extract_decoded_rows(const CommonReader &reader, StringRows &rows) {
  rows.clear();
  for (const auto row : reader) {
    rows.push_back(std::vector<std::string>());
    std::vector<std::string> &result_row = rows.back();
    for (const auto cell : row) {
      result_row.push_back(std::string());
      cell.copy_content_to(std::back_inserter(result_row.back()));
    }
  }
}
#endif

bool prepare_reader(const Options &options, CommonReader &reader, std::string &storage) {
  if (options.source == "buffer")
    return read_file(options.input, storage) && reader.parse(storage);
#if CSV2_HAS_MMAP
  if (options.source == "mmap")
    return reader.mmap(options.input);
#endif
  return false;
}

bool run_prepared(const Options &options, Observation &result, std::uint64_t &checksum,
                  std::int64_t &elapsed_ns) {
  CommonReader reader;
  std::string storage;
  if (!prepare_reader(options, reader, storage))
    return false;
  checksum = semantic_checksum(reader);

  timed_checksum_mix_calls = 0;
  timed_reader_steps = 0;
  const std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
  timed_phase = true;
  for (std::size_t run = 0; run < options.iterations; ++run) {
    const Observation sample = traverse(reader);
    result.rows += sample.rows;
    result.cells += sample.cells;
    result.row_bytes += sample.row_bytes;
  }
  const std::chrono::steady_clock::time_point stop = std::chrono::steady_clock::now();
  timed_phase = false;
  if (timed_checksum_mix_calls != 0)
    return false;
  elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return true;
}

bool run_legacy_mmap(const Options &options, Observation &result, std::uint64_t &checksum,
                     std::int64_t &elapsed_ns) {
#if CSV2_HAS_MMAP
  if (options.source != "mmap")
    return false;
  {
    CommonReader semantic_reader;
    if (!semantic_reader.mmap(options.input))
      return false;
    checksum = semantic_checksum(semantic_reader);
  }

  elapsed_ns = 0;
  timed_checksum_mix_calls = 0;
  timed_reader_steps = 0;
  for (std::size_t run = 0; run < options.iterations; ++run) {
    const std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
    timed_phase = true;
    CommonReader reader;
    if (!reader.mmap(options.input)) {
      timed_phase = false;
      return false;
    }
    const Observation sample = traverse(reader);
    const std::chrono::steady_clock::time_point stop = std::chrono::steady_clock::now();
    timed_phase = false;
    elapsed_ns += std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
    result.rows += sample.rows;
    result.cells += sample.cells;
    result.row_bytes += sample.row_bytes;
  }
  if (timed_checksum_mix_calls != 0)
    return false;
  return true;
#else
  (void)options;
  (void)result;
  (void)checksum;
  (void)elapsed_ns;
  return false;
#endif
}

bool run_writer(const Options &options, Observation &result, std::uint64_t &checksum,
                std::int64_t &elapsed_ns) {
  CommonReader reader;
  std::string storage;
  if (!prepare_reader(options, reader, storage))
    return false;

  const Observation sample = traverse(reader);
  StringRows prepared_rows;
#if defined(CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS)
  RawRows prepared_raw_rows;
#endif
  if (options.operation == "legacy_writer_raw")
    extract_raw_rows(reader, prepared_rows);
#if defined(CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS)
  else if (is_escaped_writer_operation(options.operation))
    extract_decoded_rows(reader, prepared_rows);
  else if (options.operation == "writer_raw_direct" || options.operation == "writer_raw_streamable")
    extract_raw_references(reader, prepared_raw_rows);
  else if (!is_modern_writer_operation(options.operation))
    return false;
#else
  else
    return false;
#endif

  std::size_t capacity = 0;
  if (!writer_capacity(file_size(options.input), sample, capacity))
    return false;
  FixedOutputBuffer buffer(capacity);
  std::ostream output(&buffer);
  timed_checksum_mix_calls = 0;
  timed_reader_steps = 0;
  const std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
  timed_phase = true;
  if (options.operation == "legacy_writer_raw") {
    csv2::Writer<csv2::delimiter<','>, std::ostream> writer(output);
    for (std::size_t run = 0; run < options.iterations; ++run) {
      buffer.reset();
      output.clear();
      writer.write_rows(prepared_rows);
    }
  }
#if defined(CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS)
  else if (options.operation == "writer_raw_direct") {
    csv2::basic_writer<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open,
                       csv2::quote_policy::none>
        writer(output);
    for (std::size_t run = 0; run < options.iterations; ++run) {
      buffer.reset();
      output.clear();
      for (RawRows::const_iterator row = prepared_raw_rows.begin(); row != prepared_raw_rows.end();
           ++row)
        writer.write_row(PreparedRawRow<RawDirectField>(*row));
    }
  } else if (options.operation == "writer_raw_streamable") {
    csv2::basic_writer<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open,
                       csv2::quote_policy::none>
        writer(output);
    for (std::size_t run = 0; run < options.iterations; ++run) {
      buffer.reset();
      output.clear();
      for (RawRows::const_iterator row = prepared_raw_rows.begin(); row != prepared_raw_rows.end();
           ++row)
        writer.write_row(PreparedRawRow<RawStreamableField>(*row));
    }
  } else if (options.operation == "writer_escaped_direct") {
    csv2::EscapingWriter<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open>
        writer(output);
    for (std::size_t run = 0; run < options.iterations; ++run) {
      buffer.reset();
      output.clear();
      writer.write_rows(prepared_rows);
    }
  } else if (options.operation == "writer_escaped_streamable") {
    csv2::EscapingWriter<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open>
        writer(output);
    for (std::size_t run = 0; run < options.iterations; ++run) {
      buffer.reset();
      output.clear();
      for (StringRows::const_iterator row = prepared_rows.begin(); row != prepared_rows.end();
           ++row)
        writer.write_row(StreamableStringRow(*row));
    }
  }
#endif
  const std::chrono::steady_clock::time_point stop = std::chrono::steady_clock::now();
  timed_phase = false;

  if (!output)
    return false;
  if (timed_checksum_mix_calls != 0)
    return false;
  if (timed_reader_steps != 0)
    return false;

  result.rows = sample.rows * options.iterations;
  result.cells = sample.cells * options.iterations;
  result.row_bytes = sample.row_bytes * options.iterations;
  checksum = output_checksum(buffer);
  elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return true;
}

struct OperationContract {
  const char *operation;
  const char *scope;
  const char *sources;
};

const OperationContract operation_contracts[] = {
    {"rows_cells", "traversal_only",
#if CSV2_HAS_MMAP
     "buffer+mmap"
#else
     "buffer"
#endif
    },
    {"legacy_writer_raw", "writer_only",
#if CSV2_HAS_MMAP
     "buffer+mmap"
#else
     "buffer"
#endif
    },
#if defined(CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS)
    {"writer_raw_direct", "writer_only",
#if CSV2_HAS_MMAP
     "buffer+mmap"
#else
     "buffer"
#endif
    },
    {"writer_raw_streamable", "writer_only",
#if CSV2_HAS_MMAP
     "buffer+mmap"
#else
     "buffer"
#endif
    },
    {"writer_escaped_direct", "writer_only",
#if CSV2_HAS_MMAP
     "buffer+mmap"
#else
     "buffer"
#endif
    },
    {"writer_escaped_streamable", "writer_only",
#if CSV2_HAS_MMAP
     "buffer+mmap"
#else
     "buffer"
#endif
    },
#endif
#if CSV2_HAS_MMAP
    {"legacy_mmap_rows_cells", "mmap_and_traversal", "mmap"},
#endif
};

const OperationContract *find_operation_contract(const std::string &operation) {
  for (std::size_t index = 0; index < sizeof(operation_contracts) / sizeof(operation_contracts[0]);
       ++index) {
    if (operation == operation_contracts[index].operation)
      return &operation_contracts[index];
  }
  return 0;
}

bool contract_supports_source(const OperationContract &contract, const std::string &source) {
  const std::string sources(contract.sources);
  std::string::size_type start = 0;
  while (start <= sources.size()) {
    const std::string::size_type end = sources.find('+', start);
    if (sources.substr(start, end - start) == source)
      return true;
    if (end == std::string::npos)
      break;
    start = end + 1;
  }
  return false;
}

} // namespace

int main(int argc, char **argv) {
  if (argc == 2 && std::string(argv[1]) == "--describe") {
    std::cout << "protocol=" << protocol << " revision=" << CSV2_BENCHMARK_REVISION
              << " operations=";
    for (std::size_t index = 0;
         index < sizeof(operation_contracts) / sizeof(operation_contracts[0]); ++index) {
      if (index != 0)
        std::cout << ',';
      std::cout << operation_contracts[index].operation;
    }
#if CSV2_HAS_MMAP
    std::cout << " sources=buffer,mmap";
#else
    std::cout << " sources=buffer";
#endif
    std::cout << " operation_contracts=";
    for (std::size_t index = 0;
         index < sizeof(operation_contracts) / sizeof(operation_contracts[0]); ++index) {
      if (index != 0)
        std::cout << ';';
      std::cout << operation_contracts[index].operation << ':' << operation_contracts[index].scope
                << ':' << operation_contracts[index].sources;
    }
    std::cout << '\n';
    return EXIT_SUCCESS;
  }

  Options options;
  if (!parse_options(argc, argv, options)) {
    std::cerr << "usage: csv2_common_benchmark --describe | --operation NAME "
                 "--input FILE --source buffer|mmap --iterations N\n";
    return EXIT_FAILURE;
  }
  const std::uint64_t bytes = file_size(options.input);
  if (bytes == 0) {
    std::cerr << "error: input is missing or empty\n";
    return EXIT_FAILURE;
  }
  const OperationContract *const contract = find_operation_contract(options.operation);
  if (!contract || !contract_supports_source(*contract, options.source)) {
    std::cerr << "error: unsupported operation/source contract\n";
    return EXIT_FAILURE;
  }

  Observation result;
  std::uint64_t checksum = 0;
  std::int64_t elapsed_ns = 0;
  const bool success = options.operation == "rows_cells"
                           ? run_prepared(options, result, checksum, elapsed_ns)
                       : options.operation == "legacy_mmap_rows_cells"
                           ? run_legacy_mmap(options, result, checksum, elapsed_ns)
                           : run_writer(options, result, checksum, elapsed_ns);
  if (!success) {
    std::cerr << "error: unsupported operation/source or input failure\n";
    return EXIT_FAILURE;
  }

  if (elapsed_ns <= 0)
    elapsed_ns = 1;
  benchmark_sink = result.rows ^ result.cells ^ result.row_bytes ^ checksum;
  std::cout << "protocol=" << protocol << " revision=" << CSV2_BENCHMARK_REVISION
            << " operation=" << options.operation << " scope=" << contract->scope
            << " source=" << options.source << " bytes=" << bytes
            << " iterations=" << options.iterations << " elapsed_ns=" << elapsed_ns
            << " rows=" << result.rows << " cells=" << result.cells
            << " row_bytes=" << result.row_bytes << " checksum=" << checksum
            << " timed_reader_steps=" << timed_reader_steps << '\n';
  return EXIT_SUCCESS;
}
