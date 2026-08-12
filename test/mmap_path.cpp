#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/reader.hpp>
#endif

#include <cstddef>
#include <string>
#include <type_traits>
#include <vector>
#if CSV2_HAS_MEMORY_RESOURCE
#include <memory_resource>
#endif

template <typename...> struct make_void {
  typedef void type;
};
template <typename... Types> using void_t = typename make_void<Types...>::type;

template <typename Path, typename Reader = csv2::Reader<>, typename = void>
struct reader_accepts_path : std::false_type {};
template <typename Path, typename Reader>
struct reader_accepts_path<Path, Reader,
                           void_t<decltype(std::declval<Reader &>().mmap(
                               std::declval<Path>(), std::declval<std::error_code &>()))>>
    : std::true_type {};

#if CSV2_HAS_EXPECTED
template <typename Path, typename Reader = csv2::Reader<>, typename = void>
struct reader_accepts_expected_path : std::false_type {};
template <typename Path, typename Reader>
struct reader_accepts_expected_path<
    Path, Reader, void_t<decltype(std::declval<Reader &>().mmap_expected(std::declval<Path>()))>>
    : std::true_type {};
#endif

#if CSV2_HAS_MMAP
static_assert(mio::detail::is_path<const char *>::value,
              "NUL-terminated narrow paths must be accepted");
static_assert(mio::detail::is_path<char *>::value,
              "mutable NUL-terminated narrow paths must be accepted");
static_assert(mio::detail::is_path<char[4]>::value, "narrow arrays must be accepted");
static_assert(mio::detail::is_path<const char[4]>::value, "const narrow arrays must be accepted");
static_assert(mio::detail::is_path<std::string>::value, "std::string paths must be accepted");
static_assert(!mio::detail::is_path<char>::value, "a scalar character is not a path");
static_assert(!mio::detail::is_path<const char>::value, "a const scalar character is not a path");
static_assert(!mio::detail::is_path<volatile char>::value,
              "a volatile scalar character is not a path");
static_assert(!mio::detail::is_path<volatile char *>::value,
              "a volatile character pointer cannot be converted to a C-string path");
static_assert(!mio::detail::is_path<volatile char[4]>::value,
              "a volatile character array cannot be converted to a C-string path");
static_assert(!mio::detail::is_path<const volatile char[4]>::value,
              "a volatile character array cannot be converted to a C-string path");
static_assert(!mio::detail::is_path<std::nullptr_t>::value, "nullptr alone is not a path type");
static_assert(mio::detail::is_range_path<std::vector<char>>::value,
              "a sized character range may be checked for a single trailing NUL");
static_assert(reader_accepts_path<const char *>::value,
              "Reader must expose its C-string mmap overload");
static_assert(reader_accepts_path<std::string>::value,
              "Reader must expose its std::string mmap overload");
#if CSV2_HAS_MEMORY_RESOURCE
static_assert(mio::detail::is_path<std::pmr::string>::value,
              "basic_string paths with custom allocators must be accepted");
static_assert(reader_accepts_path<std::pmr::string>::value,
              "Reader must expose its custom-allocator basic_string mmap overload");
#endif
static_assert(!reader_accepts_path<char>::value,
              "Reader must reject scalar characters before instantiating mio");
static_assert(!reader_accepts_path<const char>::value,
              "Reader must reject const scalar characters before instantiating mio");
static_assert(!reader_accepts_path<volatile char>::value,
              "Reader must reject volatile scalar characters before instantiating mio");
static_assert(!reader_accepts_path<volatile char *>::value,
              "Reader must reject volatile character pointers before instantiating mio");
static_assert(reader_accepts_path<std::vector<char>>::value,
              "Reader must preserve the legacy sized character-range path overload");
static_assert(reader_accepts_path<mio::mmap_source::handle_type>::value,
              "Reader must preserve the caller-owned native handle overload");

#if defined(_WIN32)
static_assert(mio::detail::is_path<const wchar_t *>::value,
              "NUL-terminated wide paths must be accepted on Windows");
static_assert(mio::detail::is_path<std::wstring>::value,
              "std::wstring paths must be accepted on Windows");
static_assert(reader_accepts_path<const wchar_t *>::value,
              "Reader must expose its wide C-string mmap overload on Windows");
static_assert(reader_accepts_path<std::wstring>::value,
              "Reader must expose its std::wstring mmap overload on Windows");
static_assert(!mio::detail::is_path<wchar_t>::value, "a scalar wide character is not a path");
static_assert(!mio::detail::is_path<const wchar_t>::value,
              "a const scalar wide character is not a path");
static_assert(!mio::detail::is_path<volatile wchar_t>::value,
              "a volatile scalar wide character is not a path");
static_assert(!mio::detail::is_path<volatile wchar_t *>::value,
              "a volatile wide character pointer is not a path");
static_assert(!mio::detail::is_path<volatile wchar_t[4]>::value,
              "a volatile wide character array is not a path");
#endif

#if CSV2_HAS_STRING_VIEW
#include <string_view>
struct CustomCharTraits : std::char_traits<char> {};
using CustomStringView = std::basic_string_view<char, CustomCharTraits>;
static_assert(!mio::detail::is_path<std::string_view>::value,
              "string_view cannot guarantee NUL termination");
static_assert(!reader_accepts_path<std::string_view>::value,
              "Reader must reject string_view paths");
static_assert(!mio::detail::is_range_path<CustomStringView>::value,
              "every narrow basic_string_view specialization must be rejected");
static_assert(!reader_accepts_path<CustomStringView>::value,
              "Reader must reject custom-traits narrow string_view paths");
#if CSV2_HAS_EXPECTED
static_assert(!reader_accepts_expected_path<CustomStringView>::value,
              "Reader expected adapters must reject custom-traits string_view paths");
#endif
#if defined(_WIN32)
struct CustomWideCharTraits : std::char_traits<wchar_t> {};
using CustomWideStringView = std::basic_string_view<wchar_t, CustomWideCharTraits>;
static_assert(!mio::detail::is_range_path<CustomWideStringView>::value,
              "every wide basic_string_view specialization must be rejected on Windows");
static_assert(!reader_accepts_path<CustomWideStringView>::value,
              "Reader must reject custom-traits wide string_view paths on Windows");
#if CSV2_HAS_EXPECTED
static_assert(!reader_accepts_expected_path<CustomWideStringView>::value,
              "Reader expected adapters must reject custom-traits wide string_view paths");
#endif
#endif
#endif

#if CSV2_HAS_FILESYSTEM
#include <filesystem>
static_assert(mio::detail::is_path<std::filesystem::path>::value,
              "filesystem::path must be accepted when available");
static_assert(reader_accepts_path<std::filesystem::path>::value,
              "Reader must expose its filesystem path mmap overload");
#endif

#else
static_assert(!reader_accepts_path<const char *>::value,
              "Reader must omit mmap overloads when mapping is unavailable");
#endif
