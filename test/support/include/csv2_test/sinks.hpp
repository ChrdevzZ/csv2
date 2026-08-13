#ifndef CSV2_TEST_SINKS_HPP
#define CSV2_TEST_SINKS_HPP

#include <cstddef>
#include <string>

namespace csv2_test {

class ReserveTrackingBuffer {
public:
  explicit ReserveTrackingBuffer(const char *prefix) : value(prefix) {}
  std::size_t size() const { return value.size(); }
  void reserve(std::size_t requested) {
    last_reserve = requested;
    value.reserve(requested);
  }
  void push_back(char character) { value.push_back(character); }
  std::string value;
  std::size_t last_reserve{0};
};

class ReserveOnlyBuffer {
public:
  explicit ReserveOnlyBuffer(const char *prefix) : value(prefix) {}
  void reserve(std::size_t requested) {
    last_reserve = requested;
    value.reserve(requested);
  }
  void push_back(char character) { value.push_back(character); }
  std::string value;
  std::size_t last_reserve{0};
};

class AppendOnlyBuffer {
public:
  void append(const char *data, std::size_t size) { value.append(data, size); }
  std::string value;
};

class AppendCountingBuffer {
public:
  void append(const char *data, std::size_t size) {
    ++append_calls;
    value.append(data, size);
  }
  std::string value;
  std::size_t append_calls{0};
};

class RejectZeroReserveBuffer {
public:
  void reserve(std::size_t) { reserve_called = true; }
  void push_back(char character) { value.push_back(character); }
  std::string value;
  bool reserve_called{false};
};

} // namespace csv2_test

#endif
