#!/usr/bin/env python3
"""
VecminDB Python SDK - Standard CRUD & Semantic Search Demo
Copyright (c) 2026 Shanghai Lingxin Zhisuan Intelligent Technology Co., Ltd.
All rights reserved.

This script demonstrates basic operations using the native VecminDB Python SDK:
1. Connecting to a local or remote VecminDB Server.
2. Creating a collection with custom metadata schemas.
3. Inserting high-dimensional vectors with structured payloads.
4. Performing K-Nearest Neighbors (KNN) semantic searches with metadata filtering.
5. Deleting collections and managing connections safely.
"""

import os
import sys
import time
from vecmindb import VecminClient
from vecmindb.models import DistanceMetric, IndexType

# ── 1. Configuration & Client Initialization ──────────────────────────────────────────
# Read connection parameters from environment or default to local node
SERVER_HOST = os.getenv("VECMINDB_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("VECMINDB_PORT", "5520"))
API_TOKEN = os.getenv("VECMINDB_API_TOKEN", "demo-token-key-2026")

print(f"[*] Initializing VecminDB client for {SERVER_HOST}:{SERVER_PORT}...")
client = VecminClient(host=SERVER_HOST, port=SERVER_PORT, token=API_TOKEN)

def main():
    collection_name = "lingxin_cognitive_space"
    
    try:
        # Check server cluster connectivity status
        if not client.ping():
            print("[!] Critical: Cannot reach VecminDB node server. Ensure it is running.")
            sys.exit(1)
        print("[+] Cluster status: ONLINE")

        # ── 2. Schema Lifecycle: Deleting existing and Creating clean Collection ──────
        if client.has_collection(collection_name):
            print(f"[*] Removing existing collection '{collection_name}' for pristine state...")
            client.delete_collection(collection_name)

        print(f"[*] Provisioning sharded collection '{collection_name}'...")
        collection = client.create_collection(
            name=collection_name,
            dimension=128,  # Match typical fast cognitive model dimensions
            metric=DistanceMetric.COSINE,
            index_type=IndexType.HNSW,
            shards=2,
            replicas=1
        )
        print(f"[+] Collection '{collection_name}' successfully provisioned.")

        # ── 3. Data Ingestion: Inserting vectors with rich cognitive payload ──────────
        print("[*] Performing batch ingestion into index...")
        
        # We ingest mock embeddings for sample documents
        documents = [
            {
                "id": "doc_01",
                "vector": [0.05] * 128,
                "payload": {"category": "quantum", "title": "Quantum Resonance in AI Architecture", "version": 1.2}
            },
            {
                "id": "doc_02",
                "vector": [0.15] * 128,
                "payload": {"category": "neuroscience", "title": "Synaptic Manifold Learning Models", "version": 2.0}
            },
            {
                "id": "doc_03",
                "vector": [0.25] * 128,
                "payload": {"category": "quantum", "title": "Distributed Quantum Entanglement Databases", "version": 1.0}
            }
        ]

        # Bulk insert operation
        inserted_count = collection.insert_batch(documents)
        print(f"[+] Successfully indexed {inserted_count} vector documents.")
        
        # Await small index consolidation period
        time.sleep(0.5)

        # ── 4. High-Performance Semantic KNN Search ────────────────────────────────────
        print("\n[*] Query 1: Executing raw semantic Cosine search (Top-2 closest matches)...")
        query_vector = [0.10] * 128
        results = collection.search(
            vector=query_vector,
            limit=2
        )

        for i, hit in enumerate(results, 1):
            print(f"  [{i}] ID: {hit.id} | Score (Similarity): {hit.score:.4f} | Category: {hit.payload.get('category')} | Title: {hit.payload.get('title')}")

        # ── 5. Advanced Hybrid Search: KNN Search + Strict Payload Filter ──────────────
        print("\n[*] Query 2: Executing hybrid search (Category filtered for 'quantum' only)...")
        hybrid_results = collection.search(
            vector=query_vector,
            limit=2,
            filter={"category": "quantum"}
        )

        for i, hit in enumerate(hybrid_results, 1):
            print(f"  [{i}] ID: {hit.id} | Score: {hit.score:.4f} | Payload: {hit.payload}")

        # ── 6. Cleanup & Session Termination ──────────────────────────────────────────
        print("\n[*] Tearing down temporal index spaces...")
        client.delete_collection(collection_name)
        print("[+] Teardown completed. Session closed safely.")

    except Exception as e:
        print(f"[!] Engine processing exception: {str(e)}")
        sys.exit(2)

if __name__ == "__main__":
    main()
