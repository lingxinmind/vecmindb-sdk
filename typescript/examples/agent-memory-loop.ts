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
  const client = new VecminClient({ baseUrl: ENDPOINT, apiKey: API_KEY, agentId: "example-agent" });
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

  // Recommended: pass a host-LLM signpost summary instead of the
  // mechanical fallback. The stored `text` is read by the embedding
  // model, not humans — 1–3 sentences of facts, every word a future
  // search would use; evidence goes into metadata.detail (see
  // README "Signpost summary with a host LLM").
  const signpost =
    "客户 ACME 部署方案：选 B 版（自建集群），预算 80 万，决策人张三";
  const memoryId = await mem.afterTurn(
    "客户 ACME 部署方案定了吗?",
    fakeLlm("客户 ACME 部署方案定了吗?", "(meeting transcript)"),
    { summary: signpost, isFactual: true }
  );
  console.log(`signpost stored: ${memoryId ?? "(skipped/failed)"}`);
}

main().catch((err) => {
  console.error("example failed:", err);
  process.exit(1);
});
