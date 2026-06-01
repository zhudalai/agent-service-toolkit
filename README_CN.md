# 🧰 AI Agent 服务平台 — 企业级 IT 支持系统

> 基于 [agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit) 二次开发
> 技术栈：**Python + LangGraph + FastAPI + Streamlit + ChromaDB + Docker**

本项目针对企业内部 AI 知识库和 IT 支持需求，基于开源 agent-service-toolkit 进行二次开发，构建了支持多 Agent 路由的 AI 服务系统，实现了"文档自动导入 → 向量化 → RAG 检索"的完整数据整备 Pipeline，以及支持 human-in-the-loop 的 IT 工单处理 Agent。

---

## 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│  Streamlit App (前端)                                         │
│  src/streamlit_app.py                                        │
│  多 Tab 界面：聊天 / 文档管理 / Agent 切换                    │
├──────────────────────────────────────────────────────────────┤
│  FastAPI Service (后端 API)                                   │
│  src/service/service.py                                      │
│  POST /{agent_id}/invoke    (同步调用)                        │
│  POST /{agent_id}/stream    (SSE 流式响应)                    │
│  POST /feedback             (反馈收集)                        │
│  POST /history              (对话历史)                        │
├──────────────────────────────────────────────────────────────┤
│  Agent Registry (智能体注册中心)                               │
│  src/agents/agents.py                                        │
│  research-assistant / rag-assistant / support-agent / ...     │
├──────────────────────────────────────────────────────────────┤
│  Core (LLM 抽象 + 配置管理)                                   │
│  src/core/llm.py   — 支持 11 家 LLM 提供商                    │
│  src/core/settings.py — Pydantic Settings 自动验证            
│  内置 Azure OpenAI / OpenRouter 支持                          │
├──────────────────────────────────────────────────────────────┤
│  Data Layer                                                   │
│  ChromaDB (向量数据库)  — 文档检索                             │
│  SQLite / PostgreSQL  — 对话检查点 (checkpointer)             │
└──────────────────────────────────────────────────────────────┘
```

### 请求流

```
用户输入 → Streamlit (streamlit_app.py)
         → AgentClient (HTTP)
         → FastAPI POST /support-agent/stream
         → _handle_input() → agent.astream()
         → LangGraph StateGraph 执行:
             guard_input (安全检查)
             → handle_request (LLM 推理 + 工具调用)
             → execute_action (query_ticket / search_faq / create_ticket 等)
             → 低置信度时 interrupt (human-in-the-loop)
             → generate_final (生成回复)
         → SSE 流式返回 → Streamlit 实时显示
```

---

## 核心改造点

### 1. 数据整备 Pipeline（生成AI用データ整備）

**对应业务需求**：将企业开发文档转换为 AI Agent 可自动读取的格式

- 新增 `src/scripts/ingest_documents.py`
- 支持 PDF / TXT / Markdown 文档导入
- 自动分块（chunk_size=512, overlap=64）→ Embedding 向量化 → 存入 ChromaDB
- RAG Agent 通过 `database_search` 工具检索 Top-5 相关文档片段

```bash
# 导入文档
uv run python src/scripts/ingest_documents.py --input-dir ./data/documents --reset

# 导入单个文件
uv run python src/scripts/ingest_documents.py --file ./data/documents/handbook.pdf
```

### 2. IT 工单 Support Agent（AIエージェント開発）

**对应业务需求**：开发提升客户开发流程效率的 AI Agent

- 新增 `src/agents/support_agent.py`
- 工具集：`query_ticket` / `search_faq` / `list_tickets` / `create_ticket` / `assign_ticket`
- 集成 LangGraph interrupt 实现 human-in-the-loop：创建/分配工单前请求人工确认
- 安全检查层（safeguard）防止敏感信息泄露
- 自动根据问题描述匹配专业团队（网络/硬件/权限/通用）

### 3. 多 LLM 提供商支持 / Azure OpenAI 适配

- 已支持 OpenRouter / Azure OpenAI / OpenAI 等多种 LLM 提供商
- Embedding 层根据配置自动选择（OpenAIEmbeddings / AzureOpenAIEmbeddings）
- 仅需修改 `.env` 配置即可切换，无需改动代码

---

## 快速启动

### 前置条件

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Docker（可选，用于容器化部署）
- 至少一个 LLM 提供商的 API Key

### Step 1: Clone & 安装依赖

```bash
git clone https://github.com/JoshuaC215/agent-service-toolkit.git
cd agent-service-toolkit
uv sync --frozen
```

### Step 2: 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key（至少一个）
```

最小配置示例（使用 OpenRouter）：

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
MODE=dev
DATABASE_TYPE=sqlite
```

### Step 3: 启动服务

**方式 A：本地启动（推荐开发用）**

```bash
# 终端 1：启动 FastAPI 服务
uv run python src/run_service.py

# 终端 2：启动 Streamlit 前端
uv run streamlit run src/streamlit_app.py
```

访问 http://localhost:8501

**方式 B：Docker Compose（一键启动）**

```bash
docker compose up --build -d
```

访问 http://localhost:8501（Streamlit）和 http://localhost:8080/redoc（API 文档）

### Step 4: 导入文档（可选）

```bash
uv run python src/scripts/ingest_documents.py --input-dir ./data/documents --reset
```

---

## Agent 列表

| Agent ID | 说明 | 核心能力 |
|---|---|---|
| `research-assistant` | 研究助手（默认） | Web 搜索 + 计算器 |
| `rag-assistant` | RAG 助手 | 基于向量库的文档检索问答 |
| `support-agent` | IT 支持助手 | 工单查询/创建/分配 + FAQ 搜索 + human-in-the-loop |
| `chatbot` | 简单聊天 | 基础对话 |
| `interrupt-agent` | 中断演示 | LangGraph interrupt 示例 |
| `command-agent` | 命令代理 | 流程控制演示 |
| `langgraph-supervisor-agent` | Supervisor | 多 Agent 协调 |

通过 Streamlit 界面或 API URL 切换 Agent：`POST /{agent_id}/stream`

---

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/info` | 获取可用 Agent 和模型列表 |
| GET | `/health` | 健康检查 |
| POST | `/{agent_id}/invoke` | 同步调用 Agent |
| POST | `/{agent_id}/stream` | SSE 流式调用 Agent |
| POST | `/feedback` | 提交反馈（LangSmith） |
| POST | `/history` | 获取对话历史 |

---

## Azure 部署参考

> 以下内容为企业 Azure 环境部署的配置说明。

### Azure OpenAI 配置

在 `.env` 中配置：

```env
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_DEPLOYMENT_MAP={"gpt-4o": "your-gpt4o-deployment", "gpt-4o-mini": "your-gpt4o-mini-deployment"}
DEFAULT_MODEL=azure-gpt-4o-mini
```

`core/settings.py` 会自动检测 Azure 配置并验证 deployment map 完整性。

### 推荐部署方案

| 组件 | Azure 服务 | 说明 |
|---|---|---|
| FastAPI (Agent Service) | Azure Container Apps | 后端 API，通过 ingress 暴露 |
| Streamlit (Frontend) | Azure App Service 或 Container Apps | 前端 Web 应用 |
| PostgreSQL (对话历史) | Azure Database for PostgreSQL | 托管数据库 |
| ChromaDB (向量库) | Azure Container Apps + 持久化存储 | 或使用 Azure AI Search 替代 |
| Docker 镜像 | Azure Container Registry (ACR) | 镜像仓库 |
| CI/CD | GitHub Actions | 自动构建 → push ACR → deploy |

### 认证

设置 `AUTH_SECRET` 可启用 HTTP Bearer Token 认证：

```env
AUTH_SECRET=your-secret-token
```

Streamlit 端需在请求头中携带 `Authorization: Bearer your-secret-token`。

---

## 数据流说明

### 文档整备流程

```
PDF/TXT/MD 文档
  → load_documents() 加载
  → RecursiveCharacterTextSplitter 分块 (512 tokens, overlap 64)
  → OpenAI/Azure Embedding 向量化
  → ChromaDB 持久化存储 (./chroma_db)
  → RAG Agent 通过 similarity search 检索
```

### IT 工单处理流程

```
用户问题
  → safeguard 安全检查
  → handle_request (LLM 意图识别 + 工具调用)
  → execute_action:
      ├── query_ticket / search_faq / list_tickets → 直接执行
      └── create_ticket / assign_ticket → interrupt 人工确认 → 继续
  → generate_final (生成最终回复)
```

---

## 技术要点（面试参考）

### LangGraph StateGraph

每个 Agent 都是一个 StateGraph，定义了节点（处理逻辑）和边（流转条件）。以 support-agent 为例：

```
guard_input → [safety check] → handle_request → [tool_calls?] → execute_action → generate_final → END
                  ↓ unsafe                                    ↓ no tools
              block_unsafe → END                         END
```

### SSE 流式输出

FastAPI 的 `/stream` 端点返回 `StreamingResponse`，`message_generator` 是一个 async generator。`agent.astream()` 通过 `stream_mode=["updates", "messages", "custom"]` 三种模式获取事件，然后用 SSE 格式 `data: {...}\n\n` 推送到前端。

### Human-in-the-Loop (interrupt)

LangGraph v1.0 的 `interrupt()` 机制允许 Agent 执行到某个节点时暂停，把控制权交还给用户。用户回复后通过 `Command(resume=...)` 恢复执行。在 support-agent 中用于创建/分配工单前的人工确认。

### 多 LLM 提供商抽象

`core/llm.py` 通过策略模式统一管理 11 家 LLM 提供商，`@cache` 装饰器避免重复初始化。`core/settings.py` 的 `model_post_init` 自动检测可用 Provider 并设置默认模型。

---

## License

MIT License — 基于 [JoshuaC215/agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit)
