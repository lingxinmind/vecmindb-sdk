"""Multi-tenant usage example.

Demonstrates the full tenancy flow: the admin key creates a tenant (the
server provisions the collection and returns the one-time tenant key),
the team connects with that key, and every subsequent call is
automatically bound to the team's collection.

Run with:
    VECMIN_SERVER=http://<host>:5520 ADMIN_KEY=<admin-key> \
    python examples/04_tenancy.py
"""

import os
import sys

from vecmindb import VecminClient

SERVER = os.environ.get("VECMIN_SERVER", "http://localhost:5520")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")


def main() -> None:
    if not ADMIN_KEY:
        print("set ADMIN_KEY to the server admin key", file=sys.stderr)
        sys.exit(1)

    admin = VecminClient(base_url=SERVER, api_key=ADMIN_KEY)

    # 1. Create a tenant: collection + key are issued server-side.
    tenant = admin.create_tenant("dev_team")
    print(f"tenant:   {tenant['tenant']}")
    print(f"collection: {tenant['collection']}")
    print(f"key:      {tenant['key']}   # shown once; hand it to the team")

    # 2. The team connects with the tenant key — isolation is automatic.
    team = VecminClient(base_url=SERVER, api_key=tenant["key"])
    visible = [c.name for c in team.list_tenants()]
    print(f"team sees collections: {visible}")

    # 3. MCP memory tools via the dedicated client (all nine tools).
    from vecmindb.mcp import SyncMcpClient

    mcp = SyncMcpClient(base_url=SERVER, api_key=tenant["key"])
    mcp.store_memory("team onboarding: deploy with docker compose", is_factual=True)
    print("stored via MCP")
    listing = mcp.list_memories()
    print(f"list_memories: {listing}")


if __name__ == "__main__":
    main()
