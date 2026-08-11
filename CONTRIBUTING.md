# Contributing
Contributions are welcomed. Open a pull-request or an issue.

## Repository workflow

Use an out-of-source build directory. Common local build trees such as
`build/`, `build-*`, `cmake-build-*`, and `out/` are ignored, while the source
directories `test/` and `benchmark/` remain tracked.

```bash
cmake -S . -B build -DCSV2_BUILD_TESTS=ON \
  -DCMAKE_COMPILE_WARNING_AS_ERROR=ON
cmake --build build --config Debug
ctest --test-dir build -C Debug --output-on-failure
```

The behavioral suite is compiled against both the modular headers and the
single-header distribution in C++11, C++14, C++17, and, when advertised by
CMake and the compiler, C++20 and C++23. Public-header self-containment is
checked in C++11 and C++17. To reproduce the modern-standard CI gate on a
current toolchain, configure with
`-DCSV2_REQUIRE_MODERN_STANDARD_TESTS=ON` as well.

Sanitizer behavior is compiler-specific. `CSV2_ENABLE_SANITIZERS=ON` selects
ASan and UBSan for GCC, GNU-style Clang, and AppleClang, AddressSanitizer for
MSVC, and ASan plus UBSan for x64 Clang-CL. Clang-CL sanitizer builds require a
non-Debug CRT configuration and the compiler-rt libraries distributed with the
selected compiler; CI uses Release. Its UBSan configuration excludes only the
`object-size` check because that check diagnoses the MSVC standard library's
`forward_list` pseudo-node implementation. Linux enables leak detection through
ASan, while Windows disables it because LeakSanitizer is not supported there.
See the root README for the exact CI matrix.

## Source and generated header

Make implementation changes in `include/csv2/`. The single-header file is a
generated distribution artifact and must be regenerated after a modular-header
change:

```bash
python3 utils/amalgamate/amalgamate.py -c single_include.json -s .
git diff --exit-code -- single_include/csv2/csv2.hpp
```

Add behavioral coverage to the existing `test/main.cpp` suite unless a test
genuinely requires a different translation unit. Keep public behavior and
lifetime requirements synchronized in `README.md` and any relevant tracked
component README.

## Local working notes

Temporary, draft, planning, and research notes are intentionally local and
excluded from version control. Keep durable user-facing or contributor-facing
documentation in tracked top-level or component README files instead.

## Code of conduct
This project adheres to the [Open Code of Conduct][code-of-conduct]. By participating, you are expected to honor this code.

[code-of-conduct]: https://github.com/spotify/code-of-conduct/blob/master/code-of-conduct.md
