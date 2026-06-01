# Azure 远程部署指南

> 本指南说明如何将本项目部署到 Azure 云平台。
> 需要：Azure 订阅（免费试用即可）、GitHub 账号

---

## Step 1：Fork & Push 到 GitHub

当前项目的 remote 指向上游仓库，你需要先 fork 到自己的账号下。

### 1a. Fork（在 GitHub 网页操作）

1. 打开 https://github.com/JoshuaC215/agent-service-toolkit
2. 点击右上角 **Fork** 按钮
3. 选择你的账号，创建一个 fork

### 1b. 添加你的 remote 并 push

在本地项目目录执行（替换 `<你的GitHub用户名>`）：

```bash
git remote add myfork https://github.com/<你的GitHub用户名>/agent-service-toolkit.git
git push myfork main
```

---

## Step 2：Azure 环境准备

### 2a. 安装 Azure CLI

Windows 上推荐用 winget：

```powershell
winget install Microsoft.AzureCLI
```

### 2b. 登录

```bash
az login
```

浏览器会弹出 Azure 登录页面。

### 2c. 创建资源组

```bash
az group create \
  --name agent-service-rg \
  --location japaneast
```

选择 `japaneast`（东京）离日本用户最近。

---

## Step 3：构建并推送 Docker 镜像到 ACR

### 3a. 创建 Azure Container Registry

```bash
az acr create \
  --resource-group agent-service-rg \
  --name agentserviceregistry \
  --sku Basic \
  --admin-enabled true
```

### 3b. 登录 ACR

```bash
az acr login --name agentserviceregistry
```

### 3c. 构建并推送镜像

```bash
# 构建 agent_service 镜像
docker build -f docker/Dockerfile.service -t agentserviceregistry.azurecr.io/agent-service:latest .
docker push agentserviceregistry.azurecr.io/agent-service:latest

# 构建 streamlit_app 镜像
docker build -f docker/Dockerfile.app -t agentserviceregistry.azurecr.io/streamlit-app:latest .
docker push agentserviceregistry.azurecr.io/streamlit-app:latest
```

---

## Step 4：创建 Azure Database for PostgreSQL

```bash
az postgres flexible-server create \
  --resource-group agent-service-rg \
  --name agent-service-db \
  --location japaneast \
  --admin-user postgres \
  --admin-password <设置一个强密码> \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16 \
  --storage-size 32
```

记下连接字符串，后续配置环境变量用。

---

## Step 5：部署 Container Apps

### 5a. 创建 Container Apps 环境

```bash
az containerapp env create \
  --name agent-service-env \
  --resource-group agent-service-rg \
  --location japaneast
```

### 5b. 部署 FastAPI Agent Service

```bash
az containerapp create \
  --name agent-service-api \
  --resource-group agent-service-rg \
  --environment agent-service-env \
  --image agentserviceregistry.azurecr.io/agent-service:latest \
  --target-port 8080 \
  --ingress external \
  --registry-server agentserviceregistry.azurecr.io \
  --registry-username <ACR用户名> \
  --registry-password <ACR密码> \
  --env-vars \
    DATABASE_TYPE=postgres \
    POSTGRES_HOST=agent-service-db.postgres.database.azure.com \
    POSTGRES_PORT=5432 \
    POSTGRES_DB=agent_service \
    POSTGRES_USER=postgres \
    AZURE_OPENAI_API_KEY=<你的Azure OpenAI Key> \
    AZURE_OPENAI_ENDPOINT=<你的Azure OpenAI Endpoint> \
    AZURE_OPENAI_DEPLOYMENT_MAP='{"gpt-4o":"<deployment-name>","gpt-4o-mini":"<deployment-name>"}' \
    DEFAULT_MODEL=azure-gpt-4o-mini
```

### 5c. 部署 Streamlit Frontend

首先获取 agent-service 的 URL：

```bash
az containerapp show \
  --name agent-service-api \
  --resource-group agent-service-rg \
  --query properties.configuration.ingress.fqdn
```

返回的 URL 格式为 `agent-service-api.xxx.japaneast.azurecontainerapps.io`，配置到 Streamlit 的环境变量中：

```bash
az containerapp create \
  --name agent-service-ui \
  --resource-group agent-service-rg \
  --environment agent-service-env \
  --image agentserviceregistry.azurecr.io/streamlit-app:latest \
  --target-port 8501 \
  --ingress external \
  --registry-server agentserviceregistry.azurecr.io \
  --registry-username <ACR用户名> \
  --registry-password <ACR密码> \
  --env-vars \
    AGENT_URL=https://agent-service-api.xxx.japaneast.azurecontainerapps.io
```

---

## Step 6：验证部署

```bash
# 检查 API 健康状态
curl https://agent-service-api.xxx.japaneast.azurecontainerapps.io/health

# 访问 Streamlit 前端
# 浏览器打开：https://agent-service-ui.xxx.japaneast.azurecontainerapps.io
```

---

## Step 7（可选）：配置 GitHub Actions CI/CD

创建 `.github/workflows/azure-deploy.yaml`：

```yaml
name: Deploy to Azure

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Login to ACR
        run: az acr login --name agentserviceregistry

      - name: Build & Push agent_service
        run: |
          docker build -f docker/Dockerfile.service -t agentserviceregistry.azurecr.io/agent-service:latest .
          docker push agentserviceregistry.azurecr.io/agent-service:latest

      - name: Build & Push streamlit_app
        run: |
          docker build -f docker/Dockerfile.app -t agentserviceregistry.azurecr.io/streamlit-app:latest .
          docker push agentserviceregistry.azurecr.io/streamlit-app:latest

      - name: Restart Container Apps
        run: |
          az containerapp revision copy --name agent-service-api --resource-group agent-service-rg
          az containerapp revision copy --name agent-service-ui --resource-group agent-service-rg
```

需要在 GitHub repo 的 Settings → Secrets 中添加 `AZURE_CREDENTIALS`（用 `az ad sp create-for-rbac` 生成）。

---

## 成本估算（Azure 免费试用）

| 资源 | 规格 | 预估月费 |
|---|---|---|
| Container Apps | 0.5 CPU, 1GiB RAM × 2 | ~$15-30 |
| PostgreSQL Flexible Server | Standard_B1ms | ~$15 |
| Container Registry | Basic | ~$5 |
| **合计** | | **~$35-50/月** |

Azure 免费试用有 $200 额度，足够运行 4-6 个月。

---

## 注意事项

1. Azure OpenAI 需要在 Azure Portal 预先创建资源并部署模型（gpt-4o、gpt-4o-mini）
2. ChromaDB 的持久化存储建议挂载 Azure Files 或使用 Azure AI Search 替代
3. 生产环境务必设置 `AUTH_SECRET` 启用认证
4. 建议启用 HTTPS 和自定义域名
