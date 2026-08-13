#include "../registry.hpp"

#if CSV2_HAS_MMAP
#include <csv2/mio.hpp>
#endif

#include <fstream>
#include <iterator>
#include <string>
#include <system_error>
#include <cerrno>

#if CSV2_HAS_SPAN
#include <span>
#endif

namespace csv2_benchmark {
namespace {

template <bool Verify> Result file_read(Context &context, Source, TimedObserver &observer) {
  Result result;
  errno = 0;
  std::ifstream input(context.input_path().c_str(), std::ios::binary);
  if (!input) {
    fail(result, KernelStatus::input_open_failed, errno);
    return result;
  }
  if (context.input_read_failure_for_test())
    input.setstate(std::ios::badbit);
  std::string bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  if (!input.eof() && input.fail()) {
    fail(result, KernelStatus::input_read_failed, errno);
    return result;
  }
  if (bytes.size() != context.input_size()) {
    fail(result, KernelStatus::input_changed);
    return result;
  }
  result.bytes = static_cast<std::uint64_t>(bytes.size());
  if (Verify)
    mix_bytes(result, bytes.data(), bytes.size());
  else {
    observer.memory(bytes);
    observe_result(observer, result);
  }
  return result;
}

template <bool Verify> Result mmap_open(Context &context, Source, TimedObserver &observer) {
  Result result;
#if CSV2_HAS_MMAP
  std::error_code error;
  mio::mmap_source mapping = mio::make_mmap_source(context.input_path(), error);
  if (!error && !mapping.empty()) {
    result.bytes = static_cast<std::uint64_t>(mapping.size());
    if (Verify)
      mix(result, result.bytes);
  } else
    fail(result, KernelStatus::mmap_failed, error.value());
  if constexpr (!Verify) {
    int error_value = error.value();
    observer.value(error_value);
    observe_result(observer, result);
  }
#else
  (void)context;
  (void)observer;
#endif
  return result;
}

template <bool Verify> Result mmap_touch(Context &context, Source, TimedObserver &observer) {
  Result result;
#if CSV2_HAS_MMAP
  if (context.mmap_ready()) {
    result.bytes = static_cast<std::uint64_t>(context.mapped_size());
    volatile unsigned char sink = 0;
    const std::size_t stride = 4096;
    for (std::size_t index = 0; index < context.mapped_size(); index += stride)
      sink = static_cast<unsigned char>(sink ^
                                        static_cast<unsigned char>(context.mapped_data()[index]));
    if (context.mapped_size())
      sink = static_cast<unsigned char>(
          sink ^ static_cast<unsigned char>(context.mapped_data()[context.mapped_size() - 1]));
    if (Verify)
      mix(result, sink);
    else {
      unsigned char observed_sink = sink;
      observer.value(observed_sink);
      observe_result(observer, result);
    }
  } else
    fail(result, KernelStatus::mmap_failed);
#else
  (void)context;
  (void)observer;
#endif
  return result;
}

template <bool Verify> Result parse_borrowed(Context &context, Source, TimedObserver &observer) {
  BenchmarkReader reader;
  Result result;
  bool parsed = reader.parse_borrowed(context.data().data(), context.data().size());
  if (parsed) {
    result.bytes = static_cast<std::uint64_t>(context.input_size());
    if (Verify)
      mix(result, result.bytes);
  } else
    fail(result, KernelStatus::parse_failed);
  if constexpr (!Verify) {
    observer.value(parsed);
    observer.value(reader);
    observe_result(observer, result);
  }
  return result;
}

template <bool Verify> Result parse_owned(Context &context, Source, TimedObserver &observer) {
  BenchmarkReader reader;
  Result result;
  bool parsed = reader.parse_owned(context.data());
  if (parsed) {
    result.bytes = static_cast<std::uint64_t>(context.input_size());
    if (Verify)
      mix(result, result.bytes);
  } else
    fail(result, KernelStatus::parse_failed);
  if constexpr (!Verify) {
    observer.value(parsed);
    observer.value(reader);
    observe_result(observer, result);
  }
  return result;
}

#if CSV2_HAS_SPAN
template <bool Verify> Result parse_span(Context &context, Source, TimedObserver &observer) {
  BenchmarkReader reader;
  const std::span<const char> bytes(context.data().data(), context.data().size());
  Result result;
  bool parsed = reader.parse_borrowed(bytes);
  if (parsed) {
    result.bytes = static_cast<std::uint64_t>(bytes.size());
    if (Verify)
      mix(result, result.bytes);
  } else
    fail(result, KernelStatus::parse_failed);
  if constexpr (!Verify) {
    observer.value(parsed);
    observer.value(reader);
    observe_result(observer, result);
  }
  return result;
}
#endif

} // namespace

void register_source_operations(Registry &registry) {
  registry.add("source/file-read", source_file, file_read<false>, file_read<true>);
#if CSV2_HAS_MMAP
  registry.add("source/mmap-open", source_mmap, mmap_open<false>, mmap_open<true>);
  registry.add("source/mmap-touch", source_mmap, mmap_touch<false>, mmap_touch<true>);
#endif
  registry.add("source/parse-borrowed", source_buffer, parse_borrowed<false>, parse_borrowed<true>,
               true);
  registry.add("source/parse-owned", source_buffer, parse_owned<false>, parse_owned<true>);
#if CSV2_HAS_SPAN
  registry.add("source/parse-span", source_buffer, parse_span<false>, parse_span<true>, true);
#endif
}

} // namespace csv2_benchmark
