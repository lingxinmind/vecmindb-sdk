/**
 * Runnable example: wire a hand-rolled agent loop to VecminDB memory
 * in two lines with AgentMemory.
 *
 *   npx tsx examples/agent-memory-loop.ts
 *
 * Replace ENDPOINT / API_KEY with your deployment. Memory never breaks
 * the agent: on network failure both calls degrade to no-ops.
 */

import { AgentMemory } from "../src/agent-turns.js";
import { VecminMemorySpace } from "../src/memory.js";
import { VecminClient } from "../src/client.js";

const ENDPOINT = process.env.VECMINDB_ENDPOINT ?? "http://localhost:5520";
const API_KEY = process.env.VECMINDB_API_KEY ?? "";

async function main(): Promise<void> {
  const client = new VecminClient(ENDPOINT, { apiKey: API_KEY, agentId: "example-agent" });
  const space = new VecminMemorySpace(
    client,
    "default",
    "example-agent",
    "",
    "",
  );
  const mem = new AgentMemory(space);

  // Stand-in for the agent's own LLM call — in a real agent this is your model.
  const fakeLlm = (question: string, context: string): string =>
    context
      ? `[using ${context.split("\n").length - 1} memories] answered: ${question}`
      : `answered (no relevant memory): ${question}`;

  const turns = [
    "客户对部署方式有什么要求?", // related -> before_turn returns memories
    "今天晚饭吃什么好呢?", // unrelated -> before_turn returns "" (relevance gate)
  ];

  for (const question of turns) {
    const context = await mem.beforeTurn(question, 3);
    const reply = fakeLlm(question, context);
    console.log(`Q: ${question}`);
    console.log(`context: ${context || "(empty — gated)"}`);
    console.log(`A: ${reply}`);
    const memoryId = await mem.afterTurn(question, reply);
    console.log(`stored: ${memoryId ?? "(skipped/failed)"}\n`);
  }
}

main().catch((err) => {
  console.error("example failed:", err);
  process.exit(1);
});
