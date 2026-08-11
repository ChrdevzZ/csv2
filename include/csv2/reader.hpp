#pragma once

#include <cstring>
#include <csv2/detail/config.hpp>
#include <csv2/detail/conversion.hpp>
#include <csv2/detail/output.hpp>
#include <csv2/detail/scanner.hpp>
#include <csv2/detail/validation.hpp>

#if CSV2_HAS_MMAP
#include <csv2/mio.hpp>
#endif
#include <csv2/parameters.hpp>

#include <cstdint>
#include <iterator>
#include <limits>
#include <memory>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>
#include <vector>
#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif
#if CSV2_HAS_SPAN
#include <span>
#endif
#if CSV2_HAS_RANGES
#include <ranges>
#endif
#if CSV2_HAS_EXPECTED
#include <expected>
#endif

namespace csv2 {

template <class quote_character, class trim_policy> class basic_cell {
  const char *buffer_{nullptr};
  size_t start_{0};
  size_t end_{0};
  bool escaped_{false};

  std::pair<size_t, size_t> content_bounds_() const noexcept {
    std::pair<size_t, size_t> bounds = trim_policy::trim(buffer_, start_, end_);
    if (bounds.second - bounds.first >= 2 && buffer_[bounds.first] == quote_character::value &&
        buffer_[bounds.second - 1] == quote_character::value) {
      ++bounds.first;
      --bounds.second;
    }
    return bounds;
  }

public:
  basic_cell() = default;
  basic_cell(const char *buffer, size_t start, size_t end, bool escaped) noexcept
      : buffer_(buffer), start_(start), end_(end), escaped_(escaped) {}

  const char *raw_data() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
  size_t raw_size() const noexcept { return end_ - start_; }
  bool has_escaped_quotes() const noexcept { return escaped_; }

#if CSV2_HAS_STRING_VIEW
  std::string_view raw_trimmed_view() const noexcept {
    if (!buffer_)
      return std::string_view();
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

  template <class Integer>
  typename std::enable_if<detail::is_csv_integer<Integer>::value, bool>::type
  try_parse(Integer &output, conversion_error &error, int base = 10) const noexcept {
    if (!buffer_ || escaped_)
      return detail::conversion_failure(error, conversion_errc::invalid_argument, 0);
    const std::pair<size_t, size_t> bounds = content_bounds_();
    return detail::parse_integer(buffer_ + bounds.first, buffer_ + bounds.second, output, error,
                                 base);
  }

#if CSV2_HAS_EXPECTED
  template <class Integer>
  typename std::enable_if<detail::is_csv_integer<Integer>::value,
                          std::expected<Integer, conversion_error>>::type
  parse_expected(int base = 10) const noexcept {
    Integer result{};
    conversion_error error;
    if (try_parse(result, error, base))
      return result;
    return std::unexpected(error);
  }
#endif
};

template <class delimiter, class quote_character, class trim_policy> class basic_row {
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
    const char *buffer_{nullptr};
    size_t current_{0};
    size_t end_{0};
    size_t content_end_{0};
    bool escaped_{false};
    bool at_end_{true};

    void update_bounds_() noexcept {
      if (!at_end_) {
        const detail::cell_bounds bounds =
            detail::find_cell_bounds<delimiter, quote_character>(buffer_, current_, end_);
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

    CellIterator(const char *buffer, size_t start, size_t end)
        : buffer_(buffer), current_(start), end_(end), content_end_(end), escaped_(false),
          at_end_(start >= end) {
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
      return buffer_ == rhs.buffer_ && current_ == rhs.current_ && end_ == rhs.end_ &&
             at_end_ == rhs.at_end_;
    }

    bool operator!=(const CellIterator &rhs) const noexcept { return !(*this == rhs); }
  };

  CellIterator begin() const { return CellIterator(buffer_, start_, end_); }
  CellIterator end() const { return CellIterator(buffer_, end_, end_); }
};

template <class delimiter_type, class quote_character_type, class trim_policy_type> class RowIndex {
public:
  using Row = basic_row<delimiter_type, quote_character_type, trim_policy_type>;

private:
  const char *buffer_{nullptr};
  size_t buffer_size_{0};
  std::vector<size_t> offsets_;

  Row row_at_(size_t position) const noexcept {
    const size_t start = offsets_[position];
    const detail::record_bounds bounds =
        detail::find_record_bounds<quote_character_type>(buffer_, buffer_size_, start);
    return Row(buffer_, start, bounds.content_end);
  }

public:
  RowIndex() = default;

  RowIndex(const char *buffer, size_t buffer_size, size_t start, bool ignore_empty_lines)
      : buffer_(buffer), buffer_size_(buffer_size) {
    if (!buffer_)
      return;
    while (start < buffer_size_) {
      const detail::record_bounds bounds =
          detail::find_record_bounds<quote_character_type>(buffer_, buffer_size_, start);
      if (!ignore_empty_lines || bounds.content_end != start)
        offsets_.push_back(start);
      start = bounds.next_start;
    }
  }

  size_t size() const noexcept { return offsets_.size(); }
  bool empty() const noexcept { return offsets_.empty(); }
  Row operator[](size_t position) const noexcept { return row_at_(position); }

  class iterator {
    const RowIndex *index_{nullptr};
    size_t position_{0};

  public:
    using value_type = Row;
    using difference_type = std::ptrdiff_t;
    using reference = Row;
    using pointer = void;
    using iterator_category = std::random_access_iterator_tag;
#if CSV2_HAS_RANGES
    using iterator_concept = std::random_access_iterator_tag;
#endif

    iterator() = default;
    iterator(const RowIndex *index, size_t position) noexcept
        : index_(index), position_(position) {}

    Row operator*() const noexcept { return (*index_)[position_]; }
    Row operator[](difference_type offset) const noexcept {
      return (*index_)[static_cast<size_t>(static_cast<difference_type>(position_) + offset)];
    }

    iterator &operator++() noexcept {
      ++position_;
      return *this;
    }
    iterator operator++(int) noexcept {
      iterator previous(*this);
      ++(*this);
      return previous;
    }
    iterator &operator--() noexcept {
      --position_;
      return *this;
    }
    iterator operator--(int) noexcept {
      iterator previous(*this);
      --(*this);
      return previous;
    }
    iterator &operator+=(difference_type offset) noexcept {
      position_ = static_cast<size_t>(static_cast<difference_type>(position_) + offset);
      return *this;
    }
    iterator &operator-=(difference_type offset) noexcept { return *this += -offset; }

    friend iterator operator+(iterator value, difference_type offset) noexcept {
      value += offset;
      return value;
    }
    friend iterator operator+(difference_type offset, iterator value) noexcept {
      value += offset;
      return value;
    }
    friend iterator operator-(iterator value, difference_type offset) noexcept {
      value -= offset;
      return value;
    }
    friend difference_type operator-(const iterator &left, const iterator &right) noexcept {
      return static_cast<difference_type>(left.position_) -
             static_cast<difference_type>(right.position_);
    }

    friend bool operator==(const iterator &left, const iterator &right) noexcept {
      return left.index_ == right.index_ && left.position_ == right.position_;
    }
    friend bool operator!=(const iterator &left, const iterator &right) noexcept {
      return !(left == right);
    }
    friend bool operator<(const iterator &left, const iterator &right) noexcept {
      return left.position_ < right.position_;
    }
    friend bool operator>(const iterator &left, const iterator &right) noexcept {
      return right < left;
    }
    friend bool operator<=(const iterator &left, const iterator &right) noexcept {
      return !(right < left);
    }
    friend bool operator>=(const iterator &left, const iterator &right) noexcept {
      return !(left < right);
    }
  };

  iterator begin() const noexcept { return iterator(this, 0); }
  iterator end() const noexcept { return iterator(this, size()); }
};

#if CSV2_HAS_RANGES
} // namespace csv2
namespace std {
namespace ranges {
template <class delimiter, class quote_character, class trim_policy>
inline constexpr bool enable_view<csv2::basic_row<delimiter, quote_character, trim_policy>> = true;
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

    const std::uintptr_t source_begin = reinterpret_cast<std::uintptr_t>(source);
    const std::uintptr_t data_begin = reinterpret_cast<std::uintptr_t>(data);
    if (source_size > (std::numeric_limits<std::uintptr_t>::max)() - source_begin)
      return false;
    const std::uintptr_t source_end = source_begin + source_size;
    return data_begin >= source_begin && data_begin <= source_end &&
           size <= source_end - data_begin;
  }

  static bool contains_address_(const char *source, size_t source_size, const char *data) noexcept {
    if (!source || !data)
      return false;
    const std::uintptr_t source_begin = reinterpret_cast<std::uintptr_t>(source);
    const std::uintptr_t data_begin = reinterpret_cast<std::uintptr_t>(data);
    if (source_size > (std::numeric_limits<std::uintptr_t>::max)() - source_begin)
      return false;
    return data_begin >= source_begin && data_begin <= source_begin + source_size;
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

  bool aliases_source_(const char *data) const noexcept {
    if (owned_buffer_ && contains_address_(owned_buffer_->c_str(), owned_buffer_->size(), data))
      return true;
#if CSV2_HAS_MMAP
    if (mmap_.is_mapped() && contains_address_(mmap_.data(), mmap_.size(), data))
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

#if CSV2_HAS_EXPECTED
  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value,
                          std::expected<void, std::error_code>>::type
  mmap_expected(StringType &&filename) {
    std::error_code error;
    if (mmap(std::forward<StringType>(filename), error))
      return {};
    return std::unexpected(error);
  }
#endif
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
    const bool owned_range = owns_range_(data, size);
    if (aliases_source_(data) && !owned_range) {
      reset_source_();
      return false;
    }
    if (!owned_range)
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
    const bool owned_range = owns_range_(data, size);
    if (aliases_source_(data) && !owned_range) {
      reset_source_();
      return false;
    }
    if (!owned_range)
      reset_source_();
    buffer_ = data;
    buffer_size_ = size;
    return true;
  }
#endif

  bool validate(parse_error &error) const noexcept {
    return detail::validate_csv<delimiter, quote_character, trim_policy>(buffer_, buffer_size_,
                                                                         error);
  }

#if CSV2_HAS_EXPECTED
  std::expected<void, parse_error> validate_expected() const noexcept {
    parse_error error;
    if (validate(error))
      return {};
    return std::unexpected(error);
  }
#endif

  using Cell = basic_cell<quote_character, trim_policy>;
  using Row = basic_row<delimiter, quote_character, trim_policy>;
  using RowIndex = csv2::RowIndex<delimiter, quote_character, trim_policy>;
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
        const detail::record_bounds bounds =
            detail::find_record_bounds<quote_character>(buffer_, buffer_size_, start_);
        content_end_ = bounds.content_end;
        next_start_ = bounds.next_start;
      }
    }

    RowIterator &operator++() {
      start_ = next_start_;
      if (start_ < buffer_size_) {
        const detail::record_bounds bounds =
            detail::find_record_bounds<quote_character>(buffer_, buffer_size_, start_);
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
      const detail::record_bounds header =
          detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0);
      return RowIterator(buffer_, buffer_size_, header.next_start);
    }
    return RowIterator(buffer_, buffer_size_, 0);
  }

  RowIterator end() const { return RowIterator(buffer_, buffer_size_, buffer_size_); }

  Row header() const {
    if (!buffer_ || buffer_size_ == 0)
      return Row();
    const detail::record_bounds bounds =
        detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0);
    return Row(buffer_, 0, bounds.content_end);
  }

  /** Returns the number of records, excluding the header when configured. */
  size_t rows(bool ignore_empty_lines = false) const {
    if (!buffer_ || buffer_size_ == 0)
      return 0;

    size_t start = 0;
    if (first_row_is_header::value)
      start = detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0).next_start;

    size_t result = 0;
    while (start < buffer_size_) {
      const detail::record_bounds bounds =
          detail::find_record_bounds<quote_character>(buffer_, buffer_size_, start);
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

  RowIndex index(bool ignore_empty_lines = false) const {
    size_t start = 0;
    if (buffer_ && first_row_is_header::value)
      start = detail::find_record_bounds<quote_character>(buffer_, buffer_size_, 0).next_start;
    return RowIndex(buffer_, buffer_size_, start, ignore_empty_lines);
  }
};

} // namespace csv2
