# -*- coding: utf-8 -*-
"""Runnable example: wire a hand-rolled agent loop to VecminDB memory
in two lines with AgentMemory.

    python examples/05_agent_memory.py

Replace ENDPOINT / API_KEY with your deployment. Memory never breaks
the agent: on network failure both calls degrade to no-ops.
"""

import os

from vecmindb import agent_memory

ENDPOINT = os.environ.get("VECMINDB_ENDPOINT", "http://localhost:5520")
API_KEY = os.environ.get("VECMINDB_API_KEY", "")


def fake_llm(question: str, context: str) -> str:
    """Stand-in for the agent's own LLM call — in a real agent this is your model."""
    if context:
        return f"[using {context.count(chr(10))} memories] answered: {question}"
    return f"answered (no relevant memory): {question}"


def main() -> None:
    mem = agent_memory(endpoint=ENDPOINT, api_key=API_KEY, agent_id="example-agent")

    turns = [
        "客户对部署方式有什么要求?",  # related -> before_turn returns memories
        "今天晚饭吃什么好呢?",        # unrelated -> before_turn returns "" (relevance gate)
    ]
    for question in turns:
        context = mem.before_turn(question, top_k=3)
        reply = fake_llm(question, context)
        print(f"Q: {question}")
        print(f"context: {context or '(empty — gated)'}")
        print(f"A: {reply}")
        memory_id = mem.after_turn(question, reply)
        print(f"stored: {memory_id or '(skipped/failed)'}\n")


if __name__ == "__main__":
    main()
