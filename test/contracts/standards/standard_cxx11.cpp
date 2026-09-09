#if defined(CSV2_TEST_SINGLE_HEADER)
#include <csv2/csv2.hpp>
#else
#include <csv2/errors.hpp>
#include <csv2/reader.hpp>
#include <csv2/writer.hpp>
#endif

#include <iterator>
#include <string>
#include <type_traits>
#include <vector>

using cxx11_reader = csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>,
                                  csv2::first_row_is_header<false>>;
using cxx11_header_reader =
    csv2::Reader<csv2::delimiter<','>, csv2::quote_character<'"'>, csv2::first_row_is_header<true>>;
using cxx11_alternate_reader = csv2::Reader<csv2::delimiter<'|'>, csv2::quote_character<'"'>,
                                            csv2::first_row_is_header<false>>;
static_assert(!std::is_copy_constructible<cxx11_reader>::value,
              "Reader source ownership must remain move-only");
static_assert(std::is_default_constructible<cxx11_reader::RowIterator>::value,
              "C++11 iterator algorithms require a default constructor");
static_assert(!std::is_same<cxx11_reader::Row, cxx11_header_reader::Row>::value,
              "Reader specializations must retain distinct nested Row types");
static_assert(!std::is_same<cxx11_reader::Cell, cxx11_header_reader::Cell>::value,
              "Reader specializations must retain distinct nested Cell types");
static_assert(!std::is_same<cxx11_reader::Cell, cxx11_alternate_reader::Cell>::value,
              "delimiter specializations must retain distinct nested Cell types");
static_assert(
    !std::is_same<cxx11_reader::Row::CellIterator, cxx11_header_reader::Row::CellIterator>::value,
    "Reader specializations must retain distinct nested CellIterator types");
static_assert(
    std::is_same<typename std::iterator_traits<cxx11_reader::Row::CellIterator>::value_type,
                 cxx11_reader::Cell>::value,
    "Row::CellIterator must dereference to the corresponding nested Cell");
static_assert(std::is_same<decltype(*std::declval<cxx11_reader::Row::CellIterator &>()),
                           cxx11_reader::Cell>::value,
              "Row::CellIterator dereference must preserve the nested Cell type");
static_assert(std::is_constructible<cxx11_reader::Row::CellIterator, const char *, std::size_t,
                                    std::size_t, std::size_t>::value,
              "the legacy four-argument CellIterator constructor must remain source-compatible");
static_assert(
    !std::is_same<typename std::iterator_traits<cxx11_reader::RowIterator>::pointer, void>::value,
    "RowIterator must provide classic arrow access");
static_assert(!std::is_same<typename std::iterator_traits<cxx11_reader::Row::CellIterator>::pointer,
                            void>::value,
              "CellIterator must provide classic arrow access");
static_assert(
    std::is_same<typename std::iterator_traits<cxx11_reader::RowIndex::iterator>::iterator_category,
                 std::input_iterator_tag>::value,
    "a prvalue RowIndex iterator must not claim the classic random-access category");
static_assert(std::is_same<decltype(&cxx11_reader::Row::address),
                           const char *(cxx11_reader::Row::*)() const>::value,
              "the historical Row address member must remain owned by Reader::Row");
static_assert(std::is_same<decltype(&cxx11_reader::Row::length),
                           std::size_t (cxx11_reader::Row::*)() const>::value,
              "the historical Row length member must remain owned by Reader::Row");
static_assert(std::is_same<decltype(&cxx11_reader::Row::template read_raw_value<std::string>),
                           void (cxx11_reader::Row::*)(std::string &) const>::value,
              "the historical Row extraction member must remain owned by Reader::Row");
static_assert(std::is_same<decltype(&cxx11_reader::Cell::template read_raw_value<std::string>),
                           void (cxx11_reader::Cell::*)(std::string &) const>::value,
              "the historical Cell raw extraction member must remain owned by Reader::Cell");
static_assert(std::is_same<decltype(&cxx11_reader::Cell::template read_value<std::string>),
                           void (cxx11_reader::Cell::*)(std::string &) const>::value,
              "the historical Cell decoded extraction member must remain owned by Reader::Cell");

template <template <class, class> class WriterTemplate> struct cxx11_writer_template_contract {};
using cxx11_writer_template = cxx11_writer_template_contract<csv2::Writer>;
using cxx11_writer = csv2::Writer<csv2::delimiter<','>, std::ofstream>;
using cxx11_lf_writer = csv2::Writer<csv2::delimiter<'\n'>, std::ofstream>;
using cxx11_cr_writer = csv2::Writer<csv2::delimiter<'\r'>, std::ofstream>;
using cxx11_lf_escaping_writer = csv2::EscapingWriter<csv2::delimiter<'\n'>, std::ofstream>;
using cxx11_cr_escaping_writer = csv2::EscapingWriter<csv2::delimiter<'\r'>, std::ofstream>;
static_assert(std::is_convertible<std::ofstream &, cxx11_writer>::value,
              "the historical Writer stream constructor must remain implicit");
static_assert(std::is_constructible<cxx11_lf_writer, std::ofstream &>::value,
              "Writer must retain the historical LF delimiter instantiation");
static_assert(std::is_constructible<cxx11_cr_writer, std::ofstream &>::value,
              "Writer must retain the historical CR delimiter instantiation");
static_assert(std::is_constructible<cxx11_lf_escaping_writer, std::ofstream &>::value,
              "escaping writers must preserve the Writer delimiter type domain");
static_assert(std::is_constructible<cxx11_cr_escaping_writer, std::ofstream &>::value,
              "escaping writers must preserve the Writer delimiter type domain");
static_assert(std::is_same<decltype(&cxx11_writer::close), void (cxx11_writer::*)()>::value,
              "the historical Writer close member must remain owned by Writer");
#if CSV2_HAS_MMAP
static_assert(mio::detail::is_range_path<std::vector<char>>::value,
              "C++11 sized char paths remain available with runtime termination checks");
static_assert(
    std::is_same<decltype(std::declval<cxx11_reader &>().mmap(std::declval<std::vector<char> &>())),
                 bool>::value,
    "C++11 Reader preserves its sized char path source contract");
#endif

void csv2_cxx11_nested_row_identity(class cxx11_reader::Row) {}
void csv2_cxx11_nested_row_identity(class cxx11_header_reader::Row) {}

void csv2_cxx11_nested_cell_identity(class cxx11_reader::Cell) {}
void csv2_cxx11_nested_cell_identity(class cxx11_header_reader::Cell) {}
void csv2_cxx11_nested_cell_identity(class cxx11_alternate_reader::Cell) {}

void csv2_cxx11_contract() {
  cxx11_reader reader;
  std::string input(80, '1');
  input[1] = ',';
  csv2::parse_error parse_error;
  csv2::conversion_error conversion_error;
  int value = 0;
  if (reader.parse(input) && reader.validate(parse_error)) {
    const std::size_t row_size = reader.begin()->raw_size();
    const std::size_t cell_size = (*reader.begin()).begin()->raw_size();
    const std::size_t indexed_size = reader.index().begin()->raw_size();
    (void)row_size;
    (void)cell_size;
    (void)indexed_size;
    (*(*reader.begin()).begin()).try_parse(value, conversion_error);
  }
}
