/**
 * VecminDB TypeScript SDK - LangChain.js VectorStore Integration Demo
 * Copyright (c) 2026 Shanghai Lingxin Zhisuan Intelligent Technology Co., Ltd.
 * All rights reserved.
 * 
 * Demonstrates:
 * 1. Wrapping VecminDB TS Client as a LangChain-compliant VectorStore.
 * 2. Ingesting chunks, extracting embeddings, and vector similarity search.
 */

import { VecminClient } from '../typescript'; // Local TS SDK resolve
import { VecminDBVectorStore } from '../typescript/src/langchain';

// Mock embedding generator to ensure the script is 100% executable without API keys
class MockCognitiveEmbeddings {
    async embedDocuments(texts: string[]): Promise<number[][]> {
        return texts.map(t => Array(128).fill(0.0).map((_, i) => (t.charCodeAt(i % t.length) || 32) / 256.0));
    }
    
    async embedQuery(text: string): Promise<number[]> {
        return Array(128).fill(0.0).map((_, i) => (text.charCodeAt(i % text.length) || 32) / 256.0);
    }
}

async function main() {
    console.log("=== VecminDB TypeScript LangChain Integration Demo ===");
    
    const HOST = process.env.VECMINDB_HOST || '127.0.0.1';
    const PORT = parseInt(process.env.VECMINDB_PORT || '5520', 10);
    
    const client = new VecminClient({
        host: HOST,
        port: PORT,
        token: 'demo-token-key-2026'
    });

    // Check cluster ping
    const online = await client.ping();
    if (!online) {
        console.error('[!] Server node is unreachable. Please run this demo with a running VecminDB service.');
        process.exit(1);
    }

    const collectionName = 'langchain_ts_rag_space';

    // 1. Prepare cognitive corpuses
    const docs = [
        "Sovereignty engineering guarantees that your private corporate vectors never leak to commercial third-party LLM providers.",
        "VecminDB HNSW indexing enables microsecond-level vector query times even under sharded distributed loads.",
        "The LTSM manifold consolidates short-term transactional queries into high-value cognitive semantic vectors."
    ];
    const metadatas = [
        { doc_id: 101, security_level: 'confidential' },
        { doc_id: 102, security_level: 'internal' },
        { doc_id: 103, security_level: 'top-secret' }
    ];

    const embeddings = new MockCognitiveEmbeddings();

    console.log('[*] Injecting and embedding documents in VecminDB LangChain Store...');
    
    // 2. Wrap and build LangChain store
    const vectorStore = await VecminDBVectorStore.fromTexts(
        docs,
        metadatas,
        embeddings,
        {
            client,
            collectionName
        }
    );

    console.log('[+] Ingestion successfully indexed.');
    
    // Short consolidation delay
    await new Promise(resolve => setTimeout(resolve, 300));

    // 3. Perform Similarity search with score
    const query = "What index algorithm guarantees microsecond vector queries?";
    console.log(`\n[*] Similarity search for: "${query}"`);
    
    const results = await vectorStore.similaritySearchWithScore(query, 2);

    results.forEach(([doc, score], idx) => {
        console.log(`  [${idx + 1}] L2 Distance Score: ${score.toFixed(4)}`);
        console.log(`      Content: ${doc.pageContent}`);
        console.log(`      Meta: ${JSON.stringify(doc.metadata)}\n`);
    });

    // 4. Cleanup Space
    console.log('[*] Destroying temporary RAG index space...');
    await client.deleteCollection(collectionName);
    console.log('[+] Space torn down safely. TS Demo completed.');
}

main();
