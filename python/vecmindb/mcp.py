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
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, Sequence, Union

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
        is_obsolete: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Store a memory via the ``store_memory`` MCP tool.

        Args:
            content: Text content to remember.
            agent_id: Agent or session identifier (server overrides this with
                the authenticated identity bound to the API key).
            source: Optional origin tag, stored in the memory metadata.
            is_factual: If true, exempts this memory from biological forgetting.
            is_obsolete: If true, strips any anchor so this outdated memory
                re-enters normal LTSM decay.
            metadata: Optional metadata JSON object (merged with ``source``).

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {
            "agent_id": agent_id,
            "text": content,
            "is_factual": is_factual,
        }
        if is_obsolete is not None:
            arguments["is_obsolete"] = is_obsolete
        merged_metadata = dict(metadata or {})
        if source:
            # The server schema has no top-level "source" field; fold it into
            # the documented metadata object instead.
            merged_metadata.setdefault("source", source)
        if merged_metadata:
            arguments["metadata"] = merged_metadata
        return await self.call_tool("store_memory", arguments)

    async def search_memory(
        self,
        query: str,
        *,
        agent_id: str = "default",
        top_k: int = 5,
        since_ts: Optional[int] = None,
        until_ts: Optional[int] = None,
        tags: Optional[List[str]] = None,
        keyword: Optional[str] = None,
    ) -> Any:
        """Search memories via the ``search_memory`` MCP tool.

        Args:
            query: Natural-language search query.
            agent_id: Agent or session identifier (server overrides this with
                the authenticated identity bound to the API key).
            top_k: Number of results.
            since_ts: Epoch seconds — only entries created at or after
                this time.
            until_ts: Epoch seconds — only entries created at or before
                this time.
            tags: Only entries whose metadata.tags contains at least one
                of these tags (any-of).
            keyword: Only entries whose text contains this substring
                (case-insensitive).

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {"agent_id": agent_id, "query": query, "top_k": top_k}
        if since_ts is not None:
            arguments["since_ts"] = since_ts
        if until_ts is not None:
            arguments["until_ts"] = until_ts
        if tags is not None:
            arguments["tags"] = tags
        if keyword is not None:
            arguments["keyword"] = keyword
        return await self.call_tool("search_memory", arguments)

    async def store_media(
        self,
        *,
        caption: Optional[str] = None,
        media_data: Optional[str] = None,
        media_id: Optional[str] = None,
        kind: str = "image",
        mime: Optional[str] = None,
        source_ref: Optional[str] = None,
        is_factual: bool = False,
        clip_vector: Optional[Sequence[float]] = None,
    ) -> Any:
        """Store a media item via the ``store_media`` MCP tool.

        The caption is caller-supplied (the agent generates the description
        agent-side; the server runs zero vision models). Without a caption
        the media stays ``pending`` and is not text-searchable until
        re-stored with the same ``media_id`` and a caption.

        Args:
            caption: Agent-side description; the canonical embedding text.
            media_data: Base64-encoded blob bytes.
            media_id: Optional stable id; re-uploading replaces the old
                description record (G12 upsert).
            kind: image | audio | video | file.
            mime: MIME type for allow-list validation.
            source_ref: Path/URL of the original file.
            is_factual: Explicit strong anchoring (e.g. contract scans).
            clip_vector: Optional agent-side CLIP embedding for image-to-image
                search (M4); requires ``media.clip_collection`` server-side.

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {"kind": kind, "is_factual": is_factual}
        if caption is not None:
            arguments["caption"] = caption
        if media_data is not None:
            arguments["media_data"] = media_data
        if media_id is not None:
            arguments["media_id"] = media_id
        if mime is not None:
            arguments["mime"] = mime
        if source_ref is not None:
            arguments["source_ref"] = source_ref
        if clip_vector is not None:
            arguments["clip_vector"] = list(clip_vector)
        return await self.call_tool("store_media", arguments)

    async def search_by_image(
        self,
        *,
        clip_vector: Optional[Sequence[float]] = None,
        image: Any = None,
        clip_encoder: Optional[Callable[[Any], Sequence[float]]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> Any:
        """Image-to-image search via the ``search_media_by_image`` MCP tool.

        The CLIP embedding is computed agent-side (the server runs zero
        vision models): either pass a precomputed ``clip_vector`` or supply
        ``image`` together with a ``clip_encoder`` callable that maps the
        image to a CLIP embedding. Requires ``media.clip_collection`` to be
        enabled server-side (M4, disabled by default).

        Args:
            clip_vector: Precomputed CLIP embedding of the query image.
            image: Raw image object handed to ``clip_encoder``.
            clip_encoder: Agent-side callable mapping an image to a CLIP
                embedding (``media.clip_dimension`` floats).
            top_k: Number of results.
            min_score: Optional cosine floor (0 returns raw top-k; the text
                relevance gate does not apply to CLIP space).

        Returns:
            Tool result with media_id / source_ref / caption per hit.
        """
        if clip_vector is None:
            if image is None or clip_encoder is None:
                raise ValueError(
                    "search_by_image needs either clip_vector or image + clip_encoder"
                )
            clip_vector = clip_encoder(image)
        return await self.call_tool(
            "search_media_by_image",
            {
                "clip_vector": list(clip_vector),
                "top_k": top_k,
                "min_score": min_score,
            },
        )

    async def list_memories(
        self,
        *,
        limit: int = 20,
        shared_with_me: Optional[bool] = None,
        since_hours: Optional[int] = None,
        since_ts: Optional[int] = None,
        until_ts: Optional[int] = None,
        tags: Optional[List[str]] = None,
        keyword: Optional[str] = None,
    ) -> Any:
        """List memories via the ``list_memories`` MCP tool.

        Args:
            limit: Maximum number of memories to return.
            shared_with_me: If true, inbox view — only entries other
                tenants shared with you (granted collections, own space
                excluded).
            since_hours: Inbox only — window for the "Recent sharing
                activity" summary (default 168 = 7 days).
            since_ts: Epoch seconds — only entries created at or after
                this time.
            until_ts: Epoch seconds — only entries created at or before
                this time.
            tags: Only entries whose metadata.tags contains at least one
                of these tags (any-of).
            keyword: Only entries whose text contains this substring
                (case-insensitive).

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {"limit": limit}
        if shared_with_me is not None:
            arguments["shared_with_me"] = shared_with_me
        if since_hours is not None:
            arguments["since_hours"] = since_hours
        if since_ts is not None:
            arguments["since_ts"] = since_ts
        if until_ts is not None:
            arguments["until_ts"] = until_ts
        if tags is not None:
            arguments["tags"] = tags
        if keyword is not None:
            arguments["keyword"] = keyword
        return await self.call_tool("list_memories", arguments)

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

    async def update_memory(
        self,
        memory_id: str,
        text: str,
        *,
        is_factual: Optional[bool] = None,
    ) -> Any:
        """Correct a memory in place via the ``update_memory`` MCP tool.

        The correction keeps the same id and anchors while the corrected
        text is re-embedded; the previous text is appended to a bounded
        history. Corrections of shared entries are audit-trailed (grantees
        see the new text). Only the authoring agent may correct its own
        entries.

        Args:
            memory_id: Memory vector ID to correct (own collection only).
            text: The corrected content — replaces the previous text.
            is_factual: Optional explicit re-grade: true = strong anchor,
                false = weak; absent preserves the current anchor.

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {"id": memory_id, "text": text}
        if is_factual is not None:
            arguments["is_factual"] = is_factual
        return await self.call_tool("update_memory", arguments)

    async def freeze_memory(self, memory_id: str, frozen: bool) -> Any:
        """Freeze (or unfreeze) one of your memories via the
        ``freeze_memory`` MCP tool.

        Frozen entries are exempt from LTSM distillation and staleness
        scavenging — "do not touch this memory". Advisory on top of
        anchoring (does not re-grade strong/weak), reversible any time,
        author-only.

        Args:
            memory_id: Memory vector ID (own collection only).
            frozen: True = exempt from distillation/vacuum, false = back
                to the normal lifecycle.

        Returns:
            Tool result.
        """
        return await self.call_tool(
            "freeze_memory", {"id": memory_id, "frozen": frozen}
        )

    async def export_memory(self, *, format: str = "json") -> Any:
        """Export your memories via the ``export_memory`` MCP tool.

        Author-scoped, own collection only: a self-contained JSON array
        or human-readable Markdown. The lightweight "my data" answer —
        no admin gate.

        Args:
            format: Output format — ``"json"`` (default) or ``"markdown"``.

        Returns:
            Tool result.
        """
        return await self.call_tool("export_memory", {"format": format})

    async def import_memories(self, memories: Sequence[Dict[str, Any]]) -> Any:
        """Batch-import memories via the ``import_memories`` MCP tool.

        First-run cold start: every entry goes through the same ingestion
        core as ``store_memory`` (anchoring, gate, LTSM), with per-entry
        independence and an honest partial-failure report. Cap: 200
        entries per call.

        Args:
            memories: Batch of entries; each dict needs ``text`` and may
                carry ``is_factual`` (bool) and/or ``metadata`` (object).

        Returns:
            Tool result.
        """
        return await self.call_tool("import_memories", {"memories": list(memories)})

    async def update_memory_sharing(
        self,
        *,
        shared: bool,
        memory_id: Optional[str] = None,
        memory_ids: Optional[List[str]] = None,
        scope: Optional[str] = None,
        except_tag: Optional[str] = None,
        except_ids: Optional[List[str]] = None,
        shared_scope: Optional[str] = None,
        confirm: Optional[bool] = None,
    ) -> Any:
        """Flip the cross-tenant sharing flag via the
        ``update_memory_sharing`` MCP tool.

        Owner-side only: ``shared=True`` makes entries visible (read-only,
        full text and detail) to tenants granted your collection;
        ``shared=False`` makes them private again. Target a single id, an
        ids array, or a scope selector (``"all"``, ``"tag:<name>"``,
        ``"query:<text>"``); ``except_tag`` / ``except_ids`` exclude
        entries from the match set. Batch exposure (>1 entry,
        shared=true) is two-phase: the first call returns a dry-run
        summary — re-issue with ``confirm=True`` to apply.

        Args:
            shared: True = share with granted tenants, false = private.
            memory_id: Single memory vector ID (own collection only).
            memory_ids: Batch: explicit list of memory IDs.
            scope: Batch selector — ``"all"``, ``"tag:<name>"``, or
                ``"query:<text>"`` (share by meaning without tags).
            except_tag: Exclude entries whose metadata.tags contains
                this tag from the match set.
            except_ids: Exclude these entry IDs from the match set.
            shared_scope: Field-level exposure — ``"full"`` (default,
                WYSIWYG) or ``"summary"`` (detail stripped for grantees).
            confirm: Required true to apply a batch exposure of more
                than one entry.

        Returns:
            Tool result (dry-run summary when a batch is not confirmed).
        """
        arguments: Dict[str, Any] = {"shared": shared}
        if memory_id is not None:
            arguments["id"] = memory_id
        if memory_ids is not None:
            arguments["ids"] = memory_ids
        if scope is not None:
            arguments["scope"] = scope
        if except_tag is not None:
            arguments["except_tag"] = except_tag
        if except_ids is not None:
            arguments["except_ids"] = except_ids
        if shared_scope is not None:
            arguments["shared_scope"] = shared_scope
        if confirm is not None:
            arguments["confirm"] = confirm
        return await self.call_tool("update_memory_sharing", arguments)

    async def list_memory_tags(self) -> Any:
        """List your distinct memory tags via the ``list_memory_tags``
        MCP tool: per-tag counts plus the number of untagged entries
        (author-only). Useful before sharing by tag.

        Returns:
            Tool result.
        """
        return await self.call_tool("list_memory_tags", {})

    async def set_tenant_grant(
        self,
        tenant: str,
        *,
        collections: Optional[List[str]] = None,
        revoke: Optional[bool] = None,
    ) -> Any:
        """Grant (or revoke) another tenant read access via the
        ``set_tenant_grant`` MCP tool.

        Owner-side only — you decide unilaterally; the grantee cannot
        self-provision a grant. Live immediately (no restart). Grantees
        still only see entries you marked shared via
        ``update_memory_sharing``.

        Args:
            tenant: Grantee tenant id (must already exist in
                security.tenant_keys).
            collections: Collections to grant; defaults to your own
                memory collection. You may only name collections you own.
            revoke: True = revoke the grant; false/omit = grant.
                Idempotent.

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {"tenant": tenant}
        if collections is not None:
            arguments["collections"] = collections
        if revoke is not None:
            arguments["revoke"] = revoke
        return await self.call_tool("set_tenant_grant", arguments)

    async def list_tenant_grants(self) -> Any:
        """List which tenants currently hold read access to your
        collection via the ``list_tenant_grants`` MCP tool.

        Owner-side reverse lookup, shared-entry subset only, read-only.
        Revoke with ``set_tenant_grant(revoke=True)``.

        Returns:
            Tool result.
        """
        return await self.call_tool("list_tenant_grants", {})

    async def share_with_tenant(
        self,
        tenant: str,
        what: str,
        *,
        shared_scope: Optional[str] = None,
        confirm: Optional[bool] = None,
    ) -> Any:
        """Guided one-shot share via the ``share_with_tenant`` MCP tool.

        Grants the tenant read access AND semantically selects matching
        entries of yours, then returns a dry-run with per-entry previews
        and sensitivity flags; re-issue with ``confirm=True`` to apply.
        Pure composition of ``set_tenant_grant`` +
        ``update_memory_sharing(scope="query:…")`` — same two-phase
        confirm. Revoke later with ``set_tenant_grant(revoke=True)``.

        Args:
            tenant: Grantee tenant id (must already exist in
                security.tenant_keys).
            what: Plain-words description of what to share — matched
                semantically against your own entries.
            shared_scope: ``"full"`` (default, WYSIWYG) or ``"summary"``
                (detail stripped for grantees).
            confirm: Required true to apply (first call returns a
                dry-run summary).

        Returns:
            Tool result (dry-run summary when not confirmed).
        """
        arguments: Dict[str, Any] = {"tenant": tenant, "what": what}
        if shared_scope is not None:
            arguments["shared_scope"] = shared_scope
        if confirm is not None:
            arguments["confirm"] = confirm
        return await self.call_tool("share_with_tenant", arguments)

    async def update_share_subscription(
        self,
        *,
        what: Optional[str] = None,
        tenant: Optional[str] = None,
        shared_scope: Optional[str] = None,
        remove: Optional[bool] = None,
    ) -> Any:
        """Manage your standing share rule via the
        ``update_share_subscription`` MCP tool.

        "Future entries matching <what> go to <tenant>". Pure storage —
        never shares anything by itself: pending matches appear via
        ``check_share_subscriptions`` and apply only after your explicit
        confirm. ``remove=True`` clears the subscription.

        Args:
            what: Plain-words description of the kind of content to
                share (semantically matched later).
            tenant: Grantee tenant id for future matches.
            shared_scope: Field-level exposure for future applies
                (default ``"full"``).
            remove: True = clear your subscription.

        Returns:
            Tool result.
        """
        arguments: Dict[str, Any] = {}
        if what is not None:
            arguments["what"] = what
        if tenant is not None:
            arguments["tenant"] = tenant
        if shared_scope is not None:
            arguments["shared_scope"] = shared_scope
        if remove is not None:
            arguments["remove"] = remove
        return await self.call_tool("update_share_subscription", arguments)

    async def check_share_subscriptions(self) -> Any:
        """Lazily evaluate your standing share subscription via the
        ``check_share_subscriptions`` MCP tool.

        Lists UNSHARED entries of yours that currently match, with
        previews and sensitivity flags, plus the exact one-step confirm
        command. Read-only — nothing is shared by checking.

        Returns:
            Tool result.
        """
        return await self.call_tool("check_share_subscriptions", {})

    async def get_memory_rules(
        self, *, target: str = "all", lang: str = "en"
    ) -> Any:
        """Fetch the corrected, scope-guarded memory-protocol rule block
        via the ``get_memory_rules`` MCP tool.

        Returns the block for a mainstream agent tool together with the
        exact local path to write it into; the calling agent shows the
        block to the user and writes the file itself.

        Args:
            target: One of ``claude_code`` | ``cursor`` | ``workbuddy``
                | ``all`` (default).
            lang: Rule locale — ``en`` (default) or ``zh``.

        Returns:
            Tool result.
        """
        return await self.call_tool(
            "get_memory_rules", {"target": target, "lang": lang}
        )


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

    def store_memory(
        self,
        content: str,
        *,
        agent_id: str = "default",
        source: Optional[str] = "sdk",
        is_factual: bool = False,
        is_obsolete: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Store a memory via the ``store_memory`` MCP tool.

        ``is_obsolete=True`` strips any anchor so the memory re-enters
        normal LTSM decay; ``metadata`` is merged with the ``source``
        origin tag.
        """
        arguments: Dict[str, Any] = {"agent_id": agent_id, "text": content, "is_factual": is_factual}
        if is_obsolete is not None:
            arguments["is_obsolete"] = is_obsolete
        merged_metadata = dict(metadata or {})
        if source:
            merged_metadata.setdefault("source", source)
        if merged_metadata:
            arguments["metadata"] = merged_metadata
        return self.call_tool("store_memory", arguments)

    def search_memory(
        self,
        query: str,
        *,
        agent_id: str = "default",
        top_k: int = 5,
        since_ts: Optional[int] = None,
        until_ts: Optional[int] = None,
        tags: Optional[List[str]] = None,
        keyword: Optional[str] = None,
    ) -> Any:
        """Search memories via the ``search_memory`` MCP tool.

        Optional R3-4 structured filters: ``since_ts`` / ``until_ts``
        (epoch seconds), ``tags`` (any-of), ``keyword`` (substring,
        case-insensitive).
        """
        arguments: Dict[str, Any] = {"agent_id": agent_id, "query": query, "top_k": top_k}
        if since_ts is not None:
            arguments["since_ts"] = since_ts
        if until_ts is not None:
            arguments["until_ts"] = until_ts
        if tags is not None:
            arguments["tags"] = tags
        if keyword is not None:
            arguments["keyword"] = keyword
        return self.call_tool("search_memory", arguments)

    def store_media(
        self,
        *,
        caption: Optional[str] = None,
        media_data: Optional[str] = None,
        media_id: Optional[str] = None,
        kind: str = "image",
        mime: Optional[str] = None,
        source_ref: Optional[str] = None,
        is_factual: bool = False,
        clip_vector: Optional[Sequence[float]] = None,
    ) -> Any:
        """Store a media item via the ``store_media`` MCP tool.

        The caption is caller-supplied (agent-side description; the server
        runs zero vision models). Without a caption the media stays
        ``pending`` until re-stored with the same ``media_id`` and a caption.
        ``clip_vector`` is an optional agent-side CLIP embedding for
        image-to-image search (M4).
        """
        arguments: Dict[str, Any] = {"kind": kind, "is_factual": is_factual}
        if caption is not None:
            arguments["caption"] = caption
        if media_data is not None:
            arguments["media_data"] = media_data
        if media_id is not None:
            arguments["media_id"] = media_id
        if mime is not None:
            arguments["mime"] = mime
        if source_ref is not None:
            arguments["source_ref"] = source_ref
        if clip_vector is not None:
            arguments["clip_vector"] = list(clip_vector)
        return self.call_tool("store_media", arguments)

    def search_by_image(
        self,
        *,
        clip_vector: Optional[Sequence[float]] = None,
        image: Any = None,
        clip_encoder: Optional[Callable[[Any], Sequence[float]]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> Any:
        """Image-to-image search via the ``search_media_by_image`` MCP tool.

        The CLIP embedding is computed agent-side: pass a precomputed
        ``clip_vector`` or supply ``image`` + ``clip_encoder``. Requires
        ``media.clip_collection`` server-side (M4, disabled by default).
        """
        if clip_vector is None:
            if image is None or clip_encoder is None:
                raise ValueError(
                    "search_by_image needs either clip_vector or image + clip_encoder"
                )
            clip_vector = clip_encoder(image)
        return self.call_tool(
            "search_media_by_image",
            {"clip_vector": list(clip_vector), "top_k": top_k, "min_score": min_score},
        )

    def list_memories(
        self,
        *,
        limit: int = 20,
        shared_with_me: Optional[bool] = None,
        since_hours: Optional[int] = None,
        since_ts: Optional[int] = None,
        until_ts: Optional[int] = None,
        tags: Optional[List[str]] = None,
        keyword: Optional[str] = None,
    ) -> Any:
        """List memories via the ``list_memories`` MCP tool.

        ``shared_with_me=True`` is the inbox view (only entries other
        tenants shared with you); optional R3-4 structured filters:
        ``since_ts`` / ``until_ts`` (epoch seconds), ``tags`` (any-of),
        ``keyword`` (substring, case-insensitive).
        """
        arguments: Dict[str, Any] = {"limit": limit}
        if shared_with_me is not None:
            arguments["shared_with_me"] = shared_with_me
        if since_hours is not None:
            arguments["since_hours"] = since_hours
        if since_ts is not None:
            arguments["since_ts"] = since_ts
        if until_ts is not None:
            arguments["until_ts"] = until_ts
        if tags is not None:
            arguments["tags"] = tags
        if keyword is not None:
            arguments["keyword"] = keyword
        return self.call_tool("list_memories", arguments)

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

    def update_memory(self, memory_id: str, text: str, *, is_factual: Optional[bool] = None) -> Any:
        """Correct a memory in place via the ``update_memory`` MCP tool.

        Same id and anchors; the corrected text is re-embedded and the
        previous text appended to a bounded history. ``is_factual``
        optionally re-grades the anchor; absent preserves the current
        grade. Author-only.
        """
        arguments: Dict[str, Any] = {"id": memory_id, "text": text}
        if is_factual is not None:
            arguments["is_factual"] = is_factual
        return self.call_tool("update_memory", arguments)

    def freeze_memory(self, memory_id: str, frozen: bool) -> Any:
        """Freeze (or unfreeze) one of your memories via the
        ``freeze_memory`` MCP tool: frozen entries are exempt from LTSM
        distillation and staleness scavenging. Author-only, reversible
        any time."""
        return self.call_tool("freeze_memory", {"id": memory_id, "frozen": frozen})

    def export_memory(self, *, format: str = "json") -> Any:
        """Export your memories via the ``export_memory`` MCP tool —
        author-scoped JSON (default) or Markdown."""
        return self.call_tool("export_memory", {"format": format})

    def import_memories(self, memories: Sequence[Dict[str, Any]]) -> Any:
        """Batch-import memories via the ``import_memories`` MCP tool.

        Cold start, cap 200 entries per call; each entry dict needs
        ``text`` and may carry ``is_factual`` / ``metadata``.
        """
        return self.call_tool("import_memories", {"memories": list(memories)})

    def update_memory_sharing(
        self,
        *,
        shared: bool,
        memory_id: Optional[str] = None,
        memory_ids: Optional[List[str]] = None,
        scope: Optional[str] = None,
        except_tag: Optional[str] = None,
        except_ids: Optional[List[str]] = None,
        shared_scope: Optional[str] = None,
        confirm: Optional[bool] = None,
    ) -> Any:
        """Flip the cross-tenant sharing flag via the
        ``update_memory_sharing`` MCP tool — owner-side only.

        Target a single id, an ids array, or a scope selector
        (``"all"`` | ``"tag:<name>"`` | ``"query:<text>"``). Batch
        exposure (>1 entry, shared=true) is two-phase: re-issue with
        ``confirm=True`` after the dry-run summary.
        """
        arguments: Dict[str, Any] = {"shared": shared}
        if memory_id is not None:
            arguments["id"] = memory_id
        if memory_ids is not None:
            arguments["ids"] = memory_ids
        if scope is not None:
            arguments["scope"] = scope
        if except_tag is not None:
            arguments["except_tag"] = except_tag
        if except_ids is not None:
            arguments["except_ids"] = except_ids
        if shared_scope is not None:
            arguments["shared_scope"] = shared_scope
        if confirm is not None:
            arguments["confirm"] = confirm
        return self.call_tool("update_memory_sharing", arguments)

    def list_memory_tags(self) -> Any:
        """List your distinct memory tags via the ``list_memory_tags``
        MCP tool: per-tag counts plus the number of untagged entries."""
        return self.call_tool("list_memory_tags", {})

    def set_tenant_grant(
        self,
        tenant: str,
        *,
        collections: Optional[List[str]] = None,
        revoke: Optional[bool] = None,
    ) -> Any:
        """Grant (or revoke) another tenant read access via the
        ``set_tenant_grant`` MCP tool — owner-side only, live
        immediately. Grantees still only see entries you marked shared."""
        arguments: Dict[str, Any] = {"tenant": tenant}
        if collections is not None:
            arguments["collections"] = collections
        if revoke is not None:
            arguments["revoke"] = revoke
        return self.call_tool("set_tenant_grant", arguments)

    def list_tenant_grants(self) -> Any:
        """List which tenants currently hold read access to your
        collection via the ``list_tenant_grants`` MCP tool — owner-side
        reverse lookup, read-only."""
        return self.call_tool("list_tenant_grants", {})

    def share_with_tenant(
        self,
        tenant: str,
        what: str,
        *,
        shared_scope: Optional[str] = None,
        confirm: Optional[bool] = None,
    ) -> Any:
        """Guided one-shot share via the ``share_with_tenant`` MCP tool:
        grants read access and semantically selects matching entries,
        returning a dry-run; re-issue with ``confirm=True`` to apply."""
        arguments: Dict[str, Any] = {"tenant": tenant, "what": what}
        if shared_scope is not None:
            arguments["shared_scope"] = shared_scope
        if confirm is not None:
            arguments["confirm"] = confirm
        return self.call_tool("share_with_tenant", arguments)

    def update_share_subscription(
        self,
        *,
        what: Optional[str] = None,
        tenant: Optional[str] = None,
        shared_scope: Optional[str] = None,
        remove: Optional[bool] = None,
    ) -> Any:
        """Manage your standing share rule via the
        ``update_share_subscription`` MCP tool — pure storage, never
        shares by itself; pending matches surface via
        ``check_share_subscriptions``. ``remove=True`` clears it."""
        arguments: Dict[str, Any] = {}
        if what is not None:
            arguments["what"] = what
        if tenant is not None:
            arguments["tenant"] = tenant
        if shared_scope is not None:
            arguments["shared_scope"] = shared_scope
        if remove is not None:
            arguments["remove"] = remove
        return self.call_tool("update_share_subscription", arguments)

    def check_share_subscriptions(self) -> Any:
        """Lazily evaluate your standing share subscription via the
        ``check_share_subscriptions`` MCP tool — read-only, nothing is
        shared by checking."""
        return self.call_tool("check_share_subscriptions", {})

    def get_memory_rules(self, *, target: str = "all", lang: str = "en") -> Any:
        """Fetch the memory-protocol rule block via the
        ``get_memory_rules`` MCP tool for claude_code | cursor |
        workbuddy | all (default), with the local path to write it
        into. ``lang`` is en (default) or zh."""
        return self.call_tool("get_memory_rules", {"target": target, "lang": lang})
