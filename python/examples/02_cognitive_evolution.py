#!/usr/bin/env python3
"""VecminDB Python SDK - 02 Cognitive Evolution & Centroids Example.

Demonstrates:
1. Triggering memory evolution loops (auto-promotion decisions & index optimization).
2. Retrieving LTSM distilled abstract centroids.
"""

import sys
from vecmindb import VecminClient
from vecmindb.memory import AgentMemoryManager


def main():
    endpoint = "http://localhost:5520"
    print(f"=== VecminDB Cognitive Memory Evolution Example ===")

    try:
        client = VecminClient(endpoint=endpoint)
        manager = AgentMemoryManager(
            client=client,
            agent_id="demo_agent_01",
            sovereignty_token="demo_sovereign_secret_99"
        )
        memory = manager.mount_memory(domain="user_preferences")

        # 1. Trigger Cognitive Evolution
        print("\n[1] Triggering Cognitive Evolution Loop...")
        evolution_report = memory.evolve()
        print(f"  Evolution Status: {evolution_report.get('status')}")
        print(f"  Candidates Evaluated: {evolution_report.get('candidates_evaluated')}")
        print(f"  Index Optimization: {evolution_report.get('index_optimization')}")

        # 2. Retrieve LTSM Abstract Centroids
        print("\n[2] Fetching LTSM Abstract Memory Centroids...")
        centroids = memory.get_centroids()
        print(f"  Retrieved {len(centroids)} abstract centroid clusters.")
        for idx, c in enumerate(centroids, start=1):
            print(f"    Cluster [{idx}]: {c}")

        print("\n✓ Cognitive evolution example completed!")

    except Exception as e:
        print(f"\n[Note] Server connection test: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
