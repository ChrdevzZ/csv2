#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <new>
#include <sstream>
#include <streambuf>
#include <string>
#include <system_error>
#include <vector>

#if CSV2_HAS_RANGES
#include <ranges>
#endif

namespace csv2_benchmark_allocation {

bool enabled = false;
std::uint64_t count = 0;
std::uint64_t bytes = 0;

void reset(bool enable) noexcept {
  count = 0;
  bytes = 0;
  enabled = enable;
}

void record(std::size_t size) noexcept {
  if (enabled) {
    ++count;
    bytes += static_cast<std::uint64_t>(size);
  }
}

} // namespace csv2_benchmark_allocation

#if defined(CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING)
void *operator new(std::size_t size) {
  const std::size_t allocation_size = size == 0 ? 1 : size;
  void *const memory = std::malloc(allocation_size);
  if (!memory)
    throw std::bad_alloc();
  csv2_benchmark_allocation::record(size);
  return memory;
}

void *operator new[](std::size_t size) {
  const std::size_t allocation_size = size == 0 ? 1 : size;
  void *const memory = std::malloc(allocation_size);
  if (!memory)
    throw std::bad_alloc();
  csv2_benchmark_allocation::record(size);
  return memory;
}

void operator delete(void *memory) noexcept { std::free(memory); }
void operator delete[](void *memory) noexcept { std::free(memory); }
void operator delete(void *memory, std::size_t) noexcept { std::free(memory); }
void operator delete[](void *memory, std::size_t) noexcept { std::free(memory); }
#endif

namespace {

using BenchmarkReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                     csv2::first_row_is_header<false>>;

struct Options {
  std::string operation{"rows_cells"};
  std::string input;
  std::string source{"mmap"};
  std::size_t iterations{1};
  bool check_expected{false};
  std::uint64_t expected_checksum{0};
  bool track_allocations{false};
  bool check_expected_allocations{false};
  std::uint64_t expected_allocations{0};
};

struct Result {
  std::uint64_t checksum{1469598103934665603ull};
  std::uint64_t rows{0};
  std::uint64_t cells{0};
};

void mix(std::uint64_t &checksum, std::uint64_t value) noexcept {
  checksum ^= value + 0x9e3779b97f4a7c15ull + (checksum << 6) + (checksum >> 2);
}

template <class Range> void mix_bytes(std::uint64_t &checksum, const Range &value) noexcept {
  mix(checksum, static_cast<std::uint64_t>(value.size()));
  for (const char character : value)
    mix(checksum, static_cast<unsigned char>(character));
}

bool parse_size(const char *text, std::size_t &value) {
  std::istringstream input(text);
  std::size_t parsed = 0;
  input >> parsed;
  if (!input || !input.eof() || parsed == 0)
    return false;
  value = parsed;
  return true;
}

bool parse_checksum(const char *text, std::uint64_t &value) {
  std::istringstream input(text);
  std::uint64_t parsed = 0;
  input >> parsed;
  if (!input || !input.eof())
    return false;
  value = parsed;
  return true;
}

bool parse_options(int argc, char **argv, Options &options) {
  if (argc == 2 && argv[1][0] != '-') {
    options.input = argv[1];
    return true;
  }
  for (int argument = 1; argument < argc; ++argument) {
    const std::string name(argv[argument]);
    if (name == "--track-allocations") {
      options.track_allocations = true;
      continue;
    }
    if (argument + 1 >= argc)
      return false;
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
    } else if (name == "--expect-checksum") {
      if (!parse_checksum(value, options.expected_checksum))
        return false;
      options.check_expected = true;
    } else if (name == "--expect-allocations") {
      if (!parse_checksum(value, options.expected_allocations))
        return false;
      options.track_allocations = true;
      options.check_expected_allocations = true;
    } else {
      return false;
    }
  }
  return !options.input.empty() && (options.source == "mmap" || options.source == "buffer");
}

bool read_file(const std::string &path, std::string &contents) {
  std::ifstream input(path.c_str(), std::ios::binary);
  if (!input)
    return false;
  contents.assign(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
  return input.good() || input.eof();
}

std::uint64_t file_size(const std::string &path) {
  std::ifstream input(path.c_str(), std::ios::binary | std::ios::ate);
  if (!input)
    return 0;
  const std::ifstream::pos_type end = input.tellg();
  return end > 0 ? static_cast<std::uint64_t>(end) : 0;
}

class HashBuffer : public std::streambuf {
public:
  std::uint64_t checksum{1469598103934665603ull};

protected:
  std::streamsize xsputn(const char *data, std::streamsize size) override {
    for (std::streamsize i = 0; i < size; ++i)
      mix(checksum, static_cast<unsigned char>(data[i]));
    return size;
  }

  int_type overflow(int_type character) override {
    if (!traits_type::eq_int_type(character, traits_type::eof()))
      mix(checksum, static_cast<unsigned char>(traits_type::to_char_type(character)));
    return character;
  }
};

struct RawField {
  const char *bytes;
  std::size_t length;
  const char *data() const noexcept { return bytes; }
  std::size_t size() const noexcept { return length; }
};

template <class Row> class RawRow {
  Row row_;

public:
  explicit RawRow(Row row) : row_(row) {}

  class iterator {
    typename Row::CellIterator current_;

  public:
    using value_type = RawField;
    using difference_type = std::ptrdiff_t;
    using reference = RawField;
    using pointer = void;
    using iterator_category = std::input_iterator_tag;

    iterator() = default;
    explicit iterator(typename Row::CellIterator current) : current_(current) {}
    RawField operator*() const {
      const typename Row::Cell cell = *current_;
      return {cell.raw_data(), cell.raw_size()};
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

template <class Cell> struct ContentField {
  Cell cell;
};

template <class Cell>
std::ostream &operator<<(std::ostream &output, const ContentField<Cell> &field) {
  field.cell.copy_content_to(std::ostreambuf_iterator<char>(output));
  return output;
}

template <class Row> class ContentRow {
  Row row_;

public:
  explicit ContentRow(Row row) : row_(row) {}

  class iterator {
    typename Row::CellIterator current_;

  public:
    using value_type = ContentField<typename Row::Cell>;
    using difference_type = std::ptrdiff_t;
    using reference = value_type;
    using pointer = void;
    using iterator_category = std::input_iterator_tag;

    iterator() = default;
    explicit iterator(typename Row::CellIterator current) : current_(current) {}
    value_type operator*() const { return {*current_}; }
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

void source_counts(const BenchmarkReader &reader, std::uint64_t &rows, std::uint64_t &cells) {
  rows = 0;
  cells = 0;
  for (const auto row : reader) {
    ++rows;
    for (const auto cell : row) {
      (void)cell;
      ++cells;
    }
  }
}

bool run_reader_operation(const std::string &operation, const BenchmarkReader &reader,
                          Result &result) {
  if (operation == "rows_only") {
    for (const auto row : reader) {
      ++result.rows;
      mix(result.checksum, row.raw_size());
    }
    return true;
  }
  if (operation == "rows_cells") {
    for (const auto row : reader) {
      ++result.rows;
      for (const auto cell : row) {
        ++result.cells;
        mix(result.checksum, cell.raw_size());
      }
    }
    return true;
  }
  if (operation == "raw_to_string" || operation == "decoded_to_string") {
    for (const auto row : reader) {
      ++result.rows;
      for (const auto cell : row) {
        std::string value;
        if (operation == "raw_to_string")
          cell.read_raw_value(value);
        else
          cell.read_value(value);
        ++result.cells;
        mix_bytes(result.checksum, value);
      }
    }
    return true;
  }
  if (operation == "decoded_to_vector") {
    for (const auto row : reader) {
      ++result.rows;
      for (const auto cell : row) {
        std::vector<char> value;
        cell.read_value(value);
        ++result.cells;
        mix_bytes(result.checksum, value);
      }
    }
    return true;
  }
  if (operation == "integer_conversion") {
    for (const auto row : reader) {
      ++result.rows;
      for (const auto cell : row) {
        long long value = 0;
        csv2::conversion_error error;
        const bool converted = cell.try_parse(value, error);
        ++result.cells;
        mix(result.checksum,
            converted ? static_cast<std::uint64_t>(value) : static_cast<std::uint64_t>(error.code));
      }
    }
    return true;
  }
#if CSV2_HAS_RANGES
  if (operation == "ranges_pipeline") {
    for (const auto row : reader) {
      ++result.rows;
      auto sizes = row | std::views::transform(
                             [](const BenchmarkReader::Cell cell) { return cell.raw_size(); });
      for (const std::size_t size : sizes) {
        ++result.cells;
        mix(result.checksum, size);
      }
    }
    return true;
  }
#endif
  return false;
}

bool run_writer_operation(const std::string &operation, const BenchmarkReader &reader,
                          std::size_t iterations, std::uint64_t rows, std::uint64_t cells,
                          Result &result) {
  HashBuffer buffer;
  std::ostream output(&buffer);

  if (operation == "writer_raw") {
    csv2::Writer<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open> writer(
        output);
    for (std::size_t run = 0; run < iterations; ++run)
      for (const auto row : reader)
        writer.write_row(RawRow<BenchmarkReader::Row>(row));
  } else if (operation == "writer_escaped") {
    csv2::EscapingWriter<csv2::delimiter<','>, std::ostream, csv2::stream_ownership::leave_open>
        writer(output);
    for (std::size_t run = 0; run < iterations; ++run)
      for (const auto row : reader)
        writer.write_row(ContentRow<BenchmarkReader::Row>(row));
  } else {
    return false;
  }
  result.checksum = buffer.checksum;
  result.rows = rows * iterations;
  result.cells = cells * iterations;
  return true;
}

bool run_map_only(const Options &options, Result &result) {
#if CSV2_HAS_MMAP
  for (std::size_t run = 0; run < options.iterations; ++run) {
    std::error_code error;
    mio::mmap_source mapping;
    mapping.map(options.input, error);
    if (error || !mapping.is_mapped())
      return false;
    mix(result.checksum, mapping.size());
    if (mapping.size() != 0) {
      mix(result.checksum, static_cast<unsigned char>(mapping[0]));
      mix(result.checksum, static_cast<unsigned char>(mapping[mapping.size() - 1]));
    }
  }
  return true;
#else
  (void)options;
  (void)result;
  return false;
#endif
}

} // namespace

int main(int argc, char **argv) {
  Options options;
  if (!parse_options(argc, argv, options)) {
    std::cerr << "usage: csv2_benchmark --operation NAME --input FILE "
                 "[--source mmap|buffer] [--iterations N] [--expect-checksum N] "
                 "[--track-allocations] [--expect-allocations N]\n";
    return EXIT_FAILURE;
  }
#if !defined(CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING)
  if (options.track_allocations) {
    std::cerr << "error: allocation tracking requires csv2_benchmark_allocations\n";
    return EXIT_FAILURE;
  }
#endif

  const std::uint64_t bytes = file_size(options.input);
  if (bytes == 0) {
    std::cerr << "error: input is missing or empty: " << options.input << '\n';
    return EXIT_FAILURE;
  }

  std::string storage;
  BenchmarkReader reader;
  std::uint64_t writer_rows = 0;
  std::uint64_t writer_cells = 0;
  bool prepared = true;
  if (options.operation != "map_only") {
    if (options.source == "buffer")
      prepared = read_file(options.input, storage) &&
                 reader.parse_borrowed(storage.data(), storage.size());
    else {
#if CSV2_HAS_MMAP
      prepared = reader.mmap(options.input);
#else
      prepared = false;
#endif
    }
    if (prepared && (options.operation == "writer_raw" || options.operation == "writer_escaped"))
      source_counts(reader, writer_rows, writer_cells);
  }
  if (!prepared) {
    std::cerr << "error: unsupported operation/source or input failure\n";
    return EXIT_FAILURE;
  }

  Result result;
  csv2_benchmark_allocation::reset(options.track_allocations);
  const std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
  bool success = false;
  if (options.operation == "map_only") {
    success = options.source == "mmap" && run_map_only(options, result);
  } else if (options.operation == "writer_raw" || options.operation == "writer_escaped") {
    success = run_writer_operation(options.operation, reader, options.iterations, writer_rows,
                                   writer_cells, result);
  } else {
    success = true;
    for (std::size_t run = 0; run < options.iterations && success; ++run)
      success = run_reader_operation(options.operation, reader, result);
  }
  const std::chrono::steady_clock::time_point stop = std::chrono::steady_clock::now();
  csv2_benchmark_allocation::enabled = false;

  if (!success) {
    std::cerr << "error: unsupported operation/source or input failure\n";
    return EXIT_FAILURE;
  }
  if (options.check_expected && result.checksum != options.expected_checksum) {
    std::cerr << "error: checksum mismatch: expected " << options.expected_checksum << ", got "
              << result.checksum << '\n';
    return EXIT_FAILURE;
  }
  if (options.check_expected_allocations &&
      csv2_benchmark_allocation::count != options.expected_allocations) {
    std::cerr << "error: allocation mismatch: expected " << options.expected_allocations << ", got "
              << csv2_benchmark_allocation::count << '\n';
    return EXIT_FAILURE;
  }

  const double seconds = std::chrono::duration<double>(stop - start).count();
  const double processed = static_cast<double>(bytes) * static_cast<double>(options.iterations);
  const double gib_per_second = processed / (1024.0 * 1024.0 * 1024.0) / seconds;
  std::cout << std::fixed << std::setprecision(6) << "operation=" << options.operation
            << " source=" << options.source << " bytes=" << bytes
            << " iterations=" << options.iterations << " seconds=" << seconds
            << " gib_per_second=" << gib_per_second
            << " rows_per_second=" << static_cast<double>(result.rows) / seconds
            << " cells_per_second=" << static_cast<double>(result.cells) / seconds
#if defined(CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING)
            << " allocation_tracking=available"
#else
            << " allocation_tracking=unavailable"
#endif
            << " allocations=" << csv2_benchmark_allocation::count
            << " allocated_bytes=" << csv2_benchmark_allocation::bytes
            << " checksum=" << result.checksum << '\n';
  return EXIT_SUCCESS;
}
