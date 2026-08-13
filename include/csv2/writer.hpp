#pragma once

#include <cstring>
#include <csv2/detail/config.hpp>
#include <csv2/parameters.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <type_traits>
#include <utility>
#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif

namespace csv2 {

namespace stream_ownership {
struct close_on_destroy {};
struct leave_open {};
} // namespace stream_ownership

namespace quote_policy {
struct none {};
struct minimal {};
struct always {};
} // namespace quote_policy

namespace detail {

struct direct_character_fields {};

using std::begin;
using std::end;

template <typename Range>
auto adl_begin(Range &&range) -> decltype(begin(std::forward<Range>(range))) {
  return begin(std::forward<Range>(range));
}

template <typename Range> auto adl_end(Range &&range) -> decltype(end(std::forward<Range>(range))) {
  return end(std::forward<Range>(range));
}

template <typename T> struct is_direct_character_field : std::false_type {};

template <typename Traits, typename Allocator>
struct is_direct_character_field<std::basic_string<char, Traits, Allocator>> : std::true_type {};

#if CSV2_HAS_STRING_VIEW
template <typename Traits>
struct is_direct_character_field<std::basic_string_view<char, Traits>> : std::true_type {};
#endif

} // namespace detail

template <typename, typename T> struct has_close : std::false_type {};

template <typename C, typename Ret, typename... Args> struct has_close<C, Ret(Args...)> {
private:
  template <typename T>
  static constexpr auto check(T *) ->
      typename std::is_same<decltype(std::declval<T &>().close(std::declval<Args>()...)),
                            Ret>::type;

  template <typename> static constexpr std::false_type check(...);

public:
  static constexpr bool value = decltype(check<C>(0))::value;
};

template <class delimiter = delimiter<','>, typename Stream = std::ofstream,
          typename Ownership = stream_ownership::close_on_destroy,
          typename QuotePolicy = quote_policy::none>
class basic_writer {
  static_assert(std::is_same<Ownership, stream_ownership::close_on_destroy>::value ||
                    std::is_same<Ownership, stream_ownership::leave_open>::value,
                "csv2 writer ownership policy is not supported");
  static_assert(std::is_same<QuotePolicy, quote_policy::none>::value ||
                    std::is_same<QuotePolicy, quote_policy::minimal>::value ||
                    std::is_same<QuotePolicy, quote_policy::always>::value,
                "csv2 writer quote policy is not supported");

  Stream *stream_; // output stream for the writer
  bool active_;

  static void close_stream_(Stream &stream, std::true_type) { stream.close(); }

  static void close_stream_(Stream &, std::false_type) {}

  void close_noexcept_() noexcept {
    if (!active_)
      return;
    active_ = false;
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
    try {
      close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
    } catch (...) {
    }
#else
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
#endif
  }

  void release_noexcept_(std::true_type) noexcept { close_noexcept_(); }

  void release_noexcept_(std::false_type) noexcept { active_ = false; }

  void release_noexcept_() noexcept {
    release_noexcept_(typename std::is_same<Ownership, stream_ownership::close_on_destroy>::type());
  }

  template <typename Field, typename CandidateStream = Stream>
  auto write_raw_contiguous_(const Field &field, int)
      -> decltype(std::declval<CandidateStream &>().width(),
                  std::declval<CandidateStream &>()
                      << std::string(static_cast<const char *>(field.data()),
                                     static_cast<size_t>(field.size())),
                  void()) {
    if (stream_->width() != 0) {
      *stream_ << std::string(static_cast<const char *>(field.data()),
                              static_cast<size_t>(field.size()));
      return;
    }
    stream_->write(static_cast<const char *>(field.data()),
                   static_cast<std::streamsize>(field.size()));
  }

  template <typename Field> void write_raw_contiguous_(const Field &field, long) {
    stream_->write(static_cast<const char *>(field.data()),
                   static_cast<std::streamsize>(field.size()));
  }

  template <typename Field> void write_raw_field_(const Field &field, std::true_type) {
    write_raw_contiguous_(field, 0);
  }

  template <typename Field>
  auto write_raw_fallback_(const Field &field, int) -> decltype(*stream_ << field, void()) {
    *stream_ << field;
  }

  template <typename Field> void write_raw_fallback_(const Field &field, long) {
    write_raw_contiguous_(field, 0);
  }

  template <typename Field> void write_raw_field_(const Field &field, std::false_type) {
    write_raw_fallback_(field, 0);
  }

  static bool should_quote_(const char *, size_t, quote_policy::always) noexcept { return true; }

  static bool should_quote_(const char *data, size_t size, quote_policy::minimal) noexcept {
    for (size_t i = 0; i < size; ++i) {
      if (data[i] == delimiter::value || data[i] == '"' || data[i] == '\r' || data[i] == '\n')
        return true;
    }
    return false;
  }

  template <class Policy> void write_escaped_chars_(const char *data, size_t size, Policy policy) {
    if (!should_quote_(data, size, policy)) {
      if (size != 0)
        stream_->write(data, static_cast<std::streamsize>(size));
      return;
    }

    stream_->write("\"", 1);
    size_t segment = 0;
    for (size_t i = 0; i < size; ++i) {
      if (data[i] != '"')
        continue;
      if (segment < i)
        stream_->write(data + segment, static_cast<std::streamsize>(i - segment));
      stream_->write("\"\"", 2);
      segment = i + 1;
    }
    if (segment < size)
      stream_->write(data + segment, static_cast<std::streamsize>(size - segment));
    stream_->write("\"", 1);
  }

  template <typename Field> void write_formatted_field_(const Field &field) {
    std::ostringstream formatted;
    formatted.copyfmt(*stream_);
    formatted.exceptions(std::ios_base::goodbit);
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
    struct formatted_state_guard {
      Stream *target;
      std::ostringstream *source;
      bool active;

      formatted_state_guard(Stream &target_stream, std::ostringstream &source_stream) noexcept
          : target(&target_stream), source(&source_stream), active(true) {}

      ~formatted_state_guard() noexcept {
        if (!active)
          return;
        try {
          target->width(source->width());
          if (source->rdstate() != std::ios_base::goodbit)
            target->setstate(source->rdstate());
        } catch (...) {
        }
      }

      void release() noexcept { active = false; }
    } guard(*stream_, formatted);

    formatted << field;
    guard.release();
#else
    formatted << field;
#endif

    stream_->width(formatted.width());
    const std::ios_base::iostate state = formatted.rdstate();
    const std::string value = formatted.str();
    write_escaped_chars_(value.data(), value.size(), QuotePolicy());
    if (state != std::ios_base::goodbit)
      stream_->setstate(state);
  }

  void write_formatted_field_(const char *data, size_t size) {
    write_formatted_field_(std::string(data, size));
  }

  template <typename Field, typename CandidateStream = Stream>
  auto write_escaped_contiguous_(const Field &field, int)
      -> decltype(std::declval<CandidateStream &>().width(),
                  std::declval<std::ostringstream &>().copyfmt(std::declval<CandidateStream &>()),
                  std::declval<CandidateStream &>()
                      << std::string(static_cast<const char *>(field.data()),
                                     static_cast<size_t>(field.size())),
                  void()) {
    const char *const data = static_cast<const char *>(field.data());
    const size_t size = static_cast<size_t>(field.size());
    if (stream_->width() == 0) {
      write_escaped_chars_(data, size, QuotePolicy());
      return;
    }
    write_formatted_field_(data, size);
  }

  template <typename Field> void write_escaped_contiguous_(const Field &field, long) {
    write_escaped_chars_(static_cast<const char *>(field.data()), static_cast<size_t>(field.size()),
                         QuotePolicy());
  }

  template <typename Field> void write_escaped_field_(const Field &field, std::true_type) {
    write_escaped_contiguous_(field, 0);
  }

  template <typename Field>
  auto write_escaped_fallback_(const Field &field,
                               int) -> decltype(std::declval<std::ostringstream &>() << field,
                                                void()) {
    write_formatted_field_(field);
  }

  template <typename Field> void write_escaped_fallback_(const Field &field, long) {
    write_escaped_contiguous_(field, 0);
  }

  template <typename Field> void write_escaped_field_(const Field &field, std::false_type) {
    write_escaped_fallback_(field, 0);
  }

  template <typename Field> void write_field_(const Field &field, std::true_type) {
    typedef typename std::decay<Field>::type field_type;
    write_raw_field_(field, typename detail::is_direct_character_field<field_type>::type());
  }

  template <typename Field> void write_field_(const Field &field, std::false_type) {
    typedef typename std::decay<Field>::type field_type;
    write_escaped_field_(field, typename detail::is_direct_character_field<field_type>::type());
  }

  template <typename Field>
  void write_field_(const Field &field, std::true_type, detail::direct_character_fields) {
    write_field_(field, std::true_type());
  }

  template <typename Field>
  void write_field_(const Field &field, std::false_type, detail::direct_character_fields) {
    write_field_(field, std::false_type());
  }

protected:
  template <typename Field>
  auto write_legacy_next_field_(char separator, const Field &field,
                                int) -> decltype((*stream_ << separator) << field, void()) {
    (*stream_ << separator) << field;
  }

  template <typename Field>
  void write_legacy_next_field_(char separator, const Field &field, long) {
    *stream_ << separator;
    write_raw_fallback_(field, 0);
  }

  template <typename Range> void write_legacy_iterable_row_(Range &strings) {
    auto current = detail::adl_begin(strings);
    const auto last = detail::adl_end(strings);
    if (current != last) {
      write_raw_fallback_(*current, 0);
      const char separator = delimiter::value;
      while (++current != last)
        write_legacy_next_field_(separator, *current, 0);
    }
    *stream_ << '\n';
  }

  template <typename Container>
  auto write_legacy_row_dispatch_(Container &&row, int)
      -> decltype(detail::adl_begin(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  detail::adl_end(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  void()) {
    const auto &strings = row;
    write_legacy_iterable_row_(strings);
  }

  template <typename Container> void write_legacy_row_dispatch_(Container &&row, long) {
    auto &&strings = std::forward<Container>(row);
    write_legacy_iterable_row_(strings);
  }

  template <typename Container> void write_legacy_row_(Container &&row) {
    if (!active_)
      return;
    write_legacy_row_dispatch_(std::forward<Container>(row), 0);
  }

  template <typename Range> void write_legacy_iterable_rows_(Range &container_of_rows) {
    auto current = detail::adl_begin(container_of_rows);
    const auto last = detail::adl_end(container_of_rows);
    while (current != last) {
      write_legacy_row_(*current);
      ++current;
    }
  }

  template <typename Container>
  auto write_legacy_rows_dispatch_(Container &&rows, int)
      -> decltype(detail::adl_begin(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  detail::adl_end(
                      std::declval<const typename std::remove_reference<Container>::type &>()),
                  void()) {
    const auto &container_of_rows = rows;
    write_legacy_iterable_rows_(container_of_rows);
  }

  template <typename Container> void write_legacy_rows_dispatch_(Container &&rows, long) {
    auto &&container_of_rows = std::forward<Container>(rows);
    write_legacy_iterable_rows_(container_of_rows);
  }

  template <typename Container> void write_legacy_rows_(Container &&rows) {
    if (!active_)
      return;
    write_legacy_rows_dispatch_(std::forward<Container>(rows), 0);
  }

  template <typename Container, typename FieldPolicy>
  void write_row_with_policy_(Container &&row, FieldPolicy field_policy) {
    if (!active_)
      return;
    auto &&strings = std::forward<Container>(row);
    using std::begin;
    using std::end;
    auto current = begin(strings);
    const auto last = end(strings);
    if (current != last) {
      write_field_(*current, typename std::is_same<QuotePolicy, quote_policy::none>::type(),
                   field_policy);
      const char separator = delimiter::value;
      while (++current != last) {
        *stream_ << separator;
        write_field_(*current, typename std::is_same<QuotePolicy, quote_policy::none>::type(),
                     field_policy);
      }
    }
    *stream_ << '\n';
  }

  template <typename Container, typename FieldPolicy>
  void write_rows_with_policy_(Container &&rows, FieldPolicy field_policy) {
    if (!active_)
      return;
    auto &&container_of_rows = std::forward<Container>(rows);
    using std::begin;
    using std::end;
    auto current = begin(container_of_rows);
    const auto last = end(container_of_rows);
    while (current != last) {
      write_row_with_policy_(*current, field_policy);
      ++current;
    }
  }

public:
  basic_writer(Stream &stream) noexcept : stream_(&stream), active_(true) {}

  basic_writer(const basic_writer &) = delete;
  basic_writer &operator=(const basic_writer &) = delete;

  basic_writer(basic_writer &&other) noexcept : stream_(other.stream_), active_(other.active_) {
    other.stream_ = nullptr;
    other.active_ = false;
  }

  basic_writer &operator=(basic_writer &&other) noexcept {
    if (this != &other) {
      release_noexcept_();
      stream_ = other.stream_;
      active_ = other.active_;
      other.stream_ = nullptr;
      other.active_ = false;
    }
    return *this;
  }

  ~basic_writer() noexcept { release_noexcept_(); }

  void close() {
    if (!active_)
      return;
    active_ = false;
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
  }

  template <typename Container> void write_row(Container &&row) {
    write_row_with_policy_(std::forward<Container>(row), detail::direct_character_fields());
  }

  template <typename Container> void write_rows(Container &&rows) {
    write_rows_with_policy_(std::forward<Container>(rows), detail::direct_character_fields());
  }
};

// Keep the historical two-parameter class template intact. Configurable
// ownership and quoting live on basic_writer so C++11/14 code can continue to
// pass csv2::Writer to a template-template parameter expecting two arguments.
template <class delimiter = delimiter<','>, typename Stream = std::ofstream>
class Writer : public basic_writer<delimiter, Stream, stream_ownership::close_on_destroy,
                                   quote_policy::none> {
  using base_type =
      basic_writer<delimiter, Stream, stream_ownership::close_on_destroy, quote_policy::none>;

public:
  Writer(Stream &stream) noexcept : base_type(stream) {}

  void close() { base_type::close(); }

  template <typename Container> void write_row(Container &&row) {
    this->write_legacy_row_(std::forward<Container>(row));
  }

  template <typename Container> void write_rows(Container &&rows) {
    this->write_legacy_rows_(std::forward<Container>(rows));
  }
};

template <class delimiter = delimiter<','>, typename Stream = std::ofstream,
          typename Ownership = stream_ownership::close_on_destroy>
using EscapingWriter = basic_writer<delimiter, Stream, Ownership, quote_policy::minimal>;

} // namespace csv2
