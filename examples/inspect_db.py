#!/usr/bin/env python3
"""VecminDB Database Inspector Tool.

Lists all collections, retrieves stats, and dumps vectors (with metadata)
from each collection using zero-vector exhaustive query recall.
"""

import os
import sys
from vecmindb import VecminClient

def main():
    base_url = os.getenv("VECMINDB_URL", "http://localhost:5520")
    api_key = os.getenv("VECMINDB_API_KEY", None)

    print("================================================================================")
    print("                      VecminDB Cluster & Data Inspector")
    print("================================================================================")
    print(f"Connecting to: {base_url}")
    print(f"Auth Key:      {'[PRESENT]' if api_key else '[MISSING/NONE]'}")
    print("================================================================================")

    try:
        client = VecminClient(base_url=base_url, api_key=api_key)
        
        # 1. List all collections
        collections = client.list_collections()
        if not collections:
            print("No collections found in this VecminDB instance.")
            return

        print(f"Found {len(collections)} collection(s):\n")

        for idx, col in enumerate(collections, start=1):
            print(f"[{idx}] Collection Name: {col.name}")
            print(f"    ├─ Dimension:       {col.dimension}")
            print(f"    ├─ Metric Type:    {col.metric_type}")
            print(f"    ├─ Index Type:     {col.index_type}")
            print(f"    ├─ Cognitive Domain: {col.domain}")
            print(f"    ├─ Vector Count:    {col.vector_count}")
            print(f"    └─ Size (Bytes):    {col.size_bytes}")

            # 2. If vectors exist, dump them using a zero-vector exhaustive recall
            if col.vector_count > 0:
                print(f"    ▲ Retrieving vectors for '{col.name}'...")
                # Generate a dummy zero vector of matching dimension
                zero_query = [0.0] * col.dimension
                
                try:
                    # Recall all vectors by matching their counts
                    response = client.search(
                        collection=col.name,
                        query=zero_query,
                        top_k=col.vector_count
                    )
                    
                    if response.results:
                        print(f"    🧬 Stored Vectors (Total: {len(response.results)}):")
                        for v_idx, hit in enumerate(response.results, start=1):
                            print(f"      {v_idx}. ID: {hit.id}")
                            print(f"         ├─ Query Distance Score: {hit.score:.6f}")
                            if hit.metadata:
                                print(f"         └─ Metadata (Cognitive Content):")
                                for k, v in hit.metadata.items():
                                    print(f"            • {k}: {v}")
                            else:
                                print(f"         └─ Metadata: None")
                    else:
                        print("    🧬 Stored Vectors: None returned (Index might be rebuilding)")
                except Exception as search_err:
                    print(f"    ❌ Failed to retrieve vectors: {search_err}")
            else:
                print("    🧬 Stored Vectors: Empty collection")
            print("-" * 80)

        print("Inspector finished duty cycle.")

    except Exception as e:
        print(f"\n❌ Connectivity / Authentication Error: {e}")
        print("Please make sure VECMINDB_URL and VECMINDB_API_KEY are configured correctly.")

if __name__ == "__main__":
    main()
