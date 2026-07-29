# VecminDB REST API Reference

Complete reference for the VecminDB HTTP API. All endpoints use JSON for request and response bodies unless otherwise noted.

## Table of Contents

- [Overview](#overview)
- [ONNX Auto-Embedding](#onnx-auto-embedding)
- [Authentication](#authentication)
- [Collection Management](#collection-management)
- [Vector Operations](#vector-operations)
- [Search](#search)
- [Cluster Management](#cluster-management)
- [Index Administration](#index-administration)
- [System & Telemetry](#system--telemetry)
- [Rate Limiting & Resource Quotas](#rate-limiting--resource-quotas)
- [MCP (Model Context Protocol) Integration](#mcp-model-context-protocol-integration)
- [Debug & Observability Endpoints](#debug--observability-endpoints)
- [Kubernetes Probe Configuration](#kubernetes-probe-configuration)

---

## Overview

| Item | Value |
|:-----|:------|
| **Base URL** | `http://localhost:5520` |
| **API Version** | `v1` |
| **Content-Type** | `application/json` |
| **Default HTTP Port** | `5520` |
| **Default Raft/gRPC Port** | `5521` |

### Response Format

All API responses share a unified envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "code": 200,
  "message": null
}
```

| Field | Type | Description |
|:------|:-----|:------------|
| `success` | boolean | `true` if the operation succeeded |
| `data` | any | Payload on success; `null` on error |
| `error` | string | Error message on failure; `null` on success |
| `code` | integer | HTTP-like status code |
| `message` | string | Human-readable context message |

---

## ONNX Auto-Embedding

VecminDB includes a built-in ONNX neural embedding model (`model.onnx` + `tokenizer.json`) located at `models/builtin/`. This model powers automatic text-to-vector conversion:

- **Vector Insertion**: When you provide text content in `metadata`, you can store the original text alongside vectors. VecminDB uses the ONNX model internally for feature extraction and indexing optimization.
- **Vector Search**: Query vectors can be derived from text input. The ONNX model converts text queries into vector embeddings for similarity search.
- **Lazy Loading**: The ONNX model is loaded on the first inference request, not at startup. This ensures fast server initialization.
- **Hash Fallback**: If ONNX model files are not found, VecminDB falls back to deterministic hash-based embeddings (with reduced search quality).

The ONNX model path can be overridden via the `VECMINDB_MODELS_DIR` environment variable. See [CONFIGURATION.md](CONFIGURATION.md#onnx-model-configuration) for details.

---

## Authentication

VecminDB supports two authentication mechanisms on protected routes.

### 1. API Key (Header)

Pass the key in the `x-api-key` header:

```bash
curl -H "x-api-key: <your-api-key>" http://localhost:5520/api/v1/collections
```

### 2. Bearer Token (JWT)

Pass a JWT token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer <jwt-token>" http://localhost:5520/api/v1/collections
```

### Key Roles

| Key | Permissions |
|:----|:------------|
| **Admin Key** (`security.admin_key`) | Full read/write/governance access |
| **Viewer Key** (`security.viewer_key`) | Read-only (`GET`) and search operations |

> **Note:** The following paths do **not** require authentication:
> - `/healthz/live`, `/healthz/ready`, `/healthz/startup`
> - `/dashboard`
> - `/metrics`
> - `/api/v1/health`
> - `/api/v1/cluster/login`

---

## Collection Management

Collections are logical partitions for vectors. Each collection has a fixed `dimension` and an `index_type`.

### Create Collection

```
POST /api/v1/collections
```

**Request body:**

```json
{
  "name": "my_collection",
  "dimension": 128,
  "index_type": "HNSW",
  "metadata_schema": {
    "category": "string",
    "score": "float"
  }
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `name` | string | Yes | Unique collection name |
| `dimension` | integer | Yes | Vector dimension (1--10000) |
| `index_type` | string | No | `Flat`, `HNSW`, `IVF`, `PQ`, `LSH`, `VPTree` (default: `Flat`) |
| `metadata_schema` | object | No | Optional attribute schema for filtering |

**Response (201 Created):**

```json
{
  "success": true,
  "data": {
    "name": "my_collection",
    "dimension": 128,
    "index_type": "HNSW",
    "vector_count": 0,
    "created_at": "2026-05-13T00:00:00+00:00"
  },
  "error": null,
  "code": 200,
  "message": null
}
```

---

### List Collections

```
GET /api/v1/collections
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": [
    {
      "name": "my_collection",
      "dimension": 128,
      "index_type": "HNSW",
      "vector_count": 42,
      "created_at": "2026-05-13T00:00:00+00:00"
    }
  ],
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Get Collection

```
GET /api/v1/collections/{name}
```

**Response (200 OK):** Same shape as a single item in the list response.

**Error (404 Not Found):**

```json
{
  "success": false,
  "data": null,
  "error": "Collection 'my_collection' not found.",
  "code": 404,
  "message": null
}
```

---

### Delete Collection

```
DELETE /api/v1/collections/{name}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "code": 200,
  "message": "Purged successfully."
}
```

---

### Get Collection Stats

```
GET /api/v1/collections/{name}/stats
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "name": "my_collection",
    "vector_count": 42,
    "index_type": "HNSW",
    "memory_usage": 21504,
    "index_status": "Ready"
  },
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Rebuild Collection Index

```
POST /api/v1/collections/{name}/rebuild
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "code": 200,
  "message": "Re-hydration triggered."
}
```

---

## Vector Operations

Vectors can be managed either globally (`/api/v1/vectors`) or within a specific collection (`/api/v1/collections/{name}/vectors`).

### Insert Vector (Collection-Scoped)

```
POST /api/v1/collections/{name}/vectors
```

**Request body:**

```json
{
  "id": "vec-001",
  "data": [0.1, 0.2, 0.3, ...],
  "metadata": { "text": "machine learning algorithms", "category": "demo" }
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `id` | string | Yes | Unique vector identifier |
| `data` | array of float | Yes | Vector embedding values |
| `metadata` | object | No | Arbitrary JSON metadata (use `metadata.text` to store the original text for retrieval) |

> **Auto-Embedding:** Store the original text in `metadata.text`. VecminDB's internal ONNX model uses this for feature extraction and indexing optimization. The `data` field should contain the vector embedding values for the text.

**Response (201 Created):**

```json
{
  "success": true,
  "data": {
    "id": "vec-001",
    "agent_id": "default_agent",
    "model_id": "default_model",
    "timestamp": 1715558400000,
    "data": [0.1, 0.2, 0.3, ...],
    "metadata": { "category": "demo" },
    "created_at": "2026-05-13T00:00:00+00:00",
    "updated_at": "2026-05-13T00:00:00+00:00"
  },
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Get Vector (Collection-Scoped)

```
GET /api/v1/collections/{name}/vectors/{id}
```

**Response (200 OK):** Vector object (same shape as insert response).

---

### Delete Vector (Collection-Scoped)

```
DELETE /api/v1/collections/{name}/vectors/{id}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "code": 200,
  "message": "Purged successfully."
}
```

---

### Insert Vector (Global)

```
POST /api/v1/vectors
```

**Request body:**

```json
{
  "id": "vec-001",
  "values": [0.1, 0.2, 0.3, ...],
  "collection": "default",
  "metadata": { "category": "demo" }
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `id` | string | Yes | Unique vector identifier |
| `values` | array of float | Yes | Vector embedding values |
| `collection` | string | No | Target collection (default: `default`) |
| `metadata` | object | No | Arbitrary JSON metadata |

**Response (201 Created):**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "code": 200,
  "message": "Vector ingested."
}
```

---

### Batch Insert Vectors (Global)

```
POST /api/v1/vectors/batch
```

**Request body:**

```json
{
  "vectors": [
    {
      "id": "vec-001",
      "values": [0.1, 0.2, ...],
      "collection": "default",
      "metadata": { "category": "demo" }
    },
    {
      "id": "vec-002",
      "values": [0.4, 0.5, ...],
      "collection": "default"
    }
  ]
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": 2,
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Get Vector (Global)

```
GET /api/v1/vectors/{id}
```

**Response (200 OK):** Full vector object.

---

### Delete Vector (Global)

```
DELETE /api/v1/vectors/{id}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "code": 200,
  "message": "Vector deleted."
}
```

---

### Batch Delete Vectors (Global)

```
POST /api/v1/vectors/batch/delete
```

**Request body:**

```json
{
  "vector_ids": ["vec-001", "vec-002"]
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": 2,
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Count Vectors (Global)

```
GET /api/v1/vectors/count
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": { "count": 42 },
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Batch Operations (Collection-Scoped)

```
POST /api/v1/collections/{name}/batch
```

**Request body:**

```json
{
  "operations": [
    {
      "type": "add",
      "id": "vec-003",
      "data": [0.1, 0.2, ...],
      "metadata": { "category": "batch" }
    }
  ]
}
```

> Currently supports `add` operations. Each operation must include `type`, `id`, and `data` (or `vector` alias).

---

## Search

### Search Collection

```
POST /api/v1/collections/{name}/search
```

**Request body:**

```json
{
  "query_vector": [0.1, 0.2, 0.3, ...],
  "top_k": 10,
  "metric": "cosine"
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `query_vector` | array of float | Yes | Query embedding (alias: `query`) |
| `top_k` | integer | No | Number of results (default: `10`) |
| `metric` | string | No | `cosine`, `euclidean`, `dot` (default: `cosine`) |

> **Auto-Embedding:** The `query_vector` should contain the embedding of your query text. If you are using VecminDB's ONNX model for embedding, convert your text query through the same model before passing it here. Store original text in `metadata.text` at insert time so you can retrieve readable results.

**Smart Recall:** If `top_k` is omitted, the engine uses adaptive truncation based on score gradients (semantic elbow detection).

**Response (200 OK):**

```json
{
  "success": true,
  "data": [
    {
      "id": "vec-001",
      "score": 0.9876,
      "raw_score": 0.9876,
      "metadata": { "category": "demo" },
      "agent_id": "default_agent",
      "model_id": "default_model",
      "timestamp": 1715558400000
    }
  ],
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Global Search

```
POST /api/v1/vectors/search
```

**Request body:**

```json
{
  "query_vector": [0.1, 0.2, 0.3, ...],
  "top_k": 10,
  "metric": "cosine",
  "agent_ids": ["agent-1"],
  "model_ids": ["model-1"],
  "start_time": 1715550000,
  "end_time": 1715560000,
  "filter": { "category": "demo" }
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `query_vector` | array of float | Yes | Query embedding |
| `top_k` | integer | No | Number of results (default: `10`) |
| `metric` | string | No | `cosine`, `euclidean`, `dot` (default: `cosine`) |
| `agent_ids` | array of string | No | Filter by agent identity |
| `model_ids` | array of string | No | Filter by model identity |
| `start_time` | integer | No | Epoch seconds (inclusive) |
| `end_time` | integer | No | Epoch seconds (inclusive) |
| `filter` | object | No | Metadata-level JSON filter |
| `wait` | object | No | Consistency fence target |

> **Auto-Embedding:** As with collection-scoped search, the `query_vector` should be the embedding of your query text. Use the same ONNX model for consistent embedding space.

**Response (200 OK):** Same shape as collection search.

---

## Cluster Management

> These endpoints require the `distributed` feature and admin privileges.

### Login

```
POST /api/v1/cluster/login
```

**Request body:**

```json
{
  "username": "admin",
  "password": "..."
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": { "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." },
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Get Join Info

```
GET /api/v1/cluster/join_info
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "next_node_id": 4,
    "peers": { "1": "http://node1:5520", "2": "http://node2:5522" },
    "raft_peers": { "1": "node1:5521", "2": "node2:5523" },
    "cluster_name": "vecmindb-cluster"
  },
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Get Cluster Status

```
GET /api/v1/cluster/status
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "is_distributed": true,
    "node_id": 1,
    "peers": [2, 3]
  },
  "error": null,
  "code": 200,
  "message": null
}
```

---

### Join Cluster

```
POST /api/v1/cluster/join
```

**Request body:**

```json
{
  "seed_peer_address": "http://node1:5520"
}
```

---

### Promote Node

```
POST /api/v1/cluster/promote
```

**Response (200 OK):**

```json
{
  "status": "success",
  "message": "Promotion signal broadcasted to cluster."
}
```

---

### Add Node

```
POST /api/v1/cluster/nodes
```

**Request body:**

```json
{
  "id": 4,
  "address": "http://node4:5527",
  "raft_address": "node4:5528"
}
```

**Response (202 Accepted):**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "code": 200,
  "message": "Node 4 registration successful."
}
```

---

### Remove Node

```
DELETE /api/v1/cluster/nodes
```

**Request body:**

```json
{
  "id": 4
}
```

**Response (202 Accepted):**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "code": 200,
  "message": "Node 4 removal proposed."
}
```

---

## Index Administration

### List Indexes

```
GET /index
```

### Get Index Info

```
GET /index/{collection_name}
```

### Rebuild Index

```
POST /index/{collection_name}/rebuild
```

### Optimize Index

```
POST /index/{collection_name}/optimize
```

### Get Shadow Trajectory

```
GET /index/{collection_name}/shadow/trajectory
```

### Promote Shadow Index

```
POST /index/{collection_name}/shadow/promote
```

---

## System & Telemetry

### Liveness Probe

```
GET /healthz/live
```

**Response (200 OK):**

```json
{ "status": "alive" }
```

---

### Readiness Probe

```
GET /healthz/ready
```

**Response (200 OK):**

```json
{
  "status": "ready",
  "checks": {
    "engine_initialized": { "status": "pass" },
    "storage_writable": { "status": "pass" },
    "raft_joined": { "status": "pass" }
  }
}
```

**Response (503 Service Unavailable):**

```json
{
  "status": "not_ready",
  "checks": { ... },
  "reason": "engine_not_initialized"
}
```

---

### Startup Probe

```
GET /healthz/startup
```

**Response (200 OK):**

```json
{ "status": "started" }
```

**Response (503 Service Unavailable):**

```json
{ "status": "starting" }
```

---

### Health Check

```
GET /api/v1/health
```

**Response (200 OK):**

```json
{
  "status": "healthy",
  "engine": "online",
  "version": "1.0.0",
  "timestamp": "2026-05-13T00:00:00+00:00"
}
```

---

### Status Check

```
GET /api/v1/status
```

**Response (200 OK):**

```json
{
  "overall_status": "operational",
  "subsystems": {
    "storage": { "status": "online", "base_path": "/data" },
    "consensus": { "status": "online", "peer_count": 2 },
    "cache": { "status": "active" },
    "index": { "status": "ready", "collections_active": 3 }
  },
  "timestamp": "2026-05-13T00:00:00+00:00"
}
```

---

### Prometheus Metrics

```
GET /metrics
```

**Response (200 OK):** OpenMetrics text exposition format.

Example output:

```
# TYPE vecmindb_requests_total counter
vecmindb_requests_total{method="GET",path="/api/v1/collections"} 42

# TYPE vecmindb_request_duration_seconds histogram
vecmindb_request_duration_seconds_bucket{le="0.01"} 12
```

---

### Global Stats

```
GET /stats
```

### Index Stats

```
GET /stats/index
```

### Performance Stats

```
GET /stats/performance
```

---

## Status Codes

| Code | Meaning | Typical Causes |
|:-----|:--------|:---------------|
| `200` | OK | Request succeeded |
| `201` | Created | Resource created (vectors, collections) |
| `202` | Accepted | Async operation proposed (cluster changes) |
| `400` | Bad Request | Invalid JSON, missing required fields |
| `403` | Forbidden | Invalid/missing API key or RBAC denial |
| `404` | Not Found | Collection or vector does not exist |
| `429` | Too Many Requests | Resource quota exceeded (CPU/memory tokens exhausted or QPS limit reached) |
| `503` | Service Unavailable | Readiness/startup probe failure, or circuit breaker tripped due to sustained quota violations |

---

## Debug & Observability Endpoints

### `GET /api/v1/collections/{name}/debug/checksum`

Returns bucket-level checksums for data consistency verification across replicas.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `bucket` | u32 | Yes | - | Bucket index to check |
| `total` | u32 | No | 10000 | Total number of buckets |

**Example:**

```bash
curl "http://localhost:5520/api/v1/collections/my_collection/debug/checksum?bucket=42&total=10000" \
  -H "x-api-key: YOUR_API_KEY"
```

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "collection": "my_collection",
    "bucket": 42,
    "checksum": 3072004318
  },
  "error": null,
  "code": 200,
  "message": null
}
```

**Use Case:** Multi-replica consistency verification — compare checksums across nodes to detect data divergence.

---

### `GET /api/v1/collections/{name}/debug/centroid/{term}`

Returns the feature centroid and evolution state for a specific term from the Autonomous Evolution (LTSM) engine.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Collection name |
| `term` | string | Yes | The term to query centroid for |

**Example:**

```bash
curl "http://localhost:5520/api/v1/collections/my_collection/debug/centroid/machine_learning" \
  -H "x-api-key: YOUR_API_KEY"
```

**Response (200 OK):**

```json
{
  "status": "success",
  "term": "machine_learning",
  "data": {
    "centroid": [0.12, 0.34, 0.56, ...],
    "updates_n": 142,
    "revision": 15
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `centroid` | array of float | Incremental mean of the feature vector (semantic centroid) |
| `updates_n` | integer | Accumulated observation count for this feature term |
| `revision` | integer | Global revision counter for distributed Optimistic Concurrency Control |

**Error (404 Not Found):**

```json
{
  "status": "error",
  "error": "No evolutionary trajectory found for term: unknown_term"
}
```

**Use Case:** Monitoring knowledge evolution — track how the system's understanding of concepts changes over time.

---

## Kubernetes Probe Configuration

VecminDB provides three probe endpoints optimized for Kubernetes health management:

### Recommended Configuration

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: vecmindb
    image: vecmindb/vecmindb:latest
    ports:
    - containerPort: 5520
    livenessProbe:
      httpGet:
        path: /healthz/live
        port: 5520
      initialDelaySeconds: 5
      periodSeconds: 10
      timeoutSeconds: 3
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /healthz/ready
        port: 5520
      initialDelaySeconds: 10
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 2
    startupProbe:
      httpGet:
        path: /healthz/startup
        port: 5520
      initialDelaySeconds: 5
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 30
```

### Probe Behavior

| Probe | Endpoint | Checks | Failure Action |
|-------|----------|--------|----------------|
| Startup | `/healthz/startup` | Server initialized, config loaded, storage engine open | Container restart |
| Liveness | `/healthz/live` | Process alive, not deadlocked (zero IO) | Container restart |
| Readiness | `/healthz/ready` | Engine initialized, storage writable, Raft joined (or standalone) | Remove from service |

### Notes

- **Startup probe** has high `failureThreshold` (30) because ONNX model loading can take 15-30 seconds on first boot
- **Readiness** should be used for load balancer routing — node is only "ready" when index is fully loaded and all subsystems are healthy
- **Liveness** is lightweight — only checks process health with zero IO, not storage state
- All probe endpoints are unauthenticated (no `x-api-key` required)

---

*Last updated: 2026-05-15*

---

## Index Type Selection Guide

VecminDB supports 6 index types via the REST API. Choose based on your dataset scale, accuracy requirements, and resource constraints:

| Index Type | Best For | Accuracy | Speed | Memory | Max Scale |
|-----------|----------|----------|-------|--------|-----------|
| `Flat` | <100K vectors, exact results | 100% | Slow at scale | Low | 100K |
| `HNSW` | General purpose, balanced | 95-99% | Fast | High | 10M+ |
| `IVF` | Large datasets, batch queries | 90-98% | Very fast | Medium | 100M+ |
| `PQ` | Memory-constrained, 1B+ vectors | 85-95% | Fast | Very low | 1B+ |
| `LSH` | Binary/hash similarity | 80-90% | Fastest | Low | 1B+ |
| `VPTree` | Low-dimensional, exact KNN | 100% | Medium | Medium | 1M |

### Recommendations

- **Starting out / PoC**: Use `HNSW` (best balance of speed and accuracy)
- **Production, <10M vectors**: `HNSW` with auto-tuned parameters
- **Production, 10M-100M vectors**: `IVF` with tuned `nlist` / `nprobe`
- **Production, >1B vectors**: `PQ` (quantized) or `IVF` + `PQ` hybrid (available internally as `IVFPQ`)
- **Exact results required**: `Flat` (small datasets only)
- **Hash/binary similarity**: `LSH`

### Key Parameters

**HNSW** (default: `hnsw_m=16`, `hnsw_ef_construction=200`, `hnsw_ef_search=50`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hnsw_m` | 16 | Connectivity per node (higher = more memory, better recall) |
| `hnsw_ef_construction` | 200 | Exploration factor during build (higher = slower build, better graph) |
| `hnsw_ef_search` | 50 | Exploration factor during search (higher = slower search, better recall) |

**IVF** (default: `ivf_nlist=100`, `ivf_nprobe=10`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ivf_nlist` | 100 | Number of Voronoi partitions (higher = finer granularity, slower build) |
| `ivf_nprobe` | 10 | Partitions to probe per query (higher = better recall, slower search) |

**PQ** (default: `pq_subvector_count=8`, `pq_subvector_bits=8`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pq_subvector_count` | 8 | Number of sub-vector segments (higher = better accuracy, more memory) |
| `pq_subvector_bits` | 8 | Bits per sub-vector codebook (8 = 256 centroids per segment) |

**LSH** (default: `lsh_hash_count=10`, `lsh_hash_length=32`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lsh_hash_count` | 10 | Number of hash tables (higher = better recall, more memory) |
| `lsh_hash_length` | 32 | Hash key length per table |

### Example: Creating Collections with Different Index Types

**HNSW collection (production, high recall):**

```bash
curl -X POST http://localhost:5520/api/v1/collections \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "production_hnsw",
    "dimension": 128,
    "index_type": "HNSW"
  }'
```

**IVF collection (large-scale, batch queries):**

```bash
curl -X POST http://localhost:5520/api/v1/collections \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "large_ivf",
    "dimension": 256,
    "index_type": "IVF"
  }'
```

> **Note:** Index parameters (`hnsw_m`, `ivf_nlist`, etc.) are configured internally via `IndexConfig` defaults. Advanced parameter tuning is available through the SDK and auto-tuning subsystems. Additional internal index types (`IVFPQ`, `IVFHNSW`, `Annoy`, `NGT`, `GraphIndex`, `TieredHNSW`) are available for specialized use cases via the Rust SDK.

---

## Error Reference

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Request completed successfully |
| 201 | Created | Resource created (collection, vector) |
| 202 | Accepted | Async operation proposed (cluster changes) |
| 307 | Temporary Redirect | Not the Raft leader; follow redirect to leader node |
| 400 | Bad Request | Invalid parameters, malformed JSON, unsupported index type |
| 401 | Unauthorized | Missing or invalid API key / JWT token |
| 409 | Conflict | Duplicate ID, collection already exists |
| 429 | Too Many Requests | Quota exceeded, resource limit, out of memory |
| 500 | Internal Server Error | Unexpected engine failure, storage corruption |
| 503 | Service Unavailable | Server starting up, shutting down, or not ready |

### Error Response Format

Successful responses use the unified `ApiResponse` envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "code": 200,
  "message": null
}
```

Error responses from the REST API follow the same envelope:

```json
{
  "success": false,
  "data": null,
  "error": "Human-readable error description",
  "code": 400,
  "message": null
}
```

When errors are produced by the internal `ResponseError` bridge (e.g., unhandled `Error` enum variants), the format is:

```json
{
  "status": "error",
  "code": 500,
  "message": "Internal error: ...",
  "type": "Internal"
}
```

### Business Error Types

All error variants from VecminDB's internal `Error` enum, mapped to their corresponding HTTP status codes:

#### 400 Bad Request

| Error Variant | Display Message | Description |
|--------------|----------------|-------------|
| `InvalidInput` | Invalid input: {msg} | Malformed request body, missing fields, wrong data types |
| `Validation` | Validation error: {msg} | Business rule validation failure (e.g., dimension mismatch) |
| `Serialization` | Serialization error: {msg} | JSON/binary deserialization failure |
| `InvalidParameter` | Invalid parameter: {msg} | Parameter outside acceptable range |
| `InvalidState` | Invalid state: {msg} | Operation not allowed in current runtime state |

#### 401 Unauthorized

| Error Variant | Display Message | Description |
|--------------|----------------|-------------|
| `Unauthorized` | Unauthorized: {msg} | Missing or invalid API key / JWT |
| `Security` | Security error: {msg} | Sandbox escape, forbidden access, policy violation |

#### 404 Not Found

| Error Variant | Display Message | Description |
|--------------|----------------|-------------|
| `NotFound` | Not found: {msg} | Collection or vector does not exist |

#### 409 Conflict

| Error Variant | Display Message | Description |
|--------------|----------------|-------------|
| `AlreadyExists` | Already exists: {msg} | Duplicate vector ID, collection name taken |

#### 307 Temporary Redirect

| Error Variant | Display Message | Description |
|--------------|----------------|-------------|
| `NotLeader` | This node is not the leader. Current leader is node {id} | Raft consensus redirect to the cluster leader (includes optional leader address) |

#### 429 Too Many Requests

| Error Variant | Display Message | Description |
|--------------|----------------|-------------|
| `QuotaExceeded` | Quota exceeded: {msg} | Rate limit or agent quota surpassed |
| `Resource` | Resource error: {msg} | CPU/memory resource admission control failure |
| `OutOfMemory` | Out of memory error: {msg} | Insufficient memory for operation |

#### 500 Internal Server Error

| Error Variant | Display Message | Description |
|--------------|----------------|-------------|
| `Internal` | Internal error: {msg} | Unexpected engine or runtime failure |
| `Vector` | Vector error: {msg} | Vector dimension mismatch, normalization failure |
| `Index` | Index error: {msg} | Index build failure, search crash, corruption |
| `Storage` | Storage error: {msg} | RocksDB I/O, WAL, or persistence failure |
| `Database` | Database error: {msg} | External database connector failure (MySQL, MongoDB, Neo4j) |
| `Cache` | Cache error: {msg} | Redis backend or internal cache failure |
| `Config` | Configuration error: {msg} | Invalid config file, feature not enabled |
| `Processing` | Processing error: {msg} | Data pipeline or async loader failure |
| `Io` | I/O error: {msg} | File system or network I/O failure |
| `Lock` | Lock error: {msg} | Mutex/RwLock contention or poisoning |
| `Transaction` | Transaction error: {msg} | 2PC coordination failure |
| `Connection` | Connection error: {msg} | Network connection dropped or refused |
| `ExecutionError` | Execution error: {msg} | Automation / workflow or async task failure |
| `NotImplemented` | Not implemented: {msg} | Optional feature not available in this build |
| `Network` | Network error: {msg} | Tonic/reqwest HTTP transport failure |
| `Consensus` | Consensus error: {msg} | Raft voting, replication, or leader election failure |
| `Api` | API error: {msg} | HTTP request parsing or routing failure |
| `Timeout` | Timeout: {msg} | Long-running operation exceeded deadline |
| `Algorithm` | Algorithm error: {msg} | WASM parsing, SIMD, or optimization failure |
| `Compilation` | Compilation error: {msg} | Query plan or index compilation failure |
| `OutOfBounds` | Out of bounds: {msg} | Array/vector index out of valid range |
| `IndexOutOfBounds` | Index out of bounds: {msg} | Specific index range violation |
| `Multimodal` | Multimodal processing error: {msg} | Feature extraction from mixed data types failure |
| `ServiceUnavailable` | Service unavailable: {msg} | Server shutting down or subsystem offline |
| `General` | General error: {msg} | Catch-all fallback for unclassified failures |
| `Runtime` | Runtime error: {msg} | Asynchronous orchestration failure |
| `Other` | {msg} | Unclassified or wrapped external error |

#### Sub-System Error Types (nested)

These error types are embedded from specialized subsystems and carry their own variant hierarchy:

| Error Variant | Source | Description |
|--------------|--------|-------------|
| `Extractor` | `data::feature::types::ExtractorError` | ONNX feature extraction failures (extract, config, invalid input, dimension mismatch, internal, processing) |
| `Transformer` | `data::text_features::error::TransformerError` | Neural text transformer failures (IO, parse, input, vocabulary, encoding, inference, dimension mismatch, initialization, config, serialization, memory, computation, resource, timeout) |

---

## MCP (Model Context Protocol) Integration

VecminDB natively supports MCP, allowing AI Agents to store and retrieve memories using plain text — no vector manipulation required. The server follows the MCP specification (protocol version `2024-11-05`).

### Endpoints

#### `GET /api/v1/mcp/sse` — Establish SSE Stream

Establishes a Server-Sent Events connection for MCP communication.

**Headers:**
- `x-api-key` (required): API authentication key

**Response:** SSE stream with `text/event-stream` content type. Headers include `Cache-Control: no-cache` and `Connection: keep-alive`.

**Events:**
- `endpoint` — Contains the message endpoint URL for this session (e.g. `data: /api/v1/mcp/message?session_id=<uuid>`)

---

#### `POST /api/v1/mcp/message?session_id=<uuid>` — Send MCP Tool Call

Executes an MCP tool via JSON-RPC 2.0 protocol. The `session_id` query parameter is obtained from the SSE `endpoint` event.

**Headers:**
- `Content-Type: application/json`
- `x-api-key` (required): API authentication key

**Request Body (JSON-RPC 2.0):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": { ... }
  }
}
```

**HTTP Response:** `202 Accepted` (empty body). The actual JSON-RPC response is delivered asynchronously via the SSE stream as a `message` event.

---

### JSON-RPC Methods

| Method | Description |
|--------|-------------|
| `initialize` | Handshake; returns server capabilities and protocol version |
| `notifications/initialized` | Client acknowledgment (returns empty result) |
| `tools/list` | Lists available MCP tools and their input schemas |
| `tools/call` | Invokes a tool by name with arguments |

**`initialize` Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "tools": {} },
    "serverInfo": { "name": "vecminDB-MCP-Server", "version": "<pkg_version>" }
  }
}
```

---

### Available Tools

#### `store_memory` — Store Text as Semantic Memory

Stores text content and automatically converts it to a vector using the built-in ONNX model. The resulting vector is persisted in the `default` collection under the specified sovereignty domain.

**Arguments:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | The memory text to store |
| `agent_id` | string | Yes | Agent identity for sovereignty isolation and quota tracking |
| `sovereignty_token` | string | No | Sovereignty domain token (default: `default_mcp_domain`) |
| `model_id` | string | No | Model identity; defaults to the `sovereignty_token` value |
| `metadata` | object | No | Arbitrary JSON metadata attached to the stored vector |
| `timestamp` | integer | No | Optional Unix epoch timestamp for the memory |

**Example:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "store_memory",
    "arguments": {
      "text": "User prefers dark mode and works late at night",
      "agent_id": "assistant-v1",
      "metadata": {"source": "conversation", "confidence": 0.95}
    }
  }
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Memory successfully anchored in sovereign domain 'default_mcp_domain'. Resource ID: <uuid>"
      }
    ]
  }
}
```

---

#### `search_memory` — Semantic Search by Text Query

Searches stored memories by semantic similarity. Query text is automatically converted to a vector. Results are scoped to the specified `agent_id`.

**Arguments:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query text |
| `agent_id` | string | Yes | Agent identity (searches within this agent's memories) |
| `top_k` | integer | No | Number of results (default: 5) |
| `sovereignty_token` | string | No | Sovereignty domain token (default: `default_mcp_domain`) |
| `model_id` | string | No | Model identity filter; defaults to the `sovereignty_token` value |
| `joint_model_ids` | array of string | No | Search across multiple model domains; defaults to `[model_id]` |

**Example:**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "search_memory",
    "arguments": {
      "query": "what are the user's preferences",
      "agent_id": "assistant-v1",
      "top_k": 5
    }
  }
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Retrieved 1 relevant semantic anchors from domain 'default_mcp_domain':\n1. [Score: 0.9230] ID: a1b2c3d4-...\n   Context: {\"source\":\"conversation\",\"confidence\":0.95}\n"
      }
    ]
  }
}
```

---

### MCP Error Responses

When a tool invocation fails, the server returns a JSON-RPC error response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "[ARG_ERROR] Missing mandatory 'text' string"
  }
}
```

| Error Prefix | Meaning |
|-------------|---------|
| `[ARG_ERROR]` | Missing or invalid argument |
| `[AUTH_ERROR]` | Agent identity not provided |
| `[QUOTA_EXCEEDED]` | Resource quota exceeded for this agent |
| `[INTERNAL_ERROR]` | Server-side processing failure (embedding, storage, etc.) |
| `[SOVEREIGNTY_VIOLATION]` | Token does not match the collection's sovereignty authority |
| `[SEARCH_ERROR]` | Search execution failure (shard retrieval, etc.) |
| `[SYSTEM_OFFLINE]` | Vector engine or persistence layer is uninitialized |

| JSON-RPC Error Code | Meaning |
|---------------------|---------|
| `-32601` | Method or tool not found |
| `-32602` | Invalid params (malformed JSON) |
| `-32000` | Tool execution error (see prefix above) |

---

### Session Lifecycle

1. Client establishes SSE connection via `GET /api/v1/mcp/sse`
2. Server sends `endpoint` event containing the session-specific message URL (includes `session_id`)
3. Client sends tool calls via `POST /api/v1/mcp/message?session_id=<id>`
4. Server processes the request and delivers the JSON-RPC response via the SSE stream as a `message` event
5. The HTTP response to the POST is `202 Accepted` (empty body)
6. Connection auto-closes on client disconnect; session resources are cleaned up

---

## Rate Limiting & Resource Quotas

VecminDB uses a multi-layer resource governance system to manage per-agent resource consumption. Every API handler enforces quotas before executing its core logic; when tokens are exhausted, requests receive `429 Too Many Requests`.

### How It Works

VecminDB's quota system operates on two axes:

1. **QPS (Queries Per Second)** — Each agent is rate-limited to a configurable `max_qps` value. The `ResourceManager` tracks per-agent request counts and rejects bursts that exceed the threshold. This is enforced via the `check_agent_admission()` path in the `ResourceCoordinator`'s limiter, which also integrates a **circuit breaker**: sustained quota violations trip the circuit and return `503 Service Unavailable` until the agent's error rate recovers.

2. **CPU & Memory Token Buckets** — Each API call consumes a fixed number of CPU tokens and (for write operations) Memory tokens proportional to the payload size. Token buckets refill continuously. When a bucket is empty, further requests are rejected with `429 Too Many Requests` until tokens refill.

The default per-agent quota (applied when no explicit `AgentQuota` is configured) is:

| Parameter | Default Value |
|:----------|:-------------|
| `max_qps` | 100 |
| `max_memory_bytes` | 512 MB |
| `max_cpu_ratio` | 0.5 (50%) |

These defaults are overridden by the `TierLimits` associated with the active license (see below), and can be further customized per agent via the `ResourceManager.set_agent_quota()` API.

### Operation Costs

| Operation | CPU Tokens | Memory Tokens | Notes |
|:----------|:----------|:-------------|:------|
| Create collection | 1 | — | |
| List collections | 1 | — | |
| Get collection | 1 | — | |
| Get collection stats | 1 | — | |
| Delete collection | 1 | — | |
| Rebuild collection index | 5 | — | Heavy operation |
| Insert vector (collection-scoped) | — | `vector_dim × 4` bytes | Memory only |
| Insert vector (global) | 1 | `vector_dim × 4` bytes | CPU + Memory |
| Batch insert vectors (global) | 1 | `Σ (vector_dim × 4)` bytes | Sum of all vector sizes |
| Batch operations (collection) | 1 | — | |
| Get vector | 1 | — | |
| Delete vector | 1 | — | |
| Batch delete vectors | 1 | — | |
| Search collection | 1 | — | |
| Search vectors (global) | 1 | — | |
| Count vectors | 1 | — | |
| Rebuild index | 5 | — | Heavy operation |
| List indexes | 1 | — | |
| Get index info | 1 | — | |
| Optimize index | 3 | — | Moderate operation |
| Get shadow trajectory | 1 | — | |
| Promote shadow index | 5 | — | Heavy operation |
| Global stats | 1 | — | |
| Index stats | 1 | — | |
| Performance stats | 1 | — | |
| MCP SSE connect | 1 | — | Per-connection |
| MCP message | 1 | — | Per-message |
| Bucket checksum | 1 | — | Debug probe |
| Get feature centroid | 1 | — | LTSM state |

> **Note:** "Heavy operation" (5 tokens) means the call consumes 5× the CPU tokens of a standard read. These should be scheduled during off-peak periods.

> **MCP Tools Note:** MCP tool costs (store_memory, search_memory) include embedded ONNX feature extraction in addition to the listed CPU tokens. Actual memory consumption varies based on text length and vector dimensionality (768-dim default).

### Quota Limits by License Tier

License tier determines the maximum QPS and resource ceilings. These are enforced at the `TierLimits` level.

| Tier | Max QPS | Max Collections | Max Vectors | Max Nodes | Cluster | GPU | Backup |
|:-----|:--------|:---------------|:------------|:----------|:--------|:----|:-------|
| Trial (14-day) | 1,000 | 5 | 1,000,000 | 1 | No | No | No |
| Pro | 50,000 | 50 | 100,000,000 | 3 | Yes | Yes | Yes |
| Team | 200,000 | Unlimited | Unlimited | 5 | Yes | Yes | Yes |
| Enterprise | 500,000 | Unlimited | Unlimited | Unlimited | Yes | Yes | Yes |
| Expired | 0 | 0 | 0 | 0 | No | No | No |

> An **Expired** license rejects all requests immediately (QPS = 0). Renew the license to restore service.

### Rate Limit Response

When a quota is exceeded, the API returns:

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
```

```json
{
  "success": false,
  "data": null,
  "error": "Quota Exceeded: Resource quota exceeded: CPU tokens exhausted",
  "code": 429,
  "message": null
}
```

When the circuit breaker trips due to sustained quota violations, the response is:

```
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
```

```json
{
  "success": false,
  "data": null,
  "error": "Internal Server Error: Circuit breaker open for agent <agent_id>",
  "code": 503,
  "message": null
}
```

### Token Refill & Recovery

- **CPU tokens** refill at a constant rate tied to the agent's QPS limit. Under normal load, a standard-read token (cost 1) recovers within milliseconds.
- **Memory tokens** are not bucket-based in the same way; they represent actual memory allocation. Memory is released when vectors are deleted or collections are dropped.
- **Circuit breaker** transitions from Open → Half-Open → Closed as the agent records successful requests. No manual intervention is required.
- There is **no periodic quota reset window** — the system uses continuous refill rather than fixed-interval resets.

### Monitoring

- The `/metrics` endpoint exposes `vecmindb_quota_remaining` gauges per agent and resource type.
- The `ResourceManager.get_resource_usage()` API returns a `ResourceUsageSummary` with `total_allocated`, `total_available`, `active_tasks`, and latency percentiles.

### Best Practices

- **Implement exponential backoff** on `429` responses. Start with a 1-second delay and double on each retry, up to 30 seconds.
- **Use batch operations** (`/vectors/batch`, `/collections/{name}/batch`) to reduce per-request CPU token overhead — a batch of 100 vectors costs the same 1 CPU token as a single insert.
- **Schedule rebuilds off-peak** — `rebuild_index` and `promote_shadow` each cost 5 CPU tokens.
- **Monitor `/metrics`** for `vecmindb_quota_remaining` to detect quota exhaustion before it impacts users.
- **Upgrade your license tier** if you consistently hit QPS limits. Contact support for Enterprise-tier quota customization.

---

## Index Type Selection Guide

VecminDB supports 6 index types via the REST API. Choose based on your dataset scale, accuracy requirements, and resource constraints:

| Index Type | Best For | Recall | Speed | Memory Usage | Recommended Scale |
|-----------|----------|--------|-------|--------------|-------------------|
| `Flat` | Small datasets, exact results needed | 100% | O(n) linear | Low | <100K vectors |
| `HNSW` | General purpose (recommended default) | 95-99% | O(log n) | High | Up to 10M+ |
| `IVF` | Large datasets with batch queries | 90-98% | Very fast | Medium | 10M-100M+ |
| `PQ` | Memory-constrained, billion-scale | 85-95% | Fast | Very low (16x compression) | 100M-10B+ |
| `LSH` | Binary similarity, hash-based | 80-90% | Fastest | Low | Up to 1B+ |
| `VPTree` | Low-dimensional exact KNN | 100% | Medium | Medium | <1M vectors |

### When to Use What

- **Just getting started / PoC:** `HNSW` — best balance of speed, accuracy, and simplicity
- **Production <10M vectors:** `HNSW` with VecminDB's auto-tuned parameters
- **Production 10M-100M:** `IVF` for better memory efficiency
- **Billion-scale / memory-limited:** `PQ` — trades some accuracy for 16x memory reduction
- **Need exact results, small data:** `Flat` — brute force, guarantees 100% recall

### Creating Collections with Specific Index Types

```bash
# HNSW (recommended for most use cases)
curl -X POST http://localhost:5520/api/v1/collections \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"name": "knowledge_base", "dimension": 768, "index_type": "HNSW"}'

# PQ for billion-scale with low memory
curl -X POST http://localhost:5520/api/v1/collections \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"name": "large_corpus", "dimension": 768, "index_type": "PQ"}'
```

**Note:** VecminDB's auto-tuning engine automatically optimizes index parameters based on your data distribution and query patterns. Manual parameter tuning is not required.

---

## Common Error Scenarios Reference

### Standard Error Response Format

All error responses follow this structure:

```json
{
  "success": false,
  "code": <http_status_code>,
  "message": "Human-readable error description",
  "data": null,
  "error": "<error_type>"
}
```

### HTTP Status Codes

| Code | Status | Common Causes |
|------|--------|---------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid JSON, missing required fields, dimension mismatch |
| 401 | Unauthorized | Missing or invalid `x-api-key` header |
| 402 | Payment Required | License expired — upgrade at vecmindb.com/pricing |
| 404 | Not Found | Collection or vector ID does not exist |
| 409 | Conflict | Collection name or vector ID already exists |
| 429 | Too Many Requests | Resource quota exceeded — retry after backoff |
| 500 | Internal Server Error | Unexpected server failure |
| 503 | Service Unavailable | Server starting up, shutting down, or temporarily overloaded |

### Common Error Scenarios

| Scenario | Code | Message Pattern |
|----------|------|----------------|
| Collection not found | 404 | `Collection '{name}' not found` |
| Duplicate collection | 409 | `Collection '{name}' already exists` |
| Vector not found | 404 | `Vector '{id}' not found` |
| Dimension mismatch | 400 | `Vector dimension {got} does not match collection dimension {expected}` |
| Invalid index type | 400 | `Unsupported index type: '{type}'` |
| Missing API key | 401 | `API key required` |
| Invalid API key | 401 | `Invalid API key` |
| License expired | 402 | `License expired. Please upgrade at https://vecmindb.com/pricing` |
| Quota exceeded | 429 | `Resource quota exceeded: {resource} tokens exhausted` |
| Server overloaded | 503 | `Service temporarily unavailable` |

---

## Navigation

- **[Features](FEATURES.md)** — Complete feature guide with curl examples
- **[5-Minute Quick Start](QUICKSTART_5MIN.md)** — Get started in 5 minutes
- **[Why VecminDB](WHY_VECMINDB.md)** — Architecture and differentiation
- **[Back to README](../README.md)** — Project overview and integration guide
