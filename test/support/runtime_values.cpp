#include <csv2_test/string_like.hpp>

namespace csv2_test {

std::size_t oversized_owned_string_size() { return (std::numeric_limits<std::size_t>::max)(); }

} // namespace csv2_test
