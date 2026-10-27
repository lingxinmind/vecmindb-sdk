/**
 * @module mcp
 * @description MCP (Model Context Protocol) client for VecminDB.
 *
 * Provides:
 * - SSE event-stream connection (`GET /mcp/sse`)
 * - JSON-RPC 2.0 tool invocation (`POST /mcp/messages`)
 *
 * The MCP protocol enables AI agents to store and retrieve memories
 * through a standardised tool interface.
 */

import type {
  MCPClientOptions,
  StoreMemoryParams,
  StoreMediaParams,
  SearchMemoryParams,
  SearchMediaByImageParams,
  ListMemoriesParams,
  GetMemoryParams,
  ForgetParams,
  MemoryStatusParams,
  ConsolidateParams,
  FactualityTemplateParams,
  UpdateMemoryParams,
  FreezeMemoryParams,
  ExportMemoryParams,
  ImportMemoriesParams,
  UpdateMemorySharingParams,
  SetTenantGrantParams,
  ShareWithTenantParams,
  UpdateShareSubscriptionParams,
  GetMemoryRulesParams,
  MCPSearchResult,
  JsonRpcRequest,
  JsonRpcResponse,
} from "./models.js";
import { createErrorFromStatus, VecminError } from "./errors.js";

// ---------------------------------------------------------------------------
// Event types
// ---------------------------------------------------------------------------

/** Events emitted by {@link VecminMCPClient}. */
export type MCPEventMap = {
  /** Fired when the SSE connection is established. */
  connected: void;
  /** Fired when the SSE connection is closed. */
  disconnected: void;
  /** Fired for each SSE event received from the server. */
  event: { event: string; data: string };
  /** Fired when a JSON-RPC response is received. */
  result: { id: number; result: unknown };
  /** Fired when an error occurs. */
  error: Error;
};

type EventHandler<T> = (data: T) => void;

// ---------------------------------------------------------------------------
// VecminMCPClient
// ---------------------------------------------------------------------------

/**
 * Low-level MCP client that connects to a VecminDB server's
 * Model Context Protocol endpoints.
 *
 * ### SSE (Server-Sent Events)
 * The client opens a persistent connection to `GET /mcp/sse` and parses
 * incoming events using the `eventsource-parser` library.
 *
 * ### JSON-RPC 2.0
 * Tool invocations (`store_memory`, `search_memory`) are sent as JSON-RPC
 * requests to `POST /mcp/messages`.
 *
 * @example
 * ```ts
 * const mcp = new VecminMCPClient("http://localhost:8080", { apiKey: "my-key" });
 * await mcp.connect();
 *
 * mcp.on("event", ({ event, data }) => console.log(event, data));
 *
 * await mcp.storeMemory({ text: "Hello world", agent_id: "agent-1" });
 * const results = await mcp.searchMemory({ query: "hello", agent_id: "agent-1" });
 *
 * await mcp.disconnect();
 * ```
 */
export class VecminMCPClient {
  private readonly baseUrl: string;
  private readonly mcpUrl: string;
  private readonly options: MCPClientOptions;
  private readonly handlers: Map<string, Set<EventHandler<unknown>>> = new Map();
  private rpcId = 0;
  private readonly pendingRpc: Map<number, {
    resolve: (value: unknown) => void;
    reject: (reason: unknown) => void;
  }> = new Map();
  private abortController: AbortController | null = null;
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private connected = false;

  constructor(baseUrl: string, options?: MCPClientOptions) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.mcpUrl = `${this.baseUrl}/mcp`;
    this.options = options ?? {};
  }

  // -----------------------------------------------------------------------
  // Event emitter
  // -----------------------------------------------------------------------

  /**
   * Register an event handler.
   *
   * @param event   - One of the {@link MCPEventMap} keys.
   * @param handler - Callback invoked when the event fires.
   */
  on<K extends keyof MCPEventMap>(event: K, handler: EventHandler<MCPEventMap[K]>): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }
    this.handlers.get(event)!.add(handler as EventHandler<unknown>);
  }

  /**
   * Remove a previously registered event handler.
   */
  off<K extends keyof MCPEventMap>(event: K, handler: EventHandler<MCPEventMap[K]>): void {
    this.handlers.get(event)?.delete(handler as EventHandler<unknown>);
  }

  private emit<K extends keyof MCPEventMap>(event: K, data: MCPEventMap[K]): void {
    for (const handler of this.handlers.get(event) ?? []) {
      try {
        (handler as EventHandler<MCPEventMap[K]>)(data);
      } catch {
        // Swallow handler errors — don't break the event loop.
      }
    }
  }

  // -----------------------------------------------------------------------
  // SSE Connection
  // -----------------------------------------------------------------------

  /**
   * Open the SSE event-stream connection to `GET /mcp/sse`.
   *
   * The connection remains open until {@link disconnect} is called.
   * Events are parsed and emitted via the `on("event", ...)` interface.
   */
  async connect(): Promise<void> {
    if (this.connected) return;

    this.abortController = new AbortController();
    const headers: Record<string, string> = {
      Accept: "text/event-stream",
    };
    if (this.options.apiKey) headers["x-api-key"] = this.options.apiKey;
    if (this.options.jwt) headers["Authorization"] = `Bearer ${this.options.jwt}`;
    if (this.options.agentId) headers["x-agent-id"] = this.options.agentId;
    if (this.options.modelId) headers["x-model-id"] = this.options.modelId;

    const response = await fetch(`${this.mcpUrl}/sse`, {
      method: "GET",
      headers,
      signal: this.abortController.signal,
    });

    if (!response.ok) {
      throw createErrorFromStatus(
        response.status,
        `SSE connection failed: HTTP ${response.status}`,
      );
    }

    const body = response.body;
    if (!body) {
      throw new VecminError("SSE connection returned no body", 0);
    }

    this.connected = true;
    this.emit("connected", undefined as unknown as void);

    // Start reading the SSE stream in the background.
    this.readSSEStream(body).catch((err: unknown) => {
      if (this.connected) {
        this.emit("error", err instanceof Error ? err : new Error(String(err)));
      }
    });
  }

  /**
   * Read and parse an SSE stream using `eventsource-parser`.
   */
  private async readSSEStream(stream: ReadableStream<Uint8Array>): Promise<void> {
    // Dynamic import so the dependency is only loaded when SSE is used.
    const { createParser } = await import("eventsource-parser");

    const parser = createParser((event) => {
      // eventsource-parser emits EventSourceMessage (with `data`, `event` fields)
      // or ReconnectInterval. We only handle the message type.
      if (!("data" in event)) return;

      this.emit("event", { event: (event as { event?: string; data: string }).event ?? "message", data: event.data });

      // Check if the event data is a JSON-RPC response.
      if (event.data) {
        try {
          const json = JSON.parse(event.data) as JsonRpcResponse;
          if (json.id !== undefined && json.id !== null) {
            const pending = this.pendingRpc.get(json.id);
            if (pending) {
              this.pendingRpc.delete(json.id);
              if (json.error) {
                pending.reject(
                  new VecminError(json.error.message ?? "JSON-RPC error", json.error.code),
                );
              } else {
                pending.resolve(json.result);
              }
              this.emit("result", { id: json.id, result: json.result });
            }
          }
        } catch {
          // Not JSON or not a JSON-RPC response — ignore.
        }
      }
    });

    this.reader = stream.getReader();
    const decoder = new TextDecoder();

    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await this.reader.read();
        if (done) break;
        parser.feed(decoder.decode(value, { stream: true }));
      }
    } finally {
      this.connected = false;
      this.emit("disconnected", undefined as unknown as void);
    }
  }

  // -----------------------------------------------------------------------
  // JSON-RPC Calls
  // -----------------------------------------------------------------------

  /**
   * Send a JSON-RPC 2.0 request to `POST /mcp/messages`.
   *
   * @returns The `result` field of the JSON-RPC response.
   */
  private async rpc<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> {
    const id = ++this.rpcId;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.options.apiKey) headers["x-api-key"] = this.options.apiKey;
    if (this.options.jwt) headers["Authorization"] = `Bearer ${this.options.jwt}`;
    if (this.options.agentId) headers["x-agent-id"] = this.options.agentId;
    if (this.options.modelId) headers["x-model-id"] = this.options.modelId;

    // If the SSE connection is open, also handle responses from the stream.
    // But we also POST and wait for the HTTP response for reliability.
    const rpcPromise = new Promise<T>((resolve, reject) => {
      this.pendingRpc.set(id, { resolve: resolve as (v: unknown) => void, reject });
    });

    const res = await fetch(`${this.mcpUrl}/messages`, {
      method: "POST",
      headers,
      body: JSON.stringify(request),
    });

    if (!res.ok) {
      this.pendingRpc.delete(id);
      throw createErrorFromStatus(res.status, `MCP RPC call failed: HTTP ${res.status}`);
    }

    // Try to parse the HTTP response directly first.
    const text = await res.text();
    if (text) {
      try {
        const json = JSON.parse(text) as JsonRpcResponse<T>;
        this.pendingRpc.delete(id);
        if (json.error) {
          throw new VecminError(json.error.message ?? "JSON-RPC error", json.error.code);
        }
        return (json.result ?? json) as T;
      } catch (err) {
        if (err instanceof VecminError) throw err;
        // Fall through to SSE-based response.
      }
    }

    // Wait for the SSE stream to deliver the response.
    return rpcPromise;
  }

  // -----------------------------------------------------------------------
  // MCP Tool Methods
  // -----------------------------------------------------------------------

  /**
   * Call the `store_memory` MCP tool.
   *
   * @example
   * ```ts
   * await mcp.storeMemory({ text: "User prefers dark mode", agent_id: "agent-1" });
   * ```
   */
  async storeMemory(params: StoreMemoryParams): Promise<void> {
    const metadata = {
      ...(params.metadata ?? {}),
      ...(params.source ? { source: params.source } : {}),
    };
    await this.rpc("tools/call", {
      name: "store_memory",
      arguments: {
        agent_id: params.agent_id,
        text: params.text,
        is_factual: params.is_factual ?? false,
        ...(params.is_obsolete !== undefined ? { is_obsolete: params.is_obsolete } : {}),
        ...(Object.keys(metadata).length > 0 ? { metadata } : {}),
      },
    });
  }

  /**
   * Call the `search_memory` MCP tool.
   *
   * Optional R3-4 structured filters: `since_ts` / `until_ts` (epoch
   * seconds), `tags` (any-of), `keyword` (substring, case-insensitive).
   *
   * @example
   * ```ts
   * const results = await mcp.searchMemory({ query: "preferences", agent_id: "agent-1", top_k: 5 });
   * ```
   */
  async searchMemory(params: SearchMemoryParams): Promise<MCPSearchResult[]> {
    const arguments_: Record<string, unknown> = {
      agent_id: params.agent_id,
      query: params.query,
      top_k: params.top_k ?? 5,
    };
    if (params.since_ts !== undefined) arguments_["since_ts"] = params.since_ts;
    if (params.until_ts !== undefined) arguments_["until_ts"] = params.until_ts;
    if (params.tags !== undefined) arguments_["tags"] = params.tags;
    if (params.keyword !== undefined) arguments_["keyword"] = params.keyword;
    const result = await this.rpc<MCPSearchResult[]>("tools/call", {
      name: "search_memory",
      arguments: arguments_,
    });
    return result;
  }

  /**
   * Call the `store_media` MCP tool.
   *
   * The caption is caller-supplied (the agent generates the description
   * agent-side; the server runs zero vision models). Without a caption the
   * media stays `pending` and is not text-searchable until re-stored with
   * the same `media_id` and a caption. `clip_vector` is an optional
   * agent-side CLIP embedding for image-to-image search (M4); it requires
   * `media.clip_collection` server-side.
   *
   * @example
   * ```ts
   * await mcp.storeMedia({ media_data: base64, media_id: "scan-1", caption: "signed contract" });
   * ```
   */
  async storeMedia(params: StoreMediaParams): Promise<void> {
    const arguments_: Record<string, unknown> = {
      kind: params.kind ?? "image",
      is_factual: params.is_factual ?? false,
    };
    if (params.caption !== undefined) arguments_["caption"] = params.caption;
    if (params.media_data !== undefined) arguments_["media_data"] = params.media_data;
    if (params.media_id !== undefined) arguments_["media_id"] = params.media_id;
    if (params.mime !== undefined) arguments_["mime"] = params.mime;
    if (params.source_ref !== undefined) arguments_["source_ref"] = params.source_ref;
    if (params.clip_vector !== undefined) arguments_["clip_vector"] = params.clip_vector;
    await this.rpc("tools/call", {
      name: "store_media",
      arguments: arguments_,
    });
  }

  /**
   * Image-to-image search via the `search_media_by_image` MCP tool.
   *
   * The CLIP embedding is computed agent-side (the server runs zero vision
   * models): either pass a precomputed `clip_vector` or supply `image`
   * together with a `clip_encoder` callable. Searches the auxiliary CLIP
   * space only; requires `media.clip_collection` server-side (M4, disabled
   * by default).
   *
   * @example
   * ```ts
   * const hits = await mcp.searchByImage({ clip_vector: [0.1, 0.2, 0.3], top_k: 5 });
   * ```
   */
  async searchByImage(params: SearchMediaByImageParams): Promise<unknown> {
    let clipVector = params.clip_vector;
    if (clipVector === undefined) {
      if (params.image === undefined || params.clip_encoder === undefined) {
        throw new VecminError(
          "searchByImage needs either clip_vector or image + clip_encoder",
          0,
        );
      }
      clipVector = params.clip_encoder(params.image);
    }
    return this.rpc("tools/call", {
      name: "search_media_by_image",
      arguments: {
        clip_vector: clipVector,
        top_k: params.top_k ?? 5,
        min_score: params.min_score ?? 0,
      },
    });
  }

  /**
   * Call the `list_memories` MCP tool: enumerate the caller's own memories
   * (id, full text, metadata), newest first. `shared_with_me: true` is the
   * inbox view — only entries other tenants shared with you.
   */
  async listMemories(params: ListMemoriesParams = {}): Promise<unknown> {
    const arguments_: Record<string, unknown> = {
      limit: params.limit ?? 20,
    };
    if (params.shared_with_me !== undefined) {
      arguments_["shared_with_me"] = params.shared_with_me;
    }
    if (params.since_hours !== undefined) {
      arguments_["since_hours"] = params.since_hours;
    }
    if (params.since_ts !== undefined) arguments_["since_ts"] = params.since_ts;
    if (params.until_ts !== undefined) arguments_["until_ts"] = params.until_ts;
    if (params.tags !== undefined) arguments_["tags"] = params.tags;
    if (params.keyword !== undefined) arguments_["keyword"] = params.keyword;
    return this.rpc("tools/call", {
      name: "list_memories",
      arguments: arguments_,
    });
  }

  /**
   * Call the `get_memory` MCP tool: retrieve a single memory by vector ID.
   */
  async getMemory(params: GetMemoryParams): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "get_memory",
      arguments: { id: params.id },
    });
  }

  /**
   * Call the `forget` MCP tool: delete one or more memories by ID.
   */
  async forgetMemory(params: ForgetParams): Promise<unknown> {
    const arguments_: Record<string, unknown> = {
      collection: params.collection ?? "default",
    };
    if (params.id !== undefined) arguments_["id"] = params.id;
    if (params.ids !== undefined) arguments_["ids"] = params.ids;
    if (params.sovereignty_token !== undefined) {
      arguments_["sovereignty_token"] = params.sovereignty_token;
    }
    return this.rpc("tools/call", { name: "forget", arguments: arguments_ });
  }

  /**
   * Call the `memory_status` MCP tool: report the LTSM memory lifecycle.
   */
  async memoryStatus(params: MemoryStatusParams = {}): Promise<unknown> {
    const arguments_: Record<string, unknown> = {
      collection: params.collection ?? "default",
    };
    if (params.agent_id !== undefined) arguments_["agent_id"] = params.agent_id;
    return this.rpc("tools/call", { name: "memory_status", arguments: arguments_ });
  }

  /**
   * Call the `consolidate` MCP tool: trigger an LTSM distillation cycle.
   */
  async consolidate(params: ConsolidateParams = {}): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "consolidate",
      arguments: {
        collection: params.collection ?? "default",
        force: params.force ?? false,
      },
    });
  }

  /**
   * Call the `register_factuality_template` MCP tool.
   */
  async registerFactualityTemplate(params: FactualityTemplateParams): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "register_factuality_template",
      arguments: { text: params.text, template_type: params.template_type },
    });
  }

  /**
   * Call the `remove_factuality_template` MCP tool.
   */
  async removeFactualityTemplate(params: { text: string }): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "remove_factuality_template",
      arguments: { text: params.text },
    });
  }

  /**
   * Call the `update_memory` MCP tool: correct a memory in place — same id
   * and anchors, the corrected text re-embedded, the previous text appended
   * to a bounded history. `is_factual` optionally re-grades the anchor
   * (true = strong, false = weak; absent preserves the current grade).
   * Author-only.
   */
  async updateMemory(params: UpdateMemoryParams): Promise<void> {
    const arguments_: Record<string, unknown> = {
      id: params.id,
      text: params.text,
    };
    if (params.is_factual !== undefined) arguments_["is_factual"] = params.is_factual;
    await this.rpc("tools/call", {
      name: "update_memory",
      arguments: arguments_,
    });
  }

  /**
   * Call the `freeze_memory` MCP tool: freeze (or unfreeze) one of your
   * memories — frozen entries are exempt from LTSM distillation and
   * staleness scavenging ("do not touch this memory"). Advisory on top of
   * anchoring, reversible any time, author-only.
   */
  async freezeMemory(params: FreezeMemoryParams): Promise<void> {
    await this.rpc("tools/call", {
      name: "freeze_memory",
      arguments: { id: params.id, frozen: params.frozen },
    });
  }

  /**
   * Call the `export_memory` MCP tool: export YOUR memories (author-scoped,
   * own collection) as a self-contained JSON array or human-readable
   * Markdown — the lightweight "my data" answer, no admin gate.
   */
  async exportMemory(params: ExportMemoryParams = {}): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "export_memory",
      arguments: { format: params.format ?? "json" },
    });
  }

  /**
   * Call the `import_memories` MCP tool: first-run cold-start batch import
   * (cap 200 entries per call). Every entry goes through the same ingestion
   * core as `store_memory`, per-entry independent, with an honest
   * partial-failure report.
   */
  async importMemories(params: ImportMemoriesParams): Promise<void> {
    await this.rpc("tools/call", {
      name: "import_memories",
      arguments: { memories: params.memories },
    });
  }

  /**
   * Call the `update_memory_sharing` MCP tool: flip the cross-tenant
   * sharing flag on your own memories (owner-side only). Batch exposure
   * (>1 entry, shared=true) is two-phase — the first call returns a
   * dry-run summary, re-issue with `confirm: true` to apply.
   */
  async updateMemorySharing(params: UpdateMemorySharingParams): Promise<unknown> {
    const arguments_: Record<string, unknown> = {
      shared: params.shared,
    };
    if (params.id !== undefined) arguments_["id"] = params.id;
    if (params.ids !== undefined) arguments_["ids"] = params.ids;
    if (params.scope !== undefined) arguments_["scope"] = params.scope;
    if (params.except_tag !== undefined) arguments_["except_tag"] = params.except_tag;
    if (params.except_ids !== undefined) arguments_["except_ids"] = params.except_ids;
    if (params.shared_scope !== undefined) arguments_["shared_scope"] = params.shared_scope;
    if (params.confirm !== undefined) arguments_["confirm"] = params.confirm;
    return this.rpc("tools/call", {
      name: "update_memory_sharing",
      arguments: arguments_,
    });
  }

  /**
   * Call the `list_memory_tags` MCP tool: the distinct tags you have used
   * across your own memories, with per-tag counts and the number of
   * untagged entries.
   */
  async listMemoryTags(): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "list_memory_tags",
      arguments: {},
    });
  }

  /**
   * Call the `set_tenant_grant` MCP tool (owner-side only): grant (or
   * revoke) another tenant read access to your collection. Live
   * immediately; grantees still only see entries you marked shared via
   * `update_memory_sharing`.
   */
  async setTenantGrant(params: SetTenantGrantParams): Promise<void> {
    const arguments_: Record<string, unknown> = {
      tenant: params.tenant,
    };
    if (params.collections !== undefined) arguments_["collections"] = params.collections;
    if (params.revoke !== undefined) arguments_["revoke"] = params.revoke;
    await this.rpc("tools/call", {
      name: "set_tenant_grant",
      arguments: arguments_,
    });
  }

  /**
   * Call the `list_tenant_grants` MCP tool (owner-side reverse lookup):
   * which tenants currently hold read access to your collection.
   * Read-only; revoke with `set_tenant_grant({ revoke: true })`.
   */
  async listTenantGrants(): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "list_tenant_grants",
      arguments: {},
    });
  }

  /**
   * Call the `share_with_tenant` MCP tool: guided one-shot share in plain
   * words — grants the tenant read access AND semantically selects matching
   * entries, then returns a dry-run with per-entry previews and sensitivity
   * flags; re-issue with `confirm: true` to apply.
   */
  async shareWithTenant(params: ShareWithTenantParams): Promise<unknown> {
    const arguments_: Record<string, unknown> = {
      tenant: params.tenant,
      what: params.what,
    };
    if (params.shared_scope !== undefined) arguments_["shared_scope"] = params.shared_scope;
    if (params.confirm !== undefined) arguments_["confirm"] = params.confirm;
    return this.rpc("tools/call", {
      name: "share_with_tenant",
      arguments: arguments_,
    });
  }

  /**
   * Call the `update_share_subscription` MCP tool: standing share rule —
   * "future entries matching <what> go to <tenant>". Pure storage: never
   * shares anything by itself; pending matches appear via
   * `checkShareSubscriptions` and apply only after explicit confirm.
   * `{ remove: true }` clears the subscription.
   */
  async updateShareSubscription(params: UpdateShareSubscriptionParams = {}): Promise<void> {
    const arguments_: Record<string, unknown> = {};
    if (params.what !== undefined) arguments_["what"] = params.what;
    if (params.tenant !== undefined) arguments_["tenant"] = params.tenant;
    if (params.shared_scope !== undefined) arguments_["shared_scope"] = params.shared_scope;
    if (params.remove !== undefined) arguments_["remove"] = params.remove;
    await this.rpc("tools/call", {
      name: "update_share_subscription",
      arguments: arguments_,
    });
  }

  /**
   * Call the `check_share_subscriptions` MCP tool: lazy evaluation of your
   * standing share subscription — lists UNSHARED entries of yours that
   * currently match, with previews and sensitivity flags, plus the exact
   * one-step confirm command. Read-only: nothing is shared by checking.
   */
  async checkShareSubscriptions(): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "check_share_subscriptions",
      arguments: {},
    });
  }

  /**
   * Call the `get_memory_rules` MCP tool: the corrected, scope-guarded
   * memory-protocol rule block for a mainstream agent tool (claude_code |
   * cursor | workbuddy | all), with the exact local path to write it into.
   */
  async getMemoryRules(params: GetMemoryRulesParams = {}): Promise<unknown> {
    return this.rpc("tools/call", {
      name: "get_memory_rules",
      arguments: {
        target: params.target ?? "all",
        lang: params.lang ?? "en",
      },
    });
  }

  // -----------------------------------------------------------------------
  // Lifecycle
  // -----------------------------------------------------------------------

  /**
   * Close the SSE connection and release all resources.
   */
  async disconnect(): Promise<void> {
    this.connected = false;
    this.abortController?.abort();
    this.abortController = null;

    try {
      await this.reader?.cancel();
    } catch {
      // Ignore — the reader may already be released.
    }
    this.reader = null;

    // Reject all pending RPC calls.
    for (const [id, { reject }] of this.pendingRpc) {
      reject(new VecminError("MCP client disconnected", 0));
      this.pendingRpc.delete(id);
    }
  }
}
