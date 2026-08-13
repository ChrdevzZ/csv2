#include "output_buffer.hpp"

#include <algorithm>
#include <cstring>
#include <limits>

namespace csv2_benchmark {

void OutputBuffer::reserve(std::size_t capacity) {
  storage_.resize(capacity);
  reset();
}

void OutputBuffer::reset() noexcept {
  overflowed_ = false;
  char *const first = storage_.empty() ? 0 : storage_.data();
  setp(first, first == 0 ? 0 : first + storage_.size());
}

std::size_t OutputBuffer::size() const noexcept {
  return pbase() == 0 ? 0 : static_cast<std::size_t>(pptr() - pbase());
}

std::streamsize OutputBuffer::xsputn(const char *data, std::streamsize size) {
  if (size <= 0)
    return 0;
  const std::streamsize available = pptr() == 0 ? 0 : epptr() - pptr();
  const std::streamsize written = (std::min)(available, size);
  if (written != size)
    overflowed_ = true;
  if (written > 0) {
    std::memcpy(pptr(), data, static_cast<std::size_t>(written));
    std::streamsize remaining = written;
    while (remaining > 0) {
      const int step = static_cast<int>(
          (std::min)(remaining, static_cast<std::streamsize>((std::numeric_limits<int>::max)())));
      pbump(step);
      remaining -= step;
    }
  }
  return written;
}

OutputBuffer::int_type OutputBuffer::overflow(int_type character) {
  if (traits_type::eq_int_type(character, traits_type::eof()))
    return traits_type::not_eof(character);
  if (pptr() == epptr()) {
    overflowed_ = true;
    return traits_type::eof();
  }
  *pptr() = traits_type::to_char_type(character);
  pbump(1);
  return character;
}

} // namespace csv2_benchmark
