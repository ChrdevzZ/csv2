#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <csv2/reader.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>

#ifndef CSV2_BENCHMARK_REVISION
#define CSV2_BENCHMARK_REVISION "unstamped"
#endif

namespace {

using CommonReader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::first_row_is_header<false>>;

const char protocol[] = "csv2-common-v1";
volatile std::uint64_t benchmark_sink = 0;

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
  checksum ^= value + 0x9e3779b97f4a7c15ull + (checksum << 6) + (checksum >> 2);
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
    ++result.rows;
    result.row_bytes += static_cast<std::uint64_t>(row.length());
    for (const auto cell : row) {
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

  const std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
  for (std::size_t run = 0; run < options.iterations; ++run) {
    const Observation sample = traverse(reader);
    result.rows += sample.rows;
    result.cells += sample.cells;
    result.row_bytes += sample.row_bytes;
  }
  const std::chrono::steady_clock::time_point stop = std::chrono::steady_clock::now();
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
  for (std::size_t run = 0; run < options.iterations; ++run) {
    const std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
    CommonReader reader;
    if (!reader.mmap(options.input))
      return false;
    const Observation sample = traverse(reader);
    const std::chrono::steady_clock::time_point stop = std::chrono::steady_clock::now();
    elapsed_ns += std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
    result.rows += sample.rows;
    result.cells += sample.cells;
    result.row_bytes += sample.row_bytes;
  }
  return true;
#else
  (void)options;
  (void)result;
  (void)checksum;
  (void)elapsed_ns;
  return false;
#endif
}

} // namespace

int main(int argc, char **argv) {
  if (argc == 2 && std::string(argv[1]) == "--describe") {
    std::cout << "protocol=" << protocol << " revision=" << CSV2_BENCHMARK_REVISION
              << " operations=rows_cells"
#if CSV2_HAS_MMAP
              << ",legacy_mmap_rows_cells"
              << " sources=buffer,mmap"
#else
              << " sources=buffer"
#endif
              << " prepared_scope=traversal_only legacy_scope=mmap_and_traversal\n";
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

  Observation result;
  std::uint64_t checksum = 0;
  std::int64_t elapsed_ns = 0;
  const bool success = options.operation == "rows_cells"
                           ? run_prepared(options, result, checksum, elapsed_ns)
                       : options.operation == "legacy_mmap_rows_cells"
                           ? run_legacy_mmap(options, result, checksum, elapsed_ns)
                           : false;
  if (!success) {
    std::cerr << "error: unsupported operation/source or input failure\n";
    return EXIT_FAILURE;
  }

  if (elapsed_ns <= 0)
    elapsed_ns = 1;
  benchmark_sink = result.rows ^ result.cells ^ result.row_bytes ^ checksum;
  std::cout << "protocol=" << protocol << " revision=" << CSV2_BENCHMARK_REVISION
            << " operation=" << options.operation << " scope="
            << (options.operation == "rows_cells" ? "traversal_only" : "mmap_and_traversal")
            << " source=" << options.source << " bytes=" << bytes
            << " iterations=" << options.iterations << " elapsed_ns=" << elapsed_ns
            << " rows=" << result.rows << " cells=" << result.cells
            << " row_bytes=" << result.row_bytes << " checksum=" << checksum << '\n';
  return EXIT_SUCCESS;
}
