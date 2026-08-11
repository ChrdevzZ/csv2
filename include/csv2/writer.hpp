#pragma once

#include <cstring>
#include <csv2/detail/config.hpp>
#include <csv2/parameters.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <type_traits>
#include <utility>

namespace csv2 {

namespace stream_ownership {
struct close_on_destroy {};
struct leave_open {};
} // namespace stream_ownership

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
          typename Ownership = stream_ownership::close_on_destroy>
class Writer {
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
    release_noexcept_(typename std::is_same<Ownership,
                                            stream_ownership::close_on_destroy>::type());
  }

  template <typename Field>
  auto write_field_(const Field &field, int)
      -> decltype(static_cast<const char *>(field.data()), field.size(),
                  stream_->write(static_cast<const char *>(field.data()),
                                 static_cast<std::streamsize>(field.size())),
                  void()) {
    stream_->write(static_cast<const char *>(field.data()),
                   static_cast<std::streamsize>(field.size()));
  }

  template <typename Field> void write_field_(const Field &field, long) { *stream_ << field; }

public:
  Writer(Stream &stream) noexcept : stream_(&stream), active_(true) {}

  Writer(const Writer &) = delete;
  Writer &operator=(const Writer &) = delete;

  Writer(Writer &&other) noexcept : stream_(other.stream_), active_(other.active_) {
    other.stream_ = nullptr;
    other.active_ = false;
  }

  Writer &operator=(Writer &&other) noexcept {
    if (this != &other) {
      release_noexcept_();
      stream_ = other.stream_;
      active_ = other.active_;
      other.stream_ = nullptr;
      other.active_ = false;
    }
    return *this;
  }

  ~Writer() noexcept { release_noexcept_(); }

  void close() {
    if (!active_)
      return;
    active_ = false;
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
  }

  template <typename Container> void write_row(Container &&row) {
    if (!active_)
      return;
    auto &&strings = std::forward<Container>(row);
    using std::begin;
    using std::end;
    auto current = begin(strings);
    const auto last = end(strings);
    if (current != last) {
      write_field_(*current, 0);
      const char separator = delimiter::value;
      while (++current != last) {
        *stream_ << separator;
        write_field_(*current, 0);
      }
    }
    *stream_ << '\n';
  }

  template <typename Container> void write_rows(Container &&rows) {
    if (!active_)
      return;
    auto &&container_of_rows = std::forward<Container>(rows);
    using std::begin;
    using std::end;
    auto current = begin(container_of_rows);
    const auto last = end(container_of_rows);
    while (current != last) {
      write_row(*current);
      ++current;
    }
  }
};

} // namespace csv2
