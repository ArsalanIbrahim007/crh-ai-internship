"""Tests for long-term memory persistence and recall."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from memory.long_term_memory import LongTermMemory


@pytest.fixture
def memory(tmp_path):
    """Fresh in-memory-like SQLite memory for each test."""
    db_path = tmp_path / "test_memory.sqlite"
    mem = LongTermMemory(db_path=db_path)
    yield mem
    mem.close()


class TestMemoryStore:
    def test_store_returns_id(self, memory):
        entry_id = memory.store("initiative", "Test Initiative", "Build a rate limiter")
        assert entry_id is not None
        assert entry_id > 0

    def test_store_multiple(self, memory):
        id1 = memory.store("initiative", "First", "Content one")
        id2 = memory.store("decision", "Second", "Content two")
        assert id2 > id1


class TestMemoryRecall:
    def test_recall_by_text(self, memory):
        memory.store("initiative", "Rate Limiter Project", "Build a token bucket rate limiter in Python")
        results = memory.recall("rate limiter")
        assert len(results) >= 1
        assert "rate limiter" in results[0].title.lower() or "rate limiter" in results[0].content.lower()

    def test_recall_by_category(self, memory):
        memory.store("initiative", "Init One", "Content")
        memory.store("decision", "Dec One", "Architecture decision")
        results = memory.recall("one", category="decision")
        assert all(r.category == "decision" for r in results)

    def test_recall_empty(self, memory):
        results = memory.recall("nonexistent query xyz123")
        assert results == []

    def test_recall_limit(self, memory):
        for i in range(10):
            memory.store("initiative", f"Project {i}", f"Description of project {i}")
        results = memory.recall("project", limit=3)
        assert len(results) <= 3


class TestMemoryListRecent:
    def test_list_recent(self, memory):
        memory.store("initiative", "Old", "Old content")
        memory.store("initiative", "New", "New content")
        results = memory.list_recent(limit=1)
        assert len(results) == 1
        assert results[0].title == "New"

    def test_list_by_category(self, memory):
        memory.store("initiative", "Init", "Content")
        memory.store("retrospective", "Retro", "Lesson learned")
        results = memory.list_recent(category="retrospective")
        assert all(r.category == "retrospective" for r in results)


class TestMemoryPersistence:
    def test_survives_reconnect(self, tmp_path):
        """Memory persists across close/reopen cycles."""
        db_path = tmp_path / "persist_test.sqlite"

        mem1 = LongTermMemory(db_path=db_path)
        mem1.store("decision", "Use LangGraph", "Chose LangGraph for state management")
        mem1.close()

        mem2 = LongTermMemory(db_path=db_path)
        results = mem2.recall("LangGraph")
        mem2.close()

        assert len(results) >= 1
        assert "LangGraph" in results[0].title
