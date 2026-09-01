# 本地演示指南

## 1. 准备环境

在仓库根目录执行：

```powershell
Copy-Item .env.example .env
venv\Scripts\python.exe -m backend.scripts.seed_demo_data
```

启动 API、用户端和管理端后，打开 README 中列出的三个本地地址。

## 2. 客户链路

使用 `customer.demo@example.com` 登录：

1. 打开“发现”，浏览摄影师和作品。
2. 进入摄影师详情，查看套餐和真实作品素材。
3. 创建预约订单；订单初始为待确认或待支付状态。
4. 使用界面标注的 Mock 支付完成演示支付。
5. 在消息页查看订单上下文消息。
6. 在订单详情中完成交付验收并提交评价。

预期：订单、支付、消息和验收状态来自数据库，而不是前端硬编码。

## 3. 摄影师链路

使用 `photographer.demo@example.com` 登录：

1. 查看摄影师工作台和当前资料。
2. 浏览已有作品与两个演示套餐。
3. 在订单列表中确认客户订单，或查看企划应邀记录。
4. 按状态机执行接单、开始拍摄、上传交付和改期操作。
5. 打开收入/统计页面，核对订单产生的数据。

未审核摄影师和入驻申请可由管理员账号查看审核流程。

## 4. AI Agent 链路

使用客户账号打开 AI 助手，输入：

```text
我想在香港拍一组自然、胶片感的人像，预算 2000 元，两周后周末完成。
```

观察：Agent 提取城市、风格、预算和日期槽位；缺少信息时继续追问；推荐卡片引用数据库资源；用户确认后才调用业务工具；`agent_action_logs` 记录工具名、输入、结果和状态。

默认 `AI_PROVIDER=mock`，不需要外部 API Key。Mock 只模拟模型响应，不代表已接入线上大模型。

## 5. 管理员链路

使用 `admin.demo@example.com` 登录管理端，查看平台统计、订单、摄影师入驻申请、用户、争议和财务信息。

### 图片生成演示

默认配置为 `IMAGE_PROVIDER=mock`，不需要外部图片模型密钥：

1. 使用客户账号打开 AI 助手，选择“文生图”，输入“黄昏海边的清冷人像，胶片质感”，发送后观察排队、生成和保存状态。
2. 上传一张参考图片，选择“以图生图”，输入需要保留和修改的内容，确认结果卡展示参考图与生成图。
3. 点击“重新生成”，系统会直接创建新 Job，并继承原任务的模式、提示词、参考图和生成参数。
4. 使用管理员账号打开仪表盘，在“图片生成调用”中切换近 7 天/30 天，核对成功率、图片数、平均耗时、Provider 分布和最近任务。

Mock Provider 用于演示工作流，不代表真实模型质量。切换 OpenAI-compatible Provider 前，至少配置：

```env
IMAGE_PROVIDER=openai_compatible
IMAGE_API_BASE=https://example.com/v1
IMAGE_API_KEY=replace-with-local-secret
IMAGE_MODEL=your-image-model
IMAGE_GENERATION_PATH=/images/generations
IMAGE_EDIT_PATH=/images/edits
```

参考图片可能被发送给第三方 Provider；真实部署前应同步更新隐私说明，并确认中转服务实际支持的参数和响应格式。

## 6. 重复演示与自动化验证

seed 命令可以安全重复执行，不清空数据库，也不删除非演示数据：

```powershell
venv\Scripts\python.exe -m backend.scripts.seed_demo_data
venv\Scripts\python.exe -m pytest backend/tests/test_seed_demo_data.py -q
```

前端验证：

```powershell
cd frontend
npm.cmd run test:unit -- --run
npm.cmd run build
npm.cmd run test:e2e -- --project=chromium
```

Playwright 若缺少浏览器，先执行 `npx.cmd playwright install chromium`。
