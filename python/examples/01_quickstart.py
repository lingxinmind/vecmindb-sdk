#!/usr/bin/env python3
"""VecminDB Python SDK - 01 Quickstart Example.

Demonstrates:
1. Connecting to VecminDB.
2. Mounting an Agent Cognitive Memory Space with Sovereignty Token isolation.
3. Storing episodic memories.
4. Searching memories.
"""

import sys
from vecmindb import VecminClient
from vecmindb.memory import AgentMemoryManager


def main():
    base_url = "http://localhost:5520"
    print(f"=== VecminDB Python SDK Quickstart ===")
    print(f"Connecting to VecminDB server at {base_url}...")

    try:
        client = VecminClient(base_url=base_url)
        print("✓ Successfully initialized VecminClient.")

        # 2. Collection Creation (Only Name & Optional Domain Required!)
        # Built-in Supported Domains ("domain"):
        #   - "general"       : General Purpose Default
        #   - "finance"       : Financial Risk & Asset Management
        #   - "medical"       : Healthcare & Patient Clinical Records
        #   - "legal"         : Legal Contracts & Compliance Terms
        #   - "hr"            : Human Resources & Recruitment
        #   - "code"/"software": Software Specs & Source Code
        #   - "ecommerce"     : E-Commerce & Retail Logistics
        #   - "manufacturing" : Industrial Manufacturing & Quality Control
        #   - "insurance"     : Insurance Policy & Claims Processing
        #   - "education"     : Education & Academic Records
        
        # Option A: Zero-Param Creation (Defaults to "general" domain, 1024-dim BGE-M3, Cosine, HNSW)
        client.create_collection("my_documents")

        # Option B: Domain-Anchored Creation (Specify collection name & domain!)
        client.create_collection("financial_reports", domain="finance")
        print("✓ Collections created successfully with domain factuality anchoring!")

        # 3. Mount Cognitive Memory Space for an Agent
        # Agent binds its sovereign partition directly to a target collection!
        agent_id = "demo_agent_01"
        sovereignty_token = "demo_sovereign_secret_99"
        
        print(f"\nMounting memory space for agent '{agent_id}' to collection 'financial_reports'...")
        manager = AgentMemoryManager(
            client=client,
            agent_id=agent_id,
            sovereignty_token=sovereignty_token
        )
        # Pass collection_name to mount existing collection
        memory = manager.mount_memory(collection_name="financial_reports")
        print("✓ Memory space mounted successfully.")

        # 3. Store Episodic Memories
        memories_to_store = [
            ("User prefers drinking espresso in the morning.", {"category": "beverage"}),
            ("User works as a senior backend software engineer.", {"category": "profession"}),
            ("User enjoys playing tennis on weekends.", {"category": "hobby"})
        ]

        print("\nStoring episodic memories...")
        for text, meta in memories_to_store:
            mem_id = memory.store_memory(text=text, metadata=meta)
            print(f"  + Stored memory (ID/Response: {mem_id[:30]}...)")

        # 4. Search Memories
        query = "What does the user like to drink?"
        print(f"\nSearching memory with query: '{query}'...")
        results = memory.search_memory(query=query, top_k=2)
        
        print("\n=== Search Results ===")
        for idx, item in enumerate(results, start=1):
            print(f" Hit [{idx}]: {item}")

        print("\n✓ Quickstart completed successfully!")

    except Exception as e:
        print(f"\n[Note] Server connection test: {e}")
        print("Make sure VecminDB server is running at http://localhost:8080.")
        sys.exit(0)


if __name__ == "__main__":
    main()
