"""Unit tests for agent/verification.py — the deterministic task-completion
verification layer that cross-checks a self-reported finish_task/finish_sandbox_task
claim against what was actually extracted, per the "TASK VERIFICATION" stage of the
tool-availability/execution/result/completion status taxonomy.
"""
import unittest

from agent.verification import (
    count_extracted_items,
    extract_requested_count,
    verify_completion_claim,
)


class TestExtractRequestedCount(unittest.TestCase):
    def test_parses_n_latest_jobs(self):
        self.assertEqual(extract_requested_count("Find 5 latest jobs on Naukri.com"), 5)

    def test_parses_top_n(self):
        self.assertEqual(extract_requested_count("top 3 articles about AI"), 3)

    def test_does_not_confuse_time_window_with_count(self):
        # "24 hours" must NOT be parsed as "24 items requested".
        self.assertIsNone(extract_requested_count("find jobs posted in the last 24 hours"))

    def test_no_count_present(self):
        self.assertIsNone(extract_requested_count("check whether the site is reachable"))


class TestCountExtractedItems(unittest.TestCase):
    def test_counts_numbered_list_lines(self):
        tool_results = [{
            "tool": "Browser Data Extraction",
            "output": "1. Job A\n2. Job B\n3. Job C",
        }]
        self.assertEqual(count_extracted_items(tool_results), 3)

    def test_counts_bullet_lines_via_toolname_key(self):
        tool_results = [{
            "toolName": "Browser Data Extraction",
            "data": {"output": "- Job A\n- Job B"},
        }]
        self.assertEqual(count_extracted_items(tool_results), 2)

    def test_ignores_unrelated_tools(self):
        tool_results = [{"tool": "Web Search Engine", "output": "1. foo\n2. bar"}]
        self.assertEqual(count_extracted_items(tool_results), 0)


class TestVerifyCompletionClaim(unittest.TestCase):
    def test_no_requested_count_passes_through_unchanged(self):
        status, verified, requested, note = verify_completion_claim(
            user_prompt="check if Naukri is reachable",
            tool_results=[],
            claimed_status="completed",
        )
        self.assertEqual(status, "completed")
        self.assertIsNone(note)

    def test_downgrades_completed_to_partial_when_zero_extracted(self):
        status, verified, requested, note = verify_completion_claim(
            user_prompt="Find 5 latest jobs on Naukri.com",
            tool_results=[],
            claimed_status="completed",
        )
        self.assertEqual(status, "partial")
        self.assertEqual(verified, 0)
        self.assertEqual(requested, 5)
        self.assertIsNotNone(note)

    def test_downgrades_completed_to_partial_when_undercounted(self):
        tool_results = [{
            "tool": "Browser Data Extraction",
            "output": "1. Job A\n2. Job B",
        }]
        status, verified, requested, note = verify_completion_claim(
            user_prompt="Find 5 latest jobs on Naukri.com",
            tool_results=tool_results,
            claimed_status="completed",
        )
        self.assertEqual(status, "partial")
        self.assertEqual(verified, 2)
        self.assertEqual(requested, 5)
        self.assertIsNotNone(note)

    def test_stays_completed_when_counts_match(self):
        tool_results = [{
            "tool": "Browser Data Extraction",
            "output": "1. Job A\n2. Job B\n3. Job C\n4. Job D\n5. Job E",
        }]
        status, verified, requested, note = verify_completion_claim(
            user_prompt="Find 5 latest jobs on Naukri.com",
            tool_results=tool_results,
            claimed_status="completed",
        )
        self.assertEqual(status, "completed")
        self.assertEqual(verified, 5)
        self.assertIsNone(note)

    def test_stays_completed_when_extracted_exceeds_requested(self):
        tool_results = [{
            "tool": "Browser Data Extraction",
            "output": "\n".join(f"{i}. Job {i}" for i in range(1, 8)),
        }]
        status, verified, requested, note = verify_completion_claim(
            user_prompt="Find 5 latest jobs on Naukri.com",
            tool_results=tool_results,
            claimed_status="completed",
        )
        self.assertEqual(status, "completed")
        self.assertIsNone(note)

    def test_adjusts_overclaimed_verified_count_without_status_downgrade(self):
        tool_results = [{
            "tool": "Browser Data Extraction",
            "output": "1. Job A\n2. Job B\n3. Job C",
        }]
        status, verified, requested, note = verify_completion_claim(
            user_prompt="Find 3 latest jobs on Naukri.com",
            tool_results=tool_results,
            claimed_status="partial",
            claimed_verified_count=10,
        )
        self.assertEqual(status, "partial")
        self.assertEqual(verified, 3)
        self.assertIsNotNone(note)

    def test_sandbox_tool_labels_are_recognized_by_default(self):
        tool_results = [{
            "toolName": "Sandbox File Read",
            "data": {"output": "1. file_a.py\n2. file_b.py"},
        }]
        status, verified, requested, note = verify_completion_claim(
            user_prompt="list 2 items in the project",
            tool_results=tool_results,
            claimed_status="completed",
        )
        self.assertEqual(status, "completed")
        self.assertEqual(verified, 2)


if __name__ == "__main__":
    unittest.main()
