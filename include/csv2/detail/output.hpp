#pragma once

#include <csv2/detail/config.hpp>

#include <cstddef>
#include <iterator>
#include <type_traits>
#include <utility>

namespace csv2 {
namespace detail {

template <unsigned Priority> struct output_priority : output_priority<Priority - 1> {};
template <> struct output_priority<0> {};

template <typename Container>
CSV2_FORCE_INLINE auto reserve_for_append_impl(Container &output, std::size_t additional,
                                               output_priority<2>)
    -> decltype(output.reserve(output.size() + additional), void()) {
  output.reserve(output.size() + additional);
}

template <typename Container>
CSV2_FORCE_INLINE auto reserve_for_append_impl(Container &output, std::size_t additional,
                                               output_priority<1>)
    -> decltype(output.reserve(additional), void()) {
  output.reserve(additional);
}

template <typename Container>
CSV2_FORCE_INLINE void reserve_for_append_impl(Container &, std::size_t, output_priority<0>) {}

template <typename Container>
CSV2_FORCE_INLINE void reserve_for_append(Container &output, std::size_t additional) {
  reserve_for_append_impl(output, additional, output_priority<2>());
}

template <typename Container>
CSV2_FORCE_INLINE auto append_range_impl(Container &output, const char *first, const char *last,
                                         output_priority<3>)
    -> decltype(output.append(first, static_cast<std::size_t>(last - first)), void()) {
  output.append(first, static_cast<std::size_t>(last - first));
}

template <typename Container>
CSV2_FORCE_INLINE auto append_range_impl(Container &output, const char *first, const char *last,
                                         output_priority<2>)
    -> decltype(output.insert(output.end(), first, last), void()) {
  output.insert(output.end(), first, last);
}

template <typename Container>
CSV2_FORCE_INLINE auto append_range_impl(Container &output, const char *first, const char *last,
                                         output_priority<1>)
    -> decltype(output.push_back(*first), void()) {
  while (first != last) {
    output.push_back(*first);
    ++first;
  }
}

template <typename Container>
CSV2_FORCE_INLINE void append_range(Container &output, const char *first, const char *last) {
  append_range_impl(output, first, last, output_priority<3>());
}

template <typename Container> class supports_push_back {
  template <typename Type>
  static auto check(int) -> decltype(std::declval<Type &>().push_back(char()), std::true_type());
  template <typename> static std::false_type check(...);

public:
  static const bool value = decltype(check<Container>(0))::value;
};

template <typename Container>
CSV2_FORCE_INLINE void append_optimized_range_impl(Container &output, const char *first,
                                                   const char *last, std::true_type) {
  if (last - first < 64) {
    while (first != last) {
      output.push_back(*first);
      ++first;
    }
    return;
  }
  append_range(output, first, last);
}

template <typename Container>
CSV2_FORCE_INLINE void append_optimized_range_impl(Container &output, const char *first,
                                                   const char *last, std::false_type) {
  append_range(output, first, last);
}

template <typename Container>
CSV2_FORCE_INLINE void append_optimized_range(Container &output, const char *first,
                                              const char *last) {
  append_optimized_range_impl(output, first, last,
                              std::integral_constant<bool, supports_push_back<Container>::value>());
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded_segments(Container &output, const char *buffer,
                                               std::size_t first, std::size_t last, char quote) {
  std::size_t segment_start = first;
  for (std::size_t i = first; i < last; ++i) {
    if (buffer[i] == quote && i + 1 < last && buffer[i + 1] == quote) {
      append_range(output, buffer + segment_start, buffer + i + 1);
      ++i;
      segment_start = i + 1;
    }
  }
  if (segment_start < last)
    append_range(output, buffer + segment_start, buffer + last);
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded_impl(Container &output, const char *buffer, std::size_t first,
                                           std::size_t last, char quote, std::true_type) {
  if (last - first < 64) {
    for (std::size_t i = first; i < last; ++i) {
      output.push_back(buffer[i]);
      if (buffer[i] == quote && i + 1 < last && buffer[i + 1] == quote)
        ++i;
    }
    return;
  }
  append_decoded_segments(output, buffer, first, last, quote);
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded_impl(Container &output, const char *buffer, std::size_t first,
                                           std::size_t last, char quote, std::false_type) {
  append_decoded_segments(output, buffer, first, last, quote);
}

template <typename Container>
CSV2_FORCE_INLINE void append_decoded(Container &output, const char *buffer, std::size_t first,
                                      std::size_t last, char quote) {
  append_decoded_impl(output, buffer, first, last, quote,
                      std::integral_constant<bool, supports_push_back<Container>::value>());
}

template <typename Container> class container_output_iterator {
public:
  using iterator_category = std::output_iterator_tag;
  using value_type = void;
  using difference_type = void;
  using pointer = void;
  using reference = void;

  explicit container_output_iterator(Container &output) : output_(&output) {}

  container_output_iterator &operator=(char value) {
    append_range(*output_, &value, &value + 1);
    return *this;
  }
  container_output_iterator &operator*() { return *this; }
  container_output_iterator &operator++() { return *this; }
  container_output_iterator operator++(int) { return *this; }

private:
  Container *output_;
};

template <typename Container>
container_output_iterator<Container> container_inserter(Container &output) {
  return container_output_iterator<Container>(output);
}

template <typename OutputIt>
OutputIt copy_chars(const char *first, const char *last, OutputIt output) {
  while (first != last) {
    *output = *first;
    ++output;
    ++first;
  }
  return output;
}

} // namespace detail
} // namespace csv2
