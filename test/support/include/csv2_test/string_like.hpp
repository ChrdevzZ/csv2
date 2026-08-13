#ifndef CSV2_TEST_STRING_LIKE_HPP
#define CSV2_TEST_STRING_LIKE_HPP

#include <cstddef>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>

namespace csv2_test {

struct StringLikeView {
  StringLikeView(const char *data, std::size_t size) : data(data), size_in_bytes(size) {}
  const char *c_str() const { return data; }
  std::size_t size() const { return size_in_bytes; }
  const char *data;
  std::size_t size_in_bytes;
};

struct SequencedStringLikeView {
  explicit SequencedStringLikeView(const std::string &value)
      : value(value), data_observed(false), sequence_valid(true) {}
  const char *c_str() const {
    data_observed = true;
    return value.c_str();
  }
  std::size_t size() const {
    if (!data_observed)
      sequence_valid = false;
    return value.size();
  }
  const std::string &value;
  mutable bool data_observed;
  mutable bool sequence_valid;
};

struct LazyAddressStringLikeView {
  explicit LazyAddressStringLikeView(std::string value) : value(std::move(value)) {}
  const char *c_str() const {
    if (storage.empty())
      storage = value;
    return storage.c_str();
  }
  std::size_t size() const { return value.size(); }
  std::string value;
  mutable std::string storage;
};

struct SequencedOwnedStringLike {
  SequencedOwnedStringLike(std::string value, bool &sequence_valid)
      : value(std::move(value)), sequence_valid(&sequence_valid), data_observed(false) {}
  const char *c_str() const {
    storage = value;
    data_observed = true;
    return storage.c_str();
  }
  std::size_t size() const {
    if (!data_observed) {
      *sequence_valid = false;
      return 0;
    }
    return storage.size();
  }
  std::string value;
  bool *sequence_valid;
  mutable bool data_observed;
  mutable std::string storage;
};

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
struct ThrowingOwnedStringLike {
  const char *c_str() const { throw std::runtime_error("materialization failure"); }
  std::size_t size() const { return 3; }
};

inline std::size_t oversized_owned_string_size() {
  return (std::numeric_limits<std::size_t>::max)();
}

struct OversizedOwnedStringLike {
  const char *c_str() const { return "x"; }
  std::size_t size() const { return oversized_owned_string_size(); }
};
#endif

} // namespace csv2_test

#endif
