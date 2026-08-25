# Photographer Booking

一个面向求职作品集展示的摄影师预约平台：客户浏览摄影师、作品和套餐，摄影师管理作品与订单，AI Agent 在用户确认后调用真实业务工具完成预约或企划创建。

本仓库当前是本地可运行的稳定演示版。支付、短信、邮件和 AI Provider 默认使用 mock/memory 实现，所有 mock 能力都会在界面或文档中明确标注。

## 三分钟启动

环境要求：Python 3.11+、Node.js 20+、npm。Windows PowerShell 示例：

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

## 求职展示亮点

- 展示从 Vue 前端交互到 FastAPI、数据库、订单状态机和通知的完整链路。
- AI Agent 具备槽位补齐、资源检索、用户确认、业务工具和 ActionLog 审计闭环。
- 具备客户、摄影师、管理员三种角色权限，以及订单、支付、交付、验收、争议等可审查状态。

