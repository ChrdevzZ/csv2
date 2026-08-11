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
CMake and the compiler, C++20, C++23, and C++26. C++26 requires CMake 3.30 or
newer and is a forward-compatibility build mode, not a claim of complete
compiler or standard-library conformance. Public-header self-containment is
checked in C++11 and C++17. To reproduce the CI standard gates on a current
toolchain, configure with `-DCSV2_REQUIRE_MODERN_STANDARD_TESTS=ON`; add
`-DCSV2_REQUIRE_CXX26_TESTS=ON` only when CMake reports `cxx_std_26` for the
selected compiler.

Sanitizer behavior is compiler-specific. `CSV2_ENABLE_SANITIZERS=ON` selects
ASan and UBSan for GCC, GNU-style Clang, and AppleClang, AddressSanitizer for
MSVC, and ASan plus UBSan for x64 Clang-CL. Clang-CL sanitizer builds require a
non-Debug CRT configuration and the compiler-rt libraries distributed with the
selected compiler; CI uses Release. Its UBSan configuration excludes only the
`object-size` check because that check diagnoses the MSVC standard library's
`forward_list` pseudo-node implementation. Linux enables leak detection through
ASan, while Windows disables it because LeakSanitizer is not supported there.
See the root README for the current CI matrix.

CI uses stable hosted images and stable runner/distribution toolchains. The
current enforced lines are GCC 14 and Clang/libc++ 18 on Linux, MSVC 19.51 and
Clang-CL 22.1 on Windows, and AppleClang 21 on macOS. CI verifies compiler ID
and version during CMake configuration. Do not replace these with preview
runners, compiler snapshots, PPAs, or nightly repositories merely to obtain a
newer version. Linux Clang has separate Release/no-sanitizer and
Debug/ASan+UBSan jobs; both must remain present when changing the matrix.

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
