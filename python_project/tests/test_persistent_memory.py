"""Unit tests for memory/persistent_store.py — the durable, cross-session,
per-user long-term memory store (item 4 of the agent-quality improvements)."""
import os
import tempfile
import unittest
from unittest.mock import patch

import memory.persistent_store as store


class TestPersistentMemoryStore(unittest.TestCase):
    def setUp(self):
        # Use an isolated temp DB file per test so tests don't interfere with
        # each other or with any real dev-time data.
        self._tmp_dir = tempfile.mkdtemp()
        self._tmp_db = os.path.join(self._tmp_dir, "test_user_memory.sqlite3")
        self._patcher = patch.object(store, "_DB_PATH", self._tmp_db)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_remember_and_get_facts(self):
        store.remember_fact(1, "job_preference", "Remote jobs in Bangalore")
        facts = store.get_facts(1)
        self.assertEqual(facts.get("job_preference"), "Remote jobs in Bangalore")

    def test_facts_are_scoped_per_user(self):
        store.remember_fact(1, "language", "Python")
        store.remember_fact(2, "language", "Go")
        self.assertEqual(store.get_facts(1)["language"], "Python")
        self.assertEqual(store.get_facts(2)["language"], "Go")

    def test_updating_existing_key_overwrites_value(self):
        store.remember_fact(1, "budget", "1000 USD")
        store.remember_fact(1, "budget", "1500 USD")
        self.assertEqual(store.get_facts(1)["budget"], "1500 USD")

    def test_forget_fact_removes_it(self):
        store.remember_fact(1, "temp_fact", "value")
        store.forget_fact(1, "temp_fact")
        self.assertNotIn("temp_fact", store.get_facts(1))

    def test_empty_key_or_value_is_ignored(self):
        store.remember_fact(1, "", "value")
        store.remember_fact(1, "key", "")
        self.assertEqual(store.get_facts(1), {})

    def test_per_user_fact_cap_evicts_oldest(self):
        for i in range(store._MAX_FACTS_PER_USER + 5):
            store.remember_fact(1, f"fact_{i}", f"value_{i}")
        facts = store.get_facts(1)
        self.assertLessEqual(len(facts), store._MAX_FACTS_PER_USER)
        # Oldest facts should have been evicted, newest should remain.
        self.assertIn(f"fact_{store._MAX_FACTS_PER_USER + 4}", facts)
        self.assertNotIn("fact_0", facts)

    def test_get_facts_as_context_formats_nonempty(self):
        store.remember_fact(1, "job_preference", "Remote")
        context = store.get_facts_as_context(1)
        self.assertIn("job preference", context)
        self.assertIn("Remote", context)

    def test_get_facts_as_context_empty_when_no_facts(self):
        self.assertEqual(store.get_facts_as_context(999), "")


if __name__ == "__main__":
    unittest.main()
