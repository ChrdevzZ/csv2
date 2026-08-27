#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

#if CSV2_HAS_RANGES
CSV2_TEST_CASE("reader.ranges.pipe-a-temporary-borrowed-row-view", "reader.ranges") {
  ReaderWithoutHeader reader;
  std::string input("a,bb,ccc");
  CSV2_REQUIRE(reader.parse(input));
  auto sizes = *reader.begin() |
               std::views::transform([](const PublicCell cell) { return cell.raw_size(); });
  CSV2_REQUIRE(std::ranges::equal(sizes, std::vector<std::size_t>({1, 2, 3})));

#if CSV2_HAS_RANGES_TO_CONTAINER
  const auto collected = sizes | std::ranges::to<std::vector<std::size_t>>();
  CSV2_REQUIRE(collected == std::vector<std::size_t>({1, 2, 3}));
#endif
}
#endif
