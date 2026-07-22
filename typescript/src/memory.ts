/**
 * VecminDB Sovereign Agent Memory Manager and Cognitive Spaces for TypeScript.
 */

import { VecminClient } from "./client";

export interface AgentMemoryManagerOptions {
  client: VecminClient;
  agentId: string;
  sovereigntyToken: string;
  modelId?: string;
}

export interface MountMemoryParams {
  /** Target collection name to mount. Defaults to 'agent_memory'. */
  collectionName?: string;
  /** Optional domain archetype for factuality anchoring if collection auto-creation occurs. */
  domain?: string;
  /** Dimensionality matching built-in BGE-M3 ONNX weight. @default 1024 */
  dimension?: number;
}

export class AgentMemoryManager {
  private client: VecminClient;
  private agentId: string;
  private sovereigntyToken: string;
  private modelId: string;

  constructor(options: AgentMemoryManagerOptions) {
    this.client = options.client;
    this.agentId = options.agentId;
    this.sovereigntyToken = options.sovereigntyToken;
    this.modelId = options.modelId || options.sovereigntyToken;
  }

  /**
   * Mount a sovereign memory space for an agent to a backing collection.
   */
  async mountMemory(params?: MountMemoryParams): Promise<VecminMemorySpace> {
    const collectionName = params?.collectionName || "agent_memory";
    const domain = params?.domain || "general";

    // Ensure backing collection exists with 1024-dim default
    try {
      await this.client.createCollection({
        name: collectionName,
        dimension: params?.dimension ?? 1024,
        domain: domain,
      });
    } catch {
      // Collection already exists or server ignored duplicate
    }

    return new VecminMemorySpace(
      this.client,
      collectionName,
      this.agentId,
      this.sovereigntyToken,
      this.modelId
    );
  }
}

export class VecminMemorySpace {
  constructor(
    private client: VecminClient,
    public collectionName: string,
    public agentId: string,
    public sovereigntyToken: string,
    public modelId: string
  ) {}

  /**
   * Store episodic text memory into this sovereign memory space.
   */
  async storeMemory(text: string, metadata?: Record<string, unknown>): Promise<string> {
    return this.client.mcpStoreMemory(text, this.agentId, {
      sovereigntyToken: this.sovereigntyToken,
      modelId: this.modelId,
      metadata,
    });
  }

  /**
   * Search sovereign memory space using natural language query.
   */
  async searchMemory(params: { query: string; topK?: number }): Promise<any> {
    return this.client.mcpSearchMemory(params.query, this.agentId, {
      sovereigntyToken: this.sovereigntyToken,
      modelId: this.modelId,
      topK: params.topK,
    });
  }
}
