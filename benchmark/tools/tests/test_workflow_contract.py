from __future__ import annotations

import unittest

from _support import BENCHMARK_DIR


class WorkflowContractTests(unittest.TestCase):
    def test_ctest_junit_paths_are_relative_to_the_test_directory(self) -> None:
        workflow_directory = BENCHMARK_DIR.parent / ".github" / "workflows"
        expectations = {
            "linux.yml": {"--output-junit ctest.xml": 4},
            "windows.yml": {"--output-junit ctest.xml": 1},
            "macos.yml": {"--output-junit ctest.xml": 1},
            "fuzz-benchmark.yml": {
                "--output-junit fuzz-smoke.xml": 1,
                "--output-junit benchmark-checksum.xml": 2,
            },
            "full.yml": {"--output-junit full-ctest.xml": 3},
            "perf.yml": {
                '--output-junit "$GITHUB_WORKSPACE/build-perf/reports/benchmark-checksum.xml"': 2
            },
        }

        for filename, expected_tokens in expectations.items():
            workflow = (workflow_directory / filename).read_text(encoding="utf-8")
            for token, count in expected_tokens.items():
                self.assertEqual(workflow.count(token), count, filename)
            self.assertNotRegex(
                workflow,
                r"--output-junit\s+build(?:-[^/\s]+)?/",
                filename,
            )

    def test_perf_jobs_checkout_and_verify_the_candidate_revision(self) -> None:
        workflow = (
            BENCHMARK_DIR.parent / ".github" / "workflows" / "perf.yml"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            workflow.count("ref: ${{ inputs.candidate_ref || github.sha }}"), 2
        )
        self.assertEqual(
            workflow.count("candidate=$(git rev-parse 'HEAD^{commit}')"), 2
        )
        self.assertEqual(
            workflow.count('test "$candidate" = "$requested_candidate"'), 2
        )
        self.assertIn("csv2_benchmark_allocations --clean-first", workflow)
        self.assertIn("--post-build-command", workflow)
        self.assertIn(
            '"cmake --build build-current --target csv2_benchmark_corpus"',
            workflow,
        )
        self.assertIn("--clean-first --parallel", workflow)
        self.assertLess(
            workflow.index("--post-build-command"),
            workflow.index("Verify controlled corpus artifact"),
        )
        self.assertLess(
            workflow.index("Verify controlled corpus artifact"),
            workflow.index("Upload controlled evidence"),
        )


if __name__ == "__main__":
    unittest.main()
