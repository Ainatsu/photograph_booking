# Photographer Booking

项目地址：[github.com/Ainatsu/photographer_booking](https://github.com/Ainatsu/photographer_booking)

客户浏览摄影师、作品和套餐，摄影师管理作品与订单，AI Agent 在用户确认后调用真实业务工具完成预约或企划创建。

本仓库当前是本地可运行的稳定演示版。支付、短信、邮件和 AI Provider 默认使用 mock/memory 实现，所有 mock 能力都会在界面或文档中明确标注。

## 功能概览

- 客户浏览摄影师、作品和套餐，创建预约订单，完成支付、沟通、验收和评价。
- 摄影师维护个人资料、作品和套餐，处理订单、交付作品并查看收入。
- 管理员处理摄影师入驻审核、用户、订单、争议和财务。

## 核心项目：业务型 AI Agent

本项目的重点是一个与真实业务数据和业务流程连接的 AI Agent。它不是只生成文本的聊天机器人，而是将自然语言请求转换为可校验、可追踪、需要用户确认的业务任务。

### Agent 能力

- **意图识别**：识别闲聊、摄影师/作品/套餐/企划检索、图片分析、预约、发布企划、发布套餐、发布作品、申请企划和关注摄影师等场景。
- **结构化需求理解**：从中文自然语言中抽取城市、地点、风格、预算、日期、时间、人数、拍摄时长、照片数量、妆造、交付要求等槽位，并主动识别缺失信息。
- **真实资源检索**：从数据库检索摄影师、作品、套餐和企划，支持关键词、业务条件、混合检索和图片驱动的视觉检索；推荐结果使用真实资源 ID，不虚构业务对象。
- **多模态输入**：用户可以上传参考图片，Agent 根据图片内容进行分析，并将视觉结果用于作品或套餐检索。
- **任务型工作流**：将复杂请求保存为可恢复的 Agent Task，支持收集槽位、等待详情、等待目标、等待套餐、等待日期/时间、等待确认、执行、完成、失败和取消等状态。
- **安全的业务执行**：涉及创建预约、发布企划、发布套餐或其他写操作时，Agent 先生成待执行动作并展示摘要，只有用户明确确认后才调用业务工具。
- **权限与数据隔离**：工具执行前校验当前用户身份、角色和资源归属；任务结果再次验证属于当前用户，避免跨用户访问或操作。
- **可靠性与审计**：工具动作携带幂等键，避免重复创建；执行结果写入 `agent_action_logs`，便于追踪意图、工具、参数、结果和失败原因。
- **持续上下文**：支持会话历史压缩、工作记忆、长期记忆和任务记忆检索，让 Agent 能在多轮对话中保持任务上下文。

### AI 图片生成 Provider

图片生成使用独立的 `ImageGenerationProvider`，与聊天模型的 `AIProvider` 配置互不影响。文生图和以图生图共享一套异步 Job、状态轮询、重试、重新生成、配额与媒体落盘流程，仅在输入校验和 Provider 调用方法上区分。

- `IMAGE_PROVIDER=mock`：默认演示模式，无需 API Key，使用项目内固定测试图跑通完整交互。
- `IMAGE_PROVIDER=openai_compatible`：调用 OpenAI-compatible 中转接口；生成端点与编辑端点可分别配置。
- Provider 返回的图片会校验类型、大小和真实图像内容，并保存到 `uploads/ai-generated/`，前端不长期依赖上游临时 URL。
- “重试”复用原 Job；“重新生成”创建新 Job，并继承原提示词、宽高比、数量、质量、修改强度和参考图，便于独立审计。

最小配置示例：

```env
IMAGE_PROVIDER=mock
IMAGE_MODEL=mock-image-v1
IMAGE_GENERATION_WORKER_ENABLED=true
IMAGE_MAX_CONCURRENCY=1
IMAGE_DAILY_LIMIT_PER_USER=10
```

切换真实中转服务时设置 `IMAGE_API_BASE`、`IMAGE_API_KEY`、`IMAGE_MODEL`、`IMAGE_GENERATION_PATH` 和 `IMAGE_EDIT_PATH`。仓库中的 `.env.example` 不包含真实密钥。

### Agent 工作流程

```text
用户自然语言/图片
        |
        v
意图识别 + 槽位抽取 + 能力/权限判断
        |
        +--> 信息不足：追问并保存任务状态
        |
        +--> 查询请求：检索真实数据库资源并返回可解释结果
        |
        +--> 写操作：生成待确认动作，等待用户明确确认
                                      |
                                      v
                         幂等工具调用 + 业务校验 + ActionLog 审计
                                      |
                                      v
                              返回结果并完成任务
```

Agent 的核心实现位于 `backend/app/services/`，主要包括意图编排、任务状态、工具调用、检索、视觉嵌入、记忆、策略控制和可观测性模块；API 入口位于 `backend/app/api/v1/ai.py`，用户端入口位于 `frontend/src/views/AIAssistant.vue`。

## 技术栈

FastAPI、SQLAlchemy、Alembic、JWT、SQLite/PostgreSQL、Redis/fakeredis、Vue 3、Vite、Pinia、Vue Router、Element Plus、Pytest、Vitest 和 Playwright。

## 快速开始

环境要求：Python 3.11+、Node.js 20+、npm。以下为 Windows PowerShell 示例：

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
venv\Scripts\python.exe -m backend.scripts.seed_demo_data
```

分别启动 API、用户端和管理端：

```powershell
venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5173
cd ..\admin-frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5174
```

本地地址：用户端 <http://127.0.0.1:5173>，管理端 <http://127.0.0.1:5174>，API 文档 <http://127.0.0.1:8000/docs>。

首次启动前请根据需要编辑 `.env`。`.env.example` 仅提供配置模板，不应包含真实密钥。

## 演示账号

执行 seed 后可使用以下账号，密码均为 `Demo123456!`：

| 角色 | 登录账号 | 用途 |
| --- | --- | --- |
| 客户 | `customer.demo@example.com` | 浏览、预约、Mock 支付、验收、评价、AI 助手 |
| 摄影师 | `photographer.demo@example.com` | 作品与套餐、接单、交付、收入 |
| 管理员 | `admin.demo@example.com` | 入驻审核、用户、订单、争议和财务 |

这些账号只用于本地或公开演示环境，不应复用于生产环境。

## 核心业务链路

客户：登录 → 浏览摄影师/作品/套餐 → 创建预约订单 → 摄影师确认 → Mock 支付 → 消息沟通 → 查看交付 → 验收并评价。

摄影师：登录 → 查看入驻状态 → 维护资料和作品 → 创建套餐 → 查看订单 → 接单/拒单/改期 → 上传交付 → 查看收入。

AI Agent：客户用自然语言描述城市、风格、预算、日期和人数。Agent 提取槽位、检索数据库中的摄影师/套餐/作品、追问缺失信息；用户明确确认后，才调用预约或企划工具。工具结果写入 `agent_action_logs`，推荐结果使用真实数据库资源，不生成虚假 ID。

## 系统架构

```text
Vue 3 用户端 / Vue 3 管理端
              │
              ▼
        FastAPI API 层
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
  业务服务   AI Agent   WebSocket
     │        │
     ▼        ▼
 SQLAlchemy  资源索引 / 工具调用 / ActionLog
     │
 SQLite（本地）或 PostgreSQL（部署）
```

技术栈：FastAPI、SQLAlchemy、Alembic、JWT、Vue 3、Vite、Pinia、Vue Router、Element Plus、Redis/fakeredis、Pytest、Vitest、Playwright。

## 初始化演示数据

```powershell
venv\Scripts\python.exe -m backend.scripts.seed_demo_data
```

该命令可重复执行，只按固定演示账号、`demo-*` 业务键和稳定标题查找记录，不清空数据库，也不删除用户自行创建的数据。素材来自 `docs/example-pictures/`，运行时复制到被 Git 忽略的 `uploads/demo/`。

更多操作步骤见 [docs/demo-guide.md](docs/demo-guide.md)。

## 测试与构建

```powershell
venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm.cmd run test:unit -- --run
npm.cmd run build
npm.cmd run test:e2e -- --project=chromium
cd ..\admin-frontend
npm.cmd run build
```

Playwright 需要先安装浏览器：`npx.cmd playwright install chromium`。后端测试默认使用隔离数据库、mock AI、fakeredis 和内存通知服务。

## Docker

```powershell
docker compose config
docker compose up --build
```

Compose 会启动 PostgreSQL、Redis、MinIO、API、用户端和管理端。生产部署前必须替换 `SECRET_KEY`、数据库密码和对象存储配置，不要提交 `.env`、真实密钥或数据库文件。

## 目录结构

```text
backend/app/          API、模型、schema、业务服务和工具
backend/migrations/   Alembic 迁移
backend/scripts/      演示数据和维护脚本
backend/tests/        后端测试
frontend/src/         用户端
frontend/e2e/         Playwright 核心入口测试
admin-frontend/src/   管理端
docs/                 计划、演示指南和素材
```

## 已知限制

- 支付、短信、邮件和默认 AI Provider 是 mock/memory 实现，不代表已接入真实第三方服务。
- 本地默认 SQLite；生产环境应使用 PostgreSQL、Redis 和对象存储。
- Pydantic 旧式 schema 配置、部分 SQLAlchemy 测试清理警告和前端大分块警告仍是后续技术债。
- Playwright 需要本机安装浏览器；无法安装浏览器时只能完成单元测试和构建验证。


## 上传前安全检查

项目已通过 `.gitignore` 排除环境变量、数据库和备份文件、用户上传资源、生成媒体、本地模型、虚拟环境、构建产物、日志、IDE 配置和个人文档。提交前建议执行：

```powershell
git status --short --ignored
git diff -- .gitignore README.md
git grep -n -I -E "(api[_-]?key|secret|password|token|BEGIN [A-Z ]+ PRIVATE KEY)" -- ':!*.md' ':!.env.example' || $true
```

如果密钥曾经被提交到 Git 历史，单纯添加 `.gitignore` 无法移除它；请立即吊销并重新生成密钥，再清理 Git 历史。

## 许可与演示数据

仓库中的演示账号、Mock 服务和示例图片仅用于本地开发或公开演示，不应直接用于生产环境。公开发布示例图片前，请确认你拥有相应的使用权。

