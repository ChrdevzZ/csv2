#include "context.hpp"
#include "support/mapping_touch.hpp"

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

bool parse_size(const std::string &text, std::size_t &value) {
  if (text.empty())
    return false;
  std::size_t parsed = 0;
  for (const char character : text) {
    if (character < '0' || character > '9')
      return false;
    const std::size_t digit = static_cast<std::size_t>(character - '0');
    if (parsed > ((std::numeric_limits<std::size_t>::max)() - digit) / 10)
      return false;
    parsed = parsed * 10 + digit;
  }
  value = parsed;
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
    : input_size_(0), mmap_ready_(false), mapping_pretouch_sink_(0), decoded_row_count_(0),
      decoded_cell_count_(0), output_stream_(&output_buffer_), force_output_stream_failure_(false),
      force_input_read_failure_(false), prepared_mask_(prepare_none),
      prepared_sources_(source_none) {}

bool Context::load(const std::string &path, unsigned requirements, unsigned sources,
                   std::string &error) {
  input_path_ = path;
  dataset_name_ = filename_from_path(path);
  input_size_ = 0;
  data_.clear();
  buffer_index_ = BenchmarkReader::RowIndex();
  mmap_index_ = BenchmarkReader::RowIndex();
  buffer_random_positions_.clear();
  mmap_random_positions_.clear();
  mmap_ready_ = false;
  mapping_pretouch_sink_ = 0;
  decoded_rows_.clear();
  streamable_rows_.clear();
  decoded_row_count_ = 0;
  decoded_cell_count_ = 0;
  string_scratch_.clear();
  vector_scratch_.clear();
  output_buffer_.reserve(0);
  prepared_mask_ = prepare_none;
  prepared_sources_ = sources;

  std::ifstream input(path.c_str(), std::ios::binary | std::ios::ate);
  if (!input) {
    error = "unable to open input: " + path;
    return false;
  }
  const std::streamoff length = input.tellg();
  if (length < 0 || static_cast<std::uintmax_t>(length) >
                        static_cast<std::uintmax_t>((std::numeric_limits<std::size_t>::max)())) {
    error = "unable to determine input size: " + path;
    return false;
  }
  input_size_ = static_cast<std::size_t>(length);
  if (input_size_ == 0) {
    error = "benchmark input must not be empty";
    return false;
  }

  const bool buffer_reader_requested =
      (requirements & prepare_reader) != 0 && (sources & source_buffer) != 0;
  const bool mmap_reader_requested =
      (requirements & prepare_reader) != 0 && (sources & source_mmap) != 0;
  const bool data_requested = (requirements & prepare_data) != 0 || buffer_reader_requested;
  const bool mapping_requested = (requirements & prepare_mapping) != 0 ||
                                 (requirements & prepare_pretouched_mapping) != 0 ||
                                 mmap_reader_requested;

  if (data_requested) {
    input.seekg(0, std::ios::beg);
    data_.assign(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
    if ((!input.eof() && input.fail()) || data_.size() != input_size_) {
      error = "unable to read a stable input: " + path;
      return false;
    }
    prepared_mask_ |= prepare_data;
  }
  if (buffer_reader_requested) {
    if (!buffer_reader_.parse_borrowed(data_.data(), data_.size())) {
      error = "unable to create borrowed reader";
      return false;
    }
    prepared_mask_ |= prepare_reader;
  }

#if CSV2_HAS_MMAP
  if (mapping_requested) {
    std::error_code mmap_error;
    mapping_ = mio::make_mmap_source(path, mmap_error);
    mmap_ready_ = !mmap_error && !mapping_.empty();
    if (!mmap_ready_) {
      error = "mmap unavailable for input: " + mmap_error.message();
      return false;
    }
    prepared_mask_ |= prepare_mapping;
    if ((requirements & prepare_pretouched_mapping) != 0) {
      mapping_pretouch_sink_ = touch_mapping_bytes(mapping_.data(), mapping_.size());
      prepared_mask_ |= prepare_pretouched_mapping;
    }
    if (mmap_reader_requested) {
      if (!mmap_reader_.parse_borrowed(mapping_.data(), mapping_.size())) {
        error = "unable to create mmap reader";
        return false;
      }
      prepared_mask_ |= prepare_reader;
    }
  }
#else
  if (mapping_requested) {
    error = "mmap preparation requested in a no-mmap build";
    return false;
  }
#endif

  if ((requirements & prepare_index) != 0) {
    if ((sources & source_buffer) != 0) {
      if (!buffer_reader_requested) {
        error = "buffer index requires a prepared buffer reader";
        return false;
      }
      buffer_index_ = buffer_reader_.index();
    }
#if CSV2_HAS_MMAP
    if ((sources & source_mmap) != 0) {
      if (!mmap_reader_requested) {
        error = "mmap index requires a prepared mmap reader";
        return false;
      }
      mmap_index_ = mmap_reader_.index();
    }
#endif
    prepared_mask_ |= prepare_index;
  }

  if ((requirements & prepare_random_positions) != 0) {
    if ((prepared_mask_ & prepare_index) == 0) {
      error = "random positions require a prepared row index";
      return false;
    }
    const auto prepare_positions = [](const BenchmarkReader::RowIndex &index,
                                      std::vector<std::size_t> &positions) {
      positions.reserve(index.size());
      std::uint32_t state = 0x43535632u;
      for (std::size_t count = 0; count < index.size(); ++count) {
        state = state * 1664525u + 1013904223u;
        positions.push_back(static_cast<std::size_t>(state) % index.size());
      }
    };
    if ((sources & source_buffer) != 0)
      prepare_positions(buffer_index_, buffer_random_positions_);
#if CSV2_HAS_MMAP
    if ((sources & source_mmap) != 0)
      prepare_positions(mmap_index_, mmap_random_positions_);
#endif
    prepared_mask_ |= prepare_random_positions;
  }

  std::size_t decoded_bytes = 0;
  if ((requirements & prepare_decoded_rows) != 0) {
    if (!buffer_reader_requested) {
      error = "decoded rows require a prepared buffer reader";
      return false;
    }
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
    prepared_mask_ |= prepare_decoded_rows;
  }

  if ((requirements & prepare_streamable_rows) != 0) {
    if ((prepared_mask_ & prepare_decoded_rows) == 0) {
      error = "streamable rows require decoded rows";
      return false;
    }
    streamable_rows_.reserve(decoded_rows_.size());
    for (const std::vector<std::string> &row : decoded_rows_) {
      std::vector<StreamableField> fields;
      fields.reserve(row.size());
      for (const std::string &field : row)
        fields.push_back(StreamableField{&field});
      streamable_rows_.push_back(std::move(fields));
    }
    prepared_mask_ |= prepare_streamable_rows;
  }

  if ((requirements & prepare_string_scratch) != 0) {
    string_scratch_.reserve(input_size_);
    prepared_mask_ |= prepare_string_scratch;
  }
  if ((requirements & prepare_vector_scratch) != 0) {
    vector_scratch_.reserve(input_size_);
    prepared_mask_ |= prepare_vector_scratch;
  }

  if ((requirements & prepare_output) != 0) {
    const std::size_t maximum = (std::numeric_limits<std::size_t>::max)();
    if (decoded_rows_.size() > (maximum - 64) / 2) {
      error = "input has too many rows to size the writer output buffer";
      return false;
    }
    const std::size_t overhead = decoded_rows_.size() * 2 + 64;
    if (decoded_bytes > maximum - overhead) {
      error = "input is too large to size the writer output buffer";
      return false;
    }
    const std::size_t minimum_capacity = decoded_bytes + overhead;
    if (input_size_ > (maximum - overhead) / 3) {
      error = "input is too large to size the escaped writer output buffer";
      return false;
    }
    const std::size_t escaped_capacity = input_size_ * 3 + overhead;
    output_buffer_.reserve((std::max)(minimum_capacity, escaped_capacity));
    prepared_mask_ |= prepare_output;
  }
  return true;
}

std::string Context::preparation_description() const {
  if (prepared_mask_ == prepare_none)
    return "metadata-only";
  std::string result;
  const auto append = [&result](const char *name) {
    if (!result.empty())
      result += ',';
    result += name;
  };
  if ((prepared_mask_ & prepare_data) != 0)
    append("data");
  if ((prepared_mask_ & prepare_reader) != 0 && (prepared_sources_ & source_buffer) != 0)
    append("buffer-reader");
  if ((prepared_mask_ & prepare_mapping) != 0)
    append("mapping");
  if ((prepared_mask_ & prepare_pretouched_mapping) != 0)
    append("pretouched-mapping");
  if ((prepared_mask_ & prepare_reader) != 0 && (prepared_sources_ & source_mmap) != 0)
    append("mmap-reader");
  if ((prepared_mask_ & prepare_decoded_rows) != 0)
    append("decoded-rows");
  if ((prepared_mask_ & prepare_streamable_rows) != 0)
    append("streamable-rows");
  if ((prepared_mask_ & prepare_string_scratch) != 0)
    append("string-scratch");
  if ((prepared_mask_ & prepare_vector_scratch) != 0)
    append("vector-scratch");
  if ((prepared_mask_ & prepare_output) != 0)
    append("output");
  if ((prepared_mask_ & prepare_index) != 0 && (prepared_sources_ & source_buffer) != 0)
    append("buffer-index");
  if ((prepared_mask_ & prepare_index) != 0 && (prepared_sources_ & source_mmap) != 0)
    append("mmap-index");
  if ((prepared_mask_ & prepare_random_positions) != 0)
    append("random-positions");
  return result;
}

const BenchmarkReader &Context::reader(Source source) const {
  return source == Source::mmap ? mmap_reader_ : buffer_reader_;
}

const BenchmarkReader::RowIndex &Context::row_index(Source source) const {
  return source == Source::mmap ? mmap_index_ : buffer_index_;
}

const std::vector<std::size_t> &Context::random_positions(Source source) const {
  return source == Source::mmap ? mmap_random_positions_ : buffer_random_positions_;
}

std::ostream &Context::reset_output() noexcept {
  output_stream_.clear();
  output_stream_.width(0);
  output_buffer_.reset();
  if (force_output_stream_failure_)
    output_stream_.setstate(std::ios::badbit);
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
    } else if (argument == "--csv2-preparation-audit") {
      options.preparation_audit = true;
    } else if (argument == "--csv2-test-output-capacity") {
      std::string value;
      if (!take_value(index, argc, argv, "--csv2-test-output-capacity", value, error))
        return false;
      if (!parse_size(value, options.output_capacity)) {
        error = "--csv2-test-output-capacity requires an unsigned decimal size";
        return false;
      }
      options.output_capacity_set = true;
    } else if (argument == "--csv2-test-output-stream-failure") {
      options.force_output_stream_failure = true;
    } else if (argument == "--csv2-test-input-path-after-load") {
      if (!take_value(index, argc, argv, "--csv2-test-input-path-after-load",
                      options.input_path_after_load, error))
        return false;
    } else if (argument == "--csv2-test-input-read-failure") {
      options.force_input_read_failure = true;
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
