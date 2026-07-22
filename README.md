# VecminDB SDK

The official SDK for [VecminDB](https://lingxinmind.com) — The Sovereign Memory OS for AI Agents.

> Stop letting your AI Agents hallucinate from memory rot. VecminDB naturally decays outdated memories, distills knowledge via PCA, and provides 100% Air-Gapped cryptographic data sovereignty.

⚠️ **License & Boundary Note**:
*   **SDK (This Repository)**: The client libraries (Python & TypeScript) hosted in this repository are **open-source** under the **MIT License**. We welcome community contributions, integrations, and pull requests!
*   **VecminDB Server (Pre-compiled Binaries & Docker)**: The core database server is **proprietary commercial software** protected by copyright, patent, and trade secret laws, governed by the [VecminDB Proprietary Software License Agreement](https://github.com/lingxinmind/vecminDB/blob/main/LICENSE). The Free Tier supports up to 5 agents and 100K vectors/agent. For enterprise scale-out or clusters, please visit our official website to register and obtain a commercial license: [https://lingxinmind.com](https://lingxinmind.com).

## Deployment & Installation

VecminDB can be run via Docker or as optimized, standalone pre-compiled native binary packages. No local compilers, dependencies, or Python runtimes are needed.

### Method A: Docker Deployment (All Platforms - Windows, macOS, Linux)
The fastest way to spin up VecminDB with automatic in-database bilingual embedding support.

```bash
# For Global / Overseas users:
docker run -d --name vecmindb-trial -p 5520:5520 ghcr.io/lingxinmind/vecmindb:latest

# For Domestic users (China Aliyun Mirror):
# docker run -d --name vecmindb-trial -p 5520:5520 crpi-ngtfnt7d3tsnwk7l.cn-shanghai.personal.cr.aliyuncs.com/vecmindb/vecmindb:latest
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

First, install the target client SDK:

```bash
# Install core client
pip install vecmindb

# Install with LangChain integration
pip install vecmindb[langchain]

# Install with CrewAI integration
pip install vecmindb[crewai]
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
*   **Welford & PCA Memory Distillation**: Fuses decaying memory clusters into stable Abstract Centroids using real-time Welford online variance and DP-Federated PCA. Storage converges and scales logarithmically, locking in long-term TCO budgets.
*   **3-Sigma Sentinel Guard**: Performs real-time anomaly detection and adversarial injection pruning. Evaluates cosine outlier distance with dynamic cutoffs: $\text{Threshold} = \max(\text{Mean}_s - 3 \times \text{Std}_s, 0.7)$.
*   **Sovereign Federation**: Shares collective intelligence across multiple agent domains or VPCs without raw data leak. Fuses PCA Candidate Centroids with differential privacy and a 10% principal bias: $\vec{v}_{\text{centroid}} = \text{Mean}_{\text{global}} + P_0 \times 0.1$.
*   **Raft Consensus & 1024-Bucket Anti-Entropy**: Combines strong consensus replication with self-healing topology. Employs monotonic lock validation (`pub fencing_token: u64`) and an adaptive sync cap: `(resolution * 2).min(1024)`.
*   **100% Air-Gapped Single-Binary**: Built-in BGE-M3 ONNX runtime. No Python, PyTorch, or external embedding API keys needed. Bounded tightly to machine-level HAI hardware fingerprints.

---
**Enterprise Licensing**: For multi-node SOC-2 compliant deployments, please purchase subscriptions or contact us at `contact@lingxinmind.com`.
