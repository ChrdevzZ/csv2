#include <csv2/reader.hpp>

#include <string>
#include <type_traits>
#include <vector>

template <typename...> struct make_void { typedef void type; };
template <typename... Types> using void_t = typename make_void<Types...>::type;

template <typename Path, typename = void> struct reader_accepts_path : std::false_type {};
template <typename Path>
struct reader_accepts_path<
    Path, void_t<decltype(std::declval<csv2::Reader<> &>().mmap(
              std::declval<Path>(), std::declval<std::error_code &>()))>> : std::true_type {};

static_assert(mio::detail::is_path<const char *>::value,
              "NUL-terminated narrow paths must be accepted");
static_assert(mio::detail::is_path<std::string>::value,
              "std::string paths must be accepted");
static_assert(!mio::detail::is_path<std::vector<char>>::value,
              "arbitrary contiguous storage is not a path");
static_assert(reader_accepts_path<const char *>::value,
              "Reader must expose its C-string mmap overload");
static_assert(reader_accepts_path<std::string>::value,
              "Reader must expose its std::string mmap overload");
static_assert(!reader_accepts_path<std::vector<char>>::value,
              "Reader must reject arbitrary contiguous storage");

#if CSV2_HAS_STRING_VIEW
#include <string_view>
static_assert(!mio::detail::is_path<std::string_view>::value,
              "string_view cannot guarantee NUL termination");
static_assert(!reader_accepts_path<std::string_view>::value,
              "Reader must reject string_view paths");
#endif

#if CSV2_HAS_FILESYSTEM
#include <filesystem>
static_assert(mio::detail::is_path<std::filesystem::path>::value,
              "filesystem::path must be accepted when available");
static_assert(reader_accepts_path<std::filesystem::path>::value,
              "Reader must expose its filesystem path mmap overload");
#endif
