#include <csv2_test/assertions.hpp>
#include <csv2_test/test_support.hpp>

using namespace csv2_test;

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.report-mmap-errors-and-release-handles-after-mapping-failures",
               "mio.mapping") {
  ReaderWithoutHeader reader;
  std::error_code error = std::make_error_code(std::errc::address_in_use);
  CSV2_REQUIRE(reader.mmap(fixture_path("test_01.csv"), error));
  CSV2_REQUIRE_FALSE(error);

  CSV2_REQUIRE_FALSE(reader.mmap(fixture_path("this-file-does-not-exist.csv"), error));
  CSV2_REQUIRE(error);
  CSV2_REQUIRE(reader.rows() == 0);

  CSV2_REQUIRE_FALSE(reader.mmap(fixture_path("empty.csv"), error));
  CSV2_REQUIRE(error);
#if defined(_WIN32)
  CSV2_REQUIRE(error.value() == ERROR_FILE_INVALID);
#endif

#if defined(__linux__) || defined(_WIN32)
  const std::size_t warmup_handle_count = process_handle_count();
  CSV2_REQUIRE(warmup_handle_count != (std::numeric_limits<std::size_t>::max)());
  const std::size_t handles_before = process_handle_count();
  CSV2_REQUIRE(handles_before != (std::numeric_limits<std::size_t>::max)());
  for (int attempt = 0; attempt < 2048; ++attempt) {
    mio::mmap_source mapping;
    mapping.map(fixture_path("empty.csv"), error);
    CSV2_REQUIRE(error);
#if defined(_WIN32)
    CSV2_REQUIRE(error.value() == ERROR_FILE_INVALID);
#endif
  }
  CSV2_REQUIRE(process_handle_count() == handles_before);
#endif

  mio::mmap_source mapping;
  mapping.map(fixture_path("test_01.csv"), (std::numeric_limits<std::size_t>::max)(), 2, error);
  CSV2_REQUIRE(error);
  CSV2_REQUIRE(error == std::errc::invalid_argument);
  CSV2_REQUIRE(error.category() == std::generic_category());
}
#endif

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.map-a-non-page-aligned-offset-beyond-the-first-page", "mio.mapping") {
  const std::size_t page = mio::page_size();
  CSV2_REQUIRE(page > 0);
  CSV2_REQUIRE(page < (std::numeric_limits<std::size_t>::max)() - 3);

  const std::string path = std::string(writer_output_path()) + ".mmap-offset";
  ScopedFileRemoval cleanup(path);
  std::string contents(page + 3, 'x');
  contents[page + 1] = 'Z';
  {
    std::ofstream output(path.c_str(), std::ios::binary | std::ios::trunc);
    CSV2_REQUIRE(output.is_open());
    output.write(contents.data(), static_cast<std::streamsize>(contents.size()));
    CSV2_REQUIRE(output.good());
  }

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map(path, page + 1, 1, error);
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(mapping.size() == 1);
  CSV2_REQUIRE(mapping[0] == 'Z');
  CSV2_REQUIRE(mapping.mapping_offset() == 1);
  CSV2_REQUIRE(mapping.mapped_length() == 2);
}
#endif

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.preserve-ownership-when-remapping-through-the-mapping-s-own-handle",
               "mio.mapping") {
  const std::string path = std::string(writer_output_path()) + ".mmap-remap-source";
  ScopedFileRemoval cleanup(path);
  write_binary_file(path, "a,b,c\n1,2,3\n4,5,6");

  std::error_code error;
  mio::mmap_source mapping;
  mapping.map(path, error);
  CSV2_REQUIRE_FALSE(error);

  const mio::file_handle_type handle = mapping.file_handle();
  mapping.map(handle, 6, 5, error);
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(std::string(mapping.data(), mapping.size()) == "1,2,3");

#if defined(__unix__) || defined(__APPLE__)
  errno = 0;
  CSV2_REQUIRE(::fcntl(handle, F_GETFD) != -1);
#endif

  mapping.map(handle, 12, 5, error);
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(std::string(mapping.data(), mapping.size()) == "4,5,6");

  mapping.unmap();
#if defined(__unix__) || defined(__APPLE__)
  errno = 0;
  CSV2_REQUIRE(::fcntl(handle, F_GETFD) == -1);
  CSV2_REQUIRE(errno == EBADF);
#endif
}
#endif

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.preserve-ownership-through-shared-and-writable-same-handle-remaps",
               "mio.mapping") {
  const std::string source_path = std::string(writer_output_path()) + ".shared-mmap-remap-source";
  ScopedFileRemoval source_cleanup(source_path);
  write_binary_file(source_path, "a,b,c\n1,2,3\n4,5,6");

  std::error_code error;
  mio::shared_mmap_source shared;
  shared.map(source_path, error);
  CSV2_REQUIRE_FALSE(error);
  const mio::file_handle_type shared_handle = shared.file_handle();
  shared.map(shared_handle, 6, 5, error);
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(std::string(shared.data(), shared.size()) == "1,2,3");
  shared.map(shared_handle, 12, 5, error);
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(std::string(shared.data(), shared.size()) == "4,5,6");
  shared.unmap();

  const std::string path = std::string(writer_output_path()) + ".mmap-sink";
  ScopedFileRemoval cleanup(path);
  {
    std::ofstream output(path.c_str(), std::ios::binary | std::ios::trunc);
    CSV2_REQUIRE(output.is_open());
    output << "abcdef";
    CSV2_REQUIRE(output.good());
  }

  mio::mmap_sink sink;
  sink.map(path, error);
  CSV2_REQUIRE_FALSE(error);
  const mio::file_handle_type sink_handle = sink.file_handle();
  sink.map(sink_handle, 1, 1, error);
  CSV2_REQUIRE_FALSE(error);
  const mio::mmap_sink &const_sink = sink;
  CSV2_REQUIRE(const_sink[0] == 'b');
  sink[0] = 'Z';
  CSV2_REQUIRE(const_sink[0] == 'Z');
  sink.sync(error);
  CSV2_REQUIRE_FALSE(error);
  sink.map(sink_handle, 2, 1, error);
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(const_sink[0] == 'c');
  sink.unmap();

  std::ifstream input(path.c_str(), std::ios::binary);
  std::string persisted((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  CSV2_REQUIRE(persisted == "aZcdef");
}
#endif

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.reject-mapped-paths-containing-an-embedded-nul", "mio.mapping") {
  csv2::Reader<> reader;
  std::string path(fixture_path("test_01.csv"));
  path.push_back('\0');
  path += "ignored-suffix";
  std::error_code error;

  CSV2_REQUIRE_FALSE(reader.mmap(path, error));
  CSV2_REQUIRE(error == std::make_error_code(std::errc::invalid_argument));
}
#endif

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.validate-sized-character-range-paths-before-mapping", "mio.mapping") {
  ReaderWithoutHeader reader;
  std::error_code error;

  std::vector<char> terminated_path;
  const std::string path(fixture_path("test_01.csv"));
  terminated_path.assign(path.begin(), path.end());
  terminated_path.push_back('\0');
  CSV2_REQUIRE(reader.mmap(terminated_path, error));
  CSV2_REQUIRE_FALSE(error);

  std::vector<char> unterminated(path.begin(), path.end());
  CSV2_REQUIRE_FALSE(reader.mmap(unterminated, error));
  CSV2_REQUIRE(error == std::errc::invalid_argument);

  std::vector<char> embedded(terminated_path);
  embedded.insert(embedded.end(), {'x', '\0'});
  CSV2_REQUIRE_FALSE(reader.mmap(embedded, error));
  CSV2_REQUIRE(error == std::errc::invalid_argument);
}
#endif

#if CSV2_HAS_MMAP
#if defined(__unix__) || defined(__APPLE__)
CSV2_TEST_CASE("mio.mapping.map-a-caller-owned-file-handle-without-closing-it", "mio.mapping") {
  const std::string fixture = fixture_path("test_01.csv");
  const int handle = ::open(fixture.c_str(), O_RDONLY);
  CSV2_REQUIRE(handle != -1);
  ReaderWithoutHeader reader;
  std::error_code error;
  CSV2_REQUIRE(reader.mmap(handle, error));
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(reader.rows() > 0);
  reader = ReaderWithoutHeader();
  errno = 0;
  CSV2_REQUIRE(::fcntl(handle, F_GETFD) != -1);
  CSV2_REQUIRE(::close(handle) == 0);
}
#endif
#endif

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.map-a-path-stored-in-the-reader-s-current-owned-source",
               "mio.mapping") {
  const std::string path = std::string(writer_output_path()) + ".owned-mmap-path-source";
  ScopedFileRemoval cleanup(path);
  write_binary_file(path, "mapped,data");

  ReaderWithoutHeader reader;
  CSV2_REQUIRE(reader.parse_owned(path));
  const char *const borrowed_path = reader.header().raw_data();
  CSV2_REQUIRE(reader.mmap(borrowed_path));
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"mapped", "data"}}));
}
#endif

#if CSV2_HAS_MMAP
CSV2_TEST_CASE("mio.mapping.map-a-path-stored-in-the-reader-s-current-mapped-source",
               "mio.mapping") {
  const std::string target_path = std::string(writer_output_path()) + ".mapped-path-target";
  const std::string source_path = std::string(writer_output_path()) + ".mapped-path-source";
  ScopedFileRemoval target_cleanup(target_path);
  ScopedFileRemoval source_cleanup(source_path);
  write_binary_file(target_path, "target,data");
  write_binary_file(source_path, target_path + std::string(1, '\0'));

  ReaderWithoutHeader reader;
  CSV2_REQUIRE(reader.mmap(source_path));
  const char *const borrowed_path = reader.header().raw_data();
  CSV2_REQUIRE(reader.mmap(borrowed_path));
  CSV2_REQUIRE(read_rows(reader) == std::vector<std::vector<std::string>>({{"target", "data"}}));
}
#endif

#if CSV2_HAS_MMAP
#if CSV2_HAS_FILESYSTEM
CSV2_TEST_CASE("mio.mapping.map-a-filesystem-path", "mio.mapping") {
  ReaderWithoutHeader reader;
  std::error_code error;
  CSV2_REQUIRE(reader.mmap(std::filesystem::path(fixture_path("test_01.csv")), error));
  CSV2_REQUIRE_FALSE(error);
  CSV2_REQUIRE(reader.rows() > 0);
}
#endif
#endif
