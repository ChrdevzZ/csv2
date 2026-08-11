#pragma once

#include <cstring>
#include <csv2/detail/config.hpp>
#include <csv2/detail/output.hpp>

#if CSV2_HAS_MMAP
#include <csv2/mio.hpp>
#endif
#include <csv2/parameters.hpp>

#include <functional>
#include <iterator>
#include <memory>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>
#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif
#if CSV2_HAS_SPAN
#include <span>
#endif
#if CSV2_HAS_RANGES
#include <ranges>
#endif

namespace csv2 {

template <class quote_character, class trim_policy>
class basic_cell {
  const char *buffer_{nullptr};
  size_t start_{0};
  size_t end_{0};
  bool escaped_{false};
public:
  basic_cell() = default;
  basic_cell(const char *buffer, size_t start, size_t end, bool escaped) noexcept
      : buffer_(buffer), start_(start), end_(end), escaped_(escaped) {}

  const char *raw_data() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
  size_t raw_size() const noexcept { return end_ - start_; }
  bool has_escaped_quotes() const noexcept { return escaped_; }

#if CSV2_HAS_STRING_VIEW
  std::string_view raw_trimmed_view() const noexcept {
    const auto bounds = trim_policy::trim(buffer_, start_, end_);
    return std::string_view(buffer_ + bounds.first, bounds.second - bounds.first);
  }

  std::string_view read_view() const noexcept { return raw_trimmed_view(); }
#endif

  template <typename Container> void read_raw_value(Container &result) const {
    detail::reserve_for_append(result, raw_size());
    if (start_ < end_)
      detail::append_range(result, buffer_ + start_, buffer_ + end_);
  }

  template <typename Container> void read_value(Container &result) const {
    if (start_ >= end_)
      return;
    const auto bounds = trim_policy::trim(buffer_, start_, end_);
    detail::reserve_for_append(result, bounds.second - bounds.first);
    if (!escaped_) {
      if (bounds.first < bounds.second)
        detail::append_range(result, buffer_ + bounds.first, buffer_ + bounds.second);
      return;
    }

    size_t segment_start = bounds.first;
    for (size_t i = bounds.first; i < bounds.second; ++i) {
      if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
          buffer_[i + 1] == quote_character::value) {
        detail::append_range(result, buffer_ + segment_start, buffer_ + i + 1);
        ++i;
        segment_start = i + 1;
      }
    }
    if (segment_start < bounds.second)
      detail::append_range(result, buffer_ + segment_start, buffer_ + bounds.second);
  }

  template <typename OutputIt> OutputIt copy_raw_to(OutputIt output) const {
    if (start_ >= end_)
      return output;
    return detail::copy_chars(buffer_ + start_, buffer_ + end_, output);
  }

  template <typename OutputIt> OutputIt decode_to(OutputIt output) const {
    if (start_ >= end_)
      return output;
    const auto bounds = trim_policy::trim(buffer_, start_, end_);
    for (size_t i = bounds.first; i < bounds.second; ++i) {
      *output = buffer_[i];
      ++output;
      if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
          buffer_[i + 1] == quote_character::value)
        ++i;
    }
    return output;
  }

  template <typename OutputIt> OutputIt copy_content_to(OutputIt output) const {
    if (start_ >= end_)
      return output;
    auto bounds = trim_policy::trim(buffer_, start_, end_);
    if (bounds.second - bounds.first >= 2 && buffer_[bounds.first] == quote_character::value &&
        buffer_[bounds.second - 1] == quote_character::value) {
      ++bounds.first;
      --bounds.second;
    }
    for (size_t i = bounds.first; i < bounds.second; ++i) {
      *output = buffer_[i];
      ++output;
      if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
          buffer_[i + 1] == quote_character::value)
        ++i;
    }
    return output;
  }
};

template <class delimiter, class quote_character, class trim_policy>
class basic_row {
  const char *buffer_{nullptr};
  size_t start_{0};
  size_t end_{0};
public:
  using Cell = basic_cell<quote_character, trim_policy>;

  basic_row() = default;
  basic_row(const char *buffer, size_t start, size_t end) noexcept
      : buffer_(buffer), start_(start), end_(end) {}

  const char *raw_data() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
  size_t raw_size() const noexcept { return end_ - start_; }
  const char *address() const noexcept { return raw_data(); }
  size_t length() const noexcept { return raw_size(); }

  template <typename Container> void read_raw_value(Container &result) const {
    detail::reserve_for_append(result, raw_size());
    if (start_ < end_)
      detail::append_range(result, buffer_ + start_, buffer_ + end_);
  }

  class CellIterator {
    struct CellBounds {
      size_t content_end;
      bool escaped;
    };

    const char *buffer_{nullptr};
    size_t range_size_{0};
    size_t current_{0};
    size_t end_{0};
    size_t content_end_{0};
    bool escaped_{false};
    bool at_end_{true};

    CellBounds find_cell_bounds_() const noexcept {
      bool quote_opened = false;
      bool escaped = false;
      for (size_t i = current_; i < end_; ++i) {
        if (buffer_[i] == quote_character::value) {
          const bool adjacent_quote = i + 1 < end_ && buffer_[i + 1] == quote_character::value;
          if (adjacent_quote)
            escaped = true;
          if (quote_opened && adjacent_quote) {
            ++i;
            continue;
          }
          quote_opened = !quote_opened;
        } else if (buffer_[i] == delimiter::value && !quote_opened) {
          return {i, escaped};
        }
      }
      return {end_, escaped};
    }

    void update_bounds_() noexcept {
      if (!at_end_) {
        const CellBounds bounds = find_cell_bounds_();
        content_end_ = bounds.content_end;
        escaped_ = bounds.escaped;
      } else {
        content_end_ = end_;
        escaped_ = false;
      }
    }

  public:
    using value_type = Cell;
    using difference_type = std::ptrdiff_t;
    using reference = Cell;
    using pointer = void;
    using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
    using iterator_concept = std::forward_iterator_tag;
#endif

    CellIterator() = default;

    CellIterator(const char *buffer, size_t buffer_size, size_t start, size_t end)
        : buffer_(buffer), range_size_(buffer_size), current_(start), end_(end),
          content_end_(end), escaped_(false), at_end_(start >= end) {
      update_bounds_();
    }

    CellIterator &operator++() {
      if (!at_end_) {
        if (content_end_ < end_) {
          current_ = content_end_ + 1;
        } else {
          current_ = end_;
          at_end_ = true;
        }
        update_bounds_();
      }
      return *this;
    }

    CellIterator operator++(int) {
      CellIterator previous(*this);
      ++(*this);
      return previous;
    }

    Cell operator*() const { return Cell(buffer_, current_, content_end_, escaped_); }

    bool operator==(const CellIterator &rhs) const noexcept {
      return buffer_ == rhs.buffer_ && range_size_ == rhs.range_size_ &&
             current_ == rhs.current_ && end_ == rhs.end_ && at_end_ == rhs.at_end_;
    }

    bool operator!=(const CellIterator &rhs) const noexcept { return !(*this == rhs); }
  };

  CellIterator begin() const { return CellIterator(buffer_, end_ - start_, start_, end_); }
  CellIterator end() const { return CellIterator(buffer_, end_ - start_, end_, end_); }
};

#if CSV2_HAS_RANGES
} // namespace csv2
namespace std {
namespace ranges {
template <class delimiter, class quote_character, class trim_policy>
inline constexpr bool
    enable_view<csv2::basic_row<delimiter, quote_character, trim_policy>> = true;
template <class delimiter, class quote_character, class trim_policy>
inline constexpr bool
    enable_borrowed_range<csv2::basic_row<delimiter, quote_character, trim_policy>> = true;
} // namespace ranges
} // namespace std

namespace csv2 {
#endif

template <class delimiter = delimiter<','>, class quote_character = quote_character<'"'>,
          class first_row_is_header = first_row_is_header<true>,
          class trim_policy = trim_policy::trim_whitespace>
class Reader {
  struct RecordBounds {
    size_t content_end;
    size_t next_start;
  };

  static RecordBounds find_record_bounds_(const char *buffer, size_t buffer_size,
                                          size_t start) noexcept {
    if (!buffer || start >= buffer_size)
      return {buffer_size, buffer_size};

    const char *const record_start = buffer + start;
    const size_t remaining = buffer_size - start;
    const char *const newline =
        static_cast<const char *>(std::memchr(record_start, '\n', remaining));
    const size_t candidate_length =
        newline ? static_cast<size_t>(newline - record_start) : remaining;
    const char *const quote = static_cast<const char *>(
        std::memchr(record_start, quote_character::value, candidate_length));

    // The common unquoted case avoids the state machine entirely.
    if (!quote) {
      if (!newline)
        return {buffer_size, buffer_size};
      const size_t newline_index = start + static_cast<size_t>(newline - record_start);
      const size_t content_end = newline_index > start && buffer[newline_index - 1] == '\r'
                                     ? newline_index - 1
                                     : newline_index;
      return {content_end, newline_index + 1};
    }

    bool quote_opened = false;
    for (size_t i = start; i < buffer_size; ++i) {
      if (buffer[i] == quote_character::value) {
        if (quote_opened && i + 1 < buffer_size && buffer[i + 1] == quote_character::value) {
          ++i;
          continue;
        }
        quote_opened = !quote_opened;
      } else if (buffer[i] == '\n' && !quote_opened) {
        const size_t content_end = i > start && buffer[i - 1] == '\r' ? i - 1 : i;
        return {content_end, i + 1};
      }
    }

    // An unclosed quoted field is treated as content through EOF.
    return {buffer_size, buffer_size};
  }

#if CSV2_HAS_MMAP
  mio::mmap_source mmap_;
#endif
  std::unique_ptr<std::string> owned_buffer_;
  const char *buffer_{nullptr};
  size_t buffer_size_{0};

  void clear_buffer_() noexcept {
    buffer_ = nullptr;
    buffer_size_ = 0;
  }

  void reset_source_() {
    clear_buffer_();
    owned_buffer_.reset();
#if CSV2_HAS_MMAP
    mmap_.unmap();
#endif
  }

  static bool contains_range_(const char *source, size_t source_size, const char *data,
                              size_t size) noexcept {
    if (!source || !data || size > source_size)
      return false;

    const char *const source_end = source + source_size;
    const char *const data_end = data + size;
    const std::less<const char *> less;
    return !less(data, source) && !less(source_end, data_end);
  }

  bool owns_range_(const char *data, size_t size) const noexcept {
    if (owned_buffer_ && contains_range_(owned_buffer_->c_str(), owned_buffer_->size(), data, size))
      return true;
#if CSV2_HAS_MMAP
    if (mmap_.is_mapped() && contains_range_(mmap_.data(), mmap_.size(), data, size))
      return true;
#endif
    return false;
  }

  template <typename StringType> bool parse_dispatch_(StringType &&contents, std::true_type) {
    return parse_borrowed(contents.c_str(), contents.size());
  }

  template <typename StringType> bool parse_owned_(StringType &&contents, std::true_type) {
    std::unique_ptr<std::string> new_buffer(new std::string(std::forward<StringType>(contents)));
    reset_source_();
    if (new_buffer->empty())
      return false;
    owned_buffer_ = std::move(new_buffer);
    buffer_ = owned_buffer_->c_str();
    buffer_size_ = owned_buffer_->size();
    return true;
  }

  template <typename StringType> bool parse_owned_(StringType &&contents, std::false_type) {
    std::unique_ptr<std::string> new_buffer(new std::string(contents.c_str(), contents.size()));
    reset_source_();
    if (new_buffer->empty())
      return false;
    owned_buffer_ = std::move(new_buffer);
    buffer_ = owned_buffer_->c_str();
    buffer_size_ = owned_buffer_->size();
    return true;
  }

  template <typename StringType> bool parse_dispatch_(StringType &&contents, std::false_type) {
    typedef typename std::decay<StringType>::type DecayedString;
    return parse_owned_(std::forward<StringType>(contents),
                        typename std::is_same<DecayedString, std::string>::type());
  }

public:
  Reader() = default;
  Reader(const Reader &) = delete;
  Reader &operator=(const Reader &) = delete;

  Reader(Reader &&other)
      :
#if CSV2_HAS_MMAP
        mmap_(std::move(other.mmap_)),
#endif
        owned_buffer_(std::move(other.owned_buffer_)), buffer_(other.buffer_),
        buffer_size_(other.buffer_size_) {
    other.clear_buffer_();
  }

  Reader &operator=(Reader &&other) {
    if (this != &other) {
      // The borrowed source may be a view into storage currently owned by this Reader.
      if (owns_range_(other.buffer_, other.buffer_size_)) {
        buffer_ = other.buffer_;
        buffer_size_ = other.buffer_size_;
        other.clear_buffer_();
        return *this;
      }
      reset_source_();
#if CSV2_HAS_MMAP
      mmap_ = std::move(other.mmap_);
#endif
      owned_buffer_ = std::move(other.owned_buffer_);
      buffer_ = other.buffer_;
      buffer_size_ = other.buffer_size_;
      other.clear_buffer_();
    }
    return *this;
  }

#if CSV2_HAS_MMAP
  // Memory-map a file. A failed mapping clears any previous source.
  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value, bool>::type
  mmap(StringType &&filename, std::error_code &error) {
    reset_source_();
    mmap_.map(std::forward<StringType>(filename), error);
    if (error || !mmap_.is_open() || !mmap_.is_mapped() || mmap_.size() == 0) {
      if (!error)
        error = std::make_error_code(std::errc::invalid_argument);
      mmap_.unmap();
      return false;
    }
    buffer_ = mmap_.data();
    buffer_size_ = mmap_.size();
    return true;
  }

  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value, bool>::type
  mmap(StringType &&filename) {
    std::error_code error;
    return mmap(std::forward<StringType>(filename), error);
  }
#endif

  // Lvalue strings are borrowed. Rvalue strings are owned by this Reader.
  template <typename StringType> bool parse(StringType &&contents) {
    return parse_dispatch_(std::forward<StringType>(contents),
                           typename std::is_lvalue_reference<StringType &&>::type());
  }

  // Borrow exactly size bytes. The caller keeps the storage alive.
  bool parse_borrowed(const char *data, size_t size) noexcept {
    if (!data || size == 0) {
      reset_source_();
      return false;
    }
    if (!owns_range_(data, size))
      reset_source_();
    buffer_ = data;
    buffer_size_ = size;
    return true;
  }

  // Own an independent copy (or moved value) of the input string.
  bool parse_owned(std::string contents) {
    return parse_owned_(std::move(contents), std::true_type());
  }

#if CSV2_HAS_SPAN
  bool parse_borrowed(std::span<const char> contents) noexcept {
    return parse_borrowed(contents.data(), contents.size());
  }
#endif

#if CSV2_HAS_STRING_VIEW
  // Borrow a string_view. The view's storage must outlive Reader access.
  bool parse_view(std::string_view sv) {
    const char *const data = sv.data();
    const size_t size = sv.size();
    if (size == 0) {
      reset_source_();
      return false;
    }
    if (!owns_range_(data, size))
      reset_source_();
    buffer_ = data;
    buffer_size_ = size;
    return true;
  }
#endif

  using Cell = basic_cell<quote_character, trim_policy>;
  using Row = basic_row<delimiter, quote_character, trim_policy>;
  class RowIterator;

  class RowIterator {
    const char *buffer_{nullptr};
    size_t buffer_size_{0};
    size_t start_{0};
    size_t content_end_{0};
    size_t next_start_{0};
    friend class Reader;

  public:
    using value_type = Row;
    using difference_type = std::ptrdiff_t;
    using reference = Row;
    using pointer = void;
    using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
    using iterator_concept = std::forward_iterator_tag;
#endif

    RowIterator() = default;

    RowIterator(const char *buffer, size_t buffer_size, size_t start)
        : buffer_(buffer), buffer_size_(buffer_size),
          start_(start < buffer_size ? start : buffer_size), content_end_(buffer_size),
          next_start_(buffer_size) {
      if (start_ < buffer_size_) {
        const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, start_);
        content_end_ = bounds.content_end;
        next_start_ = bounds.next_start;
      }
    }

    RowIterator &operator++() {
      start_ = next_start_;
      if (start_ < buffer_size_) {
        const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, start_);
        content_end_ = bounds.content_end;
        next_start_ = bounds.next_start;
      } else {
        start_ = buffer_size_;
        content_end_ = buffer_size_;
        next_start_ = buffer_size_;
      }
      return *this;
    }

    RowIterator operator++(int) {
      RowIterator previous(*this);
      ++(*this);
      return previous;
    }

    Row operator*() const { return Row(buffer_, start_, content_end_); }

    bool operator==(const RowIterator &rhs) const noexcept {
      return buffer_ == rhs.buffer_ && buffer_size_ == rhs.buffer_size_ && start_ == rhs.start_ &&
             content_end_ == rhs.content_end_ && next_start_ == rhs.next_start_;
    }

    bool operator!=(const RowIterator &rhs) const noexcept { return !(*this == rhs); }
  };

  RowIterator begin() const {
    if (!buffer_ || buffer_size_ == 0)
      return end();
    if (first_row_is_header::value) {
      const RecordBounds header = find_record_bounds_(buffer_, buffer_size_, 0);
      return RowIterator(buffer_, buffer_size_, header.next_start);
    }
    return RowIterator(buffer_, buffer_size_, 0);
  }

  RowIterator end() const { return RowIterator(buffer_, buffer_size_, buffer_size_); }

  Row header() const {
    if (!buffer_ || buffer_size_ == 0)
      return Row();
    const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, 0);
    return Row(buffer_, 0, bounds.content_end);
  }

  /** Returns the number of records, excluding the header when configured. */
  size_t rows(bool ignore_empty_lines = false) const {
    if (!buffer_ || buffer_size_ == 0)
      return 0;

    size_t start = 0;
    if (first_row_is_header::value)
      start = find_record_bounds_(buffer_, buffer_size_, 0).next_start;

    size_t result = 0;
    while (start < buffer_size_) {
      const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, start);
      if (!ignore_empty_lines || bounds.content_end != start)
        ++result;
      start = bounds.next_start;
    }
    return result;
  }

  size_t cols() const {
    size_t result = 0;
    for (const auto cell : header()) {
      (void)cell;
      ++result;
    }
    return result;
  }
};

} // namespace csv2
