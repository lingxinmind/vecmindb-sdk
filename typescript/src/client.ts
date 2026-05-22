/**
 * @module client
 * @description Main VecminDB SDK client.
 *
 * `VecminClient` is the primary entry-point for interacting with a
 * VecminDB server. It provides typed, async methods for every API endpoint
 * and transparently handles authentication, retries, and response unwrapping.
 */

import type {
  VecminClientOptions,
  CreateCollectionParams,
  Collection,
  CollectionStats,
  InsertParams,
  SearchParams,
  SearchResult,
  Vector,
  IndexInfo,
  LoginParams,
  Node,
  ClusterStatus,
  MCPOptions,
  MCPSearchResult,
  RetryOptions,
} from "./models.js";
import { AuthManager } from "./auth.js";
import { fetchJson } from "./retry.js";

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

/**
 * Official TypeScript client for VecminDB.
 *
 * @example
 * ```ts
 * const client = new VecminClient({ baseUrl: "http://localhost:8080", apiKey: "my-key" });
 *
 * await client.createCollection({ name: "docs", dimension: 1536 });
 * const id = await client.insert("docs", { vector: [0.1, 0.2, ...], metadata: { title: "Hello" } });
 * const results = await client.search("docs", { query: [0.1, 0.2, ...], k: 5 });
 * ```
 */
export class VecminClient {
  /** Resolved base URL (trailing slash stripped). */
  private readonly baseUrl: string;
  /** API path prefix. */
  private readonly apiUrl: string;
  /** MCP path prefix. */
  private readonly mcpUrl: string;
  /** Authentication manager. */
  private readonly auth: AuthManager;
  /** Request timeout in milliseconds. */
  private readonly timeout: number;
  /** Retry configuration propagated to every request. */
  private readonly retryOptions: RetryOptions;
  /** Default headers merged into every request. */
  private readonly defaultHeaders: Record<string, string>;
  /** Abort controllers for in-flight requests (used by `close()`). */
  private readonly controllers: Set<AbortController> = new Set();
  /** Whether the client has been closed. */
  private closed = false;

  constructor(options: VecminClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiUrl = `${this.baseUrl}/api/v1`;
    this.mcpUrl = `${this.baseUrl}/mcp`;

    this.auth = new AuthManager(this.baseUrl, options);
    this.timeout = options.timeout ?? 30_000;
    this.retryOptions = {
      maxRetries: options.maxRetries ?? 3,
      backoffFactor: options.backoffFactor ?? 0.5,
    };

    this.defaultHeaders = {
      "Content-Type": "application/json",
      ...options.defaultHeaders,
    };

    if (options.agentId) this.defaultHeaders["x-agent-id"] = options.agentId;
    if (options.modelId) this.defaultHeaders["x-model-id"] = options.modelId;
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  /** Build the full headers map for an outgoing request. */
  private async buildHeaders(): Promise<Record<string, string>> {
    const authHeaders = await this.auth.getHeaders();
    return { ...this.defaultHeaders, ...authHeaders };
  }

  /** Create an AbortController with the configured timeout and track it. */
  private createController(): AbortController {
    const controller = new AbortController();
    this.controllers.add(controller);

    const timer = setTimeout(() => controller.abort(), this.timeout);
    // Prevent the timer from holding the event-loop open.
    if (timer.unref) timer.unref();

    controller.signal.addEventListener("abort", () => {
      this.controllers.delete(controller);
    });

    return controller;
  }

  /** Perform a JSON GET request. */
  private async get<T>(path: string): Promise<T> {
    this.assertOpen();
    const controller = this.createController();
    try {
      return await fetchJson<T>(
        `${this.apiUrl}${path}`,
        {
          method: "GET",
          headers: await this.buildHeaders(),
          signal: controller.signal,
        },
        this.retryOptions,
      );
    } finally {
      this.controllers.delete(controller);
    }
  }

  /** Perform a JSON POST request. */
  private async post<T>(path: string, body?: unknown): Promise<T> {
    this.assertOpen();
    const controller = this.createController();
    try {
      return await fetchJson<T>(
        `${this.apiUrl}${path}`,
        {
          method: "POST",
          headers: await this.buildHeaders(),
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        },
        this.retryOptions,
      );
    } finally {
      this.controllers.delete(controller);
    }
  }

  /** Perform a JSON DELETE request. */
  private async del<T = void>(path: string): Promise<T> {
    this.assertOpen();
    const controller = this.createController();
    try {
      return await fetchJson<T>(
        `${this.apiUrl}${path}`,
        {
          method: "DELETE",
          headers: await this.buildHeaders(),
          signal: controller.signal,
        },
        this.retryOptions,
      );
    } finally {
      this.controllers.delete(controller);
    }
  }

  /** Throw if the client has been closed. */
  private assertOpen(): void {
    if (this.closed) {
      throw new Error("VecminClient has been closed");
    }
  }

  // -----------------------------------------------------------------------
  // Collection Management
  // -----------------------------------------------------------------------

  /**
   * Create a new collection.
   *
   * @example
   * ```ts
   * const col = await client.createCollection({
   *   name: "docs",
   *   dimension: 1536,
   *   metric_type: "Cosine",
   *   index_type: "HNSW",
   * });
   * ```
   */
  async createCollection(params: CreateCollectionParams): Promise<Collection> {
    return this.post<Collection>("/collections", params);
  }

  /**
   * List all collections.
   *
   * @example
   * ```ts
   * const collections = await client.listCollections();
   * ```
   */
  async listCollections(): Promise<Collection[]> {
    return this.get<Collection[]>("/collections");
  }

  /**
   * Get details for a specific collection.
   *
   * @example
   * ```ts
   * const col = await client.getCollection("docs");
   * ```
   */
  async getCollection(name: string): Promise<Collection> {
    return this.get<Collection>(`/collections/${encodeURIComponent(name)}`);
  }

  /**
   * Delete a collection and all its data.
   *
   * @example
   * ```ts
   * await client.deleteCollection("docs");
   * ```
   */
  async deleteCollection(name: string): Promise<void> {
    await this.del(`/collections/${encodeURIComponent(name)}`);
  }

  /**
   * Get statistics for a collection.
   *
   * @example
   * ```ts
   * const stats = await client.getCollectionStats("docs");
   * console.log(`Vectors: ${stats.vector_count}`);
   * ```
   */
  async getCollectionStats(name: string): Promise<CollectionStats> {
    return this.get<CollectionStats>(`/collections/${encodeURIComponent(name)}/stats`);
  }

  // -----------------------------------------------------------------------
  // Vector Operations
  // -----------------------------------------------------------------------

  /**
   * Insert a single vector into a collection.
   *
   * @returns The vector ID (either the caller-supplied ID or a server-generated one).
   *
   * @example
   * ```ts
   * const id = await client.insert("docs", {
   *   vector: [0.1, 0.2, /* ... *\/],
   *   metadata: { title: "Hello" },
   * });
   * ```
   */
  async insert(collection: string, params: InsertParams): Promise<string> {
    return this.post<string>(`/collections/${encodeURIComponent(collection)}/insert`, params);
  }

  /**
   * Insert multiple vectors in a single request.
   *
   * @returns An array of vector IDs in the same order as the input.
   *
   * @example
   * ```ts
   * const ids = await client.batchInsert("docs", [
   *   { vector: [0.1, 0.2], metadata: { title: "A" } },
   *   { vector: [0.3, 0.4], metadata: { title: "B" } },
   * ]);
   * ```
   */
  async batchInsert(collection: string, vectors: InsertParams[]): Promise<string[]> {
    return this.post<string[]>(`/collections/${encodeURIComponent(collection)}/batch`, vectors);
  }

  /**
   * Search for the nearest neighbours of a query vector.
   *
   * @example
   * ```ts
   * const results = await client.search("docs", {
   *   query: [0.1, 0.2, /* ... *\/],
   *   k: 5,
   *   ef_search: 100,
   * });
   * for (const r of results) {
   *   console.log(r.id, r.score);
   * }
   * ```
   */
  async search(collection: string, params: SearchParams): Promise<SearchResult[]> {
    return this.post<SearchResult[]>(`/collections/${encodeURIComponent(collection)}/search`, params);
  }

  /**
   * Retrieve a single vector by its ID.
   *
   * @example
   * ```ts
   * const vec = await client.getVector("docs", "abc-123");
   * ```
   */
  async getVector(collection: string, id: string): Promise<Vector> {
    return this.get<Vector>(`/collections/${encodeURIComponent(collection)}/vectors/${encodeURIComponent(id)}`);
  }

  /**
   * Delete a single vector by its ID.
   *
   * @example
   * ```ts
   * await client.deleteVector("docs", "abc-123");
   * ```
   */
  async deleteVector(collection: string, id: string): Promise<void> {
    await this.del(`/collections/${encodeURIComponent(collection)}/vectors/${encodeURIComponent(id)}`);
  }

  // -----------------------------------------------------------------------
  // Index Management
  // -----------------------------------------------------------------------

  /**
   * Trigger an index rebuild for a collection.
   *
   * @example
   * ```ts
   * await client.rebuildIndex("docs");
   * ```
   */
  async rebuildIndex(collection: string): Promise<void> {
    await this.post(`/collections/${encodeURIComponent(collection)}/rebuild_index`);
  }

  /**
   * List all indexes in the cluster.
   *
   * @example
   * ```ts
   * const indexes = await client.listIndexes();
   * ```
   */
  async listIndexes(): Promise<IndexInfo[]> {
    return this.get<IndexInfo[]>("/indexes");
  }

  /**
   * Rebuild a named index.
   *
   * @example
   * ```ts
   * await client.rebuildNamedIndex("docs_hnsw");
   * ```
   */
  async rebuildNamedIndex(name: string): Promise<void> {
    await this.post(`/indexes/${encodeURIComponent(name)}/rebuild`);
  }

  /**
   * Optimize a named index.
   *
   * @example
   * ```ts
   * await client.optimizeIndex("docs_hnsw");
   * ```
   */
  async optimizeIndex(name: string): Promise<void> {
    await this.post(`/indexes/${encodeURIComponent(name)}/optimize`);
  }

  // -----------------------------------------------------------------------
  // Cluster Management
  // -----------------------------------------------------------------------

  /**
   * Authenticate and obtain a JWT token.
   * The token is cached and automatically refreshed before expiry.
   *
   * @returns The JWT string.
   *
   * @example
   * ```ts
   * const jwt = await client.login({ username: "admin", password: "secret" });
   * ```
   */
  async login(credentials: LoginParams): Promise<string> {
    const jwt = await this.post<string>("/cluster/login", credentials);
    this.auth.setLoginCredentials(credentials, jwt);
    return jwt;
  }

  /**
   * List all nodes in the cluster.
   *
   * @example
   * ```ts
   * const nodes = await client.listNodes();
   * ```
   */
  async listNodes(): Promise<Node[]> {
    return this.get<Node[]>("/cluster/nodes");
  }

  /**
   * Get the overall cluster status.
   *
   * @example
   * ```ts
   * const status = await client.clusterStatus();
   * console.log(status.status, status.leader_id);
   * ```
   */
  async clusterStatus(): Promise<ClusterStatus> {
    return this.get<ClusterStatus>("/cluster/status");
  }

  /**
   * Create a cluster snapshot.
   *
   * @example
   * ```ts
   * await client.createSnapshot();
   * ```
   */
  async createSnapshot(): Promise<void> {
    await this.post("/cluster/snapshot");
  }

  // -----------------------------------------------------------------------
  // MCP Convenience Methods
  // -----------------------------------------------------------------------

  /**
   * Store a memory via the MCP `store_memory` tool.
   *
   * This is a convenience wrapper that calls the MCP JSON-RPC endpoint.
   *
   * @example
   * ```ts
   * await client.mcpStoreMemory("User prefers dark mode", "agent-1");
   * ```
   */
  async mcpStoreMemory(
    text: string,
    agentId: string,
    options?: MCPOptions,
  ): Promise<void> {
    const controller = this.createController();
    try {
      await fetchJson<unknown>(
        `${this.mcpUrl}/messages`,
        {
          method: "POST",
          headers: await this.buildHeaders(),
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: Date.now(),
            method: "tools/call",
            params: {
              name: "store_memory",
              arguments: {
                agent_id: agentId,
                content: text,
                source: options?.source ?? "typescript-sdk",
                collection: options?.collection ?? "agent_memory_mcp",
              },
            },
          }),
          signal: controller.signal,
        },
        this.retryOptions,
      );
    } finally {
      this.controllers.delete(controller);
    }
  }

  /**
   * Search memories via the MCP `search_memory` tool.
   *
   * @example
   * ```ts
   * const results = await client.mcpSearchMemory("user preferences", "agent-1", 5);
   * ```
   */
  async mcpSearchMemory(
    query: string,
    agentId: string,
    topK = 5,
  ): Promise<MCPSearchResult[]> {
    const controller = this.createController();
    try {
      const result = await fetchJson<MCPSearchResult[]>(
        `${this.mcpUrl}/messages`,
        {
          method: "POST",
          headers: await this.buildHeaders(),
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: Date.now(),
            method: "tools/call",
            params: {
              name: "search_memory",
              arguments: {
                agent_id: agentId,
                query,
                top_k: topK,
              },
            },
          }),
          signal: controller.signal,
        },
        this.retryOptions,
      );
      return result;
    } finally {
      this.controllers.delete(controller);
    }
  }

  // -----------------------------------------------------------------------
  // Lifecycle
  // -----------------------------------------------------------------------

  /**
   * Gracefully shut down the client.
   * Aborts all in-flight requests and releases resources.
   *
   * @example
   * ```ts
   * await client.close();
   * ```
   */
  async close(): Promise<void> {
    this.closed = true;
    for (const controller of this.controllers) {
      controller.abort();
    }
    this.controllers.clear();
  }
}
