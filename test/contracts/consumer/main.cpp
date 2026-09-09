#include <csv2/reader.hpp>

#include <string>

int main() {
  csv2::Reader<> reader;
  return reader.parse(std::string("a,b")) ? 0 : 1;
}
