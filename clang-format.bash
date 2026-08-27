#!/usr/bin/env bash
set -euo pipefail

mode="${1:---write}"
case "$mode" in
  --check)
    format_arguments=(-style=file --dry-run --Werror)
    ;;
  --write)
    format_arguments=(-style=file -i)
    ;;
  *)
    echo "usage: $0 [--check|--write]" >&2
    exit 2
    ;;
esac

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$repository_root"

formatter="${CLANG_FORMAT:-clang-format}"
if ! command -v "$formatter" >/dev/null 2>&1; then
  echo "clang-format executable not found: $formatter" >&2
  exit 1
fi

files=()
git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
while IFS= read -r -d '' file; do
  if [[ -f "$file" ]]; then
    files+=("$file")
  fi
done < <(
  if [[ -n "$git_root" && "$(cd -- "$git_root" && pwd -P)" == "$repository_root" ]]; then
    git ls-files -z -- '*.cpp' '*.h' '*.hpp' \
      ':!third_party/**' ':!single_include/**' ':!include/csv2/mio.hpp'
  else
    find include benchmark test -type f \
      \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) \
      ! -path 'include/csv2/mio.hpp' -print0
  fi
)

if ((${#files[@]})); then
  "$formatter" "${format_arguments[@]}" "${files[@]}"
fi
