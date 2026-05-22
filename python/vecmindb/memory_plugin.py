"""
VecminDB Memory Plugin for LangChain and CrewAI.

Provides drop-in memory backends powered by VecminDB's LTSM lifecycle:
- Working Memory → Fast-Path promotion → Episodic Memory
- Time-based decay → PCA distillation → Abstract Centroid
- Sovereign Federation for multi-agent knowledge sharing

Usage (LangChain):
    from vecmindb.memory_plugin import VecminDBMemoryPlugin
    memory = VecminDBMemoryPlugin(
        base_url="http://localhost:5520",
        agent_id="my_agent",
        sovereignty_token="my_token",
    )
    # Use with ConversationChain or LLMChain memory=memory

Usage (CrewAI):
    from vecmindb.memory_plugin import VecminDBCrewMemory
    memory = VecminDBCrewMemory(
        base_url="http://localhost:5520",
        crew_id="my_crew",
        agent_ids=["agent_1", "agent_2"],
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VecminDBMemoryPlugin:
    """LangChain-compatible memory backend powered by VecminDB.

    Implements the LangChain BaseMemory interface. Stores conversation context
    as episodic memories with automatic Fast-Path promotion evaluation.
    """

    def __init__(
        self,
        base_url: str,
        agent_id: str,
        sovereignty_token: str = "default",
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.sovereignty_token = sovereignty_token
        self.model_id = model_id or sovereignty_token
        self.api_key = api_key

        self._memory_key = "history"
        self._return_messages = False

    @property
    def memory_variables(self) -> List[str]:
        return [self._memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Search VecminDB for relevant memories given the current input."""
        query = inputs.get("input", inputs.get("query", ""))
        if not query:
            return {self._memory_key: []}

        try:
            results = self._search(query, top_k=5)
            return {self._memory_key: results}
        except Exception as e:
            logger.warning(f"VecminDB memory search failed: {e}")
            return {self._memory_key: []}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Store conversation context as episodic memory."""
        text = self._format_context(inputs, outputs)
        try:
            self._store(text)
        except Exception as e:
            logger.warning(f"VecminDB memory store failed: {e}")

    def clear(self) -> None:
        """Not directly supported — LTSM handles forgetting via decay."""
        logger.info("VecminDB: Memory clearing delegated to LTSM decay lifecycle.")

    def _store(self, text: str) -> None:
        import json
        import urllib.request

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "store_memory",
                "arguments": {
                    "text": text,
                    "agent_id": self.agent_id,
                    "sovereignty_token": self.sovereignty_token,
                    "model_id": self.model_id,
                },
            },
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/api/v1/mcp/message",
            data=payload,
            headers={
                "Content-Type": "application/json",
            },
        )
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        urllib.request.urlopen(req, timeout=30)

    def _search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        import json
        import urllib.request

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": {
                    "query": query,
                    "agent_id": self.agent_id,
                    "sovereignty_token": self.sovereignty_token,
                    "top_k": top_k,
                },
            },
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/api/v1/mcp/message",
            data=payload,
            headers={
                "Content-Type": "application/json",
            },
        )
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        return self._parse_search_results(data)

    def _parse_search_results(self, data: Dict) -> List[Dict[str, Any]]:
        try:
            content = data.get("result", {}).get("content", [])
            if content:
                text = content[0].get("text", "")
                return [{"content": text}]
        except Exception:
            pass
        return []

    def _format_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> str:
        parts = []
        inp = inputs.get("input", "")
        if inp:
            parts.append(f"User: {inp}")
        out = outputs.get("output", outputs.get("response", ""))
        if out:
            parts.append(f"Assistant: {out}")
        return "\n".join(parts) if parts else str(inputs)

    def get_centroids(self, collection_name: str = "default") -> List[Dict[str, Any]]:
        """Query LTSM abstract centroids for knowledge injection."""
        import json
        import urllib.request

        req = urllib.request.Request(
            f"{self.base_url}/api/v1/centroids/{collection_name}",
            headers={"Accept": "application/json"},
        )
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())


class VecminDBCrewMemory:
    """CrewAI-compatible multi-agent memory backed by VecminDB.

    Each agent gets an isolated memory stream via Sovereignty Token.
    Shared knowledge is accessed through Alliance Centroids.
    """

    def __init__(
        self,
        base_url: str,
        crew_id: str,
        agent_ids: List[str],
        alliance_token: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.crew_id = crew_id
        self.agent_ids = agent_ids
        self.alliance_token = alliance_token or f"alliance-{crew_id}"
        self.api_key = api_key

        self._memories: Dict[str, VecminDBMemoryPlugin] = {}

        for agent_id in agent_ids:
            self._memories[agent_id] = VecminDBMemoryPlugin(
                base_url=base_url,
                agent_id=agent_id,
                sovereignty_token=f"crew-{crew_id}-agent-{agent_id}",
                api_key=api_key,
            )

    def agent_memory(self, agent_id: str) -> VecminDBMemoryPlugin:
        """Get the isolated memory for a specific agent."""
        if agent_id not in self._memories:
            self._memories[agent_id] = VecminDBMemoryPlugin(
                base_url=self.base_url,
                agent_id=agent_id,
                sovereignty_token=f"crew-{self.crew_id}-agent-{agent_id}",
                api_key=self.api_key,
            )
        return self._memories[agent_id]

    def shared_knowledge(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query alliance-level shared knowledge centroids."""
        import json
        import urllib.request

        req = urllib.request.Request(
            f"{self.base_url}/api/v1/alliance/{self.alliance_token}/centroids",
            headers={"Accept": "application/json"},
        )
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def store(self, agent_id: str, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Store memory for a specific agent."""
        memory = self.agent_memory(agent_id)
        memory.save_context(inputs, outputs)

    def recall(self, agent_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Recall memories for a specific agent."""
        memory = self.agent_memory(agent_id)
        return memory.load_memory_variables({"input": query}).get(memory._memory_key, [])
