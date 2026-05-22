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
  SearchMemoryParams,
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
    await this.rpc("tools/call", {
      name: "store_memory",
      arguments: {
        agent_id: params.agent_id,
        text: params.text,
        source: params.source ?? "typescript-sdk",
        collection: params.collection ?? "agent_memory_mcp",
      },
    });
  }

  /**
   * Call the `search_memory` MCP tool.
   *
   * @example
   * ```ts
   * const results = await mcp.searchMemory({ query: "preferences", agent_id: "agent-1", top_k: 5 });
   * ```
   */
  async searchMemory(params: SearchMemoryParams): Promise<MCPSearchResult[]> {
    const result = await this.rpc<MCPSearchResult[]>("tools/call", {
      name: "search_memory",
      arguments: {
        agent_id: params.agent_id,
        query: params.query,
        top_k: params.top_k ?? 5,
        collection: params.collection ?? "agent_memory_mcp",
      },
    });
    return result;
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
