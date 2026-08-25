"""Unit tests for tools/tool_cache.py — the short-TTL tool-call result cache
(item 6 of the agent-quality improvements)."""
import time
import unittest

from tools.tool_cache import cached_call, clear_cache, get_cached, set_cached


class TestToolCache(unittest.TestCase):
    def setUp(self):
        clear_cache()

    def test_set_and_get_cached(self):
        set_cached("web_search", {"query": "python jobs"}, {"results": ["a"]})
        self.assertEqual(get_cached("web_search", {"query": "python jobs"}), {"results": ["a"]})

    def test_different_args_are_different_cache_entries(self):
        set_cached("web_search", {"query": "python jobs"}, "result_a")
        self.assertIsNone(get_cached("web_search", {"query": "java jobs"}))

    def test_expired_entry_returns_none(self):
        set_cached("web_search", {"query": "x"}, "result", ttl_seconds=0)
        time.sleep(0.05)
        self.assertIsNone(get_cached("web_search", {"query": "x"}))

    def test_cached_call_second_call_is_a_cache_hit_and_skips_fn(self):
        call_count = {"n": 0}

        def expensive():
            call_count["n"] += 1
            return "expensive_result"

        result1, hit1 = cached_call("browser_extract", {"instruction": "get jobs"}, expensive)
        result2, hit2 = cached_call("browser_extract", {"instruction": "get jobs"}, expensive)

        self.assertEqual(result1, "expensive_result")
        self.assertEqual(result2, "expensive_result")
        self.assertFalse(hit1)
        self.assertTrue(hit2)
        self.assertEqual(call_count["n"], 1)  # fn only actually ran once

    def test_cached_call_different_tool_name_is_not_shared(self):
        cached_call("tool_a", {"q": "same"}, lambda: "result_a")
        result_b, hit_b = cached_call("tool_b", {"q": "same"}, lambda: "result_b")
        self.assertEqual(result_b, "result_b")
        self.assertFalse(hit_b)


if __name__ == "__main__":
    unittest.main()
