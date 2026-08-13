#include "context.hpp"

#include <algorithm>
#include <cerrno>
#include <fstream>
#include <iterator>
#include <limits>
#include <system_error>

namespace csv2_benchmark {

namespace {

std::string filename_from_path(const std::string &path) {
  const std::string::size_type separator = path.find_last_of("/\\");
  return separator == std::string::npos ? path : path.substr(separator + 1);
}

bool take_value(int &index, int argc, char **argv, const char *option, std::string &value,
                std::string &error) {
  if (index + 1 >= argc) {
    error = std::string(option) + " requires a value";
    return false;
  }
  value = argv[++index];
  return true;
}

} // namespace

const char *source_name(Source source) noexcept {
  switch (source) {
  case Source::file:
    return "file";
  case Source::buffer:
    return "buffer";
  case Source::mmap:
    return "mmap";
  }
  return "unknown";
}

std::ostream &operator<<(std::ostream &stream, const StreamableField &field) {
  if (field.value)
    stream.write(field.value->data(), static_cast<std::streamsize>(field.value->size()));
  return stream;
}

Context::Context()
    : mmap_ready_(false), decoded_row_count_(0), decoded_cell_count_(0),
      output_stream_(&output_buffer_) {}

bool Context::load(const std::string &path, std::string &error) {
  std::ifstream input(path.c_str(), std::ios::binary);
  if (!input) {
    error = "unable to open input: " + path;
    return false;
  }
  data_.assign(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
  if (!input.eof() && input.fail()) {
    error = "unable to read input: " + path;
    return false;
  }
  if (data_.empty()) {
    error = "benchmark input must not be empty";
    return false;
  }
  if (!buffer_reader_.parse_borrowed(data_.data(), data_.size())) {
    error = "unable to create borrowed reader";
    return false;
  }

  input_path_ = path;
  dataset_name_ = filename_from_path(path);

#if CSV2_HAS_MMAP
  std::error_code mmap_error;
  mapping_ = mio::make_mmap_source(path, mmap_error);
  mmap_ready_ = !mmap_error && !mapping_.empty() &&
                mmap_reader_.parse_borrowed(mapping_.data(), mapping_.size());
  if (!mmap_ready_ && mmap_error)
    error = "mmap unavailable for input: " + mmap_error.message();
#else
  mmap_ready_ = false;
#endif

  decoded_rows_.clear();
  decoded_row_count_ = 0;
  decoded_cell_count_ = 0;
  std::size_t decoded_bytes = 0;
  for (const BenchmarkReader::Row row : buffer_reader_) {
    std::vector<std::string> fields;
    for (const BenchmarkReader::Cell cell : row) {
      fields.push_back(std::string());
      cell.copy_content_to(std::back_inserter(fields.back()));
      decoded_bytes += fields.back().size();
      ++decoded_cell_count_;
    }
    decoded_rows_.push_back(std::move(fields));
    ++decoded_row_count_;
  }

  streamable_rows_.clear();
  streamable_rows_.reserve(decoded_rows_.size());
  for (const std::vector<std::string> &row : decoded_rows_) {
    std::vector<StreamableField> fields;
    fields.reserve(row.size());
    for (const std::string &field : row)
      fields.push_back(StreamableField{&field});
    streamable_rows_.push_back(std::move(fields));
  }

  string_scratch_.clear();
  string_scratch_.reserve(data_.size());
  vector_scratch_.clear();
  vector_scratch_.reserve(data_.size());

  const std::size_t overhead = decoded_rows_.size() * 2 + 64;
  if (decoded_bytes > (std::numeric_limits<std::size_t>::max)() - overhead) {
    error = "input is too large to size the writer output buffer";
    return false;
  }
  const std::size_t minimum_capacity = decoded_bytes + overhead;
  if (data_.size() > ((std::numeric_limits<std::size_t>::max)() - overhead) / 3) {
    error = "input is too large to size the escaped writer output buffer";
    return false;
  }
  const std::size_t escaped_capacity = data_.size() * 3 + overhead;
  output_buffer_.reserve((std::max)(minimum_capacity, escaped_capacity));
  return true;
}

const BenchmarkReader &Context::reader(Source source) const {
  return source == Source::mmap ? mmap_reader_ : buffer_reader_;
}

std::ostream &Context::reset_output() noexcept {
  output_stream_.clear();
  output_stream_.width(0);
  output_buffer_.reset();
  return output_stream_;
}

bool parse_options(int &argc, char **argv, Options &options, std::string &error) {
  int output_index = 1;
  for (int index = 1; index < argc; ++index) {
    const std::string argument(argv[index]);
    if (argument == "--csv2-input") {
      if (!take_value(index, argc, argv, "--csv2-input", options.input, error))
        return false;
    } else if (argument == "--csv2-source") {
      if (!take_value(index, argc, argv, "--csv2-source", options.source, error))
        return false;
    } else if (argument == "--csv2-operation") {
      if (!take_value(index, argc, argv, "--csv2-operation", options.operation, error))
        return false;
    } else if (argument == "--csv2-verify") {
      options.verify = true;
    } else if (argument == "--csv2-list") {
      options.list = true;
    } else if (argument == "--csv2-observer-audit") {
      options.observer_audit = true;
    } else {
      argv[output_index++] = argv[index];
    }
  }
  argc = output_index;

  if (options.source != "all" && options.source != "file" && options.source != "buffer" &&
      options.source != "mmap") {
    error = "--csv2-source must be file, buffer, mmap, or all";
    return false;
  }
  if (options.input.empty() && !options.list) {
#if defined(CSV2_BENCHMARK_DEFAULT_INPUT)
    options.input = CSV2_BENCHMARK_DEFAULT_INPUT;
#else
    error = "--csv2-input is required";
    return false;
#endif
  }
  return true;
}

} // namespace csv2_benchmark
