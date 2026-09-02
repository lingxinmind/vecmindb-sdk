"""VecminDB MCP Client – SSE Stream + JSON-RPC.

This module provides a standalone client for the Model Context Protocol
(MCP) integration exposed by VecminDB.  It supports two transports:

1. **SSE Stream** – connects to ``GET /api/v1/mcp/sse`` and yields
   real-time events (heartbeats, tool results, notifications).
2. **JSON-RPC** – sends structured requests to ``POST /api/v1/mcp/message``
   to invoke MCP tools such as ``store_memory`` and ``search_memory``.

The client can be used independently or accessed through
:meth:`AsyncVecminClient.mcp_store_memory` /
:meth:`AsyncVecminClient.mcp_search_memory`.

Usage (async)::

    async with McpClient("http://localhost:5520", api_key="xxx") as mcp:
        # Listen for SSE events
        async for event in mcp.stream():
            print(event)

        # Call a tool
        result = await mcp.call_tool("store_memory", {
            "agent_id": "agent-1",
            "content": "Hello world",
        })

Usage (sync)::

    with SyncMcpClient("http://localhost:5520", api_key="xxx") as mcp:
        result = mcp.call_tool("store_memory", {
            "agent_id": "agent-1",
            "content": "Hello world",
        })
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union

import httpx

from .auth import AuthManager
from .exceptions import VecminError, exception_from_status
from .retry import RetryConfig, retry_async, retry_sync

logger = logging.getLogger("vecmindb.mcp")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SseEvent:
    """A single Server-Sent Event.

    Attributes:
        event: Event type (e.g. ``"message"``, ``"heartbeat"``).
        data: Event payload (usually a JSON string).
    """

    event: str = "message"
    data: str = ""


@dataclass
class JsonRpcRequest:
    """A JSON-RPC 2.0 request envelope.

    Attributes:
        method: RPC method name.
        params: Method parameters.
        id: Request identifier (auto-generated if not provided).
    """

    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: Union[int, str] = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-RPC compatible dict."""
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.id,
        }


@dataclass
class JsonRpcResponse:
    """A JSON-RPC 2.0 response.

    Attributes:
        id: Matching request identifier.
        result: Successful result payload (if any).
        error: Error payload (if any).
    """

    id: Union[int, str] = ""
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonRpcResponse":
        """Deserialise from a dict."""
        return cls(
            id=data.get("id", ""),
            result=data.get("result"),
            error=data.get("error"),
        )

    def raise_for_error(self) -> None:
        """Raise :class:`VecminError` if the response contains an error."""
        if self.error:
            msg = self.error.get("message", str(self.error))
            code = self.error.get("code", -1)
            raise VecminError(message=msg, code=code)


# ---------------------------------------------------------------------------
# SSE parsing helper
# ---------------------------------------------------------------------------


def _parse_sse_line(line: str) -> Optional[SseEvent]:
    """Parse a single SSE data line into an event object.

    SSE format::

        event: <type>
        data: <payload>

    Returns ``None`` for blank lines / comments.
    """
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if line.startswith("event:"):
        return SseEvent(event=line[6:].strip(), data="")
    if line.startswith("data:"):
        return SseEvent(data=line[5:].strip())
    return None


# ---------------------------------------------------------------------------
# Async MCP Client
# ---------------------------------------------------------------------------


class McpClient:
    """Async MCP client with SSE streaming and JSON-RPC tool invocation.

    Args:
        base_url: VecminDB server root URL.
        api_key: Optional API key for authentication.
        retry_config: Retry policy for JSON-RPC calls.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5520",
        *,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_url = f"{self._base_url}/api/v1"
        self._retry_config = retry_config or RetryConfig()
        self._auth = AuthManager(api_key=api_key)
        self._session_id: Optional[str] = None
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )

    async def __aenter__(self) -> "McpClient":  # noqa: D105
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: D105
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # SSE Stream
    # ------------------------------------------------------------------

    async def stream(self, *, session_id: Optional[str] = None) -> AsyncIterator[SseEvent]:
        """Yield SSE events from the VecminDB MCP stream.

        Connects to ``GET /api/v1/mcp/sse`` and parses the event stream,
        yielding :class:`SseEvent` objects as they arrive.

        Args:
            session_id: Optional MCP session identifier.

        Yields:
            Parsed SSE events.
        """
        headers = self._auth.auth_headers()
        headers["Accept"] = "text/event-stream"
        params: Dict[str, str] = {}
        if session_id:
            params["session_id"] = session_id

        async with self._client.stream(
            "GET",
            f"{self._api_url}/mcp/sse",
            headers=headers,
            params=params,
        ) as response:
            if response.status_code != 200:
                raise VecminError(f"SSE connection failed: HTTP {response.status_code}")
            current_event = SseEvent()
            async for line in response.aiter_lines():
                parsed = _parse_sse_line(line)
                if parsed is None:
                    # Blank line → dispatch accumulated event
                    if current_event.data:
                        yield current_event
                        current_event = SseEvent()
                    continue
                if parsed.event:
                    current_event.event = parsed.event
                if parsed.data:
                    current_event.data = parsed.data

    # ------------------------------------------------------------------
    # JSON-RPC
    # ------------------------------------------------------------------

    async def _send_rpc(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Send a JSON-RPC request and return the parsed response.

        Args:
            request: JSON-RPC request envelope.

        Returns:
            Parsed JSON-RPC response.
        """
        headers = self._auth.auth_headers()
        headers["Content-Type"] = "application/json"
        params: Dict[str, str] = {}
        if self._session_id:
            params["session_id"] = self._session_id

        async def _do() -> JsonRpcResponse:
            try:
                resp = await self._client.post(
                    f"{self._api_url}/mcp/message",
                    json=request.to_dict(),
                    headers=headers,
                    params=params,
                )
            except httpx.HTTPError as exc:
                raise VecminError(f"MCP request failed: {exc}") from exc

            if resp.status_code not in (200, 202):
                raise exception_from_status(resp.status_code, message=resp.text)

            # 202 Accepted means the result will be delivered via SSE.
            if resp.status_code == 202:
                return JsonRpcResponse(id=request.id, result={"status": "accepted"})

            try:
                data = resp.json()
            except json.JSONDecodeError:
                return JsonRpcResponse(id=request.id, result=resp.text)

            return JsonRpcResponse.from_dict(data)

        return await retry_async(_do, self._retry_config)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Invoke an MCP tool via JSON-RPC ``tools/call``.

        Args:
            name: Tool name (e.g. ``"store_memory"``, ``"search_memory"``).
            arguments: Tool arguments.

        Returns:
            Tool result payload.
        """
        request = JsonRpcRequest(
            method="tools/call",
            params={"name": name, "arguments": arguments},
        )
        response = await self._send_rpc(request)
        response.raise_for_error()
        return response.result

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Discover available MCP tools via ``tools/list``.

        Returns:
            List of tool descriptors.
        """
        request = JsonRpcRequest(method="tools/list", params={})
        response = await self._send_rpc(request)
        response.raise_for_error()
        tools = response.result or []
        if isinstance(tools, dict):
            return tools.get("tools", [tools])
        return tools if isinstance(tools, list) else [tools]

    async def initialize(self) -> Dict[str, Any]:
        """Perform the MCP ``initialize`` handshake.

        Returns:
            Server capabilities.
        """
        request = JsonRpcRequest(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "vecmindb-python-sdk", "version": "0.1.0"},
            },
        )
        response = await self._send_rpc(request)
        response.raise_for_error()
        return response.result

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    async def store_memory(
        self,
        content: str,
        *,
        agent_id: str = "default",
        source: Optional[str] = "sdk",
        is_factual: bool = False,
    ) -> Any:
        """Store a memory via the ``store_memory`` MCP tool.

        Args:
            content: Text content to remember.
            agent_id: Agent or session identifier (server overrides this with
                the authenticated identity bound to the API key).
            source: Optional origin tag, stored in the memory metadata.
            is_factual: If true, exempts this memory from biological forgetting.

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {
            "agent_id": agent_id,
            "text": content,
            "is_factual": is_factual,
        }
        if source:
            # The server schema has no top-level "source" field; fold it into
            # the documented metadata object instead.
            arguments["metadata"] = {"source": source}
        return await self.call_tool("store_memory", arguments)

    async def search_memory(
        self,
        query: str,
        *,
        agent_id: str = "default",
        top_k: int = 5,
    ) -> Any:
        """Search memories via the ``search_memory`` MCP tool.

        Args:
            query: Natural-language search query.
            agent_id: Agent or session identifier (server overrides this with
                the authenticated identity bound to the API key).
            top_k: Number of results.

        Returns:
            Tool result.
        """
        return await self.call_tool(
            "search_memory",
            {"agent_id": agent_id, "query": query, "top_k": top_k},
        )

    async def list_memories(self, *, limit: int = 20) -> Any:
        """List the caller's own memories via the ``list_memories`` MCP tool.

        Args:
            limit: Maximum number of memories to return.

        Returns:
            Tool result.
        """
        return await self.call_tool("list_memories", {"limit": limit})

    async def get_memory(self, memory_id: str) -> Any:
        """Fetch one memory by its vector ID via the ``get_memory`` MCP tool.

        Args:
            memory_id: Vector ID returned by store_memory / search_memory.

        Returns:
            Tool result.
        """
        return await self.call_tool("get_memory", {"id": memory_id})

    async def forget_memory(
        self,
        *,
        memory_id: Optional[str] = None,
        memory_ids: Optional[List[str]] = None,
        collection: str = "default",
        sovereignty_token: Optional[str] = None,
    ) -> Any:
        """Delete memories via the ``forget`` MCP tool.

        Args:
            memory_id: Single vector ID to forget.
            memory_ids: Multiple vector IDs to forget.
            collection: Target collection.
            sovereignty_token: Sovereignty token; defaults to the collection
                authority token when omitted.

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {"collection": collection}
        if memory_id is not None:
            arguments["id"] = memory_id
        if memory_ids is not None:
            arguments["ids"] = memory_ids
        if sovereignty_token is not None:
            arguments["sovereignty_token"] = sovereignty_token
        return await self.call_tool("forget", arguments)

    async def memory_status(
        self,
        *,
        agent_id: Optional[str] = None,
        collection: str = "default",
    ) -> Any:
        """Report the LTSM memory lifecycle via the ``memory_status`` MCP tool.

        Args:
            agent_id: Optional agent identity filter.
            collection: Collection to inspect.

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {"collection": collection}
        if agent_id is not None:
            arguments["agent_id"] = agent_id
        return await self.call_tool("memory_status", arguments)

    async def consolidate(self, *, collection: str = "default", force: bool = False) -> Any:
        """Trigger an LTSM distillation cycle via the ``consolidate`` MCP tool.

        Args:
            collection: Collection to consolidate.
            force: Run a full evolution cycle when true.

        Returns:
            Tool result.
        """
        return await self.call_tool("consolidate", {"collection": collection, "force": force})

    async def register_factuality_template(self, text: str, template_type: str) -> Any:
        """Register a factuality baseline template via the
        ``register_factuality_template`` MCP tool.

        Args:
            text: The template sentence text.
            template_type: Concept type — either 'profile' or 'rule'.

        Returns:
            Tool result.
        """
        return await self.call_tool(
            "register_factuality_template",
            {"text": text, "template_type": template_type},
        )

    async def remove_factuality_template(self, text: str) -> Any:
        """Remove a factuality template via the ``remove_factuality_template``
        MCP tool.

        Args:
            text: The exact template sentence text to remove.

        Returns:
            Tool result.
        """
        return await self.call_tool("remove_factuality_template", {"text": text})


# ---------------------------------------------------------------------------
# Synchronous MCP Client
# ---------------------------------------------------------------------------


class SyncMcpClient:
    """Synchronous MCP client with JSON-RPC tool invocation.

    This client does **not** support SSE streaming (use the async
    :class:`McpClient` for streaming).  It provides a convenient
    synchronous interface for one-shot tool calls.

    Args:
        base_url: VecminDB server root URL.
        api_key: Optional API key for authentication.
        retry_config: Retry policy.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5520",
        *,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_url = f"{self._base_url}/api/v1"
        self._retry_config = retry_config or RetryConfig()
        self._auth = AuthManager(api_key=api_key)
        self._session_id: Optional[str] = None
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )

    def __enter__(self) -> "SyncMcpClient":  # noqa: D105
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: D105
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    # ------------------------------------------------------------------
    # JSON-RPC
    # ------------------------------------------------------------------

    def _send_rpc(self, request: JsonRpcRequest) -> JsonRpcResponse:
        headers = self._auth.auth_headers()
        headers["Content-Type"] = "application/json"
        params: Dict[str, str] = {}
        if self._session_id:
            params["session_id"] = self._session_id

        def _do() -> JsonRpcResponse:
            try:
                resp = self._client.post(
                    f"{self._api_url}/mcp/message",
                    json=request.to_dict(),
                    headers=headers,
                    params=params,
                )
            except httpx.HTTPError as exc:
                raise VecminError(f"MCP request failed: {exc}") from exc

            if resp.status_code not in (200, 202):
                raise exception_from_status(resp.status_code, message=resp.text)

            if resp.status_code == 202:
                return JsonRpcResponse(id=request.id, result={"status": "accepted"})

            try:
                data = resp.json()
            except json.JSONDecodeError:
                return JsonRpcResponse(id=request.id, result=resp.text)

            return JsonRpcResponse.from_dict(data)

        return retry_sync(_do, self._retry_config)

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Invoke an MCP tool via JSON-RPC ``tools/call``.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Tool result payload.
        """
        request = JsonRpcRequest(
            method="tools/call",
            params={"name": name, "arguments": arguments},
        )
        response = self._send_rpc(request)
        response.raise_for_error()
        return response.result

    def list_tools(self) -> List[Dict[str, Any]]:
        """Discover available MCP tools via ``tools/list``."""
        request = JsonRpcRequest(method="tools/list", params={})
        response = self._send_rpc(request)
        response.raise_for_error()
        tools = response.result or []
        if isinstance(tools, dict):
            return tools.get("tools", [tools])
        return tools if isinstance(tools, list) else [tools]

    def initialize(self) -> Dict[str, Any]:
        """Perform the MCP ``initialize`` handshake."""
        request = JsonRpcRequest(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "vecmindb-python-sdk", "version": "0.1.0"},
            },
        )
        response = self._send_rpc(request)
        response.raise_for_error()
        return response.result

    def store_memory(self, content: str, *, agent_id: str = "default", source: Optional[str] = "sdk", is_factual: bool = False) -> Any:
        """Store a memory via the ``store_memory`` MCP tool."""
        arguments: Dict[str, Any] = {"agent_id": agent_id, "text": content, "is_factual": is_factual}
        if source:
            arguments["metadata"] = {"source": source}
        return self.call_tool("store_memory", arguments)

    def search_memory(self, query: str, *, agent_id: str = "default", top_k: int = 5) -> Any:
        """Search memories via the ``search_memory`` MCP tool."""
        return self.call_tool("search_memory", {"agent_id": agent_id, "query": query, "top_k": top_k})

    def list_memories(self, *, limit: int = 20) -> Any:
        """List the caller's own memories via the ``list_memories`` MCP tool."""
        return self.call_tool("list_memories", {"limit": limit})

    def get_memory(self, memory_id: str) -> Any:
        """Fetch one memory by its vector ID via the ``get_memory`` MCP tool."""
        return self.call_tool("get_memory", {"id": memory_id})

    def forget_memory(self, *, memory_id: Optional[str] = None, memory_ids: Optional[List[str]] = None, collection: str = "default", sovereignty_token: Optional[str] = None) -> Any:
        """Delete memories via the ``forget`` MCP tool."""
        arguments: Dict[str, Any] = {"collection": collection}
        if memory_id is not None:
            arguments["id"] = memory_id
        if memory_ids is not None:
            arguments["ids"] = memory_ids
        if sovereignty_token is not None:
            arguments["sovereignty_token"] = sovereignty_token
        return self.call_tool("forget", arguments)

    def memory_status(self, *, agent_id: Optional[str] = None, collection: str = "default") -> Any:
        """Report the LTSM memory lifecycle via the ``memory_status`` MCP tool."""
        arguments: Dict[str, Any] = {"collection": collection}
        if agent_id is not None:
            arguments["agent_id"] = agent_id
        return self.call_tool("memory_status", arguments)

    def consolidate(self, *, collection: str = "default", force: bool = False) -> Any:
        """Trigger an LTSM distillation cycle via the ``consolidate`` MCP tool."""
        return self.call_tool("consolidate", {"collection": collection, "force": force})

    def register_factuality_template(self, text: str, template_type: str) -> Any:
        """Register a factuality baseline template via the
        ``register_factuality_template`` MCP tool."""
        return self.call_tool("register_factuality_template", {"text": text, "template_type": template_type})

    def remove_factuality_template(self, text: str) -> Any:
        """Remove a factuality template via the ``remove_factuality_template``
        MCP tool."""
        return self.call_tool("remove_factuality_template", {"text": text})
