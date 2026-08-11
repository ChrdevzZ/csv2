#pragma once

#include <cstring>
#include <csv2/detail/config.hpp>

#if CSV2_HAS_MMAP
#include <csv2/mio.hpp>
#endif
#include <csv2/parameters.hpp>

#include <iterator>
#include <memory>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>
#if CSV2_HAS_STRING_VIEW
#include <functional>
#include <string_view>
#endif

namespace csv2 {

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

#if CSV2_HAS_STRING_VIEW
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
#endif

  template <typename StringType> bool parse_dispatch_(StringType &&contents, std::true_type) {
    const char *const data = contents.c_str();
    const size_t size = contents.size();
    reset_source_();
    if (size == 0)
      return false;
    buffer_ = data;
    buffer_size_ = size;
    return true;
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
#if CSV2_HAS_STRING_VIEW
      // The borrowed source may be a view into storage currently owned by this Reader.
      if (owns_range_(other.buffer_, other.buffer_size_)) {
        buffer_ = other.buffer_;
        buffer_size_ = other.buffer_size_;
        other.clear_buffer_();
        return *this;
      }
#endif
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

  class RowIterator;
  class Row;

  class Cell {
    const char *buffer_{nullptr};
    size_t start_{0};
    size_t end_{0};
    bool escaped_{false};
    friend class Row;

  public:
#if CSV2_HAS_STRING_VIEW
    std::string_view read_view() const {
      const auto bounds = trim_policy::trim(buffer_, start_, end_);
      return std::string_view(buffer_ + bounds.first, bounds.second - bounds.first);
    }
#endif

    template <typename Container> void read_raw_value(Container &result) const {
      if (start_ >= end_)
        return;
      result.reserve(result.size() + end_ - start_);
      for (size_t i = start_; i < end_; ++i)
        result.push_back(buffer_[i]);
    }

    template <typename Container> void read_value(Container &result) const {
      if (start_ >= end_)
        return;
      const auto bounds = trim_policy::trim(buffer_, start_, end_);
      result.reserve(result.size() + bounds.second - bounds.first);
      if (!escaped_) {
        for (size_t i = bounds.first; i < bounds.second; ++i)
          result.push_back(buffer_[i]);
        return;
      }

      for (size_t i = bounds.first; i < bounds.second; ++i) {
        result.push_back(buffer_[i]);
        if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
            buffer_[i + 1] == quote_character::value)
          ++i;
      }
    }
  };

  class Row {
    const char *buffer_{nullptr};
    size_t start_{0};
    size_t end_{0};
    friend class RowIterator;
    friend class Reader;

    template <typename Container>
    static auto reserve_for_append_(Container &result, size_t additional,
                                    int) -> decltype(result.reserve(result.size() + additional),
                                                     void()) {
      result.reserve(result.size() + additional);
    }

    template <typename Container>
    static void reserve_for_append_(Container &result, size_t additional, long) {
      result.reserve(additional);
    }

  public:
    const char *address() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
    size_t length() const { return end_ - start_; }

    template <typename Container> void read_raw_value(Container &result) const {
      if (start_ >= end_)
        return;
      reserve_for_append_(result, end_ - start_, 0);
      for (size_t i = start_; i < end_; ++i)
        result.push_back(buffer_[i]);
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

      friend class Row;

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

      Cell operator*() const {
        Cell cell;
        cell.buffer_ = buffer_;
        cell.start_ = current_;
        cell.end_ = content_end_;
        cell.escaped_ = escaped_;
        return cell;
      }

      bool operator==(const CellIterator &rhs) const noexcept {
        return buffer_ == rhs.buffer_ && range_size_ == rhs.range_size_ &&
               current_ == rhs.current_ && end_ == rhs.end_ && at_end_ == rhs.at_end_;
      }

      bool operator!=(const CellIterator &rhs) const noexcept { return !(*this == rhs); }
    };

    CellIterator begin() const { return CellIterator(buffer_, end_ - start_, start_, end_); }
    CellIterator end() const { return CellIterator(buffer_, end_ - start_, end_, end_); }
  };

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

    Row operator*() const {
      Row result;
      result.buffer_ = buffer_;
      result.start_ = start_;
      result.end_ = content_end_;
      return result;
    }

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
    Row result;
    result.buffer_ = buffer_;
    if (!buffer_ || buffer_size_ == 0)
      return result;
    const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, 0);
    result.end_ = bounds.content_end;
    return result;
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
