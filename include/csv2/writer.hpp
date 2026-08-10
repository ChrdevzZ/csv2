#pragma once

#include <cstring>
#include <csv2/parameters.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <type_traits>
#include <utility>

namespace csv2 {

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

template <class delimiter = delimiter<','>, typename Stream = std::ofstream> class Writer {
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
      close_stream_(*stream_,
                    std::integral_constant<bool, has_close<Stream, void()>::value>());
    } catch (...) {
    }
#else
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
#endif
  }

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
      close_noexcept_();
      stream_ = other.stream_;
      active_ = other.active_;
      other.stream_ = nullptr;
      other.active_ = false;
    }
    return *this;
  }

  ~Writer() noexcept { close_noexcept_(); }

  void close() {
    if (!active_)
      return;
    active_ = false;
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
  }

  template <typename Container> void write_row(Container &&row) {
    if (!active_)
      return;
    const auto &strings = std::forward<Container>(row);
    auto current = strings.begin();
    const auto end = strings.end();
    if (current != end) {
      *stream_ << *current;
      const char separator = delimiter::value;
      while (++current != end)
        *stream_ << separator << *current;
    }
    *stream_ << '\n';
  }

  template <typename Container> void write_rows(Container &&rows) {
    if (!active_)
      return;
    const auto &container_of_rows = std::forward<Container>(rows);
    for (const auto &row : container_of_rows) {
      write_row(row);
    }
  }
};

} // namespace csv2
