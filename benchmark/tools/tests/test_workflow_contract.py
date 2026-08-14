from __future__ import annotations

import unittest

from _support import BENCHMARK_DIR


class WorkflowContractTests(unittest.TestCase):
    def test_ctest_junit_paths_are_relative_to_the_test_directory(self) -> None:
        workflow_directory = BENCHMARK_DIR.parent / ".github" / "workflows"
        expectations = {
            "linux.yml": {
                "--output-junit ctest.xml": 4,
                "--output-junit observer-lto.xml": 1,
            },
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

    def test_perf_jobs_use_owned_builds_for_exact_revisions(self) -> None:
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
        self.assertEqual(workflow.count("benchmark/run_suite.py"), 4)
        self.assertEqual(workflow.count("benchmark/collect_metrics.py"), 2)
        self.assertEqual(workflow.count("--repository ."), 6)
        self.assertEqual(workflow.count("--candidate-ref \"$CANDIDATE_SHA\""), 6)
        self.assertEqual(workflow.count("--baseline-ref \"$BASELINE_SHA\""), 2)
        self.assertEqual(workflow.count("--baseline-ref \"$CANDIDATE_SHA\""), 2)
        self.assertEqual(workflow.count("--compiler-executable"), 6)
        self.assertEqual(workflow.count("--build-root"), 6)
        self.assertNotIn("git archive", workflow)
        self.assertNotIn("common_driver.cpp", workflow)
        self.assertNotIn("--external-artifacts", workflow)
        self.assertNotIn("--build-command", workflow)
        self.assertNotIn("--post-build-command", workflow)
        self.assertEqual(workflow.count("Verify controlled evidence bundle"), 1)
        self.assertLess(
            workflow.index("Verify controlled evidence bundle"),
            workflow.index("Upload controlled evidence"),
        )

    def test_all_direct_ci_verification_configures_require_python_audits(self) -> None:
        workflow_directory = BENCHMARK_DIR.parent / ".github" / "workflows"
        expected_configures = {
            "linux.yml": 4,
            "windows.yml": 1,
            "macos.yml": 1,
            "fuzz-benchmark.yml": 2,
            "full.yml": 4,
        }
        for filename, configure_count in expected_configures.items():
            workflow = (workflow_directory / filename).read_text(encoding="utf-8")
            self.assertEqual(workflow.count("cmake -S . -B"), configure_count, filename)
            self.assertEqual(
                workflow.count("-DCSV2_REQUIRE_PYTHON_AUDITS=ON"),
                configure_count,
                filename,
            )

        perf = (workflow_directory / "perf.yml").read_text(encoding="utf-8")
        self.assertNotIn("cmake -S . -B", perf)
        self.assertIn("benchmark/collect_metrics.py", perf)

    def test_fuzz_benchmark_builds_observer_audit_for_each_checksum_suite(self) -> None:
        workflow = (
            BENCHMARK_DIR.parent / ".github" / "workflows" / "fuzz-benchmark.yml"
        ).read_text(encoding="utf-8")

        self.assertEqual(workflow.count("csv2_benchmark_observer_audit"), 2)
        self.assertEqual(workflow.count("-L benchmark-checksum"), 2)


if __name__ == "__main__":
    unittest.main()
