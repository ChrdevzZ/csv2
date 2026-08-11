#pragma once

#include <cstddef>
#include <iterator>

namespace csv2 {
namespace detail {

template <unsigned Priority> struct output_priority : output_priority<Priority - 1> {};
template <> struct output_priority<0> {};

template <typename Container>
auto reserve_for_append_impl(Container &output, std::size_t additional, output_priority<2>)
    -> decltype(output.reserve(output.size() + additional), void()) {
  output.reserve(output.size() + additional);
}

template <typename Container>
auto reserve_for_append_impl(Container &output, std::size_t additional, output_priority<1>)
    -> decltype(output.reserve(additional), void()) {
  output.reserve(additional);
}

template <typename Container>
void reserve_for_append_impl(Container &, std::size_t, output_priority<0>) {}

template <typename Container>
void reserve_for_append(Container &output, std::size_t additional) {
  reserve_for_append_impl(output, additional, output_priority<2>());
}

template <typename Container>
auto append_range_impl(Container &output, const char *first, const char *last,
                       output_priority<3>)
    -> decltype(output.append(first, static_cast<std::size_t>(last - first)), void()) {
  output.append(first, static_cast<std::size_t>(last - first));
}

template <typename Container>
auto append_range_impl(Container &output, const char *first, const char *last,
                       output_priority<2>)
    -> decltype(output.insert(output.end(), first, last), void()) {
  output.insert(output.end(), first, last);
}

template <typename Container>
auto append_range_impl(Container &output, const char *first, const char *last,
                       output_priority<1>) -> decltype(output.push_back(*first), void()) {
  while (first != last) {
    output.push_back(*first);
    ++first;
  }
}

template <typename Container>
void append_range(Container &output, const char *first, const char *last) {
  append_range_impl(output, first, last, output_priority<3>());
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
