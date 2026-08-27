# VecminDB SDK

The self-hosted memory layer for your AI coding agents. Give Cursor, Claude Code, and friends a shared, long-term memory that runs entirely on your machine — no external embedding API, no data leaving your network.

`pip install vecmindb` · `npm install vecmindb` · Docker one-liner

Free tier: 5 agents / 100K vectors. · [lingxinmind.com](https://lingxinmind.com)

⚠️ **License & Boundary Note**:
*   **SDK (This Repository)**: The client libraries (Python & TypeScript) hosted in this repository are **open-source** under the **MIT License**. We welcome community contributions, integrations, and pull requests!
*   **VecminDB Server (Pre-compiled Binaries & Docker)**: The core database server is **proprietary commercial software** protected by copyright, patent, and trade secret laws, governed by the [VecminDB Proprietary Software License Agreement](https://github.com/lingxinmind/vecminDB/blob/main/LICENSE). The Free Tier supports up to 5 agents and 100K vectors/agent. For enterprise scale-out or clusters, please visit our official website to register and obtain a commercial license: [https://lingxinmind.com](https://lingxinmind.com).

## Deployment & Installation

VecminDB can be run via Docker or as optimized, standalone pre-compiled native binary packages. No local compilers, dependencies, or Python runtimes are needed.

### Method A: Docker Deployment (All Platforms - Windows, macOS, Linux)
The fastest way to spin up VecminDB with automatic in-database bilingual embedding support and zero-downtime rolling update capabilities.

#### Option 1: One-Line Docker Compose (Recommended for Production & Hot Updates)
```bash
# 1. Download production docker-compose.yml in one command
curl -sSL https://raw.githubusercontent.com/lingxinmind/vecmindb-sdk/main/docker-compose.yml -o docker-compose.yml

# 2. Spin up production container
docker compose up -d

# 3. Daily Online Hot Upgrade:
# docker compose pull && docker compose up -d
```

#### Option 2: Standalone Docker Run
```bash
# For Global / Overseas users:
docker run -d --name vecmindb-trial -p 5520:5520 -v vecmindb_data:/home/vecminDB/data ghcr.io/lingxinmind/vecmindb:latest

# For Domestic users (China Aliyun Mirror):
# docker run -d --name vecmindb-trial -p 5520:5520 -v vecmindb_data:/home/vecminDB/data crpi-ngtfnt7d3tsnwk7l.cn-shanghai.personal.cr.aliyuncs.com/vecmindb/vecmindb:latest
```

---

### Method B: Pre-Compiled Native Binary Bundles (Zero-Docker / Zero-Python)
Ideal for high-performance, air-gapped on-premise or private cloud servers. Download the appropriate package from our official website [Downloads](https://lingxinmind.com) portal:

*   **Windows (AMD64)**:
    Download `vecmindb-1.0.1-x86_64-pc-windows-msvc.zip`. Extract the ZIP archive, open Command Prompt or PowerShell in the directory, and run:
    ```cmd
    .\vecmindb-server.exe
    ```
*   **macOS (Apple Silicon M1/M2/M3)**:
    Download `vecmindb-1.0.1-aarch64-apple-darwin.tar.gz`. Open Terminal, extract and run:
    ```bash
    tar -xzf vecmindb-1.0.1-aarch64-apple-darwin.tar.gz
    cd vecmindb-1.0.1-aarch64-apple-darwin
    ./vecmindb-server
    ```
*   **Linux (AMD64)**:
    Download `vecmindb-offline-linux-amd64.tar.gz`. Extract and run:
    ```bash
    tar -xzf vecmindb-offline-linux-amd64.tar.gz
    cd vecmindb-offline-linux-amd64
    ./vecmindb-server
    ```

---

## SDK Quickstart

### Python SDK

```bash
# Install core client
pip install vecmindb

# Install with LangChain integration
pip install vecmindb[langchain]

# Install with CrewAI integration
pip install vecmindb[crewai]
```

### Java SDK (Maven)

```xml
<dependency>
    <groupId>com.vecmindb</groupId>
    <artifactId>vecmindb-java-sdk</artifactId>
    <version>1.0.2</version>
</dependency>
```

### TypeScript SDK (npm)

```bash
npm install vecmindb
```

### Text in, Text out (server-side embedding)

The server embeds raw text with the built-in BGE-M3 model — SDK users do
not need to run an embedding model client-side.

**Python**

```python
from vecmindb import VecminClient

client = VecminClient(base_url="http://localhost:5520", api_key="YOUR_VECMIN_API_KEY")

# Store a memory as raw text; the server embeds it and returns the vector ID
memory_id = client.add_text(
    "Customer requirement: data must stay on the intranet; prefer private deployment.",
    metadata={"priority": "high", "topic": "deployment"},
)

# Search by raw text
hits = client.search_text("default", text="data must stay on the intranet", top_k=5)
for hit in hits:
    print(hit.id, hit.score, hit.metadata)
```

`add_text` / `search_text` are also available on `AsyncVecminClient`.
Advanced users can still pass raw vectors via `create_vector` / `search`.

Full memory lifecycle is exposed via MCP-backed helpers on the client
(`mcp_get_memory` / `mcp_list_memories` / `mcp_forget`) and on mounted
memory spaces (`get_memory` / `list_memories` / `forget`).

**TypeScript**

```ts
import { VecminClient } from "vecmindb";

const client = new VecminClient({
  baseUrl: "http://localhost:5520",
  apiKey: "YOUR_VECMIN_API_KEY",
});

const memoryId = await client.insertText("default", {
  text: "Customer requirement: data must stay on the intranet; prefer private deployment.",
  metadata: { priority: "high" },
});

const hits = await client.searchText("default", {
  text: "data must stay on the intranet",
});
```

### Using with LangChain

```python
from vecmindb.memory_plugin import VecminDBMemoryPlugin
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain

# Initialize Sovereign Agent Memory
memory = VecminDBMemoryPlugin.for_langchain(agent_id="support_agent_01", base_url="http://localhost:5520")

llm = ChatOpenAI(temperature=0)
conversation = ConversationChain(llm=llm, memory=memory)

conversation.predict(input="Hi, I need help with my billing.")
```

### Using with CrewAI

```python
from vecmindb.memory_plugin import VecminDBMemoryPlugin
from crewai import Agent, Crew

# Initialize Sovereign Agent Memory
memory_storage = VecminDBMemoryPlugin.for_crewai(agent_id="finance_agent_01", base_url="http://localhost:5520")

agent = Agent(
    role='Financial Analyst',
    goal='Analyze billing data',
    backstory='An expert in financial data.',
    memory=True,
    memory_config={"storage": memory_storage} # Inject VecminDB memory
)
```

## Why VecminDB?

Unlike generic vector databases that act as static drives, VecminDB acts as a cognitive memory operating system with native lifecycle management and cryptographic isolation:

*   **Biological Forgetting (LTSM)**: Episodic memories decay dynamically following $W(t) = \exp(-\lambda \times \Delta t)$ with automatic 90-day semantic pruning (`let semantic_prune_threshold_secs = 90 * 86400;` on disk). Frequently accessed memories persist; transient noise is permanently retired.
*   **Welford & K-Means Centroid Distillation**: Fuses decaying memory clusters into stable Abstract Centroids using real-time Welford online variance and K-Means clustering. Storage converges and scales logarithmically, locking in long-term TCO budgets.
*   **3-Sigma Sentinel Guard**: Performs real-time anomaly detection and adversarial injection pruning. Evaluates cosine outlier distance with dynamic cutoffs: $\text{Threshold} = \max(\text{Mean}_s - 3 \times \text{Std}_s, 0.7)$.
*   **Sovereign Federation**: Shares collective intelligence across multiple agent domains or VPCs without raw data leak. Fuses PCA Candidate Centroids with differential privacy and a 10% principal bias: $\vec{v}_{\text{centroid}} = \text{Mean}_{\text{global}} + P_0 \times 0.1$.
*   **Raft Consensus & 1024-Bucket Anti-Entropy**: Combines strong consensus replication with self-healing topology. Employs monotonic lock validation (`pub fencing_token: u64`) and an adaptive sync cap: `(resolution * 2).min(1024)`.
*   **100% Air-Gapped Single-Binary**: Built-in BGE-M3 ONNX runtime. No Python, PyTorch, or external embedding API keys needed. Bounded tightly to machine-level HAI hardware fingerprints.

---
**Enterprise Licensing**: For multi-node SOC-2 compliant deployments, please purchase subscriptions or contact us at `contact@lingxinmind.com`.
