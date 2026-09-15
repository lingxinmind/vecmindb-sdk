/**
 * Turn-loop memory primitives for custom / self-written agents.
 *
 * Wire any agent loop to the cognitive memory layer in two lines:
 *
 * ```ts
 * const mem = new AgentMemory(space);
 * const context = await mem.beforeTurn(userMessage); // "" when nothing clears the gate
 * await mem.afterTurn(userMessage, reply);           // auto-summarized store
 * ```
 *
 * Invariants:
 * - `beforeTurn` returns an EMPTY STRING for unrelated queries. The
 *   server-side relevance gate (`memory.search_min_score`) answers
 *   "No relevant memory found" instead of returning the least-dissimilar
 *   neighbors, so clients carry zero threshold logic.
 * - Memory never breaks the agent: every call degrades to a no-op with
 *   a warning on network failure.
 * - `afterTurn` auto-summarizes (question + first 200 characters of the
 *   reply) unless `options.summary` is set; `summary: null` skips the
 *   store entirely (empty chatter).
 */

import { VecminMemorySpace, SpaceStoreOptions } from "./memory.js";

/** Characters kept from the reply tail in an auto-generated summary. */
const SUMMARY_CHAR_CAP = 200;

/** Builds the default stored summary: question + capped reply tail. */
export function autoSummary(question: string, reply: string): string {
  let tail = (reply ?? "").trim();
  if (tail.length > SUMMARY_CHAR_CAP) {
    tail = tail.slice(0, SUMMARY_CHAR_CAP).trimEnd() + "...";
  }
  return `Q: ${question.trim()}\nA: ${tail}`;
}

interface HitLike {
  score?: number;
  text?: string;
  content?: string;
}

/**
 * Tolerant extraction of a context block from whatever the search layer
 * returned: a raw human-readable report string, or structured hits.
 * Anything unexpected yields "" (an empty context is safer than a wrong
 * one).
 */
function extractContext(results: unknown): string {
  if (typeof results === "string") {
    const report = results;
    if (!report || report.includes("No relevant memory")) return "";
    const hits: HitLike[] = [];
    for (const line of report.split(/\r?\n/)) {
      const m = line.trim().match(/^\d+\. \[Score: ([\d.]+)\] ID: (\S+)/);
      if (m) {
        hits.push({ score: Number(m[1]), text: "" });
        continue;
      }
      const last = hits[hits.length - 1];
      const textMatch = line.trim().match(/^Text: (.*)$/);
      if (last && textMatch) last.text = textMatch[1];
    }
    const usable = hits.filter((h) => h.text);
    if (usable.length === 0) return "";
    const lines = ["[Relevant memories]"];
    for (const h of usable) {
      lines.push(`- (${(h.score ?? 0).toFixed(2)}) ${h.text}`);
    }
    return lines.join("\n");
  }
  if (Array.isArray(results)) {
    const arr = results as HitLike[];
    // The memory space wraps a raw server report as a single-element
    // array ({ text: report }). Route it through the report parser
    // (gate check + score/Text extraction) instead of rendering it as
    // a hit; anything unparseable falls out as "".
    const first = arr[0];
    if (
      arr.length === 1 &&
      first &&
      typeof first.text === "string" &&
      typeof first.score !== "number"
    ) {
      return extractContext(first.text);
    }
    const hits = arr.filter((h) => h && (h.text || h.content));
    if (hits.length === 0) return "";
    const lines = ["[Relevant memories]"];
    for (const h of hits) {
      const text = (h.text ?? h.content ?? "") as string;
      const score = typeof h.score === "number" ? ` (${h.score.toFixed(2)})` : "";
      lines.push(`- ${text}${score}`);
    }
    return lines.length > 1 ? lines.join("\n") : "";
  }
  return "";
}

export interface AfterTurnOptions {
  /** Override the auto-generated summary; `null` skips the store. */
  summary?: string | null;
  /** Mark durable constraints/decisions for strong anchoring. */
  isFactual?: boolean;
  metadata?: Record<string, unknown>;
}

/** Turn-loop memory facade over a memory space (never throws). */
export class AgentMemory {
  constructor(public readonly space: VecminMemorySpace) {}

  /** Returns a prompt-injectable context block, or "" when nothing
   * clears the relevance gate. Never throws. */
  async beforeTurn(query: string, topK = 3): Promise<string> {
    try {
      const results = await this.space.searchMemory({ query, topK });
      return extractContext(results);
    } catch (err) {
      console.warn("vecmindb beforeTurn degraded to empty:", err);
      return "";
    }
  }

  /** Stores this turn's memory; resolves to the memory ID or null.
   * Default summary auto-truncates; `summary: null` skips. */
  async afterTurn(
    question: string,
    reply: string,
    options: AfterTurnOptions = {},
  ): Promise<string | null> {
    const { summary, isFactual = false, metadata } = options;
    if (summary === null) return null;
    const text = summary === undefined ? autoSummary(question, reply) : summary;
    try {
      const storeOptions: SpaceStoreOptions = { metadata, isFactual };
      return await this.space.storeMemory(text, storeOptions);
    } catch (err) {
      console.warn("vecmindb afterTurn degraded to no-op:", err);
      return null;
    }
  }
}
