"""VecminDB Python SDK – Commercial-Grade Vector Database Client.

Provides both synchronous and asynchronous clients for the VecminDB REST API,
along with an MCP (Model Context Protocol) client for AI agent integration.

Quick start::

    from vecmindb import VecminClient, AsyncVecminClient

    # Synchronous
    with VecminClient("http://localhost:5520", api_key="xxx") as client:
        client.create_collection("docs", dimension=1536)

    # Asynchronous
    async with AsyncVecminClient("http://localhost:5520", api_key="xxx") as client:
        await client.create_collection("docs", dimension=1536)
"""

from .client import VecminClient
from .async_client import AsyncVecminClient
from .mcp import McpClient, SyncMcpClient
from .exceptions import (
    VecminError,
    AuthenticationError,
    PermissionError,
    NotFoundError,
    BadRequestError,
    ConflictError,
    ValidationError,
    RateLimitError,
    ServerError,
    ConnectionError,
    TimeoutError,
)
from .models import (
    VecminResponse,
    CreateCollectionRequest,
    CollectionInfo,
    CollectionStats,
    InsertRequest,
    BatchInsertRequest,
    SearchRequest,
    SearchHit,
    SearchResponse,
    CreateVectorRequest,
    BatchCreateVectorsRequest,
    BatchDeleteVectorsRequest,
    IndexInfo,
    ShadowTrajectoryPoint,
    ClusterLoginRequest,
    ClusterLoginResponse,
    ClusterJoinRequest,
    ClusterPromoteRequest,
    ClusterNodeInfo,
    ClusterStatus,
    SnapshotInfo,
    SnapshotRequest,
    HealthStatus,
    SubsystemStatus,
    GlobalStats,
    McpToolCall,
    McpStoreMemoryParams,
    McpSearchMemoryParams,
    McpInitializeParams,
)
from .auth import AuthManager
from .retry import RetryConfig
from .memory_plugin import VecminDBMemoryPlugin

__version__ = "1.0.0"

__all__ = [
    # Clients
    "VecminClient",
    "AsyncVecminClient",
    "McpClient",
    "SyncMcpClient",
    # Exceptions
    "VecminError",
    "AuthenticationError",
    "PermissionError",
    "NotFoundError",
    "BadRequestError",
    "ConflictError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    "ConnectionError",
    "TimeoutError",
    # Models
    "VecminResponse",
    "CreateCollectionRequest",
    "CollectionInfo",
    "CollectionStats",
    "InsertRequest",
    "BatchInsertRequest",
    "SearchRequest",
    "SearchHit",
    "SearchResponse",
    "CreateVectorRequest",
    "BatchCreateVectorsRequest",
    "BatchDeleteVectorsRequest",
    "IndexInfo",
    "ShadowTrajectoryPoint",
    "ClusterLoginRequest",
    "ClusterLoginResponse",
    "ClusterJoinRequest",
    "ClusterPromoteRequest",
    "ClusterNodeInfo",
    "ClusterStatus",
    "SnapshotInfo",
    "SnapshotRequest",
    "HealthStatus",
    "SubsystemStatus",
    "GlobalStats",
    "McpToolCall",
    "McpStoreMemoryParams",
    "McpSearchMemoryParams",
    "McpInitializeParams",
    # Auth & Retry
    "AuthManager",
    "RetryConfig",
    # Memory Plugin
    "VecminDBMemoryPlugin",
]
