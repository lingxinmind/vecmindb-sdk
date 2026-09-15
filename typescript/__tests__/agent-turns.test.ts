/**
 * Unit tests for the turn-loop memory primitives (AgentMemory).
 * Mirrors the Python semantics: relevance-gate empty context,
 * auto-truncated summary with override/skip, isFactual passthrough,
 * and never-throws degradation.
 */

import { AgentMemory, autoSummary } from "../src/agent-turns.js";
import { VecminMemorySpace } from "../src/memory.js";

const REPORT_WITH_HITS = [
  "Retrieved 2 relevant semantic anchors from domain 'system':",
  "1. [Score: 0.9123] ID: abc123",
  "   Text: customer requires SLA 99.9%",
  "2. [Score: 0.7031] ID: def456",
  "   Text: audit logs kept 180 days",
].join("\n");

function spaceWith(report: unknown, storeResult = "mem-id-1"): VecminMemorySpace {
  return {
    searchMemory: jest.fn().mockResolvedValue([{ text: report }]),
    storeMemory: jest.fn().mockResolvedValue(storeResult),
  } as unknown as VecminMemorySpace;
}

describe("autoSummary", () => {
  it("truncates the reply tail to the cap", () => {
    const s = autoSummary("question?", "x".repeat(500));
    expect(s.startsWith("Q: question?\nA: ")).toBe(true);
    expect(s.split("A: ", 2)[1]!.length).toBeLessThanOrEqual(203);
  });

  it("is safe on empty replies", () => {
    expect(autoSummary("q", "")).toBe("Q: q\nA: ");
  });
});

describe("AgentMemory.afterTurn", () => {
  it("auto-summarizes by default", async () => {
    const space = spaceWith("");
    const mem = new AgentMemory(space);
    const id = await mem.afterTurn("why slow?", "because hnsw_ef_search is low");
    expect(id).toBe("mem-id-1");
    const stored = (space.storeMemory as jest.Mock).mock.calls[0][0] as string;
    expect(stored).toContain("why slow?");
    expect(stored).toContain("hnsw_ef_search");
  });

  it("explicit summary wins", async () => {
    const space = spaceWith("");
    const mem = new AgentMemory(space);
    await mem.afterTurn("q", "r", { summary: "custom summary" });
    const stored = (space.storeMemory as jest.Mock).mock.calls[0][0] as string;
    expect(stored).toContain("custom summary");
  });

  it("summary: null skips the store", async () => {
    const space = spaceWith("");
    const mem = new AgentMemory(space);
    expect(await mem.afterTurn("q", "r", { summary: null })).toBeNull();
    expect(space.storeMemory).not.toHaveBeenCalled();
  });

  it("store failures degrade to null instead of throwing", async () => {
    const space = spaceWith("");
    (space.storeMemory as jest.Mock).mockRejectedValue(new Error("down"));
    const mem = new AgentMemory(space);
    await expect(mem.afterTurn("q", "r")).resolves.toBeNull();
  });

  it("passes isFactual through", async () => {
    const space = spaceWith("");
    const mem = new AgentMemory(space);
    await mem.afterTurn("q", "r", { summary: "requirement", isFactual: true });
    const options = (space.storeMemory as jest.Mock).mock.calls[0][1] as {
      isFactual: boolean;
    };
    expect(options.isFactual).toBe(true);
  });
});

describe("AgentMemory.beforeTurn", () => {
  it("formats hits into a context block", async () => {
    const mem = new AgentMemory(spaceWith(REPORT_WITH_HITS));
    const ctx = await mem.beforeTurn("SLA availability");
    expect(ctx).toContain("[Relevant memories]");
    expect(ctx).toContain("0.91");
    expect(ctx).toContain("customer requires SLA 99.9%");
  });

  it("gated empty returns an empty string", async () => {
    const mem = new AgentMemory(
      spaceWith("No relevant memory found in domain 'system' (no match cleared threshold 0.70)."),
    );
    expect(await mem.beforeTurn("unrelated topic")).toBe("");
  });

  it("unparseable reports return an empty string", async () => {
    const mem = new AgentMemory(spaceWith("some totally unexpected format"));
    expect(await mem.beforeTurn("q")).toBe("");
  });

  it("search failures return an empty string instead of throwing", async () => {
    const space = spaceWith(REPORT_WITH_HITS);
    (space.searchMemory as jest.Mock).mockRejectedValue(new Error("down"));
    const mem = new AgentMemory(space);
    await expect(mem.beforeTurn("q")).resolves.toBe("");
  });
});
