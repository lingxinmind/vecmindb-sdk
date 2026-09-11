"""Unit tests for the turn-loop memory primitives (AgentMemory / AsyncAgentMemory)."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from vecmindb import (
    AgentMemory,
    AsyncAgentMemory,
    auto_summary,
)

REPORT_WITH_HITS = (
    "Retrieved 2 relevant semantic anchors from domain 'system':\n"
    "1. [Score: 0.9123] ID: abc123\n"
    "   Text: 客户要求 SLA 99.9%\n"
    "2. [Score: 0.7031] ID: def456\n"
    "   Text: 审计日志保留 180 天\n"
)


class TestAutoSummary(unittest.TestCase):
    def test_truncates_reply_to_cap(self) -> None:
        long_reply = "很长的回答" * 100  # 500 chars
        s = auto_summary("问题?", long_reply)
        self.assertTrue(s.startswith("Q: 问题?\nA: "))
        self.assertLessEqual(len(s.split("A: ", 1)[1]), 203)  # 200 + "..."

    def test_empty_reply_is_safe(self) -> None:
        self.assertEqual(auto_summary("q", ""), "Q: q\nA: ")


class TestAgentMemoryAfterTurn(unittest.TestCase):
    def _mem(self) -> AgentMemory:
        space = MagicMock()
        space.store_memory.return_value = "mem-id-1"
        return AgentMemory(space)

    def test_auto_summary_by_default(self) -> None:
        mem = self._mem()
        rid = mem.after_turn("为什么慢?", "因为 hnsw_ef_search 默认 50 过低")
        self.assertEqual(rid, "mem-id-1")
        stored_args = mem.space.store_memory.call_args.args
        stored = {"text": stored_args[0]}
        self.assertIn("为什么慢?", stored["text"])
        self.assertIn("hnsw_ef_search", stored["text"])

    def test_explicit_summary_wins(self) -> None:
        mem = self._mem()
        mem.after_turn("q", "r", summary="定制摘要")
        self.assertIn("定制摘要", mem.space.store_memory.call_args.args[0])

    def test_none_skips_store(self) -> None:
        mem = self._mem()
        self.assertIsNone(mem.after_turn("q", "r", summary=None))
        mem.space.store_memory.assert_not_called()

    def test_store_failure_degrades_to_none(self) -> None:
        mem = self._mem()
        mem.space.store_memory.side_effect = ConnectionError("boom")
        self.assertIsNone(mem.after_turn("q", "r"))  # never raises

    def test_is_factual_passthrough(self) -> None:
        mem = self._mem()
        mem.after_turn("q", "r", summary="客户要求", is_factual=True)
        self.assertTrue(mem.space.store_memory.call_args.kwargs["is_factual"])


class TestAgentMemoryBeforeTurn(unittest.TestCase):
    def _mem(self, report) -> AgentMemory:
        space = MagicMock()
        space.search_memory.return_value = [{"text": report}]
        return AgentMemory(space)

    def test_hits_format_context(self) -> None:
        mem = self._mem(REPORT_WITH_HITS)
        ctx = mem.before_turn("SLA 可用性")
        self.assertIn("[Relevant memories]", ctx)
        self.assertIn("0.91", ctx)
        self.assertIn("客户要求 SLA 99.9%", ctx)

    def test_gated_empty_returns_empty_string(self) -> None:
        mem = self._mem(
            "No relevant memory found in domain 'system' (no match cleared threshold 0.5)."
        )
        self.assertEqual(mem.before_turn("无关话题"), "")

    def test_unparseable_report_returns_empty(self) -> None:
        mem = self._mem("some totally unexpected format")
        self.assertEqual(mem.before_turn("q"), "")

    def test_search_failure_returns_empty(self) -> None:
        mem = self._mem(REPORT_WITH_HITS)
        mem.space.search_memory.side_effect = TimeoutError("down")
        self.assertEqual(mem.before_turn("q"), "")  # never raises


class TestAsyncAgentMemory(unittest.IsolatedAsyncioTestCase):
    def _mem(self) -> AsyncAgentMemory:
        space = MagicMock()
        space.search_memory = AsyncMock(return_value=[{"text": REPORT_WITH_HITS}])
        space.store_memory = AsyncMock(return_value="mem-id-2")
        return AsyncAgentMemory(space)

    async def test_before_turn_async(self) -> None:
        mem = self._mem()
        ctx = await mem.before_turn("SLA")
        self.assertIn("客户要求 SLA 99.9%", ctx)

    async def test_after_turn_async(self) -> None:
        mem = self._mem()
        rid = await mem.after_turn("q", "r", summary="s")
        self.assertEqual(rid, "mem-id-2")

    async def test_failures_never_raise_async(self) -> None:
        mem = self._mem()
        mem.space.search_memory.side_effect = OSError("down")
        self.assertEqual(await mem.before_turn("q"), "")
        mem.space.store_memory.side_effect = OSError("down")
        self.assertIsNone(await mem.after_turn("q", "r"))


if __name__ == "__main__":
    unittest.main()
