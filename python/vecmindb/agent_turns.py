"""Turn-loop memory primitives for custom / self-written agents.

Wire any agent loop to the cognitive memory layer in two lines:

    mem = agent_memory(endpoint="http://host:5520", api_key="...", agent_id="me")
    context = mem.before_turn(user_message)     # "" when nothing clears the gate
    mem.after_turn(user_message, reply)         # auto-summarized store

Invariants:

- ``before_turn`` returns an EMPTY STRING for unrelated queries. The
  server-side relevance gate (``memory.search_min_score``) answers
  "No relevant memory found" instead of returning the least-dissimilar
  neighbors, so clients carry zero threshold logic of their own.
- Memory never breaks the agent: every call degrades to a no-op with a
  warning on network failure.
- ``after_turn`` auto-summarizes (question + first 200 characters of the
  reply) unless the caller supplies ``summary=``; ``summary=None`` skips
  the store entirely (empty chatter).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .memory import AsyncVecminMemorySpace, VecminMemorySpace

logger = logging.getLogger("vecmindb.agent_turns")

# Characters kept from the reply tail in an auto-generated summary.
SUMMARY_CHAR_CAP = 200

# The server report is human-readable: "1. [Score: 0.8213] ID: <id>"
# followed by an indented "   Text: <content>" line per hit.
_SCORE_RE = re.compile(r"^\d+\. \[Score: ([\d.]+)\] ID: (\S+)")


def auto_summary(question: str, reply: str) -> str:
    """Builds the default stored summary: question + capped reply tail."""
    tail = (reply or "").strip()
    if len(tail) > SUMMARY_CHAR_CAP:
        tail = tail[:SUMMARY_CHAR_CAP].rstrip() + "..."
    return f"Q: {question.strip()}\nA: {tail}"


def _parse_hits(report: str) -> List[Dict[str, Any]]:
    """Tolerant parser for the search_memory human-readable report.

    Only entries that carry readable text survive; anything unexpected
    yields an empty list (an empty context is safer than a wrong one).
    """
    hits: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in report.splitlines():
        m = _SCORE_RE.match(line.strip())
        if m:
            current = {"score": float(m.group(1)), "id": m.group(2), "text": ""}
            hits.append(current)
            continue
        if current is not None and line.strip().startswith("Text: "):
            current["text"] = line.strip()[len("Text: ") :]
    return [h for h in hits if h.get("text")]


def format_context(hits: List[Dict[str, Any]]) -> str:
    """Renders parsed hits into a prompt-injectable context block."""
    if not hits:
        return ""
    lines = ["[Relevant memories]"]
    for h in hits:
        lines.append(f"- ({h['score']:.2f}) {h['text']}")
    return "\n".join(lines)


class AgentMemory:
    """Synchronous turn-loop facade over a memory space.

    ``before_turn`` / ``after_turn`` are the whole API; the underlying
    :class:`VecminMemorySpace` stays reachable as ``.space`` for full CRUD.
    """

    def __init__(self, space: VecminMemorySpace) -> None:
        self.space = space

    def _search_report(self, query: str, top_k: int) -> str:
        report = self.space.search_memory(query, top_k=top_k)
        if isinstance(report, list) and report and isinstance(report[0], dict):
            # The space wraps non-JSON server responses as [{"text": ...}].
            text = report[0].get("text", "")
            if text and not text.lstrip().startswith("{"):
                return text
        return ""

    def _store(
        self,
        text: str,
        *,
        is_factual: bool,
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        return self.space.store_memory(text, metadata=metadata, is_factual=is_factual)

    def before_turn(self, query: str, top_k: int = 3) -> str:
        """Returns a prompt-injectable context block, or "" when nothing
        clears the relevance gate. Never raises."""
        try:
            report = self._search_report(query, top_k)
        except Exception as exc:  # noqa: BLE001 - memory must not break the agent
            logger.warning("vecmindb before_turn degraded to empty: %s", exc)
            return ""
        if not report or "No relevant memory" in report:
            return ""
        hits = _parse_hits(report)
        if not hits:
            logger.warning(
                "vecmindb before_turn could not parse the search report; returning empty"
            )
            return ""
        return format_context(hits)

    def after_turn(
        self,
        question: str,
        reply: str,
        *,
        summary: Optional[str] = ...,
        is_factual: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Stores this turn's memory; returns the memory ID or None.

        ``summary=...`` (default) auto-summarizes the exchange;
        ``summary="text"`` stores exactly that; ``summary=None`` skips.
        """
        if summary is None:
            return None
        if summary is ...:
            summary = auto_summary(question, reply)
        try:
            return self._store(summary, is_factual=is_factual, metadata=metadata)
        except Exception as exc:  # noqa: BLE001 - memory must not break the agent
            logger.warning("vecmindb after_turn degraded to no-op: %s", exc)
            return None


class AsyncAgentMemory:
    """Asynchronous turn-loop facade; identical semantics to AgentMemory."""

    def __init__(self, space: AsyncVecminMemorySpace) -> None:
        self.space = space

    async def _search_report(self, query: str, top_k: int) -> str:
        report = await self.space.search_memory(query, top_k=top_k)
        if isinstance(report, list) and report and isinstance(report[0], dict):
            text = report[0].get("text", "")
            if text and not text.lstrip().startswith("{"):
                return text
        return ""

    async def before_turn(self, query: str, top_k: int = 3) -> str:
        """Async context fetch; empty string when nothing clears the gate."""
        try:
            report = await self._search_report(query, top_k)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vecmindb before_turn degraded to empty: %s", exc)
            return ""
        if not report or "No relevant memory" in report:
            return ""
        hits = _parse_hits(report)
        if not hits:
            logger.warning(
                "vecmindb before_turn could not parse the search report; returning empty"
            )
            return ""
        return format_context(hits)

    async def after_turn(
        self,
        question: str,
        reply: str,
        *,
        summary: Optional[str] = ...,
        is_factual: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Async store; ``summary=None`` skips, default auto-summarizes."""
        if summary is None:
            return None
        if summary is ...:
            summary = auto_summary(question, reply)
        try:
            return await self.space.store_memory(
                summary, metadata=metadata, is_factual=is_factual
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vecmindb after_turn degraded to no-op: %s", exc)
            return None


def agent_memory(
    endpoint: str,
    *,
    api_key: Optional[str] = None,
    agent_id: Optional[str] = None,
    sovereignty_token: Optional[str] = None,
    collection_name: str = "default",
    **client_kwargs: Any,
) -> AgentMemory:
    """Builds a ready-to-use synchronous AgentMemory in one call."""
    from .client import VecminClient

    client = VecminClient(
        endpoint,
        api_key=api_key,
        agent_id=agent_id,
        sovereignty_token=sovereignty_token,
        **client_kwargs,
    )
    space = VecminMemorySpace(
        client=client,
        collection_name=collection_name,
        agent_id=agent_id or "",
        sovereignty_token=sovereignty_token or "",
        model_id=sovereignty_token or "",
    )
    return AgentMemory(space)


def async_agent_memory(
    endpoint: str,
    *,
    api_key: Optional[str] = None,
    agent_id: Optional[str] = None,
    sovereignty_token: Optional[str] = None,
    collection_name: str = "default",
    **client_kwargs: Any,
) -> AsyncAgentMemory:
    """Builds a ready-to-use asynchronous AsyncAgentMemory in one call."""
    from .async_client import AsyncVecminClient

    client = AsyncVecminClient(
        endpoint,
        api_key=api_key,
        agent_id=agent_id,
        sovereignty_token=sovereignty_token,
        **client_kwargs,
    )
    space = AsyncVecminMemorySpace(
        client=client,
        collection_name=collection_name,
        agent_id=agent_id or "",
        sovereignty_token=sovereignty_token or "",
        model_id=sovereignty_token or "",
    )
    return AsyncAgentMemory(space)
