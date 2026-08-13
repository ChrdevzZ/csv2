#ifndef CSV2_TEST_STREAMS_HPP
#define CSV2_TEST_STREAMS_HPP

#include <csv2_test/csv2_headers.hpp>

#include <cstddef>
#include <ios>
#include <ostream>
#include <sstream>
#include <string>

#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif

namespace csv2_test {

class LvalueCloseStream : public std::ostringstream {
public:
  LvalueCloseStream() : closed(false) {}
  void close() & { closed = true; }
  bool closed;
};

class CountingCloseStream : public std::ostringstream {
public:
  void close() { ++close_count; }
  int close_count{0};
};

class DirectWriteTrackingStream : public std::ostringstream {
public:
  DirectWriteTrackingStream &write(const char *data, std::streamsize size) {
    ++write_calls;
    std::ostringstream::write(data, size);
    return *this;
  }
  std::size_t write_calls{0};
};

class MinimalWriteStream {
public:
  MinimalWriteStream &write(const char *data, std::streamsize size) {
    value.append(data, static_cast<std::size_t>(size));
    return *this;
  }
  MinimalWriteStream &operator<<(char character) {
    value.push_back(character);
    return *this;
  }
  std::string value;
};

class DecoratingStringStream {
public:
  DecoratingStringStream &write(const char *data, std::streamsize size) {
    value.append(data, static_cast<std::size_t>(size));
    return *this;
  }
  DecoratingStringStream &operator<<(char character) {
    value.push_back(character);
    return *this;
  }
  DecoratingStringStream &operator<<(const std::string &field) {
    value += '<';
    value += field;
    value += '>';
    return *this;
  }
#if CSV2_HAS_STRING_VIEW
  DecoratingStringStream &operator<<(std::string_view field) {
    value += '[';
    value.append(field.data(), field.size());
    value += ']';
    return *this;
  }
#endif
  std::string value;
};

class ChainedInsertionStream {
public:
  class Proxy {
  public:
    explicit Proxy(ChainedInsertionStream &stream) : stream_(stream) {}
    Proxy &operator<<(const std::string &field) {
      stream_.value += "P{" + field + '}';
      return *this;
    }

  private:
    ChainedInsertionStream &stream_;
  };

  ChainedInsertionStream &operator<<(const std::string &field) {
    value += "S{" + field + '}';
    return *this;
  }
  Proxy operator<<(char character) {
    value.push_back(character);
    return Proxy(*this);
  }
  std::string value;
};

class ConstSelectingRow {
public:
  ConstSelectingRow() : mutable_field_("mutable"), const_field_("const") {}
  std::string *begin() { return &mutable_field_; }
  std::string *end() { return &mutable_field_ + 1; }
  const std::string *begin() const { return &const_field_; }
  const std::string *end() const { return &const_field_ + 1; }

private:
  std::string mutable_field_;
  std::string const_field_;
};

struct CommaFormattedValue {
  int left;
  int right;
};

inline std::ostream &operator<<(std::ostream &stream, const CommaFormattedValue &value) {
  return stream << value.left << ',' << value.right;
}

struct StatefulFormattedValue {
  explicit StatefulFormattedValue(std::ios_base::iostate state) : state(state) {}
  std::ios_base::iostate state;
};

inline std::ostream &operator<<(std::ostream &stream, const StatefulFormattedValue &value) {
  stream.write("a,b", 3);
  stream.setstate(value.state);
  return stream;
}

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
struct WriterUserError {};
struct ConsumingThrowValue {};
inline std::ostream &operator<<(std::ostream &stream, const ConsumingThrowValue &) {
  stream << "x";
  throw WriterUserError();
}
struct UnformattedThrowValue {};
inline std::ostream &operator<<(std::ostream &stream, const UnformattedThrowValue &) {
  stream.write("x", 1);
  throw WriterUserError();
}
struct StatefulThrowValue {};
inline std::ostream &operator<<(std::ostream &stream, const StatefulThrowValue &) {
  stream.write("x", 1);
  stream.setstate(std::ios_base::failbit);
  throw WriterUserError();
}
#endif

struct FormattedContiguousValue {
  const char *data() const { return "raw"; }
  std::size_t size() const { return 3; }
};

inline std::ostream &operator<<(std::ostream &stream, const FormattedContiguousValue &) {
  return stream << "[formatted]";
}

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
struct CloseError {};
class ThrowingCloseStream : public std::ostringstream {
public:
  void close() {
    ++close_count;
    throw CloseError();
  }
  int close_count{0};
};
#endif

} // namespace csv2_test

#endif
