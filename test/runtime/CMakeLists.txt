csv2_declare_test_domain(
  ID reader.scan
  SOURCES runtime/reader/scan.cpp
  MIN_STANDARD 11
  PROFILES quick full perf
  LABELS reader runtime
  TIMEOUT 20)
