# Agent 文生图与以图生图功能构造方案

## 1. 文档目标

本文定义摄影预约项目中两类 AI 图像创作能力的实现方案：

- **灵感可视（文生图）**：用户输入拍摄主题、风格、场景或画面描述，由图像模型生成新的摄影灵感图。
- **灵感改图（以图生图）**：用户上传一张参考图，并同时提供文字修改指令，由图像模型结合图片内容与文字要求生成新版本。

两类能力同时支持以下启动方式：

1. Agent 从用户自然语言和附件中识别生成意图。
2. 用户点击聊天框下方的“文生图”或“以图生图”入口，显式启动对应模式。

本方案面向当前求职作品集项目，优先保证：完整业务链路、可演示性、Provider 可替换、异步任务可靠性和成本可控。第一版接入 OpenAI-compatible 中转 API，同时保留 Mock Provider，暂不把本地模型作为主运行路径。

## 2. 范围与非目标

### 2.1 第一版范围

- Web 与移动端 Agent 输入区增加“文生图”和“以图生图”入口。
- 自然语言和显式入口统一进入同一套后端工作流。
- 文生图支持提示词、宽高比、生成数量和质量档位。
- 以图生图支持一张参考图、必填文字修改指令和修改强度。
- 使用异步 Job 执行模型调用，不阻塞聊天请求。
- 展示排队、生成中、完成、部分失败、失败和取消状态。
- 生成结果保存到项目自己的媒体存储，不长期依赖中转 API 的临时 URL。
- 支持重试、重新生成、下载和查看大图。
- 记录 Provider、模型、耗时、请求 ID、失败原因和生成参数。

### 2.2 第一版不做

- 局部蒙版编辑、画面扩展和擦除重绘。
- 多张参考图融合。
- 连续画布编辑器和图层系统。
- 本地 ComfyUI/SDXL Provider。
- 面向生产环境的计费结算。
- 自动公开发布生成图片。

这些能力可以在 Provider 协议稳定后分阶段增加。

### 2.3 第一版摄影语义范围

第一版以图生图主要服务于摄影创作、拍摄预演和客户与摄影师之间的视觉沟通，优先支持：

- 改变天气、时间和光线。
- 调整色调和摄影风格。
- 更换拍摄环境。
- 调整服装颜色、妆造方向和道具。
- 生成同一构图的不同创意版本。
- 保留主体姿势和位置进行场景预演。
- 调整镜头语言、景别、画面氛围和叙事方向。
- 其他与真实摄影策划、拍摄准备或创意沟通相关的修改。

这是一组产品定位和 Prompt 引导方向，不是封闭的代码白名单。系统不应因为用户没有使用上述固定词语就拒绝生成，也不应把摄影创意限制为预定义标签。

## 3. 核心架构决策

### 3.1 使用一个领域工作流、两个生成模式

后端新增统一意图：

```text
intent: image_generation_flow
route: image_generation
sub_intents:
  - text_to_image
  - image_to_image
```

任务类型统一为 `generate_image`，通过 `mode` 区分：

```text
mode=text_to_image
mode=image_to_image
```

不建议为两种模式复制两套 Job、API 和任务状态机。它们的差异主要在输入校验和 Provider 调用方法，持久化、重试、进度展示和结果保存可以共用。

### 3.2 显式入口必须使用结构化协议

用户点击按钮后，客户端不得只拼接“请帮我文生图”之类的隐藏文本来触发规则识别。客户端应在消息请求中提交结构化字段：

```json
{
  "content": "黄昏海边的清冷人像，胶片质感",
  "attachments": [],
  "generation_request": {
    "mode": "text_to_image",
    "aspect_ratio": "3:4",
    "count": 1,
    "quality": "standard",
    "idempotency_key": "uuid"
  }
}
```

显式入口的路由优先级高于意图分类器，但仍必须经过后端 Schema、权限、配额和附件校验。自然语言入口继续经过现有规则识别和 LLM 分类，最终生成相同的内部命令。

### 3.3 图像 Provider 与聊天 Provider 分离

现有 `AIProvider.chat()` 面向 `/chat/completions` 和多模态理解，不应承担图片生成职责。新增独立协议：

```python
class ImageGenerationProvider(Protocol):
    async def generate(
        self,
        request: TextToImageRequest,
    ) -> ImageGenerationProviderResult:
        ...

    async def edit(
        self,
        request: ImageToImageRequest,
    ) -> ImageGenerationProviderResult:
        ...
```

第一版实现：

- `MockImageGenerationProvider`
- `OpenAICompatibleImageGenerationProvider`

后续可以增加：

- `ComfyUIImageGenerationProvider`
- 其他云端图像模型 Provider

### 3.4 使用独立生成表，不复用现有灵感分析表

当前 `inspiration_generation_jobs` 与 `inspiration_generation_batches` 服务于“分析参考图并生成结构化摄影建议”，并且强绑定 `inspiration_id`。新功能是生成真实媒体资产，生命周期和数据结构不同，不应向现有表追加大量可空字段。

可以复用现有 worker 的实现模式，但新增独立的 `image_generation_jobs` 和 `image_generation_assets`。

### 3.5 以图生图采用“图片 + 文字”联合输入

本项目中的以图生图不是纯图片重绘。有效请求必须同时包含：

1. 一张用户有权访问的参考图片。
2. 一段非空文字指令，说明需要保留、修改或避免的内容。

图片提供视觉条件，文字提供编辑目标。后端不能在只有图片时自行猜测用户想修改什么，也不能用固定默认提示词静默发起生成。

推荐把文字指令在内部整理为以下语义，但仍保留用户原始文本：

```json
{
  "instruction": "改成黄昏海边逆光，保留人物姿势和面部特征",
  "preserve": ["人物姿势", "面部特征", "主体位置"],
  "change": ["背景改为海边", "光线改为黄昏侧逆光"],
  "avoid": ["改变人物身份", "增加文字水印"]
}
```

`preserve/change/avoid` 可以由 Prompt Planner 提取，但不是客户端必填字段。提取失败时直接使用用户原始文字指令，不阻塞生成。

## 4. 总体流程

### 4.1 文生图

```text
用户输入画面描述
    |
    +-- 点击“文生图” -------------------+
    |                                    |
    +-- Agent 识别 text_to_image --------+
                                         v
                               生成统一领域命令
                                         |
                               参数校验与额度检查
                                         |
                         创建 AgentTask + GenerationJob
                                         |
                            返回排队中的生成任务卡片
                                         |
                                  Worker 调用 API
                                         |
                         下载、校验并保存生成图片
                                         |
                              更新 Job 与任务结果
                                         |
                            客户端刷新生成结果卡片
```

### 4.2 以图生图

```text
用户上传一张参考图 + 输入必填文字修改指令
    |
    +-- 点击“以图生图” -----------------+
    |                                    |
    +-- Agent 识别 image_to_image -------+
                                         v
                          校验图片归属、类型和大小
                                         |
                          创建 AgentTask + GenerationJob
                                         |
                          Worker 读取可信图片文件
                                         |
                          multipart 调用图片编辑接口
                                         |
                         保存结果并展示原图/生成图
```

## 5. 路由与意图识别

### 5.1 路由优先级

建议在 `send_ai_message()` 中按以下顺序决定是否进入图像生成流程：

1. `generation_request` 显式请求。
2. 正在进行中的 `generate_image` 任务继续操作。
3. 确定性规则识别。
4. LLM 意图分类。
5. 普通图片分析或普通聊天兜底。

显式请求不能被分类器改写为其他意图。

### 5.2 自然语言规则示例

文生图表达：

- 帮我生成一张海边人像灵感图。
- 把这个拍摄方案可视化。
- 画一张夜景霓虹街拍效果图。
- 根据这段描述生成摄影参考图。
- 做一版 3:4 的胶片风拍摄概念图。

以图生图表达：

- 把这张图改成黄昏逆光。
- 保留人物姿势，换成海边背景。
- 根据这张参考图生成更清冷的版本。
- 把照片改成复古胶片风。
- 维持构图，把服装颜色换成白色。

### 5.3 防止误路由

- 只有图片、没有生成或修改语义：继续进入 `image_analysis`。
- “帮我分析这张图”：进入图片分析，不进入以图生图。
- “找类似作品”：进入视觉检索。
- “根据图片创建灵感笔记”：进入现有 `create_inspiration_flow`。
- “根据图片生成一张新图”：进入 `image_generation_flow/image_to_image`。
- 有生成语义但语义不明确，且没有参考图：默认文生图。
- 有明确修改语义但没有参考图：进入 `awaiting_reference_image`，不调用模型。

### 5.4 冲突处理

当用户点击“文生图”却附带图片时，客户端应在发送前显示内联提示：

```text
文生图模式不使用参考图片。请移除图片，或切换到“以图生图”。
```

第一版不静默忽略附件，也不自动切换模式。显式模式代表用户选择，应保持可预测。

## 6. 前端输入区方案

### 6.1 Web 端

在 `frontend/src/views/AIAssistant.vue` 的快捷提示区域和图片预览区域之间增加创作模式条：

```text
[普通对话] [文生图] [以图生图]
```

实现建议：

- 使用带 Lucide 图标和文本的分段控件或可选按钮，不使用 emoji。
- `普通对话` 为默认状态。
- 激活态同时使用边框、背景和文本，不只依赖颜色。
- 每个触控目标高度至少 44px。
- 点击已激活模式可恢复普通对话，也提供明确的关闭按钮。
- 模式只作用于当前一次提交，发送成功后恢复普通对话。
- 请求失败时恢复用户原输入、附件和模式。

模式激活后的输入提示：

```text
文生图：描述想要生成的场景、人物、光线和风格
以图生图：上传一张参考图，并描述需要保留和修改的内容
```

### 6.2 移动端

`mobile-app/src/pages/AIAssistantPage.vue` 已有 `agentCapabilities`、横向 capability 列表和激活态简要区域，可以直接扩展为：

```text
创作灵感 | 文生图 | 以图生图
```

其中：

- 现有“创作灵感”继续对应 `create_inspiration`。
- “文生图”对应 `generate_image + text_to_image`。
- “以图生图”对应 `generate_image + image_to_image`。
- 点击“以图生图”后，如果没有附件，自动打开图片选择器。
- 横向滚动按钮保持 44x44px，并保留键盘焦点和 `aria-label`。
- 底部输入区继续考虑 `safe-area-inset-bottom`。

### 6.3 渐进式参数

输入区默认只展示模式、文本框、附件和发送按钮。高级参数放入“生成设置”折叠面板，避免让聊天框变成复杂表单。

第一版参数：

| 参数 | 文生图 | 以图生图 | 默认值 |
| --- | --- | --- | --- |
| `aspect_ratio` | 必填 | 必填 | `1:1` |
| `count` | 1-2 | 1-2 | `1` |
| `quality` | standard/high | standard/high | `standard` |
| `strength` | 不适用 | 0.1-1.0 | `0.65` |

宽高比使用预设，不允许第一版自由输入像素：

```text
1:1  3:4  4:3  9:16  16:9
```

Provider 不支持某个参数时，由 Provider Adapter 映射或明确拒绝，不能静默伪造支持。

以图生图的文字输入不是高级参数，必须始终显示且必填。高级面板只放宽高比、质量和修改强度等可选设置。

### 6.4 生成结果卡片

聊天消息中新增 `ImageGenerationCard`，展示：

- 模式名称。
- 用户原始提示词摘要。
- 参考图缩略图（以图生图）。
- 宽高比和生成数量。
- 排队、生成中、完成、失败状态。
- 生成结果网格。
- 下载、查看大图、重新生成和重试操作。
- “AI 生成”标识。

以图生图完成后，单结果使用左右对比布局；移动端改为上下布局。多结果使用稳定宽高比网格，加载前预留空间，避免页面跳动。

第一版结果操作：

```text
查看大图 | 下载 | 重新生成
```

后续可增加：

```text
保存到灵感 | 继续修改 | 发布为作品草稿
```

### 6.5 反馈与可访问性

- 模型调用超过 300ms 必须显示状态反馈。
- 不使用一个无限旋转图标覆盖整个等待过程，应显示任务阶段文字。
- 状态文案示例：`等待生成`、`正在提交模型`、`正在保存图片`。
- 所有图片提供描述性 `alt`。
- 生成完成通过 `aria-live="polite"` 通知。
- 错误信息必须包含恢复方式，例如“中转服务暂时不可用，可点击重试”。
- 动画限制在 150-300ms，并遵循 `prefers-reduced-motion`。
- 图片使用缩略图和懒加载，完整原图只在查看或下载时加载。

## 7. API 请求协议

### 7.1 消息 Schema

在 `backend/app/schemas/ai.py` 中增加：

```python
class AIImageGenerationRequest(BaseModel):
    mode: Literal["text_to_image", "image_to_image"]
    aspect_ratio: Literal["1:1", "3:4", "4:3", "9:16", "16:9"] = "1:1"
    count: int = Field(default=1, ge=1, le=2)
    quality: Literal["standard", "high"] = "standard"
    strength: float | None = Field(default=None, ge=0.1, le=1.0)
    idempotency_key: UUID = Field(default_factory=uuid4)
```

并在 `AIMessageCreate` 中增加：

```python
generation_request: AIImageGenerationRequest | None = None
```

以图生图显式请求示例：

```json
{
  "content": "保留人物姿势和主体位置，把环境改成黄昏海边逆光，整体使用低饱和胶片色调",
  "attachments": [
    {
      "type": "image",
      "url": "/uploads/ai/reference.jpg",
      "mime_type": "image/jpeg"
    }
  ],
  "generation_request": {
    "mode": "image_to_image",
    "aspect_ratio": "3:4",
    "count": 1,
    "quality": "standard",
    "strength": 0.65,
    "idempotency_key": "uuid"
  }
}
```

后端校验：

- 文生图必须有非空 `content`，不允许图片附件。
- 以图生图必须同时具有非空 `content` 和图片附件；第一版必须有且只有一张图片附件。
- 只有图片、没有文字指令时返回 `generation_instruction_required`，不调用 Provider。
- `strength` 只允许用于以图生图。
- 同一用户和同一 `idempotency_key` 只能创建一个 Job。

### 7.2 任务查询 API

新增 API：

```text
GET  /api/v1/ai/image-generations/{job_id}
POST /api/v1/ai/image-generations/{job_id}/retry
POST /api/v1/ai/image-generations/{job_id}/cancel
```

查询响应：

```json
{
  "job_id": 123,
  "task_id": "uuid",
  "mode": "image_to_image",
  "status": "generating",
  "stage": "calling_provider",
  "progress": {
    "completed": 0,
    "total": 1
  },
  "source_images": [],
  "result_images": [],
  "can_retry": false,
  "can_cancel": true,
  "error": null
}
```

第一版客户端可每 2 秒轮询一次，仅在任务处于活动状态且页面可见时轮询。后续可替换为 WebSocket/SSE，不改变 Job Schema。

### 7.3 聊天响应 Metadata

创建 Job 后，Assistant 消息返回轻量引用：

```json
{
  "image_generation": {
    "schema_version": "image_generation_v1",
    "job_id": 123,
    "task_id": "uuid",
    "mode": "text_to_image",
    "status": "queued"
  }
}
```

消息 Metadata 不保存完整 Base64 或大尺寸图片，只保存 Job ID 和渲染所需的小型快照。

## 8. 数据模型

### 8.1 `image_generation_jobs`

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `owner_id` | 当前用户 |
| `conversation_id` | Agent 会话 |
| `source_message_id` | 启动生成的用户消息 |
| `agent_task_id` | 对应 AgentTask |
| `mode` | `text_to_image` / `image_to_image` |
| `status` | Job 状态 |
| `stage` | 当前执行阶段 |
| `prompt` | 用户原始描述 |
| `normalized_prompt` | 可选的内部标准化提示词 |
| `parameters` | 宽高比、数量、质量、强度等 JSON |
| `provider` | Provider 标识 |
| `model` | 实际模型 ID |
| `provider_request_id` | 上游请求 ID |
| `idempotency_key` | 用户级唯一幂等键 |
| `attempts` | 尝试次数 |
| `available_at` | 下次可执行时间 |
| `started_at` | 开始时间 |
| `completed_at` | 完成时间 |
| `last_error_code` | 稳定错误码 |
| `last_error` | 截断后的内部错误摘要 |
| `usage_metadata` | 上游用量或成本信息 |
| `created_at/updated_at` | 时间戳 |

唯一约束：

```text
(owner_id, idempotency_key)
```

### 8.2 `image_generation_assets`

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `job_id` | 所属 Job |
| `role` | `source` / `result` |
| `position` | 显示顺序 |
| `storage_url` | 项目自己的媒体地址 |
| `thumbnail_url` | 缩略图地址 |
| `mime_type` | 图片 MIME |
| `width/height` | 尺寸 |
| `size_bytes` | 文件大小 |
| `sha256` | 内容哈希 |
| `provider_metadata` | 单张结果元数据 |
| `created_at` | 创建时间 |

来源图片必须从当前用户消息的可信附件建立资产记录，不能接受模型或客户端提交任意 `owner_id`、本地路径或内部存储键。

## 9. Job 状态机

```text
queued
  -> validating_input
  -> preparing_request
  -> calling_provider
  -> saving_assets
  -> completed
```

异常分支：

```text
queued/generating -> retry_wait -> queued
queued/generating -> failed
queued/generating -> cancelled
saving_assets     -> partial
```

状态语义：

- `queued`：任务已创建，等待 Worker。
- `generating`：对外聚合状态，内部通过 `stage` 表示具体阶段。
- `retry_wait`：可重试错误，等待退避时间。
- `partial`：模型返回多张结果，但只有部分成功保存。
- `completed`：至少生成并保存了要求数量的结果。
- `failed`：达到最大重试次数或发生不可重试错误。
- `cancelled`：用户取消且 Worker 尚未进入不可中断阶段。

建议最大尝试 3 次，退避时间复用现有灵感 Worker 思路：

```text
5 秒 -> 20 秒 -> 失败
```

## 10. AgentTask 状态

任务类型：

```text
task_type=generate_image
```

业务状态：

```text
collecting
awaiting_reference_image
queued
generating
completed
failed
cancelled
```

建议字段：

```json
{
  "mode": "image_to_image",
  "prompt": "保留人物姿势，改成黄昏海边逆光",
  "aspect_ratio": "3:4",
  "count": 1,
  "quality": "standard",
  "strength": 0.65,
  "source_asset_ids": [456],
  "job_id": 123
}
```

AgentTask 保存业务上下文，GenerationJob 保存模型执行状态。两者不能互相替代。

## 11. Provider 适配层

### 11.1 配置项

在 `.env.example` 中规划以下配置：

```env
IMAGE_PROVIDER=mock
IMAGE_API_BASE=
IMAGE_API_KEY=
IMAGE_MODEL=
IMAGE_GENERATION_PATH=/images/generations
IMAGE_EDIT_PATH=/images/edits
IMAGE_RESPONSE_FORMAT=b64_json
IMAGE_REQUEST_TIMEOUT=180
IMAGE_MAX_CONCURRENCY=1
IMAGE_MAX_RESULTS_PER_REQUEST=2
IMAGE_PROVIDER_FALLBACK_ENABLED=true
```

不要复用 `AI_MODEL` 和 `AI_API_KEY` 的语义。聊天模型和图像模型可能来自不同服务，也可能需要不同超时、并发和配额。

### 11.2 OpenAI-compatible Adapter

Adapter 负责兼容中转站差异：

- 文生图 JSON 请求。
- 以图生图 multipart 请求。
- `url` 和 `b64_json` 两种返回格式。
- 不同模型的尺寸或宽高比参数映射。
- 不同错误响应结构归一化。
- 提取 Provider 请求 ID 和用量信息。

Provider 层返回统一结果：

```python
class GeneratedImagePayload(BaseModel):
    content: bytes | None = None
    temporary_url: str | None = None
    mime_type: str | None = None
    revised_prompt: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ImageGenerationProviderResult(BaseModel):
    images: list[GeneratedImagePayload]
    provider: str
    model: str
    request_id: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
```

业务服务不能直接解析某个中转商的原始响应。

### 11.3 Prompt 处理

第一版优先把用户原始描述直接发送给支持自然语言的图像模型，只做安全、长度和业务参数标准化。不要在模型调用前用大量硬编码摄影词污染用户意图。

可选增加一个轻量 Prompt Planner，用于将自然语言整理成结构化字段：

```json
{
  "subject": "海边女性人像",
  "environment": "黄昏海岸",
  "lighting": "侧逆光",
  "composition": "半身三分构图",
  "style": "低饱和胶片",
  "constraints": ["自然肤色", "无文字水印"]
}
```

Prompt Planner 失败时必须回退到原始提示词，不能阻塞生图主链路。

### 11.4 摄影语义 Prompt 软约束

摄影语义范围采用 Prompt 软约束，不在业务代码中维护“允许修改类型”的枚举白名单。原因包括：

- 摄影创意表达开放，无法通过有限关键词完整覆盖。
- 同一个需求可能同时涉及光线、造型、场景和叙事。
- 强规则容易误拒绝合理表达，例如“梦境舞台感”“电影剧照感”或“超现实棚拍”。
- 不同图像模型对摄影术语和自然语言的理解能力不同，Provider Adapter 需要保留调整空间。

建议在以图生图请求前加入稳定的摄影领域系统提示：

```text
你是摄影拍摄预演与创意沟通助手。
请将用户上传的参考图片和文字指令理解为摄影相关的视觉创作需求，
优先围绕天气、时间、光线、色调、摄影风格、拍摄环境、服装、妆造、
道具、构图、景别、镜头语言、主体姿势和画面叙事进行修改。

尽量保留用户明确要求保留的主体、姿势、位置、构图和身份特征，
只修改用户要求改变的部分。用户没有明确要求的关键内容不要主动大幅改动。

如果用户使用抽象或跨领域表达，请优先把它解释为摄影概念、布景、造型、
灯光或后期视觉风格，而不是直接拒绝。不要声称生成图是真实拍摄作品或真实客片。
```

实际发送给模型的 Prompt 可以由以下部分组成：

```text
摄影领域系统引导
+ 用户原始文字指令
+ preserve/change/avoid 结构化结果（提取成功时）
+ 宽高比、质量和修改强度等 Provider 参数
```

Prompt 软约束只负责产品定位和生成方向，不负责安全与业务可信边界。以下内容仍必须使用后端硬约束：

- 当前用户是否有权访问参考图片。
- 图片数量、类型、尺寸和文件大小。
- 请求幂等、并发限制和每日配额。
- Provider 支持的真实参数范围。
- 下载临时图片时的 SSRF 和响应体限制。
- 平台内容安全策略、违法内容和明确禁止的身份滥用。
- AI 生成标识，以及生成图不得伪装成摄影师真实作品或真实客片。

对于偏离摄影语义但不违反安全策略的请求，不建议在 API 层直接拒绝。Agent 可以：

1. 优先将其解释为摄影概念图或创意布景需求。
2. 在歧义较大时追问用户希望保留和修改的内容。
3. 仍然保留用户原始指令，避免领域 Prompt 完全覆盖用户意图。

## 12. 媒体保存与安全

### 12.1 结果落盘

Provider 返回结果后：

1. Base64 解码或下载临时 URL。
2. 校验响应大小和 Content-Type。
3. 使用 Pillow 解码，拒绝伪装文件。
4. 移除不需要的元数据。
5. 生成缩略图。
6. 保存到本地上传目录或对象存储。
7. 写入 `image_generation_assets`。

建议目录：

```text
uploads/ai-generated/{user_id}/{job_id}/
```

### 12.2 临时 URL 下载安全

中转 API 可能返回任意 URL。下载服务必须：

- 只允许 `https`。
- 限制重定向次数。
- 阻止回环、私网、链路本地和云元数据地址。
- 限制最大响应体，例如 20MB。
- 设置连接和读取超时。
- 不把上游临时 URL直接返回给前端长期使用。

优先配置 `b64_json`，可以减少服务端请求伪造风险和临时 URL 失效问题。

### 12.3 上传图片

以图生图应读取已经由 `/ai/uploads` 保存并校验的可信附件。向 Provider 发送时优先直接读取文件并使用 multipart 上传，不要求内部图片 URL 对公网可访问。

### 12.4 数据与产品声明

- API Key 只存在后端环境变量中。
- README 明确写为“OpenAI-compatible 图像 Provider”，除非确认使用官方服务。
- 生成结果展示“AI 生成”标识。
- 参考照片可能发送给第三方 Provider，应在隐私说明中明确。
- 不记录完整 API Key、Base64 图片或未截断的上游错误响应。

## 13. 配额与成本控制

求职演示项目不需要完整计费系统，但必须防止公开演示被刷：

- 单用户同时只允许 1 个运行中的生成 Job。
- 单次最多生成 2 张。
- 默认质量为 `standard`。
- 每用户每日设置可配置次数。
- 全局 Worker 并发默认 1。
- 相同幂等键不重复扣费或创建 Job。
- 管理端或日志中可以查看生成次数和失败率。

建议配置：

```env
IMAGE_DAILY_LIMIT_PER_USER=10
IMAGE_MAX_ACTIVE_JOBS_PER_USER=1
IMAGE_MAX_UPLOAD_BYTES=10485760
IMAGE_MAX_DOWNLOAD_BYTES=20971520
```

达到额度时返回明确错误，不调用 Provider：

```text
今天的图片生成次数已用完，请明天再试。
```

## 14. 错误分类与恢复

稳定错误码建议：

| 错误码 | 是否重试 | 用户提示 |
| --- | --- | --- |
| `invalid_generation_request` | 否 | 检查描述、图片和生成参数 |
| `reference_image_required` | 否 | 请上传一张参考图 |
| `reference_image_not_allowed` | 否 | 请移除图片或切换以图生图 |
| `generation_instruction_required` | 否 | 请描述希望保留和修改的内容 |
| `generation_quota_exceeded` | 否 | 今日额度已用完 |
| `provider_auth_failed` | 否 | 图像服务配置异常 |
| `provider_rate_limited` | 是 | 服务繁忙，任务将自动重试 |
| `provider_timeout` | 是 | 生成超时，任务将自动重试 |
| `provider_rejected` | 否 | 当前请求无法生成，请调整描述 |
| `invalid_provider_image` | 是一次 | 上游返回了无效图片 |
| `asset_save_failed` | 是 | 图片保存失败，可重试保存或重新生成 |

用户重试必须复用原 Job 输入，但创建新的 attempt 记录。已成功保存的结果不重复生成，除非用户选择“重新生成”。

## 15. 可观测性

每个 Job 记录：

- 启动来源：`intent` / `explicit_button`。
- 模式：文生图 / 以图生图。
- Provider 和实际模型。
- 上游请求 ID。
- 排队时间、模型耗时、保存耗时和总耗时。
- 尝试次数和最终状态。
- 请求生成数量与成功保存数量。
- 标准化错误码。
- 输入和输出文件大小，不记录图片二进制。

建议指标：

```text
image_generation_jobs_total
image_generation_success_total
image_generation_failure_total
image_generation_retry_total
image_generation_latency_ms
image_generation_queue_wait_ms
image_generation_provider_errors_total
```

## 16. 代码改动范围

### 16.1 后端

- `backend/app/schemas/ai.py`
  - 增加 `AIImageGenerationRequest` 和消息字段。
- `backend/app/services/ai_agent_contracts.py`
  - 注册 `image_generation_flow`。
- `backend/app/services/ai_orchestrator_service.py`
  - 增加确定性规则识别和冲突优先级。
- `backend/app/services/ai_intent_classifier_service.py`
  - 扩展分类 Schema 和提示词。
- `backend/app/services/ai_service.py`
  - 显式请求短路分类器并调用统一工作流。
- 新增 `backend/app/services/image_generation_provider.py`
  - Provider 协议、Mock 和 OpenAI-compatible Adapter。
- 新增 `backend/app/services/image_generation_workflow_service.py`
  - 输入校验、任务创建、配额和消息结果。
- 新增 `backend/app/services/image_generation_job_service.py`
  - Job claim、执行、重试、取消和恢复。
- 新增 `backend/app/models/image_generation.py`
  - Job 和 Asset 模型。
- 新增 Alembic migration。
- `backend/app/api/v1/ai.py`
  - 接收结构化请求并增加 Job 查询、重试、取消 API。
- `backend/app/core/config.py`
  - 增加图像 Provider 配置。
- `.env.example`
  - 增加无密钥的配置模板。

### 16.2 Web

- `frontend/src/views/AIAssistant.vue`
  - 增加模式选择、生成设置和结果卡片路由。
- 新增 `frontend/src/components/ai/ImageGenerationComposer.vue`
  - 输入区模式和参数。
- 新增 `frontend/src/components/ai/ImageGenerationCard.vue`
  - 状态、图片网格和操作。
- `frontend/src/api/ai.js`
  - 增加 Job 查询、重试和取消方法。

如果继续把所有逻辑堆入 `AIAssistant.vue`，组件复杂度会进一步上升，因此本功能应优先拆分组件，而不是只增加模板分支。

### 16.3 移动端

- `mobile-app/src/pages/AIAssistantPage.vue`
  - 扩展 `agentCapabilities` 和结构化提交。
- 新增 `mobile-app/src/components/ImageGenerationCard.vue`
  - 移动端结果卡片。
- 新增或扩展 `mobile-app/src/api/ai.ts`
  - Job API。
- 扩展 AgentTask TypeScript 类型。

## 17. 测试方案

### 17.1 后端单元测试

- 显式文生图请求绕过分类器并进入正确模式。
- 显式以图生图请求绕过分类器并进入正确模式。
- 自然语言文生图正确识别。
- 自然语言改图正确识别。
- 普通图片分析不会误触发生成。
- 创建灵感笔记不会误触发生成。
- 摄影领域 Prompt 会包含天气、光线、色调、环境、造型、道具、构图和姿势等引导。
- 合理但未出现在预设词表中的摄影创意不会被代码规则拒绝。
- 偏抽象的请求会被解释为摄影概念或触发澄清，而不是被摄影语义白名单拦截。
- 文生图带图片时拒绝。
- 以图生图只有图片、没有文字修改指令时拒绝。
- 以图生图没有图片或多于一张图片时拒绝。
- 同一幂等键只创建一个 Job。
- 用户不能查询、取消或重试其他用户的 Job。
- 达到配额时不会调用 Provider。
- `url` 和 `b64_json` 响应都能归一化。
- 无效图片、超大图片和伪造 MIME 被拒绝。
- 可重试错误按退避策略重试。
- Worker 崩溃后 stale Job 能恢复。
- 部分资产保存失败时进入 `partial`。

### 17.2 前端测试

- 模式选择和取消状态正确。
- 以图生图点击后自动打开图片选择器。
- 发送失败后恢复输入、附件、参数和模式。
- 生成中显示阶段而不是空白等待。
- 轮询只在活动 Job 和可见页面运行。
- 完成后停止轮询并展示结果。
- 重试和重新生成不会重复提交。
- 375px 宽度下没有横向溢出。
- 键盘可操作模式按钮、设置和结果操作。
- 减少动态效果设置下不播放非必要动画。

### 17.3 集成测试

- Mock Provider 完成文生图完整链路。
- Mock Provider 完成以图生图完整链路。
- Provider 超时后自动重试并最终成功。
- 页面刷新后从 Job 恢复生成状态。
- 会话历史重新加载后仍能打开结果图片。
- 取消排队任务后 Worker 不再调用 Provider。

## 18. 分阶段实施顺序

### 阶段一：契约和 Mock 闭环

1. 增加消息 Schema、意图和结构化显式入口协议。
2. 增加 Job/Asset 数据模型和迁移。
3. 实现 `MockImageGenerationProvider`。
4. 完成 Worker、查询、重试和取消 API。
5. 使用固定测试图片跑通后端闭环。

### 阶段二：Web 与移动端交互

1. Web 增加文生图和以图生图模式。
2. 移动端扩展现有 capability 列表。
3. 增加生成设置和结果卡片。
4. 完成轮询、恢复和错误反馈。
5. 完成前端单元测试和响应式检查。

### 阶段三：中转 API

1. 实现 OpenAI-compatible Provider。
2. 验证真实中转站的文生图和图片编辑端点。
3. 验证返回格式、参数映射、超时和错误结构。
4. 保存结果到项目媒体存储。
5. 增加配额、并发限制和调用审计。

### 阶段四：作品集增强

1. 增加“重新生成”和参数继承。
2. 增加管理端生成调用概览。
4. 在 README 和演示指南中说明 Provider 架构和 Mock 模式。

## 19. 验收标准

- 用户可以通过自然语言启动文生图或以图生图。
- 用户可以通过聊天框下方按钮明确选择生成模式。
- 显式按钮请求使用结构化协议，不依赖伪造提示词路由。
- 文生图不接受参考图片；以图生图第一版必须且只能上传一张参考图，并必须同时提交文字修改指令。
- 聊天请求快速返回 Job，不等待图片生成完成。
- 页面刷新、切换页面或重新进入会话后可以恢复任务状态。
- 模型结果保存到项目自己的媒体存储。
- Provider 不可用时任务保留，用户可以重试。
- Mock 模式下无需真实 API Key 也能演示完整交互。
- 中转 API 配置与聊天模型配置相互独立。
- 摄影语义通过 Prompt 进行开放式引导，不使用封闭的代码白名单。
- 权限、文件安全、配额、内容安全和 AI 标识继续使用后端硬约束。
- 生成任务具备幂等、配额、权限、审计和稳定错误码。
- Web 与移动端均满足 44px 触控目标、键盘焦点和生成状态反馈要求。

## 20. 推荐的第一版最终形态

第一版采用以下最小但完整的组合：

```text
一个统一 image_generation_flow
两个 mode：text_to_image / image_to_image
一个结构化 generation_request
一个独立 ImageGenerationProvider
一套 Job + Asset 数据模型
一个异步 Worker
Web 分段模式入口
移动端 capability 入口
一个通用生成结果卡片
Mock + OpenAI-compatible 两个 Provider
```

这个范围能够充分展示 Agent 意图路由、显式工具调用、异步任务、模型 Provider 抽象、媒体安全、错误恢复和跨端交互，同时避免第一版陷入复杂图片编辑器或 AMD 本地模型兼容问题。
