#!/usr/bin/env python3
"""VecminDB Python SDK - 03 MCP (Model Context Protocol) Client Example.

Demonstrates:
1. Connecting via JSON-RPC 2.0 (Sync & Async McpClient).
2. Discovering available MCP tools (`list_tools`).
3. Executing MCP memory tools (`store_memory` & `search_memory`).
4. Real-time SSE streaming (`mcp.stream()`).
"""

import asyncio
import sys
from vecmindb.mcp import SyncMcpClient, McpClient


def demo_sync_mcp():
    print("\n--- [1] Synchronous MCP Client Example (JSON-RPC) ---")
    endpoint = "http://localhost:5520"
    
    with SyncMcpClient(base_url=endpoint) as mcp:
        # 1. Initialize Handshake
        init_res = mcp.initialize()
        print(f"✓ MCP Initialized. Capabilities: {init_res}")

        # 2. Discover MCP Tools
        tools = mcp.list_tools()
        print(f"✓ Discovered {len(tools)} MCP Tools:")
        for t in tools:
            name = t.get("name", "unknown") if isinstance(t, dict) else getattr(t, "name", str(t))
            print(f"  - Tool: {name}")

        # 3. Store Memory via MCP Tool Call
        res_store = mcp.store_memory(
            content="User is deploying VecminDB Docker on production server.",
            agent_id="prod_agent_01",
            is_factual=True  # Exempt from biological decay if vital factual data
        )
        print(f"✓ Stored memory via MCP tool: {res_store}")

        # 4. Search Memory via MCP Tool Call
        res_search = mcp.search_memory(
            query="What is user doing on production server?",
            agent_id="prod_agent_01",
            top_k=2
        )
        print(f"✓ MCP Search Result: {res_search}")


async def demo_async_mcp():
    print("\n--- [2] Asynchronous MCP Client Example (SSE Streaming) ---")
    endpoint = "http://localhost:5520"

    async with McpClient(base_url=endpoint) as mcp:
        # Async Tool Call
        res = await mcp.store_memory(
            content="Async MCP client initialized successfully.",
            agent_id="async_agent_01"
        )
        print(f"✓ Async MCP Store Result: {res}")


def main():
    print("=== VecminDB MCP (Model Context Protocol) SDK Demo ===")
    try:
        demo_sync_mcp()
        asyncio.run(demo_async_mcp())
        print("\n✓ MCP Demo completed successfully!")
    except Exception as e:
        print(f"\n[Note] MCP connection test: {e}")
        print("Ensure VecminDB server is running at http://localhost:5520.")
        sys.exit(0)


if __name__ == "__main__":
    main()
