/**
 * VecminDB TypeScript SDK - Core CRUD & Query Demo
 * Copyright (c) 2026 Shanghai Lingxin Zhisuan Intelligent Technology Co., Ltd.
 * All rights reserved.
 * 
 * Demonstrates:
 * 1. Connecting to VecminDB using strongly-typed VecminClient.
 * 2. Asynchronous Collection lifecycle management.
 * 3. Batch indexing of vectors and structured payloads.
 * 4. Cosine Similarity search with metadata filters.
 */

import { VecminClient } from '../typescript'; // Resolves locally to TS SDK
import { DistanceMetric, IndexType } from '../typescript/src/models';

// Configure connection parameters
const HOST = process.env.VECMINDB_HOST || '127.0.0.1';
const PORT = parseInt(process.env.VECMINDB_PORT || '5520', 10);
const TOKEN = process.env.VECMINDB_API_TOKEN || 'demo-token-key-2026';

const client = new VecminClient({
    host: HOST,
    port: PORT,
    token: TOKEN
});

async function main() {
    console.log(`=== VecminDB TypeScript SDK Live Demo ===`);
    const collectionName = 'node_cognitive_manifold';

    try {
        // 1. Cluster Liveness Probe
        const online = await client.ping();
        if (!online) {
            console.error('[!] Server offline. Ensure a VecminDB server node is running locally.');
            process.exit(1);
        }
        console.log('[+] Server node status: ONLINE');

        // 2. Tear down existing and rebuild clean Collection Space
        const exists = await client.hasCollection(collectionName);
        if (exists) {
            console.log(`[*] Discarding old index space '${collectionName}'...`);
            await client.deleteCollection(collectionName);
        }

        console.log(`[*] Provisioning sharded collection '${collectionName}'...`);
        const collection = await client.createCollection({
            name: collectionName,
            dimension: 64, // Efficient low-dim cognitive mapping
            metric: DistanceMetric.COSINE,
            indexType: IndexType.HNSW,
            shards: 2,
            replicas: 1
        });
        console.log(`[+] Collection '${collectionName}' successfully provisioned.`);

        // 3. Batch Ingest high-dimensional vectors with JSON payloads
        console.log('[*] Inserting cognitive records into collection...');
        
        // Prepare mock vectors for demonstration
        const records = [
            {
                id: 'agent_mem_01',
                vector: Array(64).fill(0.12),
                payload: { type: 'agent_intent', user: 'alice', active: true, priority: 5 }
            },
            {
                id: 'agent_mem_02',
                vector: Array(64).fill(0.45),
                payload: { type: 'system_log', user: 'system', active: false, priority: 2 }
            },
            {
                id: 'agent_mem_03',
                vector: Array(64).fill(0.18),
                payload: { type: 'agent_intent', user: 'bob', active: true, priority: 9 }
            }
        ];

        const inserted = await collection.insertBatch(records);
        console.log(`[+] Successfully indexed ${inserted} records.`);

        // Short sleep for indexing consolidation
        await new Promise(resolve => setTimeout(resolve, 300));

        // 4. Perform strongly-typed Cosine Similarity KNN query
        console.log('\n[*] Query 1: Executing similarity search (Top-2 closest intent matches)...');
        const queryVector = Array(64).fill(0.15);
        
        const results = await collection.search({
            vector: queryVector,
            limit: 2
        });

        results.forEach((hit, idx) => {
            console.log(`  [${idx + 1}] ID: ${hit.id} | Score: ${hit.score.toFixed(4)} | Type: ${hit.payload.type} | User: ${hit.payload.user}`);
        });

        // 5. Execute Hybrid Search (KNN Search + Strict Payload filter)
        console.log('\n[*] Query 2: Executing hybrid search (Strict metadata filter: { type: "agent_intent" })...');
        const hybridResults = await collection.search({
            vector: queryVector,
            limit: 2,
            filter: { type: 'agent_intent' }
        });

        hybridResults.forEach((hit, idx) => {
            console.log(`  [${idx + 1}] ID: ${hit.id} | Score: ${hit.score.toFixed(4)} | Match: ${JSON.stringify(hit.payload)}`);
        });

        // 6. Cleanup & Resource Release
        console.log('\n[*] Releasing temporary index spaces...');
        await client.deleteCollection(collectionName);
        console.log('[+] Session safely terminated.');

    } catch (err: any) {
        console.error('[!] Runtime exception occurred:', err.message || err);
        process.exit(2);
    }
}

main();
