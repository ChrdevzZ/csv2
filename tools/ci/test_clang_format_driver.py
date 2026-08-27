from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_SCRIPT = Path(__file__).parents[2] / "clang-format.bash"


class ClangFormatDriverTests(unittest.TestCase):
    def run_check(self, root: Path) -> set[str]:
        script = root / "clang-format.bash"
        shutil.copyfile(SOURCE_SCRIPT, script)
        log = root / "clang-format-arguments.jsonl"
        formatter = root / "clang-format"
        formatter.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['CSV2_FORMAT_TEST_LOG'], 'a', encoding='utf-8') as stream:\n"
            "    json.dump(sys.argv[1:], stream)\n"
            "    stream.write('\\n')\n",
            encoding="utf-8",
        )
        formatter.chmod(0o755)

        environment = os.environ.copy()
        environment["CLANG_FORMAT"] = str(formatter)
        environment["CSV2_FORMAT_TEST_LOG"] = str(log)
        environment["PATH"] = f"{root}{os.pathsep}{environment['PATH']}"
        completed = subprocess.run(
            ["bash", str(script), "--check"],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        self.assertTrue(log.is_file(), "formatter was not invoked")
        arguments = [
            argument
            for line in log.read_text(encoding="utf-8").splitlines()
            for argument in json.loads(line)
        ]
        self.assertIn("--dry-run", arguments)
        self.assertIn("--Werror", arguments)
        self.assertNotIn("-i", arguments)
        return {
            argument.removeprefix("./")
            for argument in arguments
            if argument.endswith((".cpp", ".h", ".hpp"))
        }

    def test_check_mode_formats_only_tracked_first_party_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            included = {
                "benchmark/current/main.cpp",
                "include/csv2/reader.hpp",
                "test/platform/windows.h",
                "test/runtime/domain.hpp",
                "test/runtime/path with spaces.cpp",
            }
            excluded = {
                "include/csv2/mio.hpp",
                "single_include/csv2/csv2.hpp",
                "third_party/vendor.cpp",
            }
            deleted = "test/runtime/deleted.cpp"
            for relative in sorted(included | excluded | {deleted}):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("int value;\n", encoding="utf-8")

            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "add", "--all"], cwd=root, check=True)
            (root / deleted).unlink()
            self.assertEqual(self.run_check(root), included)

    def test_check_mode_works_without_git_metadata_in_source_archives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                "benchmark/current/main.cpp",
                "include/csv2/mio.hpp",
                "include/csv2/reader.hpp",
                "test/platform/windows.h",
                "test/runtime/domain.hpp",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("int value;\n", encoding="utf-8")
            self.assertEqual(
                self.run_check(root),
                {
                    "benchmark/current/main.cpp",
                    "include/csv2/reader.hpp",
                    "test/platform/windows.h",
                    "test/runtime/domain.hpp",
                },
            )


if __name__ == "__main__":
    unittest.main()
