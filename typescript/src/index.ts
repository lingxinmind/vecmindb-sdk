/**
 * @module index
 * @description Main entry-point for the `@vecmindb/sdk` package.
 *
 * Re-exports every public symbol so consumers can import from a single path:
 *
 * ```ts
 * import { VecminClient, VecminError, VecminMCPClient } from "@vecmindb/sdk";
 * ```
 */

// Core client
export { VecminClient } from "./client.js";

// MCP client
export { VecminMCPClient } from "./mcp.js";
export type { MCPEventMap } from "./mcp.js";

// LangChain adapter (optional — only works when @langchain/core is installed)
export { VecminDBVectorStore } from "./langchain.js";

// Authentication manager
export { AuthManager } from "./auth.js";

// Retry utilities
export { withRetry, fetchJson, resolveRetryOptions } from "./retry.js";

// Error classes
export {
  VecminError,
  AuthenticationError,
  PermissionError,
  NotFoundError,
  RateLimitError,
  ServerError,
  createErrorFromStatus,
} from "./errors.js";

// Type definitions — re-exported for consumer convenience
export type {
  VecminClientOptions,
  VecminResponse,
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
  MCPClientOptions,
  StoreMemoryParams,
  SearchMemoryParams,
  JsonRpcRequest,
  JsonRpcResponse,
  VecminVectorStoreOptions,
  MetricType,
  IndexType,
  RetryOptions,
} from "./models.js";
