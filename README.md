# 合同智能审查系统（Contract Review System）

基于 **RAG + 多模态解析 + 大模型对话** 的一体化合同智能审查平台。上传合同（PDF / Word / 扫描件），系统自动解析结构、结合知识库检索证据、生成结构化风险审查报告，并支持围绕报告的多轮流式追问。管理端可维护 RAG 知识库与风险类别体系。

> 对应产品需求文档：`prd-contract-review.html`（PRD v1.1）

## 功能特性

| 模块 | 说明 |
|---|---|
| 合同上传与多模态解析 | 支持 PDF（pdfplumber）/ Word（python-docx）/ 图片扫描件（**多模态大模型识别**，PNG/JPG），输出结构化章节与字符级定位 |
| RAG 知识库 | 管理员上传审查指引/模板/判例/法规（PDF/DOCX/TXT），自动条款级切块 → 向量化 → 入库（ChromaDB），报告风险项附带可溯源依据 |
| 智能审查报告 | 9 个审查维度独立检索 → LLM 结构化输出（总体风险按高风险条数规则判定 + 风险项：等级/原文片段/问题/修改建议/正面发现） |
| 风险项处置 | 单条风险项可标记「已确认 / 待修改 / 已忽略」，状态随报告保存 |
| 报告定稿 | 定稿后锁定风险项、禁止重审；可取消定稿，导出报告带定稿信息 |
| 报告导出 | 一键导出 Word（.docx），含风险统计、明细、正向发现与免责声明 |
| 审查模板 | 审查维度不再写死：管理员可建「采购合同」「劳动合同」等模板，发起审查时选用 |
| 版本比对 | 同一合同可上传新版本；自动做段落级差异 + 上一版风险项的「已修复/已改写/仍存在」闭环判定 |
| 任务中心 | 进行中 / 失败 / 待审查 / 解析失败四类任务总览，支持批量发起审查与自动刷新 |
| 对话追问 | 围绕审查报告的 WebSocket 流式多轮对话，30 秒超时保护，回答附带可展开的知识库引用卡片 |
| 管理后台 | 知识文档上传/替换（旧版本入历史）/删除（同步清理向量库）、版本历史、风险类别增删、操作审计日志、LLM 用量统计 |
| 模型配置 | 管理员在页面上切换模型提供商、填 API Key/模型名/Base URL，**保存即时生效**；支持一键连通性测试（真实发起最小请求，返回耗时与错误详情） |
| 安全与限额 | 上传文件魔数校验（防改扩展名）、按用户限流（审查 10 次/分、追问 30 次/分）、并发审查去重、启动时清理中断任务 |
| 异步审查 | 发起后立即返回 `running`，后台执行，报告页自动轮询刷新，可离开页面；支持进程内后台任务 / Celery 两种模式 |
| 中文检测 | 自动识别非中文合同并阻断（MVP 明确仅支持中文） |
| 法律智能问答 | 独立于合同审查的日常法律咨询页面：多会话管理、常见问题快捷入口、WebSocket 流式回答 |

## 界面预览

| 批量上传与解析异常提示 | 解析结果预览确认 |
|:---:|:---:|
| ![批量上传与解析异常提示](docs/screenshots/batch-upload-and-errors.png) | ![解析结果预览确认](docs/screenshots/parse-preview.png) |
| **审查报告（风险就地批注）** | **法律智能问答** |
| ![审查报告](docs/screenshots/review-report.png) | ![法律智能问答](docs/screenshots/legal-assistant.png) |

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3（JavaScript）· Vite · Element Plus · Pinia · Vue Router 4 · Axios |
| 后端 | FastAPI · SQLAlchemy 2.0（async）· Pydantic v2 · JWT 认证 |
| RAG | ChromaDB（embedded，本地持久化）· SiliconFlow bge-m3 Embedding（1024 维） |
| 大模型 | SiliconFlow / 豆包 / 通义 / OpenAI（OpenAI 兼容协议，`.env` 一键切换） |
| 多模态 | 视觉大模型（VISION_MODEL），OpenAI 兼容 vision 协议，用于图片合同逐字转录 |
| 异步任务 | 进程内 BackgroundTask（默认）/ Celery + Redis（可选，Docker profile: celery） |
| 数据库 | MySQL 8.x（utf8mb4） |
| 部署 | Docker Compose（含 ChromaDB standalone 生产形态）或本地直跑 |

## 项目结构

```
contract-review-system/
├── docker-compose.yml          # 完整编排（mysql/redis/chromadb/backend/worker/frontend）
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI 入口（lifespan 建表 + seed 默认数据）
│   │   ├── config.py           # pydantic-settings 配置（.env 驱动）
│   │   ├── core/               # database / security(JWT+RBAC) / dependencies / exceptions
│   │   ├── models/             # 7 张表 ORM：users/contracts/reviews/risk_items/
│   │   │                       #   conversations/messages/risk_categories/knowledge_docs
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── routers/            # auth / contracts / reviews / chat(含WebSocket) / admin
│   │   ├── services/           # 业务逻辑层
│   │   ├── rag/                # embedding / vectorstore / chunker / retriever / review_chain
│   │   ├── llm/                # Provider 抽象（OpenAI 兼容实现 + mock）
│   │   └── parsers/            # pdf / docx / image(OCR) 解析器 + 工厂
│   ├── tests/                  # 端到端测试脚本 + seed 工具
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── api/                # Axios 封装（JWT 拦截器）+ 各资源 API
│       ├── stores/             # Pinia（会话持久化 localStorage）
│       ├── router/             # 路由 + 登录/角色守卫
│       ├── views/              # Login / Home / ReviewReport(三栏) / admin/*
│       └── components/         # ChatPanel（WebSocket 流式对话）
└── data/                       # 运行时数据（上传文件，不入库）
```

## 快速开始（本地开发）

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.x（本地运行）
- （可选）Docker + Docker Compose

### 1. 初始化数据库

```sql
CREATE DATABASE contract_review CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 配置后端

```powershell
cd backend
cp .env.example .env    # 编辑 .env 填入你的 LLM / Embedding API Key
pip install -r requirements.txt
python tests/seed_db.py     # 初始化默认账号与 9 个风险类别（幂等）
python tests/migrate_db.py  # 补齐后加的字段（幂等；已建过库的环境需要执行）
uvicorn app.main:app --port 8000
```

### 3. 启动前端

```powershell
cd frontend
npm install
npm run dev    # http://localhost:5173
```

### 4. 单端口部署（推荐用于演示 / 内网穿透 / 交付）

不想同时开两个进程、或只想暴露一个端口给别人访问时，让 FastAPI 直接托管前端构建产物：

```powershell
cd frontend
npm run build            # 生成 frontend/dist

# backend/.env
SERVE_FRONTEND=true

cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 `http://<本机IP>:8000` 即为完整系统：

- 前端静态资源由 FastAPI 挂载在 `/assets`
- 其余路径走 SPA 兜底（刷新 `/reviews/15` 这类深链接不会 404）
- `/api`、`/ws` 与后端同源，**不需要额外配置 CORS 或 WebSocket 代理**
- 内网穿透只需映射 **8000 一个端口**

> 也可直接双击 `start-portable.bat`：自动构建 + 以单端口模式启动。
> 开发模式（`npm run dev` + 5173）仍然可用，两种方式互不影响。

### 5. 登录

| 账号 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 管理员（可访问知识库/类别管理） |
| user | user123 | 普通用户 |

> 登录页支持**自助注册**普通用户（「注册」标签）：用户名 3–32 位（字母/数字/下划线/中文），
> 密码至少 6 位，注册成功自动登录。管理员账号不开放注册，由 `tests/seed_db.py` 初始化。
> 如需关闭自助注册，在 `backend/.env` 设 `ALLOW_REGISTER=false`。

> 开发环境无 API Key 时，可在 `.env` 中设置 `LLM_PROVIDER=mock` 体验完整流程（返回模拟报告）。

## 模型配置

两种方式，**页面配置优先于 `.env`**：

1. **管理后台 →「模型配置」**（推荐）：选提供商、填 Key / 模型名 / Base URL，点「测试连通性」验证后保存，**立即生效，不用重启**。
   密钥保存后只显示掩码（`sk-a****z9`），留空表示不修改，输入 `-` 表示清空。
2. `.env`：服务启动时读取，作为页面未配置时的兜底。

所有主流供应商均走 OpenAI 兼容协议：

| 供应商 | LLM_BASE_URL | 模型示例 |
|---|---|---|
| 硅基流动（默认） | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct`（免费）/ `deepseek-ai/DeepSeek-V3` |
| 阿里通义 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 字节豆包 | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |

Embedding 默认使用硅基流动 `BAAI/bge-m3`（免费、1024 维、中文效果好）。切换 Embedding 供应商会改变向量维度，需清空 `data/chroma` 重建。

## 图片合同（多模态识别）

PNG / JPG 合同不做本地 OCR，直接交给视觉大模型逐字转录，再走同一套结构化流程。

```ini
# backend/.env
VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct   # 必填，也可用 doubao-vision-pro-32k / qwen-vl-plus / gpt-4o-mini
VISION_API_KEY=                            # 留空则继承 LLM_API_KEY
VISION_BASE_URL=                           # 留空则继承 LLM_BASE_URL
```

未配置时图片上传会明确提示「未配置多模态模型」，PDF / Word 不受影响。
相比本地 PaddleOCR：无需安装 300MB+ 运行时和模型文件，对拍照倾斜、表格、印章干扰更鲁棒。

## 端到端测试

后端服务运行中时执行（按顺序）：

```powershell
cd backend
python tests/make_test_contract.py   # 生成测试合同素材
python tests/test_review_e2e.py      # 上传→审查→报告
python tests/test_chat_e2e.py        # WebSocket 流式对话
python tests/test_admin_e2e.py       # 知识库 + 类别管理
```

## Docker Compose 部署

`docker-compose.yml` 已包含完整生产形态编排（MySQL + Redis + ChromaDB standalone + backend + Celery worker + frontend/Nginx）：

```powershell
docker compose up -d

# 需要独立 Celery worker 执行审查时（含 Redis 依赖）：
docker compose --profile celery up -d
```

> 审查默认在 API 进程内以后台任务执行（`REVIEW_EXECUTION_MODE=background`），本地开发无需 Redis；
> 切到 `celery` 模式才会把任务投递到 `celery-worker`，此时必须启用 `--profile celery`，否则任务无人消费。

## 安全说明

- 所有密钥通过 `backend/.env` 注入，已在 `.gitignore` 中排除，**切勿提交真实密钥**
- 生产部署前务必更换 `JWT_SECRET_KEY`、关闭 `DEBUG`、为 MySQL 设置强密码
- 前端 `.env` 仅存放非敏感的 API 地址

## API 概览

统一前缀 `/api`，认证头 `Authorization: Bearer <token>`。

| 分组 | 端点 |
|---|---|
| 认证 | `POST /api/auth/login` · `POST /api/auth/register` · `GET /api/auth/me` |
| 合同 | `POST /api/contracts/upload` · `GET /api/contracts` · `GET/DELETE /api/contracts/{id}` · `POST /api/contracts/{id}/versions`（新版本）· `GET /api/contracts/{id}/diff`（版本比对 + 问题闭环）· `POST /api/contracts/{id}/reparse`（原地重解析）· `POST /api/contracts/{id}/replace`（重传替换文件） |
| 审查 | `POST /api/reviews`（异步，立即返回 running）· `GET /api/reviews/{id}` · `GET /api/reviews/{id}/status` · `POST /api/reviews/{id}/retry` · `GET /api/reviews/by-contract/{contract_id}` · `PATCH /api/reviews/{id}/items/{item_id}` · `POST /api/reviews/{id}/finalize` · `GET /api/reviews/{id}/export` |
| 模板 | `GET/POST /api/templates` · `PUT/DELETE /api/templates/{id}` |
| 任务 | `GET /api/tasks` · `POST /api/tasks/batch-review` |
| 对话 | `GET /api/chat/conversations/{review_id}` · `GET .../messages` · `WS /ws/chat/{conv_id}?token=<jwt>` |
| 法律问答 | `POST/GET /api/assistant/sessions` · `GET/POST /api/assistant/sessions/{id}/messages` · `DELETE .../{id}` · `WS /ws/assistant/{session_id}?token=<jwt>` |
| 管理 | `POST /api/admin/knowledge/upload` · `PUT /api/admin/knowledge/{id}`（替换）· `GET /api/admin/knowledge/{id}/versions` · `GET/DELETE /api/admin/knowledge/{id}` · `GET/POST/DELETE /api/admin/categories` · `GET /api/admin/audit-logs` · `GET /api/admin/usage-stats` |
| 模型配置 | `GET/PUT /api/admin/model-config` · `POST /api/admin/model-config/test`（连通性测试）· `GET /api/admin/model-config/providers` |
| 健康 | `GET /api/health` |

## License

MIT
