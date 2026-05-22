# VecminDB SDK

The official SDK for [VecminDB](https://github.com/vecmindb) — The Sovereign Memory OS for AI Agents.

> Stop letting your AI Agents hallucinate from memory rot. VecminDB naturally decays outdated memories, distills knowledge via PCA, and provides 100% Air-Gapped cryptographic data sovereignty.

## Installation

```bash
# Install core client
pip install vecmindb

# Install with LangChain integration
pip install vecmindb[langchain]

# Install with CrewAI integration
pip install vecmindb[crewai]
```

## Quickstart

Start the local VecminDB engine:
```bash
docker run -d --name vecmindb-trial -p 5520:5520 vecmindb/vecmindb:latest
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

*   **100% Offline**: Built-in ONNX embedding model. Your data never leaves your VPC.
*   **Biological Forgetting (LTSM)**: Old, unused memories naturally decay over time to prevent context pollution.
*   **Knowledge Distillation**: Fuses semantic clusters into dense abstract centroids automatically.
*   **Sovereignty Isolation**: Agents are cryptographically isolated using HMAC-SHA256 signature chains.

---
**Enterprise Licensing**: For multi-node SOC-2 compliant deployments, contact `sulingqi@hotmail.com`.
