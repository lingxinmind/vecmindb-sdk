# VecminDB Private Deployment Guide v1.0

Deploy VecminDB on your own infrastructure in under 60 minutes. Single-node,
3-node HA cluster, or air-gapped environments — all covered.

---

## Quick Start (Single Node — 5 Minutes)

```bash
# 1. Pull the image
docker pull vecmindb/vecmindb:latest

# 2. Start with default config
docker run -d \
  --name vecmindb \
  -p 5520:5520 \
  -v vecmindb_data:/data \
  vecmindb/vecmindb:latest

# 3. Verify it's alive
curl http://localhost:5520/healthz/live
# → {"status":"healthy","engine":"online"}

# 4. Check license status (30-day trial starts automatically)
curl http://localhost:5520/license/status
# → {"state":"trial","tier":"trial","days_remaining":30,...}
```

You now have a running VecminDB instance. Proceed to **Agent Integration**
below to store your first memory.

---

## Configuration

VecminDB loads configuration from `config.yml` in the working directory.
Override any setting via environment variables:

```bash
docker run -d \
  --name vecmindb \
  -p 5520:5520 \
  -v $(pwd)/config.yml:/app/config.yml \
  -e VECMIN_PORT=5520 \
  -e VECMIN_STORAGE_PATH=/data \
  -e LOG_LEVEL=info \
  vecmindb/vecmindb:latest
```

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `storage.path` | `./data` | Persistent data directory |
| `storage.cache_size` | 1GB | RocksDB block cache |
| `resource.max_memory` | 1GB | Global memory ceiling |
| `resource.num_threads` | auto | CPU thread pool |
| `server.host` | `0.0.0.0` | Bind address |
| `server.port` | `5520` | HTTP port |

### Per-Agent Resource Quotas

In `config.yml` under `resource.agent_quotas`, define per-agent limits:

```yaml
resource:
  agent_quotas:
    my_agent:
      agent_id: "my_agent"
      max_qps: 1000
      max_memory_bytes: 1073741824   # 1GB
      max_cpu_ratio: 0.3
```

Quotas can be updated at runtime:

```bash
curl -X PUT http://localhost:5520/agents/my_agent/quota \
  -H "Content-Type: application/json" \
  -d '{"max_qps": 2000, "max_memory_bytes": 2147483648}'
```

---

## 3-Node HA Cluster

### Prerequisites

- 3 Linux nodes (amd64 or arm64) with Docker installed
- Network connectivity between all nodes on ports 5520 (HTTP) and 5521 (Raft)
- Shared nothing — each node has its own `/data` volume

### Node 1 (Leader seed)

```bash
docker run -d \
  --name vecmindb-node1 \
  --network host \
  -v /data/vecmindb/node1:/data \
  -e VECMIN_HOST=10.0.0.1 \
  -e VECMIN_PORT=5520 \
  -e VECMIN_RAFT_ADDR=10.0.0.1:5521 \
  -e VECMIN_NODE_ID=1 \
  -e VECMIN_PEERS="2=10.0.0.2:5521,3=10.0.0.3:5521" \
  vecmindb/vecmindb:latest
```

### Node 2

```bash
docker run -d \
  --name vecmindb-node2 \
  --network host \
  -v /data/vecmindb/node2:/data \
  -e VECMIN_HOST=10.0.0.2 \
  -e VECMIN_PORT=5520 \
  -e VECMIN_RAFT_ADDR=10.0.0.2:5521 \
  -e VECMIN_NODE_ID=2 \
  -e VECMIN_PEERS="1=10.0.0.1:5521,3=10.0.0.3:5521" \
  vecmindb/vecmindb:latest
```

### Node 3

```bash
docker run -d \
  --name vecmindb-node3 \
  --network host \
  -v /data/vecmindb/node3:/data \
  -e VECMIN_HOST=10.0.0.3 \
  -e VECMIN_PORT=5520 \
  -e VECMIN_RAFT_ADDR=10.0.0.3:5521 \
  -e VECMIN_NODE_ID=3 \
  -e VECMIN_PEERS="1=10.0.0.1:5521,2=10.0.0.2:5521" \
  vecmindb/vecmindb:latest
```

### Verify Cluster

```bash
# Check each node
curl http://10.0.0.1:5520/healthz/ready
curl http://10.0.0.2:5520/healthz/ready
curl http://10.0.0.3:5520/healthz/ready

# All should return: {"status":"ready"}
```

### Docker Compose

Alternatively, use the bundled `docker-compose.cluster.yml`:

```bash
# Edit the file to set correct IPs, then:
docker-compose -f docker-compose.cluster.yml up -d
```

---

## Air-Gapped Deployment

For environments without internet access:

### On a connected machine

```bash
# Save the image
docker pull vecmindb/vecmindb:latest
docker save vecmindb/vecmindb:latest | gzip > vecmindb.tar.gz

# Copy to air-gapped machine via USB/secure transfer
scp vecmindb.tar.gz operator@airgap-host:/opt/
```

### On the air-gapped machine

```bash
docker load < /opt/vecmindb.tar.gz

docker run -d \
  --name vecmindb \
  -p 5520:5520 \
  -v /data/vecmindb:/data \
  vecmindb/vecmindb:latest
```

### Offline License Activation

```bash
# 1. Generate a hardware fingerprint on the air-gapped machine
curl http://localhost:5520/license/status
# Note the instance ID from the response

# 2. On a connected machine, provide the instance ID to obtain a key
# Contact: licensing@vecmindb.com

# 3. Activate with the key
curl -X POST http://localhost:5520/license/activate \
  -H "Content-Type: application/json" \
  -d '{"activation_key": "VECMIN.1716931200.3.500.A1B2C3D4E5F6.abc123def456..."}'
```

---

## Agent Integration

### Python SDK

```bash
pip install vecmindb
```

```python
from vecmindb import McpClient
import asyncio

async def main():
    async with McpClient("http://localhost:5520") as mcp:
        # Store a memory
        await mcp.store_memory(
            content="Customer prefers email over phone for updates",
            agent_id="support_bot",
            sovereignty_token="support_team",
        )

        # Search by meaning
        results = await mcp.search_memory(
            query="how does the customer want to be contacted",
            agent_id="support_bot",
            top_k=5,
        )
        for r in results:
            print(f"[{r.score:.4f}] {r.id}")

asyncio.run(main())
```

### LangChain Integration

```python
from vecmindb.memory_plugin import VecminDBMemoryPlugin

memory = VecminDBMemoryPlugin(
    base_url="http://localhost:5520",
    agent_id="my_agent",
    sovereignty_token="my_token",
)

# Use with any LangChain chain
from langchain.chains import ConversationChain
chain = ConversationChain(llm=my_llm, memory=memory)
```

### CrewAI Multi-Agent Setup

```python
from vecmindb.memory_plugin import VecminDBCrewMemory

memory = VecminDBCrewMemory(
    base_url="http://localhost:5520",
    crew_id="support_crew",
    agent_ids=["billing_agent", "tech_agent", "manager_agent"],
)

# Each agent gets isolated memory; shared knowledge via alliance centroids
billing_memory = memory.agent_memory("billing_agent")
billing_memory.save_context(
    {"input": "User asks about refund"},
    {"output": "Refund policy: 30 days, full refund"},
)
```

### MCP Protocol (Direct HTTP)

```bash
curl -X POST http://localhost:5520/api/v1/mcp/message \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "store_memory",
      "arguments": {
        "text": "User prefers dark mode and is most active after 10pm",
        "agent_id": "my_agent",
        "sovereignty_token": "my_token"
      }
    }
  }'
```

---

## License Management

### Check License Status

```bash
curl http://localhost:5520/license/status
```

Response fields:
- `state`: `trial` | `active` | `expired`
- `days_remaining`: days left (null = perpetual)
- `max_nodes`: cluster node limit (0 = unlimited)
- `max_agents`: registered agent limit (0 = unlimited)
- `grace_period`: whether in read-only grace period
- `writes_enabled`: whether write operations are allowed
- `trial_extensions_used` / `trial_extensions_max`

### Activate a Commercial License

```bash
curl -X POST http://localhost:5520/license/activate \
  -H "Content-Type: application/json" \
  -d '{"activation_key": "VECMIN.1716931200.3.500.A1B2C3D4E5F6.signature..."}'
```

The key encodes: expiry timestamp, max cluster nodes, max agents.
Keys are Ed25519-signed and cryptographically verified.

### Trial Extensions

```bash
# Extend trial by 15 days (max 2 extensions = 30 extra days)
curl -X POST http://localhost:5520/admin/trial/extend
```

Trial baseline: 30 days + up to 2 extensions × 15 days = 60 days maximum.
After trial expiry, a 7-day grace period allows read-only access.
After grace period, all API requests return HTTP 402.

---

## Monitoring

### Prometheus Metrics

```
GET /metrics
```

Key metrics:

| Metric | Description |
|--------|-------------|
| `vecmindb_vectors_total` | Total vectors stored |
| `vecmindb_requests_total` | HTTP requests by method and status |
| `vecmindb_request_duration_seconds` | Request latency histogram |
| `vecmindb_memory_usage_bytes` | Process memory |
| `vecmindb_license_remaining_days` | License days remaining |
| `promotion_pending_count` | Pending promotion candidates |
| `promotion_approve_total` | Approved promotions |
| `promotion_veto_total` | Vetoed promotions |
| `vecmindb_abstract_centroid_count` | Active abstract centroids |
| `vecmindb_alliance_centroid_count` | Alliance-level centroids |
| `vecmindb_vacuum_cycle_duration_seconds` | Vacuum cycle duration per collection |

### Grafana Dashboard

```bash
# Add Prometheus scrape target
scrape_configs:
  - job_name: 'vecmindb'
    static_configs:
      - targets: ['localhost:5520']
```

Import the dashboard JSON from `deploy/grafana-dashboard.json`.

---

## Health Probes

| Path | Purpose | Expected |
|------|---------|----------|
| `/healthz/live` | Liveness — process alive | `{"status":"healthy"}` |
| `/healthz/ready` | Readiness — can serve traffic | `{"status":"ready"}` |
| `/healthz/startup` | Startup — initialization complete | `{"status":"started"}` |

Kubernetes example:

```yaml
livenessProbe:
  httpGet:
    path: /healthz/live
    port: 5520
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /healthz/ready
    port: 5520
  initialDelaySeconds: 10
  periodSeconds: 5

startupProbe:
  httpGet:
    path: /healthz/startup
    port: 5520
  failureThreshold: 30
  periodSeconds: 5
```

---

## Backup & Restore

```bash
# Backup the data directory while the container is running
docker exec vecmindb tar -czf /tmp/vecmindb-backup.tar.gz /data
docker cp vecmindb:/tmp/vecmindb-backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz

# Restore
docker stop vecmindb
rm -rf /data/vecmindb/*
tar -xzf backup-20260522.tar.gz -C /
docker start vecmindb
```

For cluster deployments, back up each node's `/data` independently.
Raft logs will reconcile on restart.

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `402 Payment Required` | License expired. Check `/license/status`. |
| `429 Too Many Requests` | Agent QPS quota exceeded. Check `/agents/{id}/quota`. |
| `403 Forbidden` | Sovereignty Token mismatch. Verify agent_id matches collection token. |
| `503 Service Unavailable` | Circuit breaker open — agent has sustained quota violations. |
| Engine won't start | Check disk space, `config.yml` syntax, license validity. |
| Cluster won't form | Verify all nodes can reach each other on Raft port (5521). |

### Logs

```bash
docker logs vecmindb

# For JSON-formatted structured logs:
docker run -e LOG_FORMAT=json -e LOG_LEVEL=debug ...
```

---

## Production Checklist

- [ ] Persistent volume for `/data` (not ephemeral container storage)
- [ ] License activated (not running on trial)
- [ ] Prometheus scraping configured
- [ ] Health probes wired to load balancer / K8s
- [ ] Agent quotas configured per workload
- [ ] Backup schedule established (daily recommended)
- [ ] Firewall rules: 5520 (HTTP), 5521 (Raft, cluster only)
- [ ] Resource limits set (memory, CPU) in container runtime

---

*VecminDB v1.0 — Private Deployment Guide. Last updated 2026-05-22.*
