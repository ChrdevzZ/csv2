#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("reader.source.read-a-file-its-header-rows-columns-and-cells", "reader.source") {
  ReaderWithHeader reader;
  CSV2_REQUIRE(reader.mmap(fixture_path("test_01.csv")));

  CSV2_REQUIRE(read_cells(reader.header()) == std::vector<std::string>({"a", "b", "c"}));
  CSV2_REQUIRE(reader.cols() == 3);
  CSV2_REQUIRE(reader.rows() == 2);
  CSV2_REQUIRE(read_rows(reader) ==
               std::vector<std::vector<std::string>>({{"1", "2", "3"}, {"4", "5", "6"}}));
}
#endif

CSV2_TEST_CASE("reader.source.evaluate-borrowed-string-address-before-its-extent",
               "reader.source") {
  ReaderWithoutHeader reader;
  const std::string input("a,b");
  SequencedStringLikeView view(input);
  CSV2_REQUIRE(reader.parse(view));
  CSV2_REQUIRE(view.sequence_valid);
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"a", "b"}));

  LazyAddressStringLikeView lazy("c,d");
  CSV2_REQUIRE(reader.parse(lazy));
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));
}

CSV2_TEST_CASE("reader.source.materialize-an-owned-string-address-before-its-extent",
               "reader.source") {
  ReaderWithoutHeader reader;
  bool sequence_valid = true;
  CSV2_REQUIRE(reader.parse(SequencedOwnedStringLike("c,d", sequence_valid)));
  CSV2_REQUIRE(sequence_valid);
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));

#if !defined(CSV2_TEST_NO_EXCEPTIONS)
  CSV2_REQUIRE_THROWS_AS(reader.parse(ThrowingOwnedStringLike()), std::runtime_error);
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));

  CSV2_REQUIRE_THROWS(reader.parse(OversizedOwnedStringLike()));
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"c", "d"}));
#endif
}

CSV2_TEST_CASE("reader.source.expose-raw-byte-views-and-explicit-source-ownership",
               "reader.source") {
  const char borrowed[] = "  \"a\"\"b\"  ,tail";
  ReaderWithoutHeader reader;
  CSV2_REQUIRE(reader.parse_borrowed(borrowed, sizeof(borrowed) - 1));

  const auto row = *reader.begin();
  CSV2_REQUIRE(row.raw_data() == borrowed);
  CSV2_REQUIRE(row.raw_size() == sizeof(borrowed) - 1);
  CSV2_REQUIRE(row.address() == row.raw_data());
  CSV2_REQUIRE(row.length() == row.raw_size());

  const auto cell = *row.begin();
  CSV2_REQUIRE(cell.raw_data() == borrowed);
  CSV2_REQUIRE(cell.raw_size() == 10);
  CSV2_REQUIRE(cell.has_escaped_quotes());
#if CSV2_HAS_STRING_VIEW
  CSV2_REQUIRE(cell.raw_trimmed_view() == "\"a\"\"b\"");
#endif

  std::string owned("owned,value");
  CSV2_REQUIRE(reader.parse_owned(owned));
  owned[0] = 'X';
  std::string owned_row;
  (*reader.begin()).read_raw_value(owned_row);
  CSV2_REQUIRE(owned_row == "owned,value");
}

CSV2_TEST_CASE("reader.source.reject-an-owned-alias-range-that-extends-beyond-its-backing-source",
               "reader.source") {
  ReaderWithoutHeader reader;
  const std::string input("owned,value");
  CSV2_REQUIRE(reader.parse_owned(input));
  const char *const source = (*reader.begin()).raw_data();

  CSV2_REQUIRE_FALSE(reader.parse_borrowed(source + 1, input.size()));
  CSV2_REQUIRE(reader.rows() == 0);
}

CSV2_TEST_CASE("reader.source.preserve-owned-storage-when-parse-borrowed-selects-a-cell-range",
               "reader.source") {
  ReaderWithoutHeader reader;
  const std::string first_cell(512, 'b');
  CSV2_REQUIRE(reader.parse_owned(first_cell + ",discarded"));

  const auto cell = *(*reader.begin()).begin();
  const char *const data = cell.raw_data();
  const size_t size = cell.raw_size();
  CSV2_REQUIRE(reader.parse_borrowed(data, size));
  CSV2_REQUIRE((*reader.begin()).raw_data() == data);
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("reader.source.preserve-mapped-storage-when-parse-borrowed-selects-a-cell-range",
               "reader.source") {
  const std::string path = std::string(writer_output_path()) + ".parse-borrowed-mmap-source";
  ScopedFileRemoval cleanup(path);
  const std::string first_cell(512, 'p');
  write_binary_file(path, first_cell + ",discarded");

  ReaderWithoutHeader reader;
  CSV2_REQUIRE(reader.mmap(path));
  const auto cell = *(*reader.begin()).begin();
  const char *const data = cell.raw_data();
  const size_t size = cell.raw_size();
  CSV2_REQUIRE(reader.parse_borrowed(data, size));
  CSV2_REQUIRE((*reader.begin()).raw_data() == data);
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}
#endif

#if CSV2_HAS_SPAN
CSV2_TEST_CASE("reader.source.borrow-a-span-source-without-copying", "reader.source") {
  char bytes[] = {'a', ',', 'b'};
  ReaderWithoutHeader reader;
  CSV2_REQUIRE(reader.parse_borrowed(std::span<const char>(bytes)));
  CSV2_REQUIRE((*reader.begin()).raw_data() == bytes);
  bytes[0] = 'x';
  std::string row;
  (*reader.begin()).read_raw_value(row);
  CSV2_REQUIRE(row == "x,b");
}
#endif

CSV2_TEST_CASE("reader.source.reacquire-cursors-and-indexes-after-same-extent-source-mutation",
               "reader.source") {
  ReaderWithoutHeader reader;
  std::string input("a,b\nc,d");
  CSV2_REQUIRE(reader.parse(input));
  CSV2_REQUIRE(reader.index().size() == 2);

  input[3] = ',';
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"a", "b", "c", "d"}}));
  CSV2_REQUIRE(reader.index().size() == 1);

  input[1] = ';';
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"a;b", "c", "d"}));

  std::string quoted("\"a,b\",c");
  CSV2_REQUIRE(reader.parse(quoted));
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"\"a,b\"", "c"}));
  quoted[0] = 'x';
  quoted[4] = 'x';
  CSV2_REQUIRE(read_cells(*reader.begin()) == std::vector<std::string>({"xa", "bx", "c"}));
  CSV2_REQUIRE(reader.index().size() == 1);
}

CSV2_TEST_CASE("reader.source.own-rvalue-input-borrow-lvalue-input-and-preserve-input-across-moves",
               "reader.source") {
  ReaderWithoutHeader temporary_reader;
  const std::string first_cell(512, 'a');
  const std::string temporary_payload = first_cell + ",b\nc,d";
  CSV2_REQUIRE(temporary_reader.parse(std::string(temporary_payload)));
  std::vector<std::string> heap_churn(512, std::string(temporary_payload.size(), 'x'));
  (void)heap_churn;
  CSV2_REQUIRE(read_rows(temporary_reader) ==
               std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));

  ReaderWithoutHeader borrowed_reader;
  std::string borrowed_input("borrowed,data");
  CSV2_REQUIRE(borrowed_reader.parse(borrowed_input));
  CSV2_REQUIRE((*borrowed_reader.begin()).address() == borrowed_input.c_str());

  ReaderWithoutHeader string_like_reader;
  std::string string_like_input("generic,value");
  CSV2_REQUIRE(string_like_reader.parse(
      StringLikeView(string_like_input.c_str(), string_like_input.size())));
  string_like_input.assign(string_like_input.size(), 'x');
  CSV2_REQUIRE(read_rows(string_like_reader) ==
               std::vector<std::vector<std::string>>({{"generic", "value"}}));

  ReaderWithoutHeader moved(std::move(temporary_reader));
  CSV2_REQUIRE(temporary_reader.rows() == 0);
  CSV2_REQUIRE(read_rows(moved) ==
               std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));

  ReaderWithoutHeader assigned;
  assigned = std::move(moved);
  CSV2_REQUIRE(moved.rows() == 0);
  CSV2_REQUIRE(read_rows(assigned) ==
               std::vector<std::vector<std::string>>({{first_cell, "b"}, {"c", "d"}}));
}

CSV2_TEST_CASE("reader.source.clear-old-input-when-replacing-a-source-or-a-source-fails",
               "reader.source") {
  ReaderWithoutHeader reader;
  CSV2_REQUIRE(reader.parse(std::string("owned,data")));

  std::string borrowed("borrowed,data");
  CSV2_REQUIRE(reader.parse(borrowed));
  CSV2_REQUIRE((*reader.begin()).address() == borrowed.c_str());

  CSV2_REQUIRE_FALSE(reader.parse(std::string()));
  CSV2_REQUIRE(reader.rows() == 0);

#if CSV2_HAS_MMAP
  CSV2_REQUIRE(reader.parse(borrowed));
  CSV2_REQUIRE_FALSE(reader.mmap(fixture_path("this-file-does-not-exist.csv")));
  CSV2_REQUIRE(reader.rows() == 0);

  CSV2_REQUIRE(reader.parse(borrowed));
  CSV2_REQUIRE_FALSE(reader.mmap(fixture_path("empty.csv")));
  CSV2_REQUIRE(reader.rows() == 0);
#endif
}

#if ((defined(_MSVC_LANG) && _MSVC_LANG >= 201703L) || __cplusplus >= 201703L)
CSV2_TEST_CASE("reader.source.borrow-storage-passed-through-parse-view", "reader.source") {
  ReaderWithoutHeader reader;
  std::string input("view,data");
  CSV2_REQUIRE(reader.parse_view(std::string_view(input)));
  CSV2_REQUIRE((*reader.begin()).address() == input.data());
}
#endif

#if ((defined(_MSVC_LANG) && _MSVC_LANG >= 201703L) || __cplusplus >= 201703L)
CSV2_TEST_CASE("reader.source.preserve-a-complete-owned-source-when-parse-view-aliases-it",
               "reader.source") {
  ReaderWithoutHeader reader;
  const std::string first_cell(512, 'f');
  const std::string input = first_cell + ",second\nthird,fourth";
  CSV2_REQUIRE(reader.parse(std::string(input)));

  const char *const source_address = (*reader.begin()).address();
  CSV2_REQUIRE(reader.parse_view(std::string_view(source_address, input.size())));
  CSV2_REQUIRE((*reader.begin()).address() == source_address);
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>(
                                        {{first_cell, "second"}, {"third", "fourth"}}));
}
#endif

#if ((defined(_MSVC_LANG) && _MSVC_LANG >= 201703L) || __cplusplus >= 201703L)
CSV2_TEST_CASE("reader.source.preserve-owned-storage-when-parse-view-selects-a-cell-subview",
               "reader.source") {
  ReaderWithoutHeader reader;
  const std::string first_cell(512, 'a');
  CSV2_REQUIRE(reader.parse(std::string(first_cell + ",discarded")));

  const std::string_view view = (*(*reader.begin()).begin()).read_view();
  CSV2_REQUIRE(reader.parse_view(view));
  CSV2_REQUIRE((*reader.begin()).address() == view.data());
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}
#endif

#if ((defined(_MSVC_LANG) && _MSVC_LANG >= 201703L) || __cplusplus >= 201703L)
#if CSV2_HAS_MMAP
CSV2_TEST_CASE("reader.source.preserve-mapped-storage-when-parse-view-selects-a-cell-subview",
               "reader.source") {
  const std::string path = std::string(writer_output_path()) + ".parse-view-mmap-source";
  ScopedFileRemoval cleanup(path);
  const std::string first_cell(512, 'm');
  write_binary_file(path, first_cell + ",discarded");

  ReaderWithoutHeader reader;
  CSV2_REQUIRE(reader.mmap(path));
  const std::string_view view = (*(*reader.begin()).begin()).read_view();
  CSV2_REQUIRE(reader.parse_view(view));
  CSV2_REQUIRE((*reader.begin()).address() == view.data());
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{first_cell}}));
}
#endif
#endif

#if ((defined(_MSVC_LANG) && _MSVC_LANG >= 201703L) || __cplusplus >= 201703L)
CSV2_TEST_CASE(
    "reader.source.preserve-destination-owned-storage-when-move-assigning-a-view-borrower",
    "reader.source") {
  ReaderWithoutHeader owner;
  const std::string first_cell(512, 'o');
  CSV2_REQUIRE(owner.parse(std::string(first_cell + ",discarded")));
  const std::string_view view = (*(*owner.begin()).begin()).read_view();

  ReaderWithoutHeader borrower;
  CSV2_REQUIRE(borrower.parse_view(view));
  owner = std::move(borrower);

  CSV2_REQUIRE(borrower.rows() == 0);
  CSV2_REQUIRE((*owner.begin()).address() == view.data());
  CSV2_REQUIRE(read_rows(owner) == std::vector<std::vector<std::string>>({{first_cell}}));
}
#endif
