"""VecminDB MCP Server – FastMCP Integration.

Provides an MCP (Model Context Protocol) server that exposes VecminDB
operations as tools that LLMs can invoke directly.  Uses the commercial-grade
VecminDB Python SDK under the hood.
"""

import os
from typing import List, Optional

from vecmindb.client import VecminClient
from vecmindb.exceptions import VecminError

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("VecminDB-Memory-Engine")
    def tool_decorator(): return mcp.tool()
except ImportError:
    mcp = None
    def tool_decorator():
        def decorator(func):
            return func
        return decorator

VECMIN_URL = os.getenv("VECMIN_URL", "http://localhost:5520")
VECMIN_API_KEY = os.getenv("VECMIN_API_KEY", "")

vecmin = VecminClient(base_url=VECMIN_URL, api_key=VECMIN_API_KEY or None)

# Ensure default collection exists
try:
    vecmin.ensure_collection("agent_memory_mcp", dimension=384)
except Exception as e:
    print(f"Warning: Could not connect to VecminDB at startup: {e}")


def get_embedding(text: str) -> List[float]:
    """Retrieve vector embeddings.

    If ``OPENAI_API_KEY`` is set, calls the OpenAI embedding API.
    Otherwise, uses a deterministic mock hash for local testing without
    external dependencies.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        import requests
        res = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": text, "model": "text-embedding-3-small"},
        )
        if res.status_code == 200:
            full_vector = res.json()["data"][0]["embedding"]
            return full_vector[:384]

    # Fallback: mock mathematical embedding for local zero-config testing
    import hashlib
    h = hashlib.md5(text.encode()).digest()
    base_val = sum(h) / 255.0
    return [base_val * (i % 10) * 0.1 for i in range(384)]


@tool_decorator()
def store_memory(agent_id: str, content: str, source: str = "mcp_session") -> str:
    """Store an important memory, fact, or instruction for the AI Agent into VecminDB long-term memory.

    Args:
        agent_id: A unique identifier for the current agent or session.
        content: The text content to remember (e.g., "User prefers dark mode").
        source: Where this memory came from.
    """
    vector = get_embedding(content)
    metadata = {
        "agent_id": agent_id,
        "content": content,
        "source": source,
    }
    try:
        doc_id = vecmin.insert("agent_memory_mcp", vector=vector, metadata=metadata)
        return f"Successfully stored memory with ID: {doc_id}"
    except VecminError as e:
        return f"Failed to store memory: {e}"


@tool_decorator()
def search_memory(agent_id: str, query: str, top_k: int = 3) -> str:
    """Search the VecminDB Active Memory Engine for relevant past facts or conversation context.

    Args:
        agent_id: A unique identifier for the current agent or session.
        query: The natural language question or topic to search for.
        top_k: Number of results to retrieve.
    """
    vector = get_embedding(query)
    try:
        response = vecmin.search("agent_memory_mcp", query=vector, top_k=top_k)
        agent_results = []
        for hit in response.results:
            meta = hit.metadata or {}
            r_agent = meta.get("agent_id", {})
            if isinstance(r_agent, dict):
                r_agent = r_agent.get("String")

            if r_agent == agent_id:
                content = meta.get("content", {})
                if isinstance(content, dict):
                    content = content.get("String", "")
                agent_results.append(f"- {content} (Score: {hit.score:.4f})")

        if not agent_results:
            return f"No relevant memories found for {agent_id}."

        return "Found the following memories:\n" + "\n".join(agent_results)

    except VecminError as e:
        return f"Failed to search memory: {e}"


if __name__ == "__main__":
    if mcp:
        mcp.run()
    else:
        print("[Mock Mode] FastMCP not installed (requires Python 3.10+). Running logic test...")
        print("\n1. Testing store_memory...")
        res_store = store_memory("agent_mcp_test", "The user's favorite programming language is Rust.")
        print(f"Result: {res_store}")

        print("\n2. Testing search_memory...")
        res_search = search_memory("agent_mcp_test", "programming language")
        print(f"Result:\n{res_search}")

        if "Rust" in res_search:
            print("\n✓ MCP Logic Integration Passed!")
        else:
            print("\n! MCP Logic Integration Failed (missing expected memory).")
