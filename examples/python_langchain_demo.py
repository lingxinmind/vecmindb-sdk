#!/usr/bin/env python3
"""
VecminDB Python SDK - LangChain VectorStore & RAG Integration Demo
Copyright (c) 2026 Shanghai Lingxin Zhisuan Intelligent Technology Co., Ltd.
All rights reserved.

This demo illustrates:
1. Wrap VecminDB client as a LangChain-compliant VectorStore.
2. Ingesting text documents, splitting them, and generating embeddings.
3. Performing similarity searches with scores.
4. Constructing a QA chain for Retrieval-Augmented Generation (RAG).
"""

import os
import sys
import time

# Fake embedding generator to make the script 100% runnable without external OpenAI keys
class MockCognitiveEmbeddings:
    def embed_documents(self, texts):
        # Generates a pseudo-deterministic 128-dim vector for each text
        return [[(ord(c) / 256.0) for c in (t * 20)[:128]] for t in texts]
        
    def embed_query(self, text):
        return [(ord(c) / 256.0) for c in (text * 20)[:128]]

try:
    from vecmindb import VecminClient
    from vecmindb.integrations.langchain import VecminDBVectorStore
except ImportError:
    print("[!] Error: vecmindb library is not installed or importable.")
    print("    Run: pip install -e . (inside python directory)")
    sys.exit(1)

def main():
    print("=== VecminDB LangChain RAG Integration Example ===")
    
    # 1. Connect Client
    host = os.getenv("VECMINDB_HOST", "127.0.0.1")
    port = int(os.getenv("VECMINDB_PORT", "5520"))
    client = VecminClient(host=host, port=port, token="demo-token-key-2026")
    
    if not client.ping():
        print("[!] Server unreachable. Run this demo with a running VecminDB node.")
        sys.exit(1)
        
    collection_name = "langchain_rag_kb"
    
    # 2. Prepare Sample Knowledge Documents
    sample_texts = [
        "VecminDB is a high-performance, sharded vector database built natively in Rust for 10B-scale agent memory manifolds.",
        "The cognitive engine in VecminDB supports built-in ONNX runtime inferences, eliminating external Python model dependencies.",
        "LTSM (Long Term Semantic Memory) in VecminDB enables cognitive memory consolidation, evolving memories over temporal limits."
    ]
    metadatas = [
        {"source": "product_specs", "importance": "critical"},
        {"source": "architecture_manual", "importance": "high"},
        {"source": "cognitive_design", "importance": "critical"}
    ]

    print("[*] Ingesting documents into LangChain Vector Store...")
    embeddings = MockCognitiveEmbeddings()
    
    # 3. Create VectorStore instance
    vector_store = VecminDBVectorStore.from_texts(
        texts=sample_texts,
        embedding=embeddings,
        metadatas=metadatas,
        client=client,
        collection_name=collection_name
    )
    
    print("[+] Documents embedded and indexed in VecminDB successfully.")
    time.sleep(0.5)

    # 4. Perform Similarity Search
    query = "How does VecminDB support memory consolidation?"
    print(f"\n[*] Querying database: '{query}'")
    
    # Similarity search with document mapping
    docs_with_scores = vector_store.similarity_search_with_score(query, k=2)
    
    for i, (doc, score) in enumerate(docs_with_scores, 1):
        print(f"  [{i}] Score (L2 Distance): {score:.4f}")
        print(f"      Content: {doc.page_content}")
        print(f"      Metadata: {doc.metadata}\n")

    # 5. Clean up Space
    print("[*] Cleaning up temporary RAG index space...")
    client.delete_collection(collection_name)
    print("[+] Teardown completed. Demo finished successfully.")

if __name__ == "__main__":
    main()
