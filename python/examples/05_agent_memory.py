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

    # Recommended: pass a host-LLM signpost summary instead of the
    # mechanical fallback. The stored `text` is read by the embedding
    # model, not humans — 1–3 sentences of facts, every word a future
    # search would use; evidence goes into metadata.detail (see the
    # package README "Signpost summary with a host LLM").
    signpost = "客户 ACME 部署方案：选 B 版（自建集群），预算 80 万，决策人张三"
    memory_id = mem.after_turn(
        "客户 ACME 部署方案定了吗?",
        fake_llm("客户 ACME 部署方案定了吗?", "(meeting transcript)"),
        summary=signpost,
        is_factual=True,
    )
    print(f"signpost stored: {memory_id or '(skipped/failed)'}")


if __name__ == "__main__":
    main()
