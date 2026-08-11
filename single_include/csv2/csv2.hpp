#pragma once

#include <cstring>
// #include <csv2/detail/config.hpp>

// Normalize the language mode. MSVC reports its selected standard through
// _MSVC_LANG unless /Zc:__cplusplus is enabled.
#if defined(_MSVC_LANG)
#define CSV2_CPLUSPLUS _MSVC_LANG
#else
#define CSV2_CPLUSPLUS __cplusplus
#endif

#if defined(__has_include)
#if __has_include(<version>)
#include <version>
#endif
#endif

#if defined(__has_cpp_attribute)
#if CSV2_CPLUSPLUS >= 201703L && __has_cpp_attribute(nodiscard)
#define CSV2_NODISCARD [[nodiscard]]
#else
#define CSV2_NODISCARD
#endif
#else
#define CSV2_NODISCARD
#endif

#if CSV2_CPLUSPLUS >= 201402L
#define CSV2_CONSTEXPR14 constexpr
#else
#define CSV2_CONSTEXPR14
#endif

#if CSV2_CPLUSPLUS >= 201703L
#define CSV2_CONSTEXPR17 constexpr
#else
#define CSV2_CONSTEXPR17
#endif

#if defined(__cpp_lib_string_view) && __cpp_lib_string_view >= 201606L
#define CSV2_HAS_STRING_VIEW 1
#else
#define CSV2_HAS_STRING_VIEW 0
#endif

#if defined(__cpp_lib_filesystem) && __cpp_lib_filesystem >= 201703L
#define CSV2_HAS_FILESYSTEM 1
#else
#define CSV2_HAS_FILESYSTEM 0
#endif

#if defined(__cpp_lib_to_chars) && __cpp_lib_to_chars >= 201611L
#define CSV2_HAS_CHARCONV 1
#else
#define CSV2_HAS_CHARCONV 0
#endif

#if defined(__cpp_lib_memory_resource) && __cpp_lib_memory_resource >= 201603L
#define CSV2_HAS_MEMORY_RESOURCE 1
#else
#define CSV2_HAS_MEMORY_RESOURCE 0
#endif

#if defined(__cpp_lib_span) && __cpp_lib_span >= 202002L
#define CSV2_HAS_SPAN 1
#else
#define CSV2_HAS_SPAN 0
#endif

#if defined(__cpp_lib_ranges) && __cpp_lib_ranges >= 201911L
#define CSV2_HAS_RANGES 1
#else
#define CSV2_HAS_RANGES 0
#endif

#if defined(__cpp_lib_expected) && __cpp_lib_expected >= 202202L
#define CSV2_HAS_EXPECTED 1
#else
#define CSV2_HAS_EXPECTED 0
#endif

#if defined(__cpp_lib_ranges_to_container) && __cpp_lib_ranges_to_container >= 202202L
#define CSV2_HAS_RANGES_TO_CONTAINER 1
#else
#define CSV2_HAS_RANGES_TO_CONTAINER 0
#endif

#ifndef CSV2_HAS_MMAP
#if defined(__has_include)
#if defined(_WIN32)
#if __has_include(<windows.h>)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#elif __has_include(<sys/mman.h>)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#elif defined(_WIN32) || defined(__unix__) || defined(__unix) || defined(__APPLE__)
#define CSV2_HAS_MMAP 1
#else
#define CSV2_HAS_MMAP 0
#endif
#endif

// #include <csv2/detail/output.hpp>

#include <cstddef>
#include <iterator>

namespace csv2 {
namespace detail {

template <unsigned Priority> struct output_priority : output_priority<Priority - 1> {};
template <> struct output_priority<0> {};

template <typename Container>
auto reserve_for_append_impl(Container &output, std::size_t additional, output_priority<2>)
    -> decltype(output.reserve(output.size() + additional), void()) {
  output.reserve(output.size() + additional);
}

template <typename Container>
auto reserve_for_append_impl(Container &output, std::size_t additional, output_priority<1>)
    -> decltype(output.reserve(additional), void()) {
  output.reserve(additional);
}

template <typename Container>
void reserve_for_append_impl(Container &, std::size_t, output_priority<0>) {}

template <typename Container>
void reserve_for_append(Container &output, std::size_t additional) {
  reserve_for_append_impl(output, additional, output_priority<2>());
}

template <typename Container>
auto append_range_impl(Container &output, const char *first, const char *last,
                       output_priority<3>)
    -> decltype(output.append(first, static_cast<std::size_t>(last - first)), void()) {
  output.append(first, static_cast<std::size_t>(last - first));
}

template <typename Container>
auto append_range_impl(Container &output, const char *first, const char *last,
                       output_priority<2>)
    -> decltype(output.insert(output.end(), first, last), void()) {
  output.insert(output.end(), first, last);
}

template <typename Container>
auto append_range_impl(Container &output, const char *first, const char *last,
                       output_priority<1>) -> decltype(output.push_back(*first), void()) {
  while (first != last) {
    output.push_back(*first);
    ++first;
  }
}

template <typename Container>
void append_range(Container &output, const char *first, const char *last) {
  append_range_impl(output, first, last, output_priority<3>());
}

template <typename Container> class container_output_iterator {
public:
  using iterator_category = std::output_iterator_tag;
  using value_type = void;
  using difference_type = void;
  using pointer = void;
  using reference = void;

  explicit container_output_iterator(Container &output) : output_(&output) {}

  container_output_iterator &operator=(char value) {
    append_range(*output_, &value, &value + 1);
    return *this;
  }
  container_output_iterator &operator*() { return *this; }
  container_output_iterator &operator++() { return *this; }
  container_output_iterator operator++(int) { return *this; }

private:
  Container *output_;
};

template <typename Container>
container_output_iterator<Container> container_inserter(Container &output) {
  return container_output_iterator<Container>(output);
}

template <typename OutputIt>
OutputIt copy_chars(const char *first, const char *last, OutputIt output) {
  while (first != last) {
    *output = *first;
    ++output;
    ++first;
  }
  return output;
}

} // namespace detail
} // namespace csv2


#if CSV2_HAS_MMAP
// #include <csv2/mio.hpp>
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_MMAP_HEADER
#define MIO_MMAP_HEADER

// #include "mio/page.hpp"
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_PAGE_HEADER
#define MIO_PAGE_HEADER

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace mio {

/**
 * This is used by `basic_mmap` to determine whether to create a read-only or
 * a read-write memory mapping.
 */
enum class access_mode { read, write };

/**
 * Determines the operating system's page allocation granularity.
 *
 * On the first call to this function, it invokes the operating system specific syscall
 * to determine the page size, caches the value, and returns it. Any subsequent call to
 * this function serves the cached value, so no further syscalls are made.
 */
inline size_t page_size() {
  static const size_t page_size = [] {
#ifdef _WIN32
    SYSTEM_INFO SystemInfo;
    GetSystemInfo(&SystemInfo);
    return SystemInfo.dwAllocationGranularity;
#else
    return sysconf(_SC_PAGE_SIZE);
#endif
  }();
  return page_size;
}

/**
 * Alligns `offset` to the operating's system page size such that it subtracts the
 * difference until the nearest page boundary before `offset`, or does nothing if
 * `offset` is already page aligned.
 */
inline size_t make_offset_page_aligned(size_t offset) noexcept {
  const size_t page_size_ = page_size();
  // Use integer division to round down to the nearest page alignment.
  return offset / page_size_ * page_size_;
}

} // namespace mio

#endif // MIO_PAGE_HEADER

#include <cstdint>
#include <iterator>
#include <limits>
#include <string>
#include <system_error>
// #include <csv2/detail/config.hpp>
#if CSV2_HAS_FILESYSTEM
#include <filesystem>
#endif

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif // WIN32_LEAN_AND_MEAN
#include <windows.h>
#else // ifdef _WIN32
#define INVALID_HANDLE_VALUE -1
#endif // ifdef _WIN32

namespace mio {

// This value may be provided as the `length` parameter to the constructor or
// `map`, in which case a memory mapping of the entire file is created.
enum { map_entire_file = 0 };

#ifdef _WIN32
using file_handle_type = HANDLE;
#else
using file_handle_type = int;
#endif

// This value represents an invalid file handle type. This can be used to
// determine whether `basic_mmap::file_handle` is valid, for example.
const static file_handle_type invalid_handle = INVALID_HANDLE_VALUE;

// Windows file-mapping APIs use nullptr rather than INVALID_HANDLE_VALUE.
#ifdef _WIN32
const static file_handle_type invalid_mapping_handle = nullptr;
#else
const static file_handle_type invalid_mapping_handle = invalid_handle;
#endif

template <access_mode AccessMode, typename ByteT> struct basic_mmap {
  using value_type = ByteT;
  using size_type = size_t;
  using reference = value_type &;
  using const_reference = const value_type &;
  using pointer = value_type *;
  using const_pointer = const value_type *;
  using difference_type = std::ptrdiff_t;
  using iterator = pointer;
  using const_iterator = const_pointer;
  using reverse_iterator = std::reverse_iterator<iterator>;
  using const_reverse_iterator = std::reverse_iterator<const_iterator>;
  using iterator_category = std::random_access_iterator_tag;
  using handle_type = file_handle_type;

  static_assert(sizeof(ByteT) == sizeof(char), "ByteT must be the same size as char.");

private:
  // Points to the first requested byte, and not to the actual start of the mapping.
  pointer data_ = nullptr;

  // Length--in bytes--requested by user (which may not be the length of the
  // full mapping) and the length of the full mapping.
  size_type length_ = 0;
  size_type mapped_length_ = 0;

  // Letting user map a file using both an existing file handle and a path
  // introcudes some complexity (see `is_handle_internal_`).
  // On POSIX, we only need a file handle to create a mapping, while on
  // Windows systems the file handle is necessary to retrieve a file mapping
  // handle, but any subsequent operations on the mapped region must be done
  // through the latter.
  handle_type file_handle_ = INVALID_HANDLE_VALUE;
#ifdef _WIN32
  handle_type file_mapping_handle_ = invalid_mapping_handle;
#endif

  // Letting user map a file using both an existing file handle and a path
  // introcudes some complexity in that we must not close the file handle if
  // user provided it, but we must close it if we obtained it using the
  // provided path. For this reason, this flag is used to determine when to
  // close `file_handle_`.
  bool is_handle_internal_ = false;

public:
  /**
   * The default constructed mmap object is in a non-mapped state, that is,
   * any operation that attempts to access nonexistent underlying data will
   * result in undefined behaviour/segmentation faults.
   */
  basic_mmap() = default;

#ifdef __cpp_exceptions
  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  template <typename String>
  basic_mmap(const String &path, const size_type offset = 0,
             const size_type length = map_entire_file) {
    std::error_code error;
    map(path, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }

  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  basic_mmap(const handle_type handle, const size_type offset = 0,
             const size_type length = map_entire_file) {
    std::error_code error;
    map(handle, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }
#endif // __cpp_exceptions

  /**
   * `basic_mmap` has single-ownership semantics, so transferring ownership
   * may only be accomplished by moving the object.
   */
  basic_mmap(const basic_mmap &) = delete;
  basic_mmap(basic_mmap &&);
  basic_mmap &operator=(const basic_mmap &) = delete;
  basic_mmap &operator=(basic_mmap &&);

  /**
   * If this is a read-write mapping, the destructor invokes sync. Regardless
   * of the access mode, unmap is invoked as a final step.
   */
  ~basic_mmap();

  /**
   * On UNIX systems 'file_handle' and 'mapping_handle' are the same. On Windows,
   * however, a mapped region of a file gets its own handle, which is returned by
   * 'mapping_handle'.
   */
  handle_type file_handle() const noexcept { return file_handle_; }
  handle_type mapping_handle() const noexcept;

  /** Returns whether a valid memory mapping has been created. */
  bool is_open() const noexcept { return file_handle_ != invalid_handle; }

  /**
   * Returns true if no mapping was established, that is, conceptually the
   * same as though the length that was mapped was 0. This function is
   * provided so that this class has Container semantics.
   */
  bool empty() const noexcept { return length() == 0; }

  /** Returns true if a mapping was established. */
  bool is_mapped() const noexcept;

  /**
   * `size` and `length` both return the logical length, i.e. the number of bytes
   * user requested to be mapped, while `mapped_length` returns the actual number of
   * bytes that were mapped which is a multiple of the underlying operating system's
   * page allocation granularity.
   */
  size_type size() const noexcept { return length(); }
  size_type length() const noexcept { return length_; }
  size_type mapped_length() const noexcept { return mapped_length_; }

  /** Returns the offset relative to the start of the mapping. */
  size_type mapping_offset() const noexcept { return mapped_length_ - length_; }

  /**
   * Returns a pointer to the first requested byte, or `nullptr` if no memory mapping
   * exists.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  pointer data() noexcept {
    return data_;
  }
  const_pointer data() const noexcept { return data_; }

  /**
   * Returns an iterator to the first requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  iterator begin() noexcept {
    return data();
  }
  const_iterator begin() const noexcept { return data(); }
  const_iterator cbegin() const noexcept { return data(); }

  /**
   * Returns an iterator one past the last requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  iterator end() noexcept {
    return data() + length();
  }
  const_iterator end() const noexcept { return data() + length(); }
  const_iterator cend() const noexcept { return data() + length(); }

  /**
   * Returns a reverse iterator to the last memory mapped byte, if a valid
   * memory mapping exists, otherwise this function call is undefined
   * behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rbegin() noexcept {
    return reverse_iterator(end());
  }
  const_reverse_iterator rbegin() const noexcept { return const_reverse_iterator(end()); }
  const_reverse_iterator crbegin() const noexcept { return const_reverse_iterator(end()); }

  /**
   * Returns a reverse iterator past the first mapped byte, if a valid memory
   * mapping exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rend() noexcept {
    return reverse_iterator(begin());
  }
  const_reverse_iterator rend() const noexcept { return const_reverse_iterator(begin()); }
  const_reverse_iterator crend() const noexcept { return const_reverse_iterator(begin()); }

  /**
   * Returns a reference to the `i`th byte from the first requested byte (as returned
   * by `data`). If this is invoked when no valid memory mapping has been created
   * prior to this call, undefined behaviour ensues.
   */
  reference operator[](const size_type i) noexcept { return data_[i]; }
  const_reference operator[](const size_type i) const noexcept { return data_[i]; }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  template <typename String>
  void map(const String &path, const size_type offset, const size_type length,
           std::error_code &error);

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  template <typename String> void map(const String &path, std::error_code &error) {
    map(path, 0, map_entire_file, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is
   * unsuccesful, the reason is reported via `error` and the object remains in
   * a state as if this function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  void map(const handle_type handle, const size_type offset, const size_type length,
           std::error_code &error);

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is
   * unsuccesful, the reason is reported via `error` and the object remains in
   * a state as if this function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  void map(const handle_type handle, std::error_code &error) {
    map(handle, 0, map_entire_file, error);
  }

  /**
   * If a valid memory mapping has been created prior to this call, this call
   * instructs the kernel to unmap the memory region and disassociate this object
   * from the file.
   *
   * The file handle associated with the file that is mapped is only closed if the
   * mapping was created using a file path. If, on the other hand, an existing
   * file handle was used to create the mapping, the file handle is not closed.
   */
  void unmap();

  void swap(basic_mmap &other);

  /** Flushes the memory mapped page to disk. Errors are reported via `error`. */
  template <access_mode A = AccessMode>
  typename std::enable_if<A == access_mode::write, void>::type sync(std::error_code &error);

  /**
   * All operators compare the address of the first byte and size of the two mapped
   * regions.
   */

private:
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  pointer get_mapping_start() noexcept {
    return !data() ? nullptr : data() - mapping_offset();
  }

  const_pointer get_mapping_start() const noexcept {
    return !data() ? nullptr : data() - mapping_offset();
  }

  /**
   * The destructor syncs changes to disk if `AccessMode` is `write`, but not
   * if it's `read`, but since the destructor cannot be templated, we need to
   * do SFINAE in a dedicated function, where one syncs and the other is a noop.
   */
  template <access_mode A = AccessMode>
  typename std::enable_if<A == access_mode::write, void>::type conditional_sync();
  template <access_mode A = AccessMode>
  typename std::enable_if<A == access_mode::read, void>::type conditional_sync();
};

template <access_mode AccessMode, typename ByteT>
bool operator==(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator!=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator<(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator<=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator>(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

template <access_mode AccessMode, typename ByteT>
bool operator>=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b);

/**
 * This is the basis for all read-only mmap objects and should be preferred over
 * directly using `basic_mmap`.
 */
template <typename ByteT> using basic_mmap_source = basic_mmap<access_mode::read, ByteT>;

/**
 * This is the basis for all read-write mmap objects and should be preferred over
 * directly using `basic_mmap`.
 */
template <typename ByteT> using basic_mmap_sink = basic_mmap<access_mode::write, ByteT>;

/**
 * These aliases cover the most common use cases, both representing a raw byte stream
 * (either with a char or an unsigned char/uint8_t).
 */
using mmap_source = basic_mmap_source<char>;
using ummap_source = basic_mmap_source<unsigned char>;

using mmap_sink = basic_mmap_sink<char>;
using ummap_sink = basic_mmap_sink<unsigned char>;

/**
 * Convenience factory method that constructs a mapping for any `basic_mmap` or
 * `basic_mmap` type.
 */
template <typename MMap, typename MappingToken>
MMap make_mmap(const MappingToken &token, int64_t offset, int64_t length, std::error_code &error) {
  MMap mmap;
  mmap.map(token, offset, length, error);
  return mmap;
}

/**
 * Convenience factory method.
 *
 * MappingToken may be a supported NUL-terminated path (`std::string`, `const char*`,
 * and, in C++17, `std::filesystem::path`) or a `mmap_source::handle_type`.
 */
template <typename MappingToken>
mmap_source make_mmap_source(const MappingToken &token, mmap_source::size_type offset,
                             mmap_source::size_type length, std::error_code &error) {
  return make_mmap<mmap_source>(token, offset, length, error);
}

template <typename MappingToken>
mmap_source make_mmap_source(const MappingToken &token, std::error_code &error) {
  return make_mmap_source(token, 0, map_entire_file, error);
}

/**
 * Convenience factory method.
 *
 * MappingToken may be a supported NUL-terminated path (`std::string`, `const char*`,
 * and, in C++17, `std::filesystem::path`) or a `mmap_sink::handle_type`.
 */
template <typename MappingToken>
mmap_sink make_mmap_sink(const MappingToken &token, mmap_sink::size_type offset,
                         mmap_sink::size_type length, std::error_code &error) {
  return make_mmap<mmap_sink>(token, offset, length, error);
}

template <typename MappingToken>
mmap_sink make_mmap_sink(const MappingToken &token, std::error_code &error) {
  return make_mmap_sink(token, 0, map_entire_file, error);
}

} // namespace mio

// #include "detail/mmap.ipp"
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_BASIC_MMAP_IMPL
#define MIO_BASIC_MMAP_IMPL

// #include "mio/mmap.hpp"

// #include "mio/page.hpp"

// #include "mio/detail/string_util.hpp"
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_STRING_UTIL_HEADER
#define MIO_STRING_UTIL_HEADER

#include <type_traits>

namespace mio {
namespace detail {

template <typename S, typename C = typename std::decay<S>::type,
          typename = decltype(std::declval<C>().data()),
          typename = typename std::enable_if<std::is_same<typename C::value_type, char>::value
#ifdef _WIN32
                                             || std::is_same<typename C::value_type, wchar_t>::value
#endif
                                             >::type>
struct char_type_helper {
  using type = typename C::value_type;
};

template <class T> struct char_type { using type = typename char_type_helper<T>::type; };

// TODO: can we avoid this brute force approach?
template <> struct char_type<char *> { using type = char; };

template <> struct char_type<const char *> { using type = char; };

template <size_t N> struct char_type<char[N]> { using type = char; };

template <size_t N> struct char_type<const char[N]> { using type = char; };

#ifdef _WIN32
template <> struct char_type<wchar_t *> { using type = wchar_t; };

template <> struct char_type<const wchar_t *> { using type = wchar_t; };

template <size_t N> struct char_type<wchar_t[N]> { using type = wchar_t; };

template <size_t N> struct char_type<const wchar_t[N]> { using type = wchar_t; };
#endif // _WIN32

template <typename CharT, typename S> struct is_c_str_helper {
  static constexpr bool value =
      std::is_same<CharT *,
                   // TODO: I'm so sorry for this... Can this be made cleaner?
                   typename std::add_pointer<typename std::remove_cv<typename std::remove_pointer<
                       typename std::decay<S>::type>::type>::type>::type>::value;
};

template <typename S> struct is_c_str {
  static constexpr bool value = is_c_str_helper<char, S>::value;
};

#ifdef _WIN32
template <typename S> struct is_c_wstr {
  static constexpr bool value = is_c_str_helper<wchar_t, S>::value;
};
#endif // _WIN32

template <typename S> struct is_c_str_or_c_wstr {
  static constexpr bool value = is_c_str<S>::value
#ifdef _WIN32
                                || is_c_wstr<S>::value
#endif
      ;
};

template <typename S> struct is_object_path {
  using type = typename std::decay<S>::type;
  static constexpr bool value = std::is_same<type, std::string>::value
#ifdef _WIN32
                                || std::is_same<type, std::wstring>::value
#endif
#if CSV2_HAS_FILESYSTEM
                                || std::is_same<type, std::filesystem::path>::value
#endif
      ;
};

template <typename S> struct is_path {
  static constexpr bool value = is_c_str_or_c_wstr<S>::value || is_object_path<S>::value;
};

#if CSV2_HAS_FILESYSTEM
template <> struct char_type<std::filesystem::path> {
  using type = std::filesystem::path::value_type;
};
#endif

template <typename String,
          typename = typename std::enable_if<is_object_path<String>::value>::type>
auto c_str(const String &path) -> decltype(path.c_str()) {
  return path.c_str();
}

template <typename String,
          typename = typename std::enable_if<is_object_path<String>::value>::type>
bool empty(const String &path) {
  return path.empty();
}

template <typename String,
          typename = typename std::enable_if<is_c_str_or_c_wstr<String>::value>::type>
const typename char_type<String>::type *c_str(String path) {
  return path;
}

template <typename String,
          typename = typename std::enable_if<is_c_str_or_c_wstr<String>::value>::type>
bool empty(String path) {
  return !path || (*path == 0);
}

template <typename CharT, typename Traits, typename Allocator>
size_t path_size(const std::basic_string<CharT, Traits, Allocator> &path) {
  return path.size();
}

#if CSV2_HAS_FILESYSTEM
inline size_t path_size(const std::filesystem::path &path) { return path.native().size(); }
#endif

template <typename String,
          typename = typename std::enable_if<is_object_path<String>::value>::type>
bool has_embedded_null(const String &path) {
  typedef typename char_type<String>::type char_type;
  return std::char_traits<char_type>::length(c_str(path)) != path_size(path);
}

template <typename String,
          typename = typename std::enable_if<is_c_str_or_c_wstr<String>::value>::type>
bool has_embedded_null(String) {
  return false;
}

} // namespace detail
} // namespace mio

#endif // MIO_STRING_UTIL_HEADER

#include <algorithm>

#ifndef _WIN32
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace mio {
namespace detail {

#ifdef _WIN32
namespace win {

/** Returns the 4 upper bytes of an 8-byte integer. */
inline DWORD int64_high(int64_t n) noexcept { return n >> 32; }

/** Returns the 4 lower bytes of an 8-byte integer. */
inline DWORD int64_low(int64_t n) noexcept { return n & 0xffffffff; }

template <typename String, typename = typename std::enable_if<
                               std::is_same<typename char_type<String>::type, char>::value>::type>
file_handle_type open_file_helper(const String &path, const access_mode mode) {
  return ::CreateFileA(
      c_str(path), mode == access_mode::read ? GENERIC_READ : GENERIC_READ | GENERIC_WRITE,
      FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
}

template <typename String>
typename std::enable_if<std::is_same<typename char_type<String>::type, wchar_t>::value,
                        file_handle_type>::type
open_file_helper(const String &path, const access_mode mode) {
  return ::CreateFileW(
      c_str(path), mode == access_mode::read ? GENERIC_READ : GENERIC_READ | GENERIC_WRITE,
      FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
}

} // namespace win
#endif // _WIN32

/**
 * Returns the last platform specific system error (errno on POSIX and
 * GetLastError on Win) as a `std::error_code`.
 */
inline std::error_code last_error() noexcept {
  std::error_code error;
#ifdef _WIN32
  error.assign(GetLastError(), std::system_category());
#else
  error.assign(errno, std::system_category());
#endif
  return error;
}

template <typename String>
file_handle_type open_file(const String &path, const access_mode mode, std::error_code &error) {
  error.clear();
  if (detail::empty(path) || detail::has_embedded_null(path)) {
    error = std::make_error_code(std::errc::invalid_argument);
    return invalid_handle;
  }
#ifdef _WIN32
  const auto handle = win::open_file_helper(path, mode);
#else // POSIX
  const auto handle = ::open(c_str(path), mode == access_mode::read ? O_RDONLY : O_RDWR);
#endif
  if (handle == invalid_handle) {
    error = detail::last_error();
  }
  return handle;
}

inline void close_file(const file_handle_type handle) noexcept {
  if (handle == invalid_handle)
    return;
#ifdef _WIN32
  ::CloseHandle(handle);
#else
  ::close(handle);
#endif
}

class file_handle_guard {
public:
  explicit file_handle_guard(const file_handle_type handle) noexcept : handle_(handle) {}
  ~file_handle_guard() { close_file(handle_); }

  file_handle_guard(const file_handle_guard &) = delete;
  file_handle_guard &operator=(const file_handle_guard &) = delete;

  void release() noexcept { handle_ = invalid_handle; }

private:
  file_handle_type handle_;
};

inline size_t query_file_size(file_handle_type handle, std::error_code &error) {
  error.clear();
#ifdef _WIN32
  LARGE_INTEGER file_size;
  if (::GetFileSizeEx(handle, &file_size) == 0) {
    error = detail::last_error();
    return 0;
  }
  const int64_t file_size_value = file_size.QuadPart;
#else // POSIX
  struct stat sbuf;
  if (::fstat(handle, &sbuf) == -1) {
    error = detail::last_error();
    return 0;
  }
  const int64_t file_size_value = sbuf.st_size;
#endif
  if (file_size_value < 0 ||
      static_cast<std::uintmax_t>(file_size_value) > (std::numeric_limits<size_t>::max)()) {
    error = std::make_error_code(std::errc::value_too_large);
    return 0;
  }
  return static_cast<size_t>(file_size_value);
}

struct mmap_context {
  char *data;
  int64_t length;
  int64_t mapped_length;
#ifdef _WIN32
  file_handle_type file_mapping_handle;
#endif
};

inline mmap_context memory_map(const file_handle_type file_handle, const int64_t offset,
                               const int64_t length, const access_mode mode,
                               std::error_code &error) {
  const int64_t aligned_offset = make_offset_page_aligned(offset);
  const int64_t length_to_map = offset - aligned_offset + length;
#ifdef _WIN32
  const int64_t max_file_size = offset + length;
  const auto file_mapping_handle = ::CreateFileMapping(
      file_handle, 0, mode == access_mode::read ? PAGE_READONLY : PAGE_READWRITE,
      win::int64_high(max_file_size), win::int64_low(max_file_size), 0);
  if (file_mapping_handle == invalid_mapping_handle) {
    error = detail::last_error();
    return {};
  }
  char *mapping_start = static_cast<char *>(::MapViewOfFile(
      file_mapping_handle, mode == access_mode::read ? FILE_MAP_READ : FILE_MAP_WRITE,
      win::int64_high(aligned_offset), win::int64_low(aligned_offset), length_to_map));
  if (mapping_start == nullptr) {
    const std::error_code mapping_error = detail::last_error();
    ::CloseHandle(file_mapping_handle);
    error = mapping_error;
    return {};
  }
#else // POSIX
  char *mapping_start =
      static_cast<char *>(::mmap(0, // Don't give hint as to where to map.
                                 length_to_map, mode == access_mode::read ? PROT_READ : PROT_WRITE,
                                 MAP_SHARED, file_handle, aligned_offset));
  if (mapping_start == MAP_FAILED) {
    error = detail::last_error();
    return {};
  }
#endif
  mmap_context ctx;
  ctx.data = mapping_start + (offset - aligned_offset);
  ctx.length = length;
  ctx.mapped_length = length_to_map;
#ifdef _WIN32
  ctx.file_mapping_handle = file_mapping_handle;
#endif
  return ctx;
}

} // namespace detail

// -- basic_mmap --

template <access_mode AccessMode, typename ByteT> basic_mmap<AccessMode, ByteT>::~basic_mmap() {
  conditional_sync();
  unmap();
}

template <access_mode AccessMode, typename ByteT>
basic_mmap<AccessMode, ByteT>::basic_mmap(basic_mmap &&other)
    : data_(std::move(other.data_)), length_(std::move(other.length_)),
      mapped_length_(std::move(other.mapped_length_)), file_handle_(std::move(other.file_handle_))
#ifdef _WIN32
      ,
      file_mapping_handle_(std::move(other.file_mapping_handle_))
#endif
      ,
      is_handle_internal_(std::move(other.is_handle_internal_)) {
  other.data_ = nullptr;
  other.length_ = other.mapped_length_ = 0;
  other.file_handle_ = invalid_handle;
#ifdef _WIN32
  other.file_mapping_handle_ = invalid_mapping_handle;
#endif
  other.is_handle_internal_ = false;
}

template <access_mode AccessMode, typename ByteT>
basic_mmap<AccessMode, ByteT> &basic_mmap<AccessMode, ByteT>::operator=(basic_mmap &&other) {
  if (this != &other) {
    // First the existing mapping needs to be removed.
    unmap();
    data_ = std::move(other.data_);
    length_ = std::move(other.length_);
    mapped_length_ = std::move(other.mapped_length_);
    file_handle_ = std::move(other.file_handle_);
#ifdef _WIN32
    file_mapping_handle_ = std::move(other.file_mapping_handle_);
#endif
    is_handle_internal_ = std::move(other.is_handle_internal_);

    // The moved from basic_mmap's fields need to be reset, because
    // otherwise other's destructor will unmap the same mapping that was
    // just moved into this.
    other.data_ = nullptr;
    other.length_ = other.mapped_length_ = 0;
    other.file_handle_ = invalid_handle;
#ifdef _WIN32
    other.file_mapping_handle_ = invalid_mapping_handle;
#endif
    other.is_handle_internal_ = false;
  }
  return *this;
}

template <access_mode AccessMode, typename ByteT>
typename basic_mmap<AccessMode, ByteT>::handle_type
basic_mmap<AccessMode, ByteT>::mapping_handle() const noexcept {
#ifdef _WIN32
  return file_mapping_handle_;
#else
  return file_handle_;
#endif
}

template <access_mode AccessMode, typename ByteT>
template <typename String>
void basic_mmap<AccessMode, ByteT>::map(const String &path, const size_type offset,
                                        const size_type length, std::error_code &error) {
  error.clear();
  if (detail::empty(path)) {
    error = std::make_error_code(std::errc::invalid_argument);
    return;
  }
  const auto handle = detail::open_file(path, AccessMode, error);
  if (error) {
    return;
  }

  detail::file_handle_guard handle_guard(handle);
  map(handle, offset, length, error);
  if (error)
    return;

  is_handle_internal_ = true;
  handle_guard.release();
}

template <access_mode AccessMode, typename ByteT>
void basic_mmap<AccessMode, ByteT>::map(const handle_type handle, const size_type offset,
                                        const size_type length, std::error_code &error) {
  error.clear();
  if (handle == invalid_handle) {
    error = std::make_error_code(std::errc::bad_file_descriptor);
    return;
  }

  const auto file_size = detail::query_file_size(handle, error);
  if (error) {
    return;
  }

  if (offset > file_size || length > file_size - offset) {
    error = std::make_error_code(std::errc::invalid_argument);
    return;
  }

  const bool remapping_internal_handle = is_handle_internal_ && handle == file_handle_;
  const auto ctx = detail::memory_map(
      handle, offset, length == map_entire_file ? (file_size - offset) : length, AccessMode, error);
  if (!error) {
    // We must unmap the previous mapping that may have existed prior to this call.
    // Note that this must only be invoked after a new mapping has been created in
    // order to provide the strong guarantee that, should the new mapping fail, the
    // `map` function leaves this instance in a state as though the function had
    // never been invoked.
    if (remapping_internal_handle)
      is_handle_internal_ = false;
    unmap();
    file_handle_ = handle;
    is_handle_internal_ = remapping_internal_handle;
    data_ = reinterpret_cast<pointer>(ctx.data);
    length_ = ctx.length;
    mapped_length_ = ctx.mapped_length;
#ifdef _WIN32
    file_mapping_handle_ = ctx.file_mapping_handle;
#endif
  }
}

template <access_mode AccessMode, typename ByteT>
template <access_mode A>
typename std::enable_if<A == access_mode::write, void>::type
basic_mmap<AccessMode, ByteT>::sync(std::error_code &error) {
  error.clear();
  if (!is_open()) {
    error = std::make_error_code(std::errc::bad_file_descriptor);
    return;
  }

  if (data()) {
#ifdef _WIN32
    if (::FlushViewOfFile(get_mapping_start(), mapped_length_) == 0)
#else // POSIX
    if (::msync(get_mapping_start(), mapped_length_, MS_SYNC) != 0)
#endif
    {
      error = detail::last_error();
      return;
    }
  }
#ifdef _WIN32
  if (::FlushFileBuffers(file_handle_) == 0) {
    error = detail::last_error();
  }
#endif
}

template <access_mode AccessMode, typename ByteT> void basic_mmap<AccessMode, ByteT>::unmap() {
  if (!is_open()) {
    return;
  }
  // TODO do we care about errors here?
#ifdef _WIN32
  if (is_mapped()) {
    ::UnmapViewOfFile(get_mapping_start());
    ::CloseHandle(file_mapping_handle_);
  }
#else // POSIX
  if (data_) {
    ::munmap(const_cast<pointer>(get_mapping_start()), mapped_length_);
  }
#endif

  // If `file_handle_` was obtained by our opening it (when map is called with
  // a path, rather than an existing file handle), we need to close it,
  // otherwise it must not be closed as it may still be used outside this
  // instance.
  if (is_handle_internal_) {
#ifdef _WIN32
    ::CloseHandle(file_handle_);
#else // POSIX
    ::close(file_handle_);
#endif
  }

  // Reset fields to their default values.
  data_ = nullptr;
  length_ = mapped_length_ = 0;
  file_handle_ = invalid_handle;
#ifdef _WIN32
  file_mapping_handle_ = invalid_mapping_handle;
#endif
  is_handle_internal_ = false;
}

template <access_mode AccessMode, typename ByteT>
bool basic_mmap<AccessMode, ByteT>::is_mapped() const noexcept {
#ifdef _WIN32
  return file_mapping_handle_ != invalid_mapping_handle;
#else // POSIX
  return is_open();
#endif
}

template <access_mode AccessMode, typename ByteT>
void basic_mmap<AccessMode, ByteT>::swap(basic_mmap &other) {
  if (this != &other) {
    using std::swap;
    swap(data_, other.data_);
    swap(file_handle_, other.file_handle_);
#ifdef _WIN32
    swap(file_mapping_handle_, other.file_mapping_handle_);
#endif
    swap(length_, other.length_);
    swap(mapped_length_, other.mapped_length_);
    swap(is_handle_internal_, other.is_handle_internal_);
  }
}

template <access_mode AccessMode, typename ByteT>
template <access_mode A>
typename std::enable_if<A == access_mode::write, void>::type
basic_mmap<AccessMode, ByteT>::conditional_sync() {
  // This is invoked from the destructor, so not much we can do about
  // failures here.
  std::error_code ec;
  sync(ec);
}

template <access_mode AccessMode, typename ByteT>
template <access_mode A>
typename std::enable_if<A == access_mode::read, void>::type
basic_mmap<AccessMode, ByteT>::conditional_sync() {
  // noop
}

template <access_mode AccessMode, typename ByteT>
bool operator==(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return a.data() == b.data() && a.size() == b.size();
}

template <access_mode AccessMode, typename ByteT>
bool operator!=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return !(a == b);
}

template <access_mode AccessMode, typename ByteT>
bool operator<(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  if (a.data() == b.data()) {
    return a.size() < b.size();
  }
  return a.data() < b.data();
}

template <access_mode AccessMode, typename ByteT>
bool operator<=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return !(a > b);
}

template <access_mode AccessMode, typename ByteT>
bool operator>(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  if (a.data() == b.data()) {
    return a.size() > b.size();
  }
  return a.data() > b.data();
}

template <access_mode AccessMode, typename ByteT>
bool operator>=(const basic_mmap<AccessMode, ByteT> &a, const basic_mmap<AccessMode, ByteT> &b) {
  return !(a < b);
}

} // namespace mio

#endif // MIO_BASIC_MMAP_IMPL

#endif // MIO_MMAP_HEADER
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_PAGE_HEADER
#define MIO_PAGE_HEADER

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace mio {

/**
 * This is used by `basic_mmap` to determine whether to create a read-only or
 * a read-write memory mapping.
 */
enum class access_mode { read, write };

/**
 * Determines the operating system's page allocation granularity.
 *
 * On the first call to this function, it invokes the operating system specific syscall
 * to determine the page size, caches the value, and returns it. Any subsequent call to
 * this function serves the cached value, so no further syscalls are made.
 */
inline size_t page_size() {
  static const size_t page_size = [] {
#ifdef _WIN32
    SYSTEM_INFO SystemInfo;
    GetSystemInfo(&SystemInfo);
    return SystemInfo.dwAllocationGranularity;
#else
    return sysconf(_SC_PAGE_SIZE);
#endif
  }();
  return page_size;
}

/**
 * Alligns `offset` to the operating's system page size such that it subtracts the
 * difference until the nearest page boundary before `offset`, or does nothing if
 * `offset` is already page aligned.
 */
inline size_t make_offset_page_aligned(size_t offset) noexcept {
  const size_t page_size_ = page_size();
  // Use integer division to round down to the nearest page alignment.
  return offset / page_size_ * page_size_;
}

} // namespace mio

#endif // MIO_PAGE_HEADER
/* Copyright 2017 https://github.com/mandreyel
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies
 * or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef MIO_SHARED_MMAP_HEADER
#define MIO_SHARED_MMAP_HEADER

// #include "mio/mmap.hpp"

#include <memory>       // std::shared_ptr
#include <system_error> // std::error_code

namespace mio {

/**
 * Exposes (nearly) the same interface as `basic_mmap`, but endowes it with
 * `std::shared_ptr` semantics.
 *
 * This is not the default behaviour of `basic_mmap` to avoid allocating on the heap if
 * shared semantics are not required.
 */
template <access_mode AccessMode, typename ByteT> class basic_shared_mmap {
  using impl_type = basic_mmap<AccessMode, ByteT>;
  std::shared_ptr<impl_type> pimpl_;

public:
  using value_type = typename impl_type::value_type;
  using size_type = typename impl_type::size_type;
  using reference = typename impl_type::reference;
  using const_reference = typename impl_type::const_reference;
  using pointer = typename impl_type::pointer;
  using const_pointer = typename impl_type::const_pointer;
  using difference_type = typename impl_type::difference_type;
  using iterator = typename impl_type::iterator;
  using const_iterator = typename impl_type::const_iterator;
  using reverse_iterator = typename impl_type::reverse_iterator;
  using const_reverse_iterator = typename impl_type::const_reverse_iterator;
  using iterator_category = typename impl_type::iterator_category;
  using handle_type = typename impl_type::handle_type;
  using mmap_type = impl_type;

  basic_shared_mmap() = default;
  basic_shared_mmap(const basic_shared_mmap &) = default;
  basic_shared_mmap &operator=(const basic_shared_mmap &) = default;
  basic_shared_mmap(basic_shared_mmap &&) = default;
  basic_shared_mmap &operator=(basic_shared_mmap &&) = default;

  /** Takes ownership of an existing mmap object. */
  basic_shared_mmap(mmap_type &&mmap) : pimpl_(std::make_shared<mmap_type>(std::move(mmap))) {}

  /** Takes ownership of an existing mmap object. */
  basic_shared_mmap &operator=(mmap_type &&mmap) {
    pimpl_ = std::make_shared<mmap_type>(std::move(mmap));
    return *this;
  }

  /** Initializes this object with an already established shared mmap. */
  basic_shared_mmap(std::shared_ptr<mmap_type> mmap) : pimpl_(std::move(mmap)) {}

  /** Initializes this object with an already established shared mmap. */
  basic_shared_mmap &operator=(std::shared_ptr<mmap_type> mmap) {
    pimpl_ = std::move(mmap);
    return *this;
  }

#ifdef __cpp_exceptions
  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  template <typename String>
  basic_shared_mmap(const String &path, const size_type offset = 0,
                    const size_type length = map_entire_file) {
    std::error_code error;
    map(path, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }

  /**
   * The same as invoking the `map` function, except any error that may occur
   * while establishing the mapping is wrapped in a `std::system_error` and is
   * thrown.
   */
  basic_shared_mmap(const handle_type handle, const size_type offset = 0,
                    const size_type length = map_entire_file) {
    std::error_code error;
    map(handle, offset, length, error);
    if (error) {
      throw std::system_error(error);
    }
  }
#endif // __cpp_exceptions

  /**
   * If this is a read-write mapping and the last reference to the mapping,
   * the destructor invokes sync. Regardless of the access mode, unmap is
   * invoked as a final step.
   */
  ~basic_shared_mmap() = default;

  /** Returns the underlying `std::shared_ptr` instance that holds the mmap. */
  std::shared_ptr<mmap_type> get_shared_ptr() { return pimpl_; }

  /**
   * On UNIX systems 'file_handle' and 'mapping_handle' are the same. On Windows,
   * however, a mapped region of a file gets its own handle, which is returned by
   * 'mapping_handle'.
   */
  handle_type file_handle() const noexcept {
    return pimpl_ ? pimpl_->file_handle() : invalid_handle;
  }

  handle_type mapping_handle() const noexcept {
    return pimpl_ ? pimpl_->mapping_handle() : invalid_mapping_handle;
  }

  /** Returns whether a valid memory mapping has been created. */
  bool is_open() const noexcept { return pimpl_ && pimpl_->is_open(); }

  /**
   * Returns true if no mapping was established, that is, conceptually the
   * same as though the length that was mapped was 0. This function is
   * provided so that this class has Container semantics.
   */
  bool empty() const noexcept { return !pimpl_ || pimpl_->empty(); }

  /**
   * `size` and `length` both return the logical length, i.e. the number of bytes
   * user requested to be mapped, while `mapped_length` returns the actual number of
   * bytes that were mapped which is a multiple of the underlying operating system's
   * page allocation granularity.
   */
  size_type size() const noexcept { return pimpl_ ? pimpl_->length() : 0; }
  size_type length() const noexcept { return pimpl_ ? pimpl_->length() : 0; }
  size_type mapped_length() const noexcept { return pimpl_ ? pimpl_->mapped_length() : 0; }

  /**
   * Returns a pointer to the first requested byte, or `nullptr` if no memory mapping
   * exists.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  pointer data() noexcept {
    return pimpl_->data();
  }
  const_pointer data() const noexcept { return pimpl_ ? pimpl_->data() : nullptr; }

  /**
   * Returns an iterator to the first requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  iterator begin() noexcept { return pimpl_->begin(); }
  const_iterator begin() const noexcept { return pimpl_->begin(); }
  const_iterator cbegin() const noexcept { return pimpl_->cbegin(); }

  /**
   * Returns an iterator one past the last requested byte, if a valid memory mapping
   * exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  iterator end() noexcept {
    return pimpl_->end();
  }
  const_iterator end() const noexcept { return pimpl_->end(); }
  const_iterator cend() const noexcept { return pimpl_->cend(); }

  /**
   * Returns a reverse iterator to the last memory mapped byte, if a valid
   * memory mapping exists, otherwise this function call is undefined
   * behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rbegin() noexcept {
    return pimpl_->rbegin();
  }
  const_reverse_iterator rbegin() const noexcept { return pimpl_->rbegin(); }
  const_reverse_iterator crbegin() const noexcept { return pimpl_->crbegin(); }

  /**
   * Returns a reverse iterator past the first mapped byte, if a valid memory
   * mapping exists, otherwise this function call is undefined behaviour.
   */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  reverse_iterator rend() noexcept {
    return pimpl_->rend();
  }
  const_reverse_iterator rend() const noexcept { return pimpl_->rend(); }
  const_reverse_iterator crend() const noexcept { return pimpl_->crend(); }

  /**
   * Returns a reference to the `i`th byte from the first requested byte (as returned
   * by `data`). If this is invoked when no valid memory mapping has been created
   * prior to this call, undefined behaviour ensues.
   */
  reference operator[](const size_type i) noexcept { return (*pimpl_)[i]; }
  const_reference operator[](const size_type i) const noexcept { return (*pimpl_)[i]; }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  template <typename String>
  void map(const String &path, const size_type offset, const size_type length,
           std::error_code &error) {
    map_impl(path, offset, length, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `path`, which must be a path to an existing file, is used to retrieve a file
   * handle (which is closed when the object destructs or `unmap` is called), which is
   * then used to memory map the requested region. Upon failure, `error` is set to
   * indicate the reason and the object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  template <typename String> void map(const String &path, std::error_code &error) {
    map_impl(path, 0, map_entire_file, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * `offset` is the number of bytes, relative to the start of the file, where the
   * mapping should begin. When specifying it, there is no need to worry about
   * providing a value that is aligned with the operating system's page allocation
   * granularity. This is adjusted by the implementation such that the first requested
   * byte (as returned by `data` or `begin`), so long as `offset` is valid, will be at
   * `offset` from the start of the file.
   *
   * `length` is the number of bytes to map. It may be `map_entire_file`, in which
   * case a mapping of the entire file is created.
   */
  void map(const handle_type handle, const size_type offset, const size_type length,
           std::error_code &error) {
    map_impl(handle, offset, length, error);
  }

  /**
   * Establishes a memory mapping with AccessMode. If the mapping is unsuccesful, the
   * reason is reported via `error` and the object remains in a state as if this
   * function hadn't been called.
   *
   * `handle`, which must be a valid file handle, which is used to memory map the
   * requested region. Upon failure, `error` is set to indicate the reason and the
   * object remains in an unmapped state.
   *
   * The entire file is mapped.
   */
  void map(const handle_type handle, std::error_code &error) {
    map_impl(handle, 0, map_entire_file, error);
  }

  /**
   * If a valid memory mapping has been created prior to this call, this call
   * instructs the kernel to unmap the memory region and disassociate this object
   * from the file.
   *
   * The file handle associated with the file that is mapped is only closed if the
   * mapping was created using a file path. If, on the other hand, an existing
   * file handle was used to create the mapping, the file handle is not closed.
   */
  void unmap() {
    if (pimpl_)
      pimpl_->unmap();
  }

  void swap(basic_shared_mmap &other) { pimpl_.swap(other.pimpl_); }

  /** Flushes the memory mapped page to disk. Errors are reported via `error`. */
  template <access_mode A = AccessMode,
            typename = typename std::enable_if<A == access_mode::write>::type>
  void sync(std::error_code &error) {
    if (pimpl_)
      pimpl_->sync(error);
  }

  /** All operators compare the underlying `basic_mmap`'s addresses. */

  friend bool operator==(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ == b.pimpl_;
  }

  friend bool operator!=(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return !(a == b);
  }

  friend bool operator<(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ < b.pimpl_;
  }

  friend bool operator<=(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ <= b.pimpl_;
  }

  friend bool operator>(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ > b.pimpl_;
  }

  friend bool operator>=(const basic_shared_mmap &a, const basic_shared_mmap &b) {
    return a.pimpl_ >= b.pimpl_;
  }

private:
  template <typename MappingToken>
  void map_impl(const MappingToken &token, const size_type offset, const size_type length,
                std::error_code &error) {
    if (!pimpl_) {
      mmap_type mmap = make_mmap<mmap_type>(token, offset, length, error);
      if (error) {
        return;
      }
      pimpl_ = std::make_shared<mmap_type>(std::move(mmap));
    } else {
      pimpl_->map(token, offset, length, error);
    }
  }
};

/**
 * This is the basis for all read-only mmap objects and should be preferred over
 * directly using basic_shared_mmap.
 */
template <typename ByteT>
using basic_shared_mmap_source = basic_shared_mmap<access_mode::read, ByteT>;

/**
 * This is the basis for all read-write mmap objects and should be preferred over
 * directly using basic_shared_mmap.
 */
template <typename ByteT>
using basic_shared_mmap_sink = basic_shared_mmap<access_mode::write, ByteT>;

/**
 * These aliases cover the most common use cases, both representing a raw byte stream
 * (either with a char or an unsigned char/uint8_t).
 */
using shared_mmap_source = basic_shared_mmap_source<char>;
using shared_ummap_source = basic_shared_mmap_source<unsigned char>;

using shared_mmap_sink = basic_shared_mmap_sink<char>;
using shared_ummap_sink = basic_shared_mmap_sink<unsigned char>;

} // namespace mio

#endif // MIO_SHARED_MMAP_HEADER

#endif
// #include <csv2/parameters.hpp>

// #include <csv2/detail/config.hpp>

#include <cstddef>
#include <utility>

namespace csv2 {

namespace trim_policy {
struct no_trimming {
public:
  static std::pair<std::size_t, std::size_t> trim(const char *buffer, std::size_t start,
                                                  std::size_t end) {
    (void)(buffer); // to silence unused parameter warning
    return {start, end};
  }
};

template <char... character_list> struct trim_characters {
private:
  constexpr static bool is_trim_char(char) { return false; }

  template <class... Tail> constexpr static bool is_trim_char(char c, char head, Tail... tail) {
    return c == head || is_trim_char(c, tail...);
  }

public:
  static std::pair<std::size_t, std::size_t> trim(const char *buffer, std::size_t start,
                                                  std::size_t end) {
    std::size_t new_start = start, new_end = end;
    while (new_start != new_end && is_trim_char(buffer[new_start], character_list...))
      ++new_start;
    while (new_start != new_end && is_trim_char(buffer[new_end - 1], character_list...))
      --new_end;
    return {new_start, new_end};
  }
};

using trim_whitespace = trim_characters<' ', '\t'>;
} // namespace trim_policy

template <char character> struct delimiter {
  constexpr static char value = character;
};

template <char character> struct quote_character {
  constexpr static char value = character;
};

template <bool flag> struct first_row_is_header {
  constexpr static bool value = flag;
};

} // namespace csv2


#include <functional>
#include <iterator>
#include <memory>
#include <string>
#include <system_error>
#include <type_traits>
#include <utility>
#if CSV2_HAS_STRING_VIEW
#include <string_view>
#endif
#if CSV2_HAS_SPAN
#include <span>
#endif

namespace csv2 {

template <class delimiter = delimiter<','>, class quote_character = quote_character<'"'>,
          class first_row_is_header = first_row_is_header<true>,
          class trim_policy = trim_policy::trim_whitespace>
class Reader {
  struct RecordBounds {
    size_t content_end;
    size_t next_start;
  };

  static RecordBounds find_record_bounds_(const char *buffer, size_t buffer_size,
                                          size_t start) noexcept {
    if (!buffer || start >= buffer_size)
      return {buffer_size, buffer_size};

    const char *const record_start = buffer + start;
    const size_t remaining = buffer_size - start;
    const char *const newline =
        static_cast<const char *>(std::memchr(record_start, '\n', remaining));
    const size_t candidate_length =
        newline ? static_cast<size_t>(newline - record_start) : remaining;
    const char *const quote = static_cast<const char *>(
        std::memchr(record_start, quote_character::value, candidate_length));

    // The common unquoted case avoids the state machine entirely.
    if (!quote) {
      if (!newline)
        return {buffer_size, buffer_size};
      const size_t newline_index = start + static_cast<size_t>(newline - record_start);
      const size_t content_end = newline_index > start && buffer[newline_index - 1] == '\r'
                                     ? newline_index - 1
                                     : newline_index;
      return {content_end, newline_index + 1};
    }

    bool quote_opened = false;
    for (size_t i = start; i < buffer_size; ++i) {
      if (buffer[i] == quote_character::value) {
        if (quote_opened && i + 1 < buffer_size && buffer[i + 1] == quote_character::value) {
          ++i;
          continue;
        }
        quote_opened = !quote_opened;
      } else if (buffer[i] == '\n' && !quote_opened) {
        const size_t content_end = i > start && buffer[i - 1] == '\r' ? i - 1 : i;
        return {content_end, i + 1};
      }
    }

    // An unclosed quoted field is treated as content through EOF.
    return {buffer_size, buffer_size};
  }

#if CSV2_HAS_MMAP
  mio::mmap_source mmap_;
#endif
  std::unique_ptr<std::string> owned_buffer_;
  const char *buffer_{nullptr};
  size_t buffer_size_{0};

  void clear_buffer_() noexcept {
    buffer_ = nullptr;
    buffer_size_ = 0;
  }

  void reset_source_() {
    clear_buffer_();
    owned_buffer_.reset();
#if CSV2_HAS_MMAP
    mmap_.unmap();
#endif
  }

  static bool contains_range_(const char *source, size_t source_size, const char *data,
                              size_t size) noexcept {
    if (!source || !data || size > source_size)
      return false;

    const char *const source_end = source + source_size;
    const char *const data_end = data + size;
    const std::less<const char *> less;
    return !less(data, source) && !less(source_end, data_end);
  }

  bool owns_range_(const char *data, size_t size) const noexcept {
    if (owned_buffer_ && contains_range_(owned_buffer_->c_str(), owned_buffer_->size(), data, size))
      return true;
#if CSV2_HAS_MMAP
    if (mmap_.is_mapped() && contains_range_(mmap_.data(), mmap_.size(), data, size))
      return true;
#endif
    return false;
  }

  template <typename StringType> bool parse_dispatch_(StringType &&contents, std::true_type) {
    return parse_borrowed(contents.c_str(), contents.size());
  }

  template <typename StringType> bool parse_owned_(StringType &&contents, std::true_type) {
    std::unique_ptr<std::string> new_buffer(new std::string(std::forward<StringType>(contents)));
    reset_source_();
    if (new_buffer->empty())
      return false;
    owned_buffer_ = std::move(new_buffer);
    buffer_ = owned_buffer_->c_str();
    buffer_size_ = owned_buffer_->size();
    return true;
  }

  template <typename StringType> bool parse_owned_(StringType &&contents, std::false_type) {
    std::unique_ptr<std::string> new_buffer(new std::string(contents.c_str(), contents.size()));
    reset_source_();
    if (new_buffer->empty())
      return false;
    owned_buffer_ = std::move(new_buffer);
    buffer_ = owned_buffer_->c_str();
    buffer_size_ = owned_buffer_->size();
    return true;
  }

  template <typename StringType> bool parse_dispatch_(StringType &&contents, std::false_type) {
    typedef typename std::decay<StringType>::type DecayedString;
    return parse_owned_(std::forward<StringType>(contents),
                        typename std::is_same<DecayedString, std::string>::type());
  }

public:
  Reader() = default;
  Reader(const Reader &) = delete;
  Reader &operator=(const Reader &) = delete;

  Reader(Reader &&other)
      :
#if CSV2_HAS_MMAP
        mmap_(std::move(other.mmap_)),
#endif
        owned_buffer_(std::move(other.owned_buffer_)), buffer_(other.buffer_),
        buffer_size_(other.buffer_size_) {
    other.clear_buffer_();
  }

  Reader &operator=(Reader &&other) {
    if (this != &other) {
      // The borrowed source may be a view into storage currently owned by this Reader.
      if (owns_range_(other.buffer_, other.buffer_size_)) {
        buffer_ = other.buffer_;
        buffer_size_ = other.buffer_size_;
        other.clear_buffer_();
        return *this;
      }
      reset_source_();
#if CSV2_HAS_MMAP
      mmap_ = std::move(other.mmap_);
#endif
      owned_buffer_ = std::move(other.owned_buffer_);
      buffer_ = other.buffer_;
      buffer_size_ = other.buffer_size_;
      other.clear_buffer_();
    }
    return *this;
  }

#if CSV2_HAS_MMAP
  // Memory-map a file. A failed mapping clears any previous source.
  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value, bool>::type
  mmap(StringType &&filename, std::error_code &error) {
    reset_source_();
    mmap_.map(std::forward<StringType>(filename), error);
    if (error || !mmap_.is_open() || !mmap_.is_mapped() || mmap_.size() == 0) {
      if (!error)
        error = std::make_error_code(std::errc::invalid_argument);
      mmap_.unmap();
      return false;
    }
    buffer_ = mmap_.data();
    buffer_size_ = mmap_.size();
    return true;
  }

  template <typename StringType>
  typename std::enable_if<mio::detail::is_path<StringType>::value, bool>::type
  mmap(StringType &&filename) {
    std::error_code error;
    return mmap(std::forward<StringType>(filename), error);
  }
#endif

  // Lvalue strings are borrowed. Rvalue strings are owned by this Reader.
  template <typename StringType> bool parse(StringType &&contents) {
    return parse_dispatch_(std::forward<StringType>(contents),
                           typename std::is_lvalue_reference<StringType &&>::type());
  }

  // Borrow exactly size bytes. The caller keeps the storage alive.
  bool parse_borrowed(const char *data, size_t size) noexcept {
    if (!data || size == 0) {
      reset_source_();
      return false;
    }
    if (!owns_range_(data, size))
      reset_source_();
    buffer_ = data;
    buffer_size_ = size;
    return true;
  }

  // Own an independent copy (or moved value) of the input string.
  bool parse_owned(std::string contents) {
    return parse_owned_(std::move(contents), std::true_type());
  }

#if CSV2_HAS_SPAN
  bool parse_borrowed(std::span<const char> contents) noexcept {
    return parse_borrowed(contents.data(), contents.size());
  }
#endif

#if CSV2_HAS_STRING_VIEW
  // Borrow a string_view. The view's storage must outlive Reader access.
  bool parse_view(std::string_view sv) {
    const char *const data = sv.data();
    const size_t size = sv.size();
    if (size == 0) {
      reset_source_();
      return false;
    }
    if (!owns_range_(data, size))
      reset_source_();
    buffer_ = data;
    buffer_size_ = size;
    return true;
  }
#endif

  class RowIterator;
  class Row;

  class Cell {
    const char *buffer_{nullptr};
    size_t start_{0};
    size_t end_{0};
    bool escaped_{false};
    friend class Row;

  public:
    const char *raw_data() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
    size_t raw_size() const noexcept { return end_ - start_; }
    bool has_escaped_quotes() const noexcept { return escaped_; }

#if CSV2_HAS_STRING_VIEW
    std::string_view raw_trimmed_view() const noexcept {
      const auto bounds = trim_policy::trim(buffer_, start_, end_);
      return std::string_view(buffer_ + bounds.first, bounds.second - bounds.first);
    }

    std::string_view read_view() const noexcept { return raw_trimmed_view(); }
#endif

    template <typename Container> void read_raw_value(Container &result) const {
      detail::reserve_for_append(result, raw_size());
      copy_raw_to(detail::container_inserter(result));
    }

    template <typename Container> void read_value(Container &result) const {
      const auto bounds = trim_policy::trim(buffer_, start_, end_);
      detail::reserve_for_append(result, bounds.second - bounds.first);
      decode_to(detail::container_inserter(result));
    }

    template <typename OutputIt> OutputIt copy_raw_to(OutputIt output) const {
      if (start_ >= end_)
        return output;
      return detail::copy_chars(buffer_ + start_, buffer_ + end_, output);
    }

    template <typename OutputIt> OutputIt decode_to(OutputIt output) const {
      if (start_ >= end_)
        return output;
      const auto bounds = trim_policy::trim(buffer_, start_, end_);
      for (size_t i = bounds.first; i < bounds.second; ++i) {
        *output = buffer_[i];
        ++output;
        if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
            buffer_[i + 1] == quote_character::value)
          ++i;
      }
      return output;
    }

    template <typename OutputIt> OutputIt copy_content_to(OutputIt output) const {
      if (start_ >= end_)
        return output;
      auto bounds = trim_policy::trim(buffer_, start_, end_);
      if (bounds.second - bounds.first >= 2 && buffer_[bounds.first] == quote_character::value &&
          buffer_[bounds.second - 1] == quote_character::value) {
        ++bounds.first;
        --bounds.second;
      }
      for (size_t i = bounds.first; i < bounds.second; ++i) {
        *output = buffer_[i];
        ++output;
        if (buffer_[i] == quote_character::value && i + 1 < bounds.second &&
            buffer_[i + 1] == quote_character::value)
          ++i;
      }
      return output;
    }
  };

  class Row {
    const char *buffer_{nullptr};
    size_t start_{0};
    size_t end_{0};
    friend class RowIterator;
    friend class Reader;

  public:
    const char *raw_data() const noexcept { return buffer_ ? buffer_ + start_ : nullptr; }
    size_t raw_size() const noexcept { return end_ - start_; }
    const char *address() const noexcept { return raw_data(); }
    size_t length() const noexcept { return raw_size(); }

    template <typename Container> void read_raw_value(Container &result) const {
      detail::reserve_for_append(result, raw_size());
      if (start_ < end_)
        detail::append_range(result, buffer_ + start_, buffer_ + end_);
    }

    class CellIterator {
      struct CellBounds {
        size_t content_end;
        bool escaped;
      };

      const char *buffer_{nullptr};
      size_t range_size_{0};
      size_t current_{0};
      size_t end_{0};
      size_t content_end_{0};
      bool escaped_{false};
      bool at_end_{true};

      CellBounds find_cell_bounds_() const noexcept {
        bool quote_opened = false;
        bool escaped = false;
        for (size_t i = current_; i < end_; ++i) {
          if (buffer_[i] == quote_character::value) {
            const bool adjacent_quote = i + 1 < end_ && buffer_[i + 1] == quote_character::value;
            if (adjacent_quote)
              escaped = true;
            if (quote_opened && adjacent_quote) {
              ++i;
              continue;
            }
            quote_opened = !quote_opened;
          } else if (buffer_[i] == delimiter::value && !quote_opened) {
            return {i, escaped};
          }
        }
        return {end_, escaped};
      }

      void update_bounds_() noexcept {
        if (!at_end_) {
          const CellBounds bounds = find_cell_bounds_();
          content_end_ = bounds.content_end;
          escaped_ = bounds.escaped;
        } else {
          content_end_ = end_;
          escaped_ = false;
        }
      }

      friend class Row;

    public:
      using value_type = Cell;
      using difference_type = std::ptrdiff_t;
      using reference = Cell;
      using pointer = void;
      using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
      using iterator_concept = std::forward_iterator_tag;
#endif

      CellIterator() = default;

      CellIterator(const char *buffer, size_t buffer_size, size_t start, size_t end)
          : buffer_(buffer), range_size_(buffer_size), current_(start), end_(end),
            content_end_(end), escaped_(false), at_end_(start >= end) {
        update_bounds_();
      }

      CellIterator &operator++() {
        if (!at_end_) {
          if (content_end_ < end_) {
            current_ = content_end_ + 1;
          } else {
            current_ = end_;
            at_end_ = true;
          }
          update_bounds_();
        }
        return *this;
      }

      CellIterator operator++(int) {
        CellIterator previous(*this);
        ++(*this);
        return previous;
      }

      Cell operator*() const {
        Cell cell;
        cell.buffer_ = buffer_;
        cell.start_ = current_;
        cell.end_ = content_end_;
        cell.escaped_ = escaped_;
        return cell;
      }

      bool operator==(const CellIterator &rhs) const noexcept {
        return buffer_ == rhs.buffer_ && range_size_ == rhs.range_size_ &&
               current_ == rhs.current_ && end_ == rhs.end_ && at_end_ == rhs.at_end_;
      }

      bool operator!=(const CellIterator &rhs) const noexcept { return !(*this == rhs); }
    };

    CellIterator begin() const { return CellIterator(buffer_, end_ - start_, start_, end_); }
    CellIterator end() const { return CellIterator(buffer_, end_ - start_, end_, end_); }
  };

  class RowIterator {
    const char *buffer_{nullptr};
    size_t buffer_size_{0};
    size_t start_{0};
    size_t content_end_{0};
    size_t next_start_{0};
    friend class Reader;

  public:
    using value_type = Row;
    using difference_type = std::ptrdiff_t;
    using reference = Row;
    using pointer = void;
    using iterator_category = std::input_iterator_tag;
#if CSV2_HAS_RANGES
    using iterator_concept = std::forward_iterator_tag;
#endif

    RowIterator() = default;

    RowIterator(const char *buffer, size_t buffer_size, size_t start)
        : buffer_(buffer), buffer_size_(buffer_size),
          start_(start < buffer_size ? start : buffer_size), content_end_(buffer_size),
          next_start_(buffer_size) {
      if (start_ < buffer_size_) {
        const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, start_);
        content_end_ = bounds.content_end;
        next_start_ = bounds.next_start;
      }
    }

    RowIterator &operator++() {
      start_ = next_start_;
      if (start_ < buffer_size_) {
        const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, start_);
        content_end_ = bounds.content_end;
        next_start_ = bounds.next_start;
      } else {
        start_ = buffer_size_;
        content_end_ = buffer_size_;
        next_start_ = buffer_size_;
      }
      return *this;
    }

    RowIterator operator++(int) {
      RowIterator previous(*this);
      ++(*this);
      return previous;
    }

    Row operator*() const {
      Row result;
      result.buffer_ = buffer_;
      result.start_ = start_;
      result.end_ = content_end_;
      return result;
    }

    bool operator==(const RowIterator &rhs) const noexcept {
      return buffer_ == rhs.buffer_ && buffer_size_ == rhs.buffer_size_ && start_ == rhs.start_ &&
             content_end_ == rhs.content_end_ && next_start_ == rhs.next_start_;
    }

    bool operator!=(const RowIterator &rhs) const noexcept { return !(*this == rhs); }
  };

  RowIterator begin() const {
    if (!buffer_ || buffer_size_ == 0)
      return end();
    if (first_row_is_header::value) {
      const RecordBounds header = find_record_bounds_(buffer_, buffer_size_, 0);
      return RowIterator(buffer_, buffer_size_, header.next_start);
    }
    return RowIterator(buffer_, buffer_size_, 0);
  }

  RowIterator end() const { return RowIterator(buffer_, buffer_size_, buffer_size_); }

  Row header() const {
    Row result;
    result.buffer_ = buffer_;
    if (!buffer_ || buffer_size_ == 0)
      return result;
    const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, 0);
    result.end_ = bounds.content_end;
    return result;
  }

  /** Returns the number of records, excluding the header when configured. */
  size_t rows(bool ignore_empty_lines = false) const {
    if (!buffer_ || buffer_size_ == 0)
      return 0;

    size_t start = 0;
    if (first_row_is_header::value)
      start = find_record_bounds_(buffer_, buffer_size_, 0).next_start;

    size_t result = 0;
    while (start < buffer_size_) {
      const RecordBounds bounds = find_record_bounds_(buffer_, buffer_size_, start);
      if (!ignore_empty_lines || bounds.content_end != start)
        ++result;
      start = bounds.next_start;
    }
    return result;
  }

  size_t cols() const {
    size_t result = 0;
    for (const auto cell : header()) {
      (void)cell;
      ++result;
    }
    return result;
  }
};

} // namespace csv2
#pragma once

#include <cstring>
// #include <csv2/detail/config.hpp>
// #include <csv2/parameters.hpp>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <type_traits>
#include <utility>

namespace csv2 {

template <typename, typename T> struct has_close : std::false_type {};

template <typename C, typename Ret, typename... Args> struct has_close<C, Ret(Args...)> {
private:
  template <typename T>
  static constexpr auto check(T *) ->
      typename std::is_same<decltype(std::declval<T &>().close(std::declval<Args>()...)),
                            Ret>::type;

  template <typename> static constexpr std::false_type check(...);

public:
  static constexpr bool value = decltype(check<C>(0))::value;
};

template <class delimiter = delimiter<','>, typename Stream = std::ofstream> class Writer {
  Stream *stream_; // output stream for the writer
  bool active_;

  static void close_stream_(Stream &stream, std::true_type) { stream.close(); }

  static void close_stream_(Stream &, std::false_type) {}

  void close_noexcept_() noexcept {
    if (!active_)
      return;
    active_ = false;
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
    try {
      close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
    } catch (...) {
    }
#else
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
#endif
  }

public:
  Writer(Stream &stream) noexcept : stream_(&stream), active_(true) {}

  Writer(const Writer &) = delete;
  Writer &operator=(const Writer &) = delete;

  Writer(Writer &&other) noexcept : stream_(other.stream_), active_(other.active_) {
    other.stream_ = nullptr;
    other.active_ = false;
  }

  Writer &operator=(Writer &&other) noexcept {
    if (this != &other) {
      close_noexcept_();
      stream_ = other.stream_;
      active_ = other.active_;
      other.stream_ = nullptr;
      other.active_ = false;
    }
    return *this;
  }

  ~Writer() noexcept { close_noexcept_(); }

  void close() {
    if (!active_)
      return;
    active_ = false;
    close_stream_(*stream_, std::integral_constant<bool, has_close<Stream, void()>::value>());
  }

  template <typename Container> void write_row(Container &&row) {
    if (!active_)
      return;
    const auto &strings = std::forward<Container>(row);
    auto current = strings.begin();
    const auto end = strings.end();
    if (current != end) {
      *stream_ << *current;
      const char separator = delimiter::value;
      while (++current != end)
        *stream_ << separator << *current;
    }
    *stream_ << '\n';
  }

  template <typename Container> void write_rows(Container &&rows) {
    if (!active_)
      return;
    const auto &container_of_rows = std::forward<Container>(rows);
    for (const auto &row : container_of_rows) {
      write_row(row);
    }
  }
};

} // namespace csv2
