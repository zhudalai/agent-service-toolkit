# 🧰 AI Agent Service Platform

> **English** | [中文](#中文) | [日本語](#日本語)
>
> Based on [agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit) | Tech Stack: **Python + LangGraph + FastAPI + Streamlit + ChromaDB + Docker**

---

## English

An enterprise-grade AI agent service platform built on top of `agent-service-toolkit`. Designed for internal corporate use, it features a complete **document ingestion → vectorization → RAG retrieval** pipeline and an **IT support ticket agent** with human-in-the-loop capabilities.

### What's Added

| Feature | Description |
|---|---|
| **Document Ingestion Pipeline** | `src/scripts/ingest_documents.py` — PDF/TXT/Markdown → chunking (512 tokens, overlap 64) → embedding → ChromaDB |
| **IT Support Agent** | `src/agents/support_agent.py` — 5 tools (query/create/assign tickets, FAQ search, list tickets) + LangGraph interrupt for human confirmation |
| **Multi-LLM Embedding** | Embedding layer auto-detects OpenRouter / Azure OpenAI / OpenAI based on `.env` config |
| **Docker Healthcheck Fix** | Added `curl` to Dockerfiles, fixed `HOST` binding for container networking |

### Quick Start

```bash
git clone https://github.com/zhudalai/agent-service-toolkit.git
cd agent-service-toolkit
uv sync --frozen

# Configure .env (at least one LLM API key required)
cp .env.example .env

# Option A: Local
uv run python src/run_service.py          # Terminal 1
uv run streamlit run src/streamlit_app.py # Terminal 2

# Option B: Docker Compose
docker compose up --build -d

# Ingest sample documents
uv run python src/scripts/ingest_documents.py --input-dir ./data/documents --reset
```

Visit http://localhost:8501

### Architecture

```
Streamlit (Frontend)
  → AgentClient (HTTP)
  → FastAPI (/stream, /invoke, /history)
  → LangGraph StateGraph Agent
      ├── guard_input (safety check)
      ├── handle_request (LLM + tool calls)
      ├── execute_action (tools / interrupt)
      └── generate_final (response)
  → SSE streaming → real-time token display
```

### Agents

| Agent | Description |
|---|---|
| `research-assistant` | Web search + calculator |
| `rag-assistant` | RAG-based document Q&A |
| `support-agent` | IT ticket management + FAQ + human-in-the-loop |
| `chatbot` | Basic chat |
| `interrupt-agent` | LangGraph interrupt demo |

### API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/info` | List agents and models |
| GET | `/health` | Health check |
| POST | `/{agent_id}/invoke` | Synchronous agent call |
| POST | `/{agent_id}/stream` | SSE streaming agent call |
| POST | `/feedback` | Submit feedback |
| POST | `/history` | Get chat history |

### Azure Deployment

See [AZURE_DEPLOY.md](./AZURE_DEPLOY.md) for full deployment guide.

Key config for Azure OpenAI:

```env
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_MAP={"gpt-4o":"deployment-name","gpt-4o-mini":"deployment-name"}
DEFAULT_MODEL=azure-gpt-4o-mini
```

---

## 中文

基于 `agent-service-toolkit` 二次开发的企业级 AI Agent 服务平台。针对企业内部 AI 知识库和 IT 支持需求，实现了**文档自动导入 → 向量化 → RAG 检索**的完整数据整备 Pipeline，以及支持 human-in-the-loop 的 IT 工单处理 Agent。

### 核心改造

| 功能 | 说明 |
|---|---|
| **数据整备 Pipeline** | `src/scripts/ingest_documents.py` — PDF/TXT/Markdown → 分块 → Embedding → ChromaDB |
| **IT Support Agent** | `src/agents/support_agent.py` — 5个工具 + LangGraph interrupt 人工确认 |
| **多 LLM Embedding** | 根据 `.env` 自动检测 OpenRouter / Azure OpenAI / OpenAI |
| **Docker 健康检查修复** | 安装 curl、修正 HOST 绑定 |

### 快速启动

```bash
git clone https://github.com/zhudalai/agent-service-toolkit.git
cd agent-service-toolkit
uv sync --frozen

cp .env.example .env
# 编辑 .env，填入至少一个 LLM API Key

# 方式 A：本地启动
uv run python src/run_service.py
uv run streamlit run src/streamlit_app.py

# 方式 B：Docker Compose
docker compose up --build -d

# 导入文档
uv run python src/scripts/ingest_documents.py --input-dir ./data/documents --reset
```

访问 http://localhost:8501

### 架构

```
Streamlit（前端）
  → AgentClient（HTTP）
  → FastAPI（/stream、/invoke、/history）
  → LangGraph StateGraph Agent
      ├── guard_input（安全检查）
      ├── handle_request（LLM 推理 + 工具调用）
      ├── execute_action（工具执行 / interrupt）
      └── generate_final（生成回复）
  → SSE 流式返回 → 实时显示
```

### Agent 列表

| Agent | 说明 |
|---|---|
| `research-assistant` | Web 搜索 + 计算器 |
| `rag-assistant` | 基于向量库的文档检索问答 |
| `support-agent` | IT 工单管理 + FAQ + human-in-the-loop |
| `chatbot` | 基础对话 |
| `interrupt-agent` | LangGraph interrupt 演示 |

### API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/info` | 获取 Agent 和模型列表 |
| GET | `/health` | 健康检查 |
| POST | `/{agent_id}/invoke` | 同步调用 |
| POST | `/{agent_id}/stream` | SSE 流式调用 |
| POST | `/feedback` | 提交反馈 |
| POST | `/history` | 获取对话历史 |

### Azure 部署

详见 [AZURE_DEPLOY.md](./AZURE_DEPLOY.md)。

Azure OpenAI 配置：

```env
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_MAP={"gpt-4o":"deployment-name","gpt-4o-mini":"deployment-name"}
DEFAULT_MODEL=azure-gpt-4o-mini
```

---

## 日本語

`agent-service-toolkit` をベースに二次開発した、エンタープライズ向け AI Agent サービスプラットフォームです。社内 AI ナレッジベースと IT サポートのニーズに対応し、**ドキュメント自動取り込み → ベクトル化 → RAG 検索**の完全なデータ整備パイプラインと、human-in-the-loop 対応の IT チケット処理 Agent を実装しています。

### 主な改造ポイント

| 機能 | 説明 |
|---|---|
| **データ整備パイプライン** | `src/scripts/ingest_documents.py` — PDF/TXT/Markdown → チャンク分割 → Embedding → ChromaDB |
| **IT サポート Agent** | `src/agents/support_agent.py` — 5ツール + LangGraph interrupt による人工確認 |
| **マルチ LLM Embedding** | `.env` 設定に基づき OpenRouter / Azure OpenAI / OpenAI を自動切替 |
| **Docker ヘルスチェック修正** | curl インストール、HOST バインド修正 |

### クイックスタート

```bash
git clone https://github.com/zhudalai/agent-service-toolkit.git
cd agent-service-toolkit
uv sync --frozen

cp .env.example .env
# .env を編集し、少なくとも1つの LLM API Key を設定

# 方法 A：ローカル起動
uv run python src/run_service.py
uv run streamlit run src/streamlit_app.py

# 方法 B：Docker Compose
docker compose up --build -d

# ドキュメント取り込み
uv run python src/scripts/ingest_documents.py --input-dir ./data/documents --reset
```

http://localhost:8501 にアクセス

### アーキテクチャ

```
Streamlit（フロントエンド）
  → AgentClient（HTTP）
  → FastAPI（/stream、/invoke、/history）
  → LangGraph StateGraph Agent
      ├── guard_input（セキュリティチェック）
      ├── handle_request（LLM 推論 + ツール呼び出し）
      ├── execute_action（ツール実行 / interrupt）
      └── generate_final（応答生成）
  → SSE ストリーミング → リアルタイム表示
```

### Agent 一覧

| Agent | 説明 |
|---|---|
| `research-assistant` | Web 検索 + 計算機 |
| `rag-assistant` | ベクトルベースのドキュメント Q&A |
| `support-agent` | IT チケット管理 + FAQ + human-in-the-loop |
| `chatbot` | 基本チャット |
| `interrupt-agent` | LangGraph interrupt デモ |

### API エンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/info` | Agent とモデル一覧取得 |
| GET | `/health` | ヘルスチェック |
| POST | `/{agent_id}/invoke` | 同期呼び出し |
| POST | `/{agent_id}/stream` | SSE ストリーミング呼び出し |
| POST | `/feedback` | フィードバック送信 |
| POST | `/history` | 会話履歴取得 |

### Azure デプロイ

詳細は [AZURE_DEPLOY.md](./AZURE_DEPLOY.md) を参照。

Azure OpenAI 設定例：

```env
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_MAP={"gpt-4o":"deployment-name","gpt-4o-mini":"deployment-name"}
DEFAULT_MODEL=azure-gpt-4o-mini
```

---

## License

MIT License — Based on [JoshuaC215/agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit)
