# VecminDB — AI Agent 的自演化记忆引擎 (Memory OS)

> **这不是一个向量数据库。这是一个管理 Agent 记忆生命周期的底层操作系统。**

---

## 🎯 重新定义品类：我们到底替代了什么？

当你在构建长生命周期的 AI Agent 时，你一定会遇到”记忆管理”的问题。市场上现有的解决方案分为四个层级，VecminDB 处于它们之上的第五层：

| 层级 | 现有方案 | 存在的问题 | VecminDB 的降维打击 |
| :--- | :--- | :--- | :--- |
| **DIY 拼凑层** | pgvector + LangChain Memory + 自己写的摘要脚本 | 代码臃肿，极易出错，维护成本极高。 | **直接替代这一整层**。开箱即用，自带蒸馏与生命周期。 |
| **Agent 记忆框架** | Mem0、Letta (MemGPT)、Zep | SaaS 模式，数据离境，网络延迟高。 | **同层竞争**。但我们是**引擎层本地二进制**，数据绝对不出域。 |
| **向量数据库** | Pinecone、Qdrant、Milvus | 只负责静态存取，不管理”遗忘”和”生命周期”。 | 不是直接竞品，而是**被我们降级为底层依赖（或直接替代）**。 |
| **开发者的惰性** | “我把所有东西都塞进上下文窗口” | Agent 很快变蠢，LLM Token 账单爆炸。 | 让开发者意识到：**记忆需要管理，而不是无脑堆叠**。 |
| **第五层：记忆引擎** | **VecminDB** | — | 唯一一个管理 Agent 记忆**完整生命周期**的品类——存储、衰减、蒸馏、遗忘、联邦、审计。 |

---

## 💥 开发者痛点 (获客：为什么你今天就要下载试用)

开发者第一周最痛的不是“Token 账单”，而是 **"Agent 变蠢了"** 以及 **"我不想自己手写一整套记忆生命周期管理代码"**。

1. **痛点 1：Agent 回答质量随时间下降（记忆腐化）**
   * *现状*：几个月后，Agent 搜索出 10 条互相冲突的陈旧日记，开始严重幻觉。
   * *VecminDB*：内置 **LTSM 生物学遗忘曲线**，陈旧且低价值的记忆自动衰减。
2. **痛点 2：我得自己搭记忆管理系统**
   * *现状*：开发者必须自己写 Cron 定时任务，调用 LLM 去总结历史向量。
   * *VecminDB*：引擎级 **PCA 质心蒸馏**，无需外部 LLM 介入，底层自动压缩相似记忆。
3. **痛点 3：Agent 重复写同样的东西，导致索引膨胀**
   * *现状*：Agent 每次都记录“用户喜欢暗黑模式”，存了 100 遍。
   * *VecminDB*：存储层的 **InsertionLatch 去重锁**，语义极其相似的写入会被底层拦截融合。
4. **痛点 4：我需要配 Python/PyTorch/ONNX 才能做 Embedding**
   * *现状*：本地跑个向量环境，光配环境就要折腾半天。
   * *VecminDB*：**单文件闭源二进制 Docker**，内部直接静态编译集成了 ~15MB 的轻量 ONNX 提取模型，**零环境依赖**。
5. **痛点 5：新 Agent 从零开始，知识无法共享**
   * *现状*：部署了新客服，它完全不知道老客服积累的客户偏好。
   * *VecminDB*：通过 **Alliance Centroid 联邦机制**，Agent 之间可以共享提取后的“高维知识质心”，而不泄露底层原始对话（隐私保护）。
6. **痛点 6：完全是黑盒，不知道记忆系统是否健康**
   * *现状*：向量库里乱七八糟，无从下手排查。
   * *VecminDB*：内置 **Prometheus 指标 + 极客感 Glassmorphism 拓扑大盘**，肉眼可见记忆的聚类和衰减。

---

## 🏢 企业决策痛点 (变现：为什么企业愿意掏 5 万元/年)

当开发者把 VecminDB 跑起来并推荐给技术总监时，企业会为以下能力痛快买单：

7. **痛点 7：数据绝对不能出境（信创/隐私合规）**
   * *VecminDB*：完全 **100% 离线物理隔离部署（Air-gapped）**，不仅支持 x86，还原生支持信创架构，满足最严苛的跨国/政务/医疗隔离要求。
8. **痛点 8：跨部门数据泄漏风险**
   * *VecminDB*：抛弃脆弱的应用层 Namespace，在底层内核强绑定 **Sovereignty Token 主权隔离**，客服 Agent 物理上绝对无法读取财务 Agent 的数据。
9. **痛点 9：按存储量计费是无底洞**
   * *VecminDB*：传统的 SaaS 向量库（如 Pinecone）Agent 越多费用越高；VecminDB 的自动衰减剪枝机制让存储空间在长期运行中**始终收敛**。
10. **痛点 10：无法审计 Agent 的决策依据**
    * *VecminDB*：基于 **HMAC-SHA256 的 WAL 审计链**。每一条记忆的写入和篡改防线，都能在审计日志中精准溯源，轻松应对 SOC-2 合规审计。
11. **痛点 11：参数调优需要高薪 DBA，没人会**
    * *VecminDB*：内置 **NSGA-II 自动调优引擎**与 **Shadow Index 零停机热替换**。索引自己在后台进化，业务 0 感知。
12. **痛点 12：外部 Embedding 模型升级，历史向量全部作废**
    * *现状*：OpenAI `text-embedding-3-small` 从 v1 升到 v2，5000 万条向量语义不兼容——要么全部重新编码，要么接受召回质量坍塌。
    * *VecminDB*：**原始文本与向量同步落盘**。向量是派生结果——当内置或外部模型升级时，原始文本可被新一代模型重新编码。**10 年数据主权：即使这一代模型被淘汰，你的数据永远具备重新解释权。**

---

## 🏃 3分钟跑 Demo 亲眼验证价值 (Aha! Moments)

无需任何繁琐配置，直接在本地见证：

### 1. 一键本地部署 (Docker)
```bash
docker pull vecmindb/vecmindb:latest
docker run -d --name vecmindb-trial -p 5520:5520 vecmindb/vecmindb:latest
```

### 2. 30 秒看到第一个价值（无需任何 SDK）
```bash
# 存一条记忆（纯文本，不要向量——VecminDB 内置模型自动处理）
curl -X POST http://localhost:5520/api/v1/mcp/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"store_memory","arguments":{"text":"Customer #4521 always disputes charges over $50; requires manager approval for refunds","agent_id":"billing"}}}'

# 语义搜索——不是关键词匹配。"who disputes charges" 找到 "always disputes charges over $50"
curl -X POST http://localhost:5520/api/v1/mcp/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_memory","arguments":{"query":"who disputes charges","agent_id":"billing"}}}'

# 检查 Agent 配额
curl http://localhost:5520/agents/billing/quota

# 查看 Prometheus 指标
curl http://localhost:5520/metrics | grep "vecmindb_"
```

### 3. 跑完整 LTSM 生命周期 Demo
```bash
VECMIN_URL=http://localhost:5520 bash examples/demo_ltsm_lifecycle.sh
```

### 4. 实时联动见证
*   终端输出 `Sovereignty isolation enforced... PASS`，验证 **跨租户强隔离（痛点 8）**。
*   终端输出 `LTSM Centroid Query... PASS`，验证 **记忆自动蒸馏与降维（痛点 2）**。
*   浏览器打开 **`http://localhost:5520/dashboard`**，**Avg Latency 稳定在 0.5ms 以内**，实时渲染流量波峰——验证**本地引擎级性能**。
