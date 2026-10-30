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
  /** Optional domain/namespace tag for the collection. */
  domain?: string;
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
  /** Unique identifier for the vector. If omitted the client generates a UUID. */
  id?: string;
  /** The vector embedding. */
  vector: number[];
  /** Arbitrary key-value metadata attached to the vector. */
  metadata?: Record<string, unknown>;
}

/** Parameters for storing raw text (server-side embedding). */
export interface InsertTextParams {
  /** Unique identifier for the vector. If omitted the client generates a UUID. */
  id?: string;
  /** Raw text; the server embeds it with the built-in BGE-M3 model. */
  text: string;
  /** Arbitrary key-value metadata attached to the vector. */
  metadata?: Record<string, unknown>;
}

/** Parameters for searching with raw text (server-side embedding). */
export interface SearchTextParams {
  /** Raw query text; the server embeds it with the built-in BGE-M3 model. */
  text: string;
  /** Number of nearest neighbours to return. @default 10 */
  k?: number;
  /** Metadata filter expression (server-side). */
  filter?: Record<string, unknown>;
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
  /**
   * Collection to store memories in. Omit (recommended) to write to the
   * authenticated tenant collection - the server rejects free-form
   * collection names with FORBIDDEN.
   */
  collection?: string;
  /** Source tag for the memory. */
  source?: string;
  /** Mark durable constraints/decisions for strong anchoring. */
  isFactual?: boolean;
  /** Embedding dimension. @default 384 */
  dimension?: number;
  /** Sovereignty token (bound server-side to the API key; accepted for parity). */
  sovereigntyToken?: string;
  /** Model id (bound server-side to the API key; accepted for parity). */
  modelId?: string;
  /** Optional metadata payload for the memory. */
  metadata?: Record<string, unknown>;
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
  /** Agent identifier (the server overrides this with the authenticated
   * identity bound to the API key). */
  agent_id: string;
  /** Source tag, folded into the memory metadata. */
  source?: string;
  /** If true, permanently exempts this memory from LTSM forgetting. */
  is_factual?: boolean;
  /** If true, strips any anchor so this outdated memory re-enters
   * normal LTSM decay. */
  is_obsolete?: boolean;
  /** Optional metadata as a JSON object. */
  metadata?: Record<string, unknown>;
}

/** Parameters for the `search_memory` MCP tool. */
export interface SearchMemoryParams {
  /** Natural-language query. */
  query: string;
  /** Agent identifier (the server overrides this with the authenticated
   * identity bound to the API key). */
  agent_id: string;
  /** Number of results. @default 5 */
  top_k?: number;
  /** Epoch seconds: only entries created at or after this time. */
  since_ts?: number;
  /** Epoch seconds: only entries created at or before this time. */
  until_ts?: number;
  /** Only entries whose metadata.tags contains at least one of these
   * tags (any-of). */
  tags?: string[];
  /** Only entries whose text contains this substring (case-insensitive). */
  keyword?: string;
}

/** Parameters for the `store_media` MCP tool. */
export interface StoreMediaParams {
  /** Agent-side description; the canonical embedding text. The server runs
   * zero vision models, so without a caption the media stays `pending`
   * and is not text-searchable until re-stored with the same `media_id`
   * and a caption. */
  caption?: string;
  /** Base64-encoded blob bytes. */
  media_data?: string;
  /** Optional stable id; re-uploading replaces the old description record
   * (G12 upsert). */
  media_id?: string;
  /** image | audio | video | file. @default "image" */
  kind?: string;
  /** MIME type for allow-list validation. */
  mime?: string;
  /** Path/URL of the original file. */
  source_ref?: string;
  /** Explicit strong anchoring (e.g. contract scans). @default false */
  is_factual?: boolean;
  /** Optional agent-side CLIP embedding for image-to-image search (M4);
   * requires `media.clip_collection` server-side. */
  clip_vector?: number[];
}

/** Parameters for image-to-image search via the `search_media_by_image`
 * MCP tool. */
export interface SearchMediaByImageParams {
  /** Precomputed CLIP embedding of the query image. */
  clip_vector?: number[];
  /** Raw image object handed to `clip_encoder`. */
  image?: unknown;
  /** Agent-side callable mapping an image to a CLIP embedding
   * (`media.clip_dimension` floats). */
  clip_encoder?: (image: unknown) => number[];
  /** Number of results. @default 5 */
  top_k?: number;
  /** Optional cosine floor (0 returns raw top-k; the text relevance gate
   * does not apply to CLIP space). @default 0 */
  min_score?: number;
}

/** Parameters for the `list_memories` MCP tool. */
export interface ListMemoriesParams {
  /** Maximum number of memories to return. @default 20 */
  limit?: number;
  /** true = inbox view: only entries other tenants shared with you
   * (granted collections; own memories and the product pack excluded). */
  shared_with_me?: boolean;
  /** Inbox only: window in hours for the "Recent sharing activity"
   * summary. @default 168 (7 days) */
  since_hours?: number;
  /** Epoch seconds: only entries created at or after this time. */
  since_ts?: number;
  /** Epoch seconds: only entries created at or before this time. */
  until_ts?: number;
  /** Only entries whose metadata.tags contains at least one of these
   * tags (any-of). */
  tags?: string[];
  /** Only entries whose text contains this substring (case-insensitive). */
  keyword?: string;
}

/** Parameters for the `get_memory` MCP tool. */
export interface GetMemoryParams {
  /** The memory vector ID returned by store_memory or search_memory. */
  id: string;
}

/** Parameters for the `forget` MCP tool. */
export interface ForgetParams {
  /** Single vector ID to forget. */
  id?: string;
  /** Multiple vector IDs to forget. */
  ids?: string[];
  /** Target collection. @default "default" */
  collection?: string;
  /** Sovereignty token; defaults to the collection authority token. */
  sovereignty_token?: string;
}

/** Parameters for the `memory_status` MCP tool. */
export interface MemoryStatusParams {
  /** Optional agent identity filter. */
  agent_id?: string;
  /** Collection to inspect. @default "default" */
  collection?: string;
}

/** Parameters for the `consolidate` MCP tool. */
export interface ConsolidateParams {
  /** Collection to consolidate. @default "default" */
  collection?: string;
  /** Run a full evolution cycle when true. @default false */
  force?: boolean;
}

/** Parameters for the factuality template tools. */
export interface FactualityTemplateParams {
  /** The template sentence text. */
  text: string;
  /** Concept type: either 'profile' or 'rule'. */
  template_type: string;
}

/** Parameters for the `update_memory` MCP tool: correct a memory in
 * place (same id and anchors; the corrected text is re-embedded and the
 * previous text appended to a bounded history). Author-only. */
export interface UpdateMemoryParams {
  /** Memory vector ID to correct (own collection only). */
  id: string;
  /** The corrected content — replaces the previous text. */
  text: string;
  /** Optional explicit re-grade: true = strong anchor, false = weak;
   * absent preserves the current anchor. */
  is_factual?: boolean;
}

/** Parameters for the `freeze_memory` MCP tool: frozen entries are
 * exempt from LTSM distillation and staleness scavenging. Advisory on
 * top of anchoring, reversible any time, author-only. */
export interface FreezeMemoryParams {
  /** Memory vector ID (own collection only). */
  id: string;
  /** true = exempt from distillation/vacuum, false = back to the
   * normal lifecycle. */
  frozen: boolean;
}

/** Parameters for the `export_memory` MCP tool (author-scoped, own
 * collection — the lightweight "my data" answer, no admin gate). */
export interface ExportMemoryParams {
  /** Output format. @default "json" */
  format?: "json" | "markdown";
}

/** One entry of an `import_memories` batch. */
export interface ImportMemoryEntry {
  /** The memory text (canonical embedding content). */
  text: string;
  /** Explicit strong anchoring (default false = weak). */
  is_factual?: boolean;
  /** Optional metadata (e.g. tags, detail, source_ref). */
  metadata?: Record<string, unknown>;
}

/** Parameters for the `import_memories` MCP tool: first-run cold-start
 * batch import, cap 200 entries per call. Every entry goes through the
 * same ingestion core as `store_memory`, per-entry independent, with an
 * honest partial-failure report. */
export interface ImportMemoriesParams {
  /** Batch of memory entries. */
  memories: ImportMemoryEntry[];
}

/** Parameters for the `update_memory_sharing` MCP tool: flips the
 * cross-tenant sharing flag on the caller's own memories (owner-side
 * only). Batch exposure (>1 entry, shared=true) is two-phase — the
 * first call returns a dry-run summary, re-issue with confirm:true. */
export interface UpdateMemorySharingParams {
  /** Single memory vector ID (own collection only). */
  id?: string;
  /** Batch: explicit list of memory IDs (own collection only). */
  ids?: string[];
  /** Batch selector: "all", "tag:<name>", or "query:<text>" (share by
   * meaning without needing tags). */
  scope?: string;
  /** Exclude entries whose metadata.tags contains this tag from the
   * match set. */
  except_tag?: string;
  /** Exclude these entry IDs from the match set. */
  except_ids?: string[];
  /** Field-level exposure for shared entries: full (default, WYSIWYG)
   * or summary (text survives, detail stripped for grantees). */
  shared_scope?: "full" | "summary";
  /** true = share with granted tenants, false = private again. */
  shared: boolean;
  /** Required true to apply a batch exposure of more than one entry. */
  confirm?: boolean;
}

/** Parameters for the `set_tenant_grant` MCP tool (owner-side only):
 * grant/revoke another tenant read access to your collection. Live
 * immediately; grantees still only see entries you marked shared. */
export interface SetTenantGrantParams {
  /** Grantee tenant id (must already exist in security.tenant_keys). */
  tenant: string;
  /** Collections to grant; defaults to your own memory collection. You
   * may only name collections you own. */
  collections?: string[];
  /** true = revoke the grant; false/omit = grant. Idempotent. */
  revoke?: boolean;
}

/** Parameters for the `share_with_tenant` MCP tool: guided one-shot
 * share — grants read access AND semantically selects matching entries,
 * then returns a dry-run with previews and sensitivity flags; re-issue
 * with confirm:true to apply. */
export interface ShareWithTenantParams {
  /** Grantee tenant id (must already exist in security.tenant_keys). */
  tenant: string;
  /** Plain-words description of what to share — matched semantically
   * against your own entries. */
  what: string;
  /** full (default, WYSIWYG) or summary (detail stripped for grantees). */
  shared_scope?: "full" | "summary";
  /** Required true to apply (the first call returns a dry-run summary). */
  confirm?: boolean;
}

/** Parameters for the `update_share_subscription` MCP tool: standing
 * share rule — "future entries matching <what> go to <tenant>". Pure
 * storage, never shares anything by itself; pending matches appear via
 * `check_share_subscriptions`. */
export interface UpdateShareSubscriptionParams {
  /** Plain-words description of the kind of content to share. */
  what?: string;
  /** Grantee tenant id for future matches. */
  tenant?: string;
  /** Field-level exposure for future applies (default full). */
  shared_scope?: "full" | "summary";
  /** true = clear your subscription. */
  remove?: boolean;
}

/** Parameters for the `get_memory_rules` MCP tool: the corrected,
 * scope-guarded memory-protocol rule block with the exact local path to
 * write it into. */
export interface GetMemoryRulesParams {
  /** One of: claude_code | cursor | workbuddy | all. @default "all" */
  target?: string;
  /** Rule locale: en (default) | zh. @default "en" */
  lang?: string;
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
