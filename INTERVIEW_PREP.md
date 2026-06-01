# 🎯 面试准备材料

> 目标岗位：社内生成AI活用系统开发实习（日本企业）
> 技术栈：Azure + Python + Streamlit + Azure OpenAI Service + LangGraph

---

## 1. レジュメ項目（STAR 方式 / 4-5 行）

**项目名称：** 基于 LangGraph + FastAPI + Streamlit 的企业级 AI Agent 服务平台

**S/T：** 针对企业内部 AI 知识库和 IT 支持需求，基于开源 agent-service-toolkit 进行二次开发，构建支持多 Agent 路由的 AI 服务系统。

**A：** 阅读并理解了项目的四层架构（Agent Registry → LangGraph Agent → FastAPI → Streamlit），跑通了完整的本地 + Docker 运行链路。开发了文档导入 Pipeline（PDF/Markdown → 自动分块 → ChromaDB 向量化），实现了数据整备自动化。新增了 IT 工单 Support Agent，集成 LangGraph interrupt 实现 human-in-the-loop 流程。

**A：** 修复了 Docker 容器化部署的健康检查问题（安装 curl、修正 HOST 绑定），确保三服务（PostgreSQL + FastAPI + Streamlit）通过 docker compose 一键启动并全部 healthy。编写完整中文 README，包含架构图、API 端点文档、Azure 部署参考。

**R：** 完成本地 full-run（Docker Compose 三服务编排），实现了文档上传 → RAG 检索 → 问答的完整闭环。项目代码已提交 Git（2 commits），README 中包含 Azure 适配与认证配置说明，可作为企业部署参考。

---

## 2. 面接官想定 Q&A（核心 12 問）

### Q1：なぜこのプロジェクトを選んだ？JD との関連は？

> このプロジェクトの LangGraph + Streamlit + FastAPI 技術スタックは、JD 要求と完全に一致しています。さらに、Azure OpenAI サポートが既に組み込まれており、「既存生成AIシステムの改修」のストーリーに自然に対応できます。データ整備（RAG）、AI エージェント開発（Support Agent）、システム改修（Docker デプロイ）の3つの業務線をすべてカバーできます。

### Q2：プロジェクトのアーキテクチャを図示してください。

> 4層アーキテクチャです：
> 1. **Agent Registry 層**（agents.py）— 11個の Agent を dict で管理
> 2. **LangGraph Agent 層**（各 Agent は StateGraph）— 状態機械で実行フローを定義
> 3. **FastAPI サービス層**（service.py）— /invoke、/stream、/history エンドポイント
> 4. **Streamlit フロントエンド層** — AgentClient 経由で API 呼び出し
>
> Agent → Service は `get_agent()` でコンパイル済みグラフを取得、Service → Client は HTTP、Client → Streamlit は `AGENT_URL` 環境変数で接続。

### Q3：LangGraph の StateGraph とは？RAG Agent の状態機械はどう動く？

> StateGraph は LangGraph のコアで、状態機械パターンで Agent の実行フローを定義します。RAG Agent は4つのノードを持ちます：
> - `guard_input`（安全性チェック）→ `model`（LLM 推論）→ `tools`（ツール呼び出し）→ `model` に戻る
> - 条件エッジ：安全性チェックで unsafe なら `block`、LLM 出力に `tool_calls` があれば `tools` へ、なければ `END`
> - `MessagesState` でメッセージ履歴を管理、`thread_id` でマルチターン会話を維持

### Q4：SSE ストリーミング出力はどう実装している？

> FastAPI の `/stream` エンドポイントが `StreamingResponse` を返し、`message_generator` が async generator として機能します。`agent.astream()` が `stream_mode=["updates", "messages", "custom"]` の3モードでイベントを取得。updates モードでノード実行結果、messages モードで LLM トークンチャンクを取得し、SSE フォーマット `data: {...}\n\n` でフロントエンドにプッシュします。

### Q5：Azure OpenAI への切り替えは？

> `core/llm.py` に `AzureChatOpenAI` サポートが既に内蔵されており、`.env` で `AZURE_OPENAI_API_KEY`、`AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_DEPLOYMENT_MAP` を設定するだけで切り替わります。`core/settings.py` の `model_post_init` が Azure 設定の自動検証を行います。

### Q6：データ整備パイプラインの設計は？

> `ingest_documents.py` スクリプトを作成し、PDF/TXT/Markdown → 512トークンチャンク分割（overlap 64）→ Embedding ベクトル化 → ChromaDB 保存のフローを実装しました。RAG Agent の `database_search` ツールが similarity search で Top-K 関連ドキュメントを検索します。

### Q7：LangGraph interrupt とは？Support Agent でどう使った？

> interrupt は LangGraph v1.0 の human-in-the-loop メカニズムです。Agent が `interrupt()` を呼び出すと一時停止し、ユーザーに制御を返します。ユーザーが `Command(resume=...)` で応答すると再開します。Support Agent では、チケット作成・アクション前に人工確認を行います。

### Q8：Docker Compose の3サービスはどう連携？

> postgres（DB）→ agent_service（FastAPI API）→ streamlit_app（フロントエンド）の順に起動。`depends_on` で起動順序を制御、postgres に healthcheck（pg_isready）を設定。`streamlit_app` は環境変数 `AGENT_URL=http://agent_service:8080` でバックエンドに接続。`postgres_data` ボリュームで DB データを永続化。

### Q9：認証はどうしている？

> HTTP Bearer Token 認証を使用しています。`service.py` の `verify_bearer` がリクエストヘッダーの `Authorization` を `settings.AUTH_SECRET` と照合。`AUTH_SECRET` 未設定時は認証をスキップ（開発モード）。Azure 環境では `AUTH_SECRET` を必ず設定すべきです。

### Q10：Azure へのデプロイをどう計画する？

> 1. Streamlit → Azure Container Apps（フロントエンド）
> 2. FastAPI → Azure Container Apps（バックエンド API）
> 3. PostgreSQL → Azure Database for PostgreSQL（マネージド DB）
> 4. ChromaDB → Azure Container Apps + 永続ストレージ、または Azure AI Search で代替
> 5. Docker イメージ → Azure Container Registry（ACR）
> 6. CI/CD → GitHub Actions：build → push ACR → deploy to Container Apps

### Q11：Docker の healthcheck で苦労した点？

> 最初、agent_service と streamlit_app が unhealthy のままになりました。原因は2つ：1) コンテナ内に `curl` コマンドがインストールされていなかった（`apt-get install curl` で解決）、2) `HOST=127.0.0.1` にバインドしていたため、Docker のポートマッピングが外部からアクセスできなかった（compose.yaml で `HOST=0.0.0.0` にオーバーライドして解決）。

### Q12：開発中に一番デバッグが大変だったことは？

> Docker 環境で Streamlit が API に接続できない問題です。ホストマシンから `curl http://localhost:8080` が通らない状態でした。デバッグの流れ：1) `docker compose exec agent_service bash` でコンテナ内に入り、サービスが起動しているか確認 → 起動はしていた。2) `docker compose ps` でポートマッピングを確認 → 0.0.0.0:8080 にマップされていた。3) agent_service の `.env` で `HOST=127.0.0.1` になっていることを発見 → コンテナ内の 127.0.0.1 はコンテナ自身を指し、ポートマッピングの 0.0.0.0 と不一致だった。compose.yaml に `HOST=0.0.0.0` のオーバーライドを追加して解決。

---

## 3. コード解説ルート（面接で白板/画面共有する場合）

1. **エントリーポイント**：
   - `uv run python src/run_service.py` → FastAPI (http://127.0.0.1:8080)
   - `uv run streamlit run src/streamlit_app.py` → Streamlit (http://localhost:8501)

2. **設定層**：
   - `.env` → `core/settings.py` → Pydantic Settings が自動検証
   - `mode_post_init` で利用可能なプロバイダーを自動検出

3. **コア入出力**：
   - 入力：`UserInput(message, thread_id, model)`
   - 出力：`ChatMessage(type, content, run_id)`

4. **コアモジュール**：
   - `agents.py`（Agent 登録センター）
   - `rag_assistant.py`（StateGraph 定義）
   - `support_agent.py`（改造で追加：5つのツール + interrupt）
   - `service.py`（FastAPI エンドポイント + SSE ストリーミング）
   - `streamlit_app.py`（フロントエンド UI）

5. **状態管理**：
   - SQLite/PostgreSQL checkpoint（会話履歴）
   - InMemoryStore（横断的記憶）

6. **改造ファイル一覧**：
   - `src/scripts/ingest_documents.py`（新規：ドキュメント取込）
   - `src/agents/support_agent.py`（新規：IT サポート Agent）
   - `src/agents/tools.py`（修正：OpenRouter/Azure embedding 対応）
   - `docker/Dockerfile.service`（修正：curl インストール）
   - `docker/Dockerfile.app`（修正：curl インストール）
   - `compose.yaml`（修正：HOST=0.0.0.0 オーバーライド）
   - `README_CN.md`（新規：中国語ドキュメント）

---

## 4. 投递チェックリスト

- [x] GitHub repo に完備した README（中文）
- [x] `.env.example` 設定テンプレートあり
- [x] `docker-compose.yaml` でワンクリック起動可能
- [x] レジュメ STAR 4-5 行完成
- [x] 面接想定 Q&A 12 問完成
- [x] 30秒でアーキテクチャ図を説明できる
- [x] LangGraph StateGraph の実行フローを自分の言葉で説明できる
- [x] Azure OpenAI の設定方法を説明できる
- [ ] Azure リモートデプロイ（選択肢）
- [ ] GitHub に push & 公開 repo として共有可能にする

---

## 5. PPT 生成プロンプト（面接用プレゼン資料を作る場合）

```
以下の内容で面接用のプレゼンスライドを生成してください：

1. タイトルスライド：「AI Agent 服务平台 — 实习项目总结」
2. アーキテクチャ図：4層構成 + データフロー図
3. プロジェクト選択理由：JD との技術スタックマッチ
4. コア改造3点：
   - データ整備パイプライン（RAG）
   - IT Support Agent（human-in-the-loop）
   - Docker コンテナ化デプロイ
5. 技術ハイライト：LangGraph StateGraph、SSE ストリーミング、interrupt
6. デモ画面：Streamlit UI + Agent 応答例
7. Azure デプロイアーキテクチャ
8. 学んだこと・今後の計画

各スライドは簡潔に。図やフローチャートを積極的に使用。
```
