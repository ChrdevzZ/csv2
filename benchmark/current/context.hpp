#ifndef CSV2_BENCHMARK_CURRENT_CONTEXT_HPP
#define CSV2_BENCHMARK_CURRENT_CONTEXT_HPP

#include "support/output_buffer.hpp"

#include <csv2/reader.hpp>
#if CSV2_HAS_MMAP
#include <csv2/mio.hpp>
#endif

#include <cstddef>
#include <cstdint>
#include <iosfwd>
#include <ostream>
#include <string>
#include <vector>

namespace csv2_benchmark {

using BenchmarkReader =
    csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>, csv2::first_row_is_header<false>,
                 csv2::trim_policy::no_trimming>;

enum class Source { file, buffer, mmap };

const char *source_name(Source source) noexcept;

struct StreamableField {
  const std::string *value;
};

std::ostream &operator<<(std::ostream &stream, const StreamableField &field);

struct Options {
  std::string input;
  std::string source;
  std::string operation;
  bool verify;
  bool list;
  bool observer_audit;
  bool output_capacity_set;
  std::size_t output_capacity;
  bool force_output_stream_failure;
  std::string input_path_after_load;
  bool force_input_read_failure;

  Options()
      : source("all"), verify(false), list(false), observer_audit(false),
        output_capacity_set(false), output_capacity(0), force_output_stream_failure(false),
        force_input_read_failure(false) {}
};

class Context {
  std::string input_path_;
  std::string dataset_name_;
  std::string data_;
  BenchmarkReader buffer_reader_;
  BenchmarkReader mmap_reader_;
#if CSV2_HAS_MMAP
  mio::mmap_source mapping_;
#endif
  bool mmap_ready_;
  std::uint64_t decoded_row_count_;
  std::uint64_t decoded_cell_count_;
  std::vector<std::vector<std::string>> decoded_rows_;
  std::vector<std::vector<StreamableField>> streamable_rows_;
  std::string string_scratch_;
  std::vector<char> vector_scratch_;
  OutputBuffer output_buffer_;
  std::ostream output_stream_;
  bool force_output_stream_failure_;
  bool force_input_read_failure_;

public:
  Context();

  bool load(const std::string &path, std::string &error);
  const BenchmarkReader &reader(Source source) const;

  const std::string &input_path() const noexcept { return input_path_; }
  const std::string &dataset_name() const noexcept { return dataset_name_; }
  const std::string &data() const noexcept { return data_; }
  std::size_t input_size() const noexcept { return data_.size(); }
  bool mmap_ready() const noexcept { return mmap_ready_; }
  std::uint64_t decoded_row_count() const noexcept { return decoded_row_count_; }
  std::uint64_t decoded_cell_count() const noexcept { return decoded_cell_count_; }
#if CSV2_HAS_MMAP
  const char *mapped_data() const noexcept { return mapping_.data(); }
  std::size_t mapped_size() const noexcept { return mapping_.size(); }
#endif

  std::string &reset_string_scratch() noexcept {
    string_scratch_.clear();
    return string_scratch_;
  }
  std::vector<char> &reset_vector_scratch() noexcept {
    vector_scratch_.clear();
    return vector_scratch_;
  }

  const std::vector<std::vector<std::string>> &decoded_rows() const noexcept {
    return decoded_rows_;
  }
  const std::vector<std::vector<StreamableField>> &streamable_rows() const noexcept {
    return streamable_rows_;
  }

  std::ostream &reset_output() noexcept;
  void limit_output_capacity_for_test(std::size_t capacity) { output_buffer_.reserve(capacity); }
  void force_output_stream_failure_for_test(bool enabled) noexcept {
    force_output_stream_failure_ = enabled;
  }
  void replace_input_path_for_test(const std::string &path) { input_path_ = path; }
  void force_input_read_failure_for_test(bool enabled) noexcept {
    force_input_read_failure_ = enabled;
  }
  bool input_read_failure_for_test() const noexcept { return force_input_read_failure_; }
  OutputBuffer &output_buffer() noexcept { return output_buffer_; }
  const OutputBuffer &output_buffer() const noexcept { return output_buffer_; }
};

bool parse_options(int &argc, char **argv, Options &options, std::string &error);

} // namespace csv2_benchmark

#endif
