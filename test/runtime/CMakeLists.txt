csv2_declare_test_domain(
  ID reader.scan
  SOURCES runtime/reader/scan.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime
  TIMEOUT 20)

csv2_declare_test_domain(
  ID reader.iterate
  SOURCES runtime/reader/iterate.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime iterator
  TIMEOUT 20)

csv2_declare_test_domain(
  ID reader.extract
  SOURCES runtime/reader/extract.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime extraction
  TIMEOUT 20)

csv2_declare_test_domain(
  ID reader.source
  SOURCES runtime/reader/source.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime ownership
  TIMEOUT 30)

csv2_declare_test_domain(
  ID reader.validate
  SOURCES runtime/reader/validate.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime validation
  TIMEOUT 20)

csv2_declare_test_domain(
  ID reader.convert
  SOURCES runtime/reader/convert.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime conversion
  TIMEOUT 20)

csv2_declare_test_domain(
  ID reader.ranges
  SOURCES runtime/reader/ranges.cpp
  MIN_STANDARD 20
  PROFILES quick full perf
  LABELS reader runtime ranges
  TIMEOUT 20)

csv2_declare_test_domain(
  ID reader.index
  SOURCES runtime/reader/index.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime index
  TIMEOUT 20)

csv2_declare_test_domain(
  ID writer.raw
  SOURCES runtime/writer/raw.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS writer runtime
  TIMEOUT 20)

csv2_declare_test_domain(
  ID writer.escape
  SOURCES runtime/writer/escape.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS writer runtime escaping
  TIMEOUT 20)

csv2_declare_test_domain(
  ID writer.stream
  SOURCES runtime/writer/stream.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS writer runtime stream
  TIMEOUT 20)

csv2_declare_test_domain(
  ID mio.mapping
  SOURCES runtime/mio/mapping.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  REQUIRES mmap
  LABELS mio runtime mapping
  TIMEOUT 30)

csv2_declare_test_domain(
  ID property.roundtrip
  SOURCES runtime/property/roundtrip.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS property runtime roundtrip
  TIMEOUT 30)
