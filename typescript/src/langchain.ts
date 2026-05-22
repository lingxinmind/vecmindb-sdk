/**
 * @module langchain
 * @description LangChain.js VectorStore adapter for VecminDB.
 *
 * Implements the {@link VectorStore} interface from `@langchain/core`,
 * enabling drop-in usage of VecminDB as a vector store within the
 * LangChain.js ecosystem.
 *
 * **Note:** `@langchain/core` is an optional peer dependency.
 * If it is not installed, importing this module will throw at runtime.
 */

import type { VecminVectorStoreOptions, SearchResult } from "./models.js";
import { VecminClient } from "./client.js";

// ---------------------------------------------------------------------------
// Dynamic LangChain imports (optional peer dependency)
// ---------------------------------------------------------------------------

/** Lazy-loaded LangChain base classes. */
let LangChain: typeof import("@langchain/core/vectorstores") | null = null;
let LangChainDocs: typeof import("@langchain/core/documents") | null = null;

async function ensureLangChain(): Promise<{
  VectorStore: typeof import("@langchain/core/vectorstores").VectorStore;
  Document: typeof import("@langchain/core/documents").Document;
  Embeddings: typeof import("@langchain/core/embeddings").Embeddings;
}> {
  if (LangChain && LangChainDocs) {
    return {
      VectorStore: LangChain.VectorStore,
      Document: LangChainDocs.Document,
      Embeddings: (await import("@langchain/core/embeddings")).Embeddings,
    };
  }

  try {
    const vc = await import("@langchain/core/vectorstores");
    const docs = await import("@langchain/core/documents");
    const emb = await import("@langchain/core/embeddings");
    LangChain = vc;
    LangChainDocs = docs;
    return {
      VectorStore: vc.VectorStore,
      Document: docs.Document,
      Embeddings: emb.Embeddings,
    };
  } catch {
    throw new Error(
      "@langchain/core is required for VecminDBVectorStore. " +
      "Install it with: npm install @langchain/core",
    );
  }
}

// ---------------------------------------------------------------------------
// VecminDBVectorStore
// ---------------------------------------------------------------------------

/**
 * LangChain.js VectorStore adapter backed by VecminDB.
 *
 * Extends the abstract `VectorStore` class from `@langchain/core`
 * so it can be used anywhere LangChain expects a vector store —
 * retrievers, chains, agents, etc.
 *
 * @example
 * ```ts
 * import { OpenAIEmbeddings } from "@langchain/openai";
 * import { VecminDBVectorStore } from "@vecmindb/sdk/langchain";
 *
 * const embeddings = new OpenAIEmbeddings();
 * const store = new VecminDBVectorStore(embeddings, {
 *   baseUrl: "http://localhost:8080",
 *   apiKey: "my-key",
 *   collectionName: "my_docs",
 *   dimension: 1536,
 * });
 *
 * await store.addDocuments([
 *   { pageContent: "Hello world", metadata: { source: "test" } },
 * ]);
 *
 * const results = await store.similaritySearch("hello", 5);
 * ```
 */
export class VecminDBVectorStore {
  /** Underlying VecminDB client used for all I/O. */
  public readonly client: VecminClient;
  /** LangChain embeddings instance. */
  private readonly _embeddings: unknown; // typed as unknown to avoid requiring @langchain/core at import time
  /** Collection name in VecminDB. */
  private readonly collectionName: string;
  /** Vector dimensionality. */
  private readonly dimension: number;
  /** Whether the collection has been ensured to exist. */
  private ensured = false;

  // LangChain VectorStore interface fields
  /** @internal */ public lc_namespace = ["vecmindb", "vectorstores"];
  /** @internal */ public lc_serializable = true;

  constructor(embeddings: unknown, options: VecminVectorStoreOptions) {
    this._embeddings = embeddings;
    this.collectionName = options.collectionName ?? "langchain_memory";
    this.dimension = options.dimension ?? 1536;

    this.client = new VecminClient({
      baseUrl: options.baseUrl,
      apiKey: options.apiKey,
      timeout: options.timeout,
    });
  }

  // -----------------------------------------------------------------------
  // Collection bootstrap
  // -----------------------------------------------------------------------

  /**
   * Ensure the target collection exists in VecminDB.
   * Called lazily before the first write operation.
   */
  private async ensureCollection(): Promise<void> {
    if (this.ensured) return;
    try {
      await this.client.createCollection({
        name: this.collectionName,
        dimension: this.dimension,
        metric_type: "Cosine",
        index_type: "HNSW",
        index_params: { m: 16, ef_construction: 100 },
      });
    } catch (err: unknown) {
      // Collection may already exist — that's fine.
      if (err instanceof Error && err.message?.includes("already exists")) {
        // Expected — nothing to do.
      } else if (
        err instanceof Error &&
        (err.message?.includes("409") || err.message?.includes("Conflict"))
      ) {
        // Also fine.
      } else if (err instanceof Error && err.message?.includes("404") === false) {
        // For 404 on create, we re-throw. Otherwise, log and continue.
        throw err;
      }
    }
    this.ensured = true;
  }

  // -----------------------------------------------------------------------
  // LangChain VectorStore interface
  // -----------------------------------------------------------------------

  /**
   * Add documents to the vector store.
   * Embeds the document texts and inserts them into VecminDB.
   */
  async addDocuments(documents: Array<{ pageContent: string; metadata: Record<string, unknown> }>): Promise<string[]> {
    const { Embeddings } = await ensureLangChain();
    const emb = this._embeddings as InstanceType<typeof Embeddings>;

    const texts = documents.map((d) => d.pageContent);
    const metadatas = documents.map((d) => d.metadata ?? {});

    const vectors = (await emb.embedDocuments(texts)) as number[][];
    return this.addVectors(vectors, documents, metadatas);
  }

  /**
   * Add pre-computed vectors to the vector store.
   */
  async addVectors(
    vectors: number[][],
    documents: Array<{ pageContent: string; metadata: Record<string, unknown> }>,
    metadatas?: Array<Record<string, unknown>>,
  ): Promise<string[]> {
    await this.ensureCollection();

    const ids: string[] = [];
    for (let i = 0; i < vectors.length; i++) {
      const doc = documents[i]!;
      const meta: Record<string, unknown> = {
        ...(metadatas?.[i] ?? doc.metadata ?? {}),
        text: doc.pageContent, // Store the text in metadata for retrieval.
      };

      const id = await this.client.insert(this.collectionName, {
        vector: vectors[i]!,
        metadata: meta,
      });
      ids.push(id);
    }
    return ids;
  }

  /**
   * Search for the most similar vectors and return results with scores.
   *
   * @param query - Query vector.
   * @param k     - Number of results. @default 4
   */
  async similaritySearchVectorWithScore(
    query: number[],
    k = 4,
  ): Promise<Array<[{ pageContent: string; metadata: Record<string, unknown> }, number]>> {
    const results = await this.client.search(this.collectionName, {
      query,
      k,
    });

    return results.map((r: SearchResult) => {
      const meta = (r.metadata ?? {}) as Record<string, unknown>;
      const text = typeof meta["text"] === "string" ? meta["text"] as string : "";
      // Remove the internal `text` field from the metadata we return.
      const cleanMeta = { ...meta };
      delete cleanMeta["text"];

      return [
        { pageContent: text, metadata: cleanMeta },
        r.score,
      ];
    });
  }

  /**
   * Convenience method: search for similar documents (without scores).
   */
  async similaritySearch(
    query: string,
    k = 4,
  ): Promise<Array<{ pageContent: string; metadata: Record<string, unknown> }>> {
    const { Embeddings } = await ensureLangChain();
    const emb = this._embeddings as InstanceType<typeof Embeddings>;

    const queryVector = (await emb.embedQuery(query)) as number[];
    const results = await this.similaritySearchVectorWithScore(queryVector, k);
    return results.map(([doc]) => doc);
  }

  /**
   * Convenience method: search for similar documents with scores.
   */
  async similaritySearchWithScore(
    query: string,
    k = 4,
  ): Promise<Array<[{ pageContent: string; metadata: Record<string, unknown> }, number]>> {
    const { Embeddings } = await ensureLangChain();
    const emb = this._embeddings as InstanceType<typeof Embeddings>;

    const queryVector = (await emb.embedQuery(query)) as number[];
    return this.similaritySearchVectorWithScore(queryVector, k);
  }

  // -----------------------------------------------------------------------
  // Static factory methods
  // -----------------------------------------------------------------------

  /**
   * Create a VecminDBVectorStore from an array of Document objects.
   *
   * @example
   * ```ts
   * const store = await VecminDBVectorStore.fromDocuments(
   *   [{ pageContent: "Hello", metadata: {} }],
   *   embeddings,
   *   { baseUrl: "http://localhost:8080" },
   * );
   * ```
   */
  static async fromDocuments(
    documents: Array<{ pageContent: string; metadata: Record<string, unknown> }>,
    embeddings: unknown,
    options: VecminVectorStoreOptions,
  ): Promise<VecminDBVectorStore> {
    const store = new VecminDBVectorStore(embeddings, options);
    await store.addDocuments(documents);
    return store;
  }

  /**
   * Create a VecminDBVectorStore from an array of texts.
   *
   * @example
   * ```ts
   * const store = await VecminDBVectorStore.fromTexts(
   *   ["Hello world", "Goodbye world"],
   *   [{}, {}],
   *   embeddings,
   *   { baseUrl: "http://localhost:8080" },
   * );
   * ```
   */
  static async fromTexts(
    texts: string[],
    metadatas: Array<Record<string, unknown>>,
    embeddings: unknown,
    options: VecminVectorStoreOptions,
  ): Promise<VecminDBVectorStore> {
    const documents = texts.map((text, i) => ({
      pageContent: text,
      metadata: metadatas[i] ?? {},
    }));
    return VecminDBVectorStore.fromDocuments(documents, embeddings, options);
  }

  // -----------------------------------------------------------------------
  // Cleanup
  // -----------------------------------------------------------------------

  /**
   * Close the underlying client connection.
   */
  async close(): Promise<void> {
    await this.client.close();
  }
}
