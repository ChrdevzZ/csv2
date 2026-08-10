#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#endif

#include <string>
#include <system_error>
#include <vector>

namespace {

class NoExceptionCloseStream {
public:
  template <typename Value> NoExceptionCloseStream &operator<<(const Value &) { return *this; }
  void close() { ++close_count; }

  int close_count{0};
};

} // namespace

int main(int argc, char **argv) {
  NoExceptionCloseStream stream;
  {
    csv2::Writer<csv2::delimiter<','>, NoExceptionCloseStream> writer(stream);
    writer.write_row(std::vector<std::string>());
  }
  if (stream.close_count != 1)
    return 1;

#if CSV2_HAS_MMAP
  if (argc != 2)
    return 2;

  csv2::Reader<> reader;
  if (reader.mmap(argv[1]))
    return 3;

  std::error_code error;
  if (reader.mmap(argv[1], error))
    return 4;
  return error ? 0 : 5;
#else
  (void)argc;
  (void)argv;
  return 0;
#endif
}
