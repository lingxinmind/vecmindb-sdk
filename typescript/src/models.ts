/**
 * @module models
 * @description TypeScript type definitions for the VecminDB SDK.
 * Covers all API request/response types, configuration options,
 * and data structures used across the SDK.
 */

// ---------------------------------------------------------------------------
// Client Configuration
// ---------------------------------------------------------------------------

/** Options for constructing a {@link VecminClient} instance. */
export interface VecminClientOptions {
  /** Base URL of the VecminDB server (e.g. `http://localhost:8080`). */
  baseUrl: string;
  /** API key for authentication via `x-api-key` header. */
  apiKey?: string;
  /** JWT token for authentication. If provided alongside `apiKey`, JWT takes precedence on protected routes. */
  jwt?: string;
  /** Request timeout in milliseconds. @default 30_000 */
  timeout?: number;
  /** Maximum number of automatic retries on transient failures. @default 3 */
  maxRetries?: number;
  /** Backoff multiplier (seconds) for exponential retry delay. @default 0.5 */
  backoffFactor?: number;
  /** Custom HTTP headers included with every request. */
  defaultHeaders?: Record<string, string>;
  /** Optional agent identifier injected via `x-agent-id` header. */
  agentId?: string;
  /** Optional model identifier injected via `x-model-id` header. */
  modelId?: string;
}

// ---------------------------------------------------------------------------
// Standard API Response
// ---------------------------------------------------------------------------

/** Standardised response envelope returned by every VecminDB API endpoint. */
export interface VecminResponse<T> {
  /** HTTP-style status code. */
  code: number;
  /** Human-readable status message. */
  message: string;
  /** Response payload. */
  data: T;
}

// ---------------------------------------------------------------------------
// Collection Types
// ---------------------------------------------------------------------------

/** Parameters for creating a new collection. */
export interface CreateCollectionParams {
  /** Unique name for the collection. */
  name: string;
  /** Dimensionality of the vectors stored in the collection. */
  dimension: number;
  /** Distance metric. @default "Cosine" */
  metric_type?: MetricType;
  /** Index algorithm. @default "HNSW" */
  index_type?: IndexType;
  /** Algorithm-specific parameters. */
  index_params?: Record<string, unknown>;
}

/** A VecminDB collection. */
export interface Collection {
  /** Collection name. */
  name: string;
  /** Vector dimensionality. */
  dimension: number;
  /** Distance metric used. */
  metric_type: MetricType;
  /** Index algorithm used. */
  index_type: IndexType;
  /** Index hyper-parameters. */
  index_params: Record<string, unknown>;
  /** Number of vectors stored. */
  vector_count?: number;
  /** ISO-8601 creation timestamp. */
  created_at?: string;
  /** ISO-8601 last-update timestamp. */
  updated_at?: string;
}

/** Statistical summary of a collection. */
export interface CollectionStats {
  /** Collection name. */
  name: string;
  /** Number of stored vectors. */
  vector_count: number;
  /** Storage consumption in bytes. */
  storage_bytes: number;
  /** Index build progress (0–100). */
  index_progress?: number;
  /** ISO-8601 creation timestamp. */
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Vector Operation Types
// ---------------------------------------------------------------------------

/** Parameters for inserting a single vector. */
export interface InsertParams {
  /** Unique identifier for the vector. If omitted the server generates one. */
  id?: string;
  /** The vector embedding. */
  vector: number[];
  /** Arbitrary key-value metadata attached to the vector. */
  metadata?: Record<string, unknown>;
}

/** Parameters for searching vectors. */
export interface SearchParams {
  /** Query vector. */
  query: number[];
  /** Number of nearest neighbours to return. @default 10 */
  k?: number;
  /** HNSW ef-search parameter. @default 50 */
  ef_search?: number;
  /** Override the collection's default metric for this query. */
  metric?: MetricType;
  /** Metadata filter expression (server-side). */
  filter?: Record<string, unknown>;
}

/** A single search result item. */
export interface SearchResult {
  /** Vector identifier. */
  id: string;
  /** Similarity score (higher = more similar for cosine/inner-product). */
  score: number;
  /** The vector itself (may be omitted by the server for efficiency). */
  vector?: number[];
  /** Attached metadata. */
  metadata?: Record<string, unknown>;
}

/** A stored vector record. */
export interface Vector {
  /** Unique identifier. */
  id: string;
  /** The vector embedding. */
  vector: number[];
  /** Attached metadata. */
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Index Types
// ---------------------------------------------------------------------------

/** Index summary returned by the list-indexes endpoint. */
export interface IndexInfo {
  /** Index name. */
  name: string;
  /** Algorithm used. */
  index_type: IndexType;
  /** Collection this index belongs to. */
  collection: string;
  /** Build status. */
  status?: string;
}

// ---------------------------------------------------------------------------
// Cluster Types
// ---------------------------------------------------------------------------

/** Login credentials for JWT authentication. */
export interface LoginParams {
  /** Username or API key. */
  username: string;
  /** Password or secret. */
  password: string;
}

/** A node in the VecminDB cluster. */
export interface Node {
  /** Unique node identifier. */
  id: string;
  /** Network address (host:port). */
  address: string;
  /** Node role. */
  role: "leader" | "follower" | "candidate";
  /** `true` if the node is reachable. */
  healthy: boolean;
}

/** Cluster-wide status overview. */
export interface ClusterStatus {
  /** Cluster health indicator. */
  status: "healthy" | "degraded" | "unavailable";
  /** Current leader node ID. */
  leader_id: string;
  /** Total number of nodes. */
  node_count: number;
  /** Number of healthy nodes. */
  healthy_count: number;
  /** Raft term. */
  term?: number;
  /** Raft commit index. */
  commit_index?: number;
}

// ---------------------------------------------------------------------------
// MCP Types
// ---------------------------------------------------------------------------

/** Options for MCP operations. */
export interface MCPOptions {
  /** Collection to store/search memories in. @default "agent_memory_mcp" */
  collection?: string;
  /** Source tag for the memory. */
  source?: string;
  /** Embedding dimension. @default 384 */
  dimension?: number;
}

/** A single MCP search result. */
export interface MCPSearchResult {
  /** Document ID. */
  id: string;
  /** Similarity score. */
  score: number;
  /** The original text content. */
  content: string;
  /** Agent that stored this memory. */
  agent_id: string;
  /** Source tag. */
  source?: string;
  /** Full metadata object. */
  metadata?: Record<string, unknown>;
}

/** MCP client configuration. */
export interface MCPClientOptions {
  /** API key for authenticating MCP requests. */
  apiKey?: string;
  /** JWT token. */
  jwt?: string;
  /** Agent identifier. */
  agentId?: string;
  /** Model identifier. */
  modelId?: string;
}

/** Parameters for the `store_memory` MCP tool. */
export interface StoreMemoryParams {
  /** The text content to store. */
  text: string;
  /** Agent identifier. */
  agent_id: string;
  /** Source tag. */
  source?: string;
  /** Override target collection. */
  collection?: string;
}

/** Parameters for the `search_memory` MCP tool. */
export interface SearchMemoryParams {
  /** Natural-language query. */
  query: string;
  /** Agent identifier to scope the search. */
  agent_id: string;
  /** Number of results. @default 5 */
  top_k?: number;
  /** Override target collection. */
  collection?: string;
}

/** JSON-RPC 2.0 request envelope. */
export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params?: Record<string, unknown>;
}

/** JSON-RPC 2.0 success response. */
export interface JsonRpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id: number;
  result?: T;
  error?: {
    code: number;
    message: string;
    data?: unknown;
  };
}

// ---------------------------------------------------------------------------
// LangChain Adapter Types
// ---------------------------------------------------------------------------

/** Options for constructing a {@link VecminDBVectorStore}. */
export interface VecminVectorStoreOptions {
  /** VecminDB base URL. */
  baseUrl: string;
  /** API key. */
  apiKey?: string;
  /** Collection name. @default "langchain_memory" */
  collectionName?: string;
  /** Vector dimensionality. @default 1536 */
  dimension?: number;
  /** Distance metric. @default "Cosine" */
  metricType?: MetricType;
  /** Index type. @default "HNSW" */
  indexType?: IndexType;
  /** Index hyper-parameters. */
  indexParams?: Record<string, unknown>;
  /** Request timeout. */
  timeout?: number;
}

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

/** Supported distance metrics. */
export type MetricType = "Cosine" | "L2" | "InnerProduct";

/** Supported index algorithms. */
export type IndexType = "HNSW" | "IVF" | "Flat";

// ---------------------------------------------------------------------------
// Retry Types
// ---------------------------------------------------------------------------

/** Configuration for the retry policy. */
export interface RetryOptions {
  /** Maximum retry attempts. @default 3 */
  maxRetries?: number;
  /** Backoff multiplier in seconds. @default 0.5 */
  backoffFactor?: number;
  /** HTTP status codes that trigger a retry. @default [429,500,502,503,504] */
  retryableStatusCodes?: number[];
}
