"""VecminDB SDK Pydantic Data Models.

Defines request / response schemas for every API endpoint.  All models
inherit from ``pydantic.BaseModel`` so they are validated at construction
time and serialise trivially to / from JSON.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ===========================================================================
# Generic envelope
# ===========================================================================


class VecminResponse(BaseModel):
    """Standard response envelope returned by every VecminDB endpoint.

    Attributes:
        code: Numeric status code (mirrors HTTP status or internal code).
        message: Human-readable status description.
        data: Optional payload – structure depends on the endpoint.
    """

    code: int = 200
    message: str = "Success"
    data: Optional[Any] = None


# ===========================================================================
# Collection models
# ===========================================================================


class CreateCollectionRequest(BaseModel):
    """Payload for ``POST /api/v1/collections``.

    Attributes:
        name: Unique collection identifier.
        dimension: Vector dimensionality.
        metric_type: Distance metric (Cosine, L2, InnerProduct).
        index_type: Index algorithm (HNSW, IVF, Flat).
        index_params: Algorithm-specific parameters.
        domain: Cognitive factuality domain (general, finance, etc.).
    """

    name: str
    dimension: int = 1536
    metric_type: str = "Cosine"
    index_type: str = "HNSW"
    index_params: Optional[Dict[str, Any]] = None
    domain: Optional[str] = "general"


class CollectionInfo(BaseModel):
    """Metadata returned for a single collection.

    Attributes:
        name: Collection identifier.
        dimension: Vector dimensionality.
        metric_type: Distance metric in use.
        index_type: Index algorithm in use.
        vector_count: Number of vectors stored.
        size_bytes: Approximate on-disk size.
        created_at: ISO-8601 creation timestamp.
        domain: Cognitive domain of the collection.
    """

    name: str
    dimension: int = 1536
    metric_type: str = "Cosine"
    index_type: str = "HNSW"
    vector_count: int = 0
    size_bytes: int = 0
    created_at: str = ""
    domain: Optional[str] = "general"


class CollectionStats(BaseModel):
    """Statistical summary for a collection.

    Attributes:
        name: Collection identifier.
        vector_count: Number of stored vectors.
        index_size_bytes: Size of the index on disk.
        memory_usage_bytes: Approximate memory footprint.
        fragmentation_ratio: Index fragmentation metric (0.0 – 1.0).
    """

    name: str
    vector_count: int = 0
    index_size_bytes: int = 0
    memory_usage_bytes: int = 0
    fragmentation_ratio: float = 0.0


# ===========================================================================
# Vector models
# ===========================================================================


class InsertRequest(BaseModel):
    """Payload for inserting a single vector into a collection.

    Attributes:
        id: Optional client-assigned vector identifier.
        values: The embedding vector.
        metadata: Arbitrary key-value metadata.
    """

    id: Optional[str] = None
    values: List[float]
    metadata: Optional[Dict[str, Any]] = None


class BatchInsertRequest(BaseModel):
    """Payload for ``POST /api/v1/collections/{name}/batch``.

    Attributes:
        vectors: List of vectors to insert.
    """

    vectors: List[InsertRequest]


class SearchRequest(BaseModel):
    """Payload for vector similarity search.

    Attributes:
        query: The query embedding vector.
        k: Number of nearest neighbours to return.
        ef_search: HNSW search-width parameter.
        metric: Override the default distance metric.
        filter: Optional metadata filter expression.
    """

    query: List[float]
    k: int = 10
    ef_search: int = 50
    metric: Optional[str] = None
    filter: Optional[Dict[str, Any]] = None


class SearchHit(BaseModel):
    """A single result from a vector similarity search.

    Attributes:
        id: Vector identifier.
        score: Similarity score (higher is more similar for Cosine/IP).
        metadata: Stored metadata associated with the vector.
        values: The vector itself (included when ``include_vectors=True``).
    """

    id: str = ""
    score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    values: Optional[List[float]] = None


class SearchResponse(BaseModel):
    """Response from a vector similarity search.

    Attributes:
        results: Ordered list of search hits.
        total: Total number of matching results (before top-k truncation).
    """

    results: List[SearchHit] = Field(default_factory=list)
    total: int = 0


# ===========================================================================
# Global vector models
# ===========================================================================


class CreateVectorRequest(BaseModel):
    """Payload for ``POST /api/v1/vectors`` (global namespace).

    Attributes:
        id: Optional client-assigned identifier.
        values: The embedding vector.
        metadata: Arbitrary key-value metadata.
        collection: Target collection name.
    """

    id: Optional[str] = None
    values: List[float]
    metadata: Optional[Dict[str, Any]] = None
    collection: Optional[str] = None


class BatchCreateVectorsRequest(BaseModel):
    """Payload for ``POST /api/v1/vectors/batch``.

    Attributes:
        vectors: List of vectors to create.
    """

    vectors: List[CreateVectorRequest]


class BatchDeleteVectorsRequest(BaseModel):
    """Payload for ``POST /api/v1/vectors/batch/delete``.

    Attributes:
        ids: List of vector identifiers to delete.
    """

    ids: List[str]


# ===========================================================================
# Index models
# ===========================================================================


class IndexInfo(BaseModel):
    """Information about an index for a collection.

    Attributes:
        collection_name: The collection this index belongs to.
        index_type: Algorithm used (HNSW, IVF, Flat).
        status: Current index status (ready, building, degraded).
        vector_count: Number of indexed vectors.
        params: Index construction parameters.
    """

    collection_name: str
    index_type: str = "HNSW"
    status: str = "ready"
    vector_count: int = 0
    params: Optional[Dict[str, Any]] = None


class ShadowTrajectoryPoint(BaseModel):
    """A point on the shadow-index Nash trajectory.

    Attributes:
        epoch: Training epoch.
        nsg_score: NSGA-II score.
        recall: Estimated recall.
        latency_us: Average query latency in microseconds.
    """

    epoch: int = 0
    nsg_score: float = 0.0
    recall: float = 0.0
    latency_us: float = 0.0


# ===========================================================================
# Cluster models
# ===========================================================================


class ClusterLoginRequest(BaseModel):
    """Payload for ``POST /api/v1/cluster/login``.

    Attributes:
        password: Admin password for JWT issuance.
    """

    password: str


class ClusterLoginResponse(BaseModel):
    """Response from a successful cluster login.

    Attributes:
        token: JWT bearer token.
        expires_in: Token validity duration in seconds.
    """

    token: str
    expires_in: int = 3600


class ClusterJoinRequest(BaseModel):
    """Payload for ``POST /api/v1/cluster/join``.

    Attributes:
        node_id: Unique identifier for the joining node.
        addr: Network address of the joining node.
    """

    node_id: str
    addr: str


class ClusterPromoteRequest(BaseModel):
    """Payload for ``POST /api/v1/cluster/promote``.

    Attributes:
        node_id: Identifier of the node to promote to leader.
    """

    node_id: str


class ClusterNodeInfo(BaseModel):
    """Information about a cluster node.

    Attributes:
        node_id: Unique node identifier.
        addr: Network address.
        role: Node role (Leader, Follower, Candidate).
        state: Raft state.
        is_leader: Whether this node is the current leader.
    """

    node_id: str = ""
    addr: str = ""
    role: str = "Follower"
    state: str = ""
    is_leader: bool = False


class ClusterStatus(BaseModel):
    """Overall cluster status.

    Attributes:
        leader_id: Current leader node identifier.
        term: Current Raft term.
        nodes: List of cluster member information.
        is_healthy: Whether the cluster is in a healthy state.
    """

    leader_id: str = ""
    term: int = 0
    nodes: List[ClusterNodeInfo] = Field(default_factory=list)
    is_healthy: bool = True


class SnapshotRequest(BaseModel):
    """Payload for creating a cluster snapshot.

    Attributes:
        snapshot_id: Optional client-assigned snapshot identifier.
    """

    snapshot_id: Optional[str] = None


class SnapshotInfo(BaseModel):
    """Information about a cluster snapshot.

    Attributes:
        snapshot_id: Snapshot identifier.
        size_bytes: Snapshot file size.
        created_at: ISO-8601 creation timestamp.
    """

    snapshot_id: str = ""
    size_bytes: int = 0
    created_at: str = ""


# ===========================================================================
# Health / Status models
# ===========================================================================


class HealthStatus(BaseModel):
    """Health check response.

    Attributes:
        status: 'healthy' or 'degraded'.
        engine: 'online' or 'offline'.
        version: Server version string.
        timestamp: ISO-8601 timestamp.
    """

    status: str = "healthy"
    engine: str = "online"
    version: str = ""
    timestamp: str = ""


class SubsystemStatus(BaseModel):
    """Detailed subsystem status.

    Attributes:
        overall_status: 'operational' or 'degraded'.
        subsystems: Nested subsystem health details.
        timestamp: ISO-8601 timestamp.
    """

    overall_status: str = "operational"
    subsystems: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


# ===========================================================================
# Stats models
# ===========================================================================


class GlobalStats(BaseModel):
    """Global database statistics.

    Attributes:
        total_collections: Number of collections.
        total_vectors: Total vectors across all collections.
        total_index_size_bytes: Aggregate index size.
    """

    total_collections: int = 0
    total_vectors: int = 0
    total_index_size_bytes: int = 0


# ===========================================================================
# MCP models
# ===========================================================================


class McpToolCall(BaseModel):
    """A JSON-RPC ``tools/call`` request for MCP.

    Attributes:
        method: JSON-RPC method name.
        params: Method parameters.
        id: Request identifier.
    """

    method: str = "tools/call"
    params: Dict[str, Any] = Field(default_factory=dict)
    id: Union[int, str] = 1


class McpStoreMemoryParams(BaseModel):
    """Parameters for the MCP ``store_memory`` tool.

    Attributes:
        agent_id: Agent or session identifier.
        content: Text content to store.
        source: Origin of the memory.
    """

    agent_id: str
    content: str
    source: str = "sdk"


class McpSearchMemoryParams(BaseModel):
    """Parameters for the MCP ``search_memory`` tool.

    Attributes:
        agent_id: Agent or session identifier.
        query: Natural-language search query.
        top_k: Number of results to return.
    """

    agent_id: str
    query: str
    top_k: int = 5


class McpInitializeParams(BaseModel):
    """Parameters for the MCP ``initialize`` method.

    Attributes:
        client_info: Client identification.
        protocol_version: MCP protocol version.
    """

    client_info: Dict[str, str] = Field(default_factory=lambda: {"name": "vecmindb-python-sdk", "version": "0.1.0"})
    protocol_version: str = "2024-11-05"
