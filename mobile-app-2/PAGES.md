# PAGES.md — 页面清单与路由规格

> 本文件是本应用**页面集合、路由、权限与深链契约**的唯一执行规格。
> 目标：**外观重构，行为不变。** 页面、路由、数据流、状态机都参照 `../mobile-app/`，只重做呈现层。
>
> 权威边界：
> - **有哪些页面、每页路由与权限、数据从哪来** → 以本文件为准。
> - **页面怎么长** → 以 `DESIGN.md` 为准。
> - **工程约定与命令** → 以 `AGENTS.md` 为准。
> - **业务规则与数值**（订单状态机、退款梯度、时限） → 以 `../docs/rules/*.md` 与 `../backend/` 为准，本文件不重复。

## 1. 重构的性质

这不是重做产品，是**换皮**。因此：

| 可以改 | 不可以改 |
| --- | --- |
| 视觉：配色、字体、间距、圆角、阴影、动效 | 页面集合与功能覆盖（40 个页面，一个都不能丢） |
| 布局与信息层级（同一页内怎么排版） | 每页的数据来源、调用的接口、提交的字段 |
| 底部 Tab 的主题与图标 | 底部 Tab 的**数量**（设计契约要求恰好五个） |
| 路由的 `path` 与 `name`（见 §7 的三条例外） | 订单/企划/交付/争议的状态流转与角色权限 |
| 组件内部的实现方式 | 深链契约的字符串格式（见 §7） |

一句话判断标准：**用户看到的可以全变，用户能做的事和做完之后发生什么不能变。**

### 1.1 已确认的范围决定

| 决定 | 日期 | 说明 |
| --- | --- | --- |
| 作品详情页**保持现有结构**，只换视觉 | 2026-09-10 | `reference/作品详情页-*.jpg` 那种社区内容形态（图片轮播 + 话题标签 + 楼中楼评论 + 底部"说点什么"输入条）**不采纳**。`WorkDetailPage` 继续沿用参照实现的信息架构与交互，只重做呈现层 |
| 促销横幅不做 | 2026-09-10 | 理由见 `DESIGN.md` §1.2 |
| 摄影师完成率按 API 原值显示 | 2026-09-10 | 参照实现的 `formatDashboardPercent` 做了 `(value * 100)`，但 `/orders/dashboard/public/{id}` 的 `completion_rate` **已经是百分数**（实测返回 `80`），界面上会显示成「8000%」。这是显示缺陷而非既有行为，本应用按原值渲染为「80%」 |

第一条尤其重要：参考图里有一张与其余 9 张不属于同一形态，容易让人误以为整个详情页要改成社区流。**不要**因为图长成那样就给它加评论区、加底部点赞收藏条——那会同时违反本节的"行为不变"与上表。

## 2. 资产盘点

参照实现 `../mobile-app/` 的实际清点结果：

| 项 | 数量 | 说明 |
| --- | --- | --- |
| 页面组件文件 | **40** | `../mobile-app/src/pages/*.vue` |
| 有路由的页面组件 | **38** | 其中 3 个组件各服务 2 条路由（见下） |
| 路由记录 | **41** | 5 条 Tab 子路由 + 36 条根级路由 |
| 无路由的页面文件 | **2** | `DraftsPage.vue`、`UserContentPage.vue` —— 见 §2.2 |
| 共享组件 | 34 | `../mobile-app/src/components/*.vue` —— 见 §8 |
| api 模块 | 19 | `../mobile-app/src/api/*.ts`（另 3 个 `.test.ts`） |
| 底部 Tab | 5 | 发现 / 橱窗 / ＋发布 / 消息 / 我的 |

**一个组件服务两条路由**（编辑页复用新建页，靠有无 `:id` 参数区分模式）：

| 组件 | 路由 A（新建） | 路由 B（编辑） |
| --- | --- | --- |
| `PackagePublishPage` | `/publish/package` | `/packages/:packageId/edit` |
| `ProjectPublishPage` | `/publish/project` | `/projects/:projectId/edit` |
| `InspirationEditPage` | `/inspirations/new` | `/inspirations/:inspirationId/edit` |

重建时保留这个模式，不要拆成两个组件。

### 2.1 `/tabs/publish` 已决定保留

`/tabs/publish` → `PublishPage.vue`：路由存在，但底部 Tab 的第三个按钮**不导航**，而是打开 `PublishActionSheet`（三个发布入口都在面板里）。全仓库没有任何地方 `push` 到这个路由名或路径。

**决定（2026-09-10）：保留。** 它只靠直接输入 URL 可达，`PublishPage` 保留为将来可能用到的发布落地页。

因此重建时：

- 路由与页面都保留，**不要因为"没有入站入口"就当作死代码删掉**。
- 不要给它加入站链接——那会改变现有导航行为（Tab 第三位应当继续打开动作面板）。
- 该页面的内容按普通页面实现即可，参照实现里它是 353 行的发布入口页。

### 2.2 两个无路由的页面文件

| 文件 | 是什么 | 判断 |
| --- | --- | --- |
| `UserContentPage.vue` | 带分段切换的用户主页内容页（作品／方案／企划） | 已被 `/users/:userId/works`、`/users/:userId/packages`、`/users/:userId/projects` 三个独立页面取代。**属死代码，不重建** |
| `DraftsPage.vue` | 本机草稿列表（发布时自动存在本机的文字草稿） | 功能完整但从未接线。**先确认是否要这个功能**，再决定是否给它路由 |

两者都是**完整实现**，不是空壳，所以不能靠"看着像废弃"来删。要按上表逐条确认。

## 3. 信息架构与底部导航

现状：五个 Tab，中间第三个不是页面而是**发布动作面板**（`PublishActionSheet`，从底部弹出，内含发布作品/方案/企划三个入口）。

| Tab | 标签 | 图标 | 路由 | 备注 |
| --- | --- | --- | --- | --- |
| 1 | 发现 | `Compass` | `/tabs/discover` | 默认落地页 |
| 2 | 橱窗 | `Store` | `/tabs/showcase` | |
| 3 | ＋发布 | `Plus`（实心圆底） | 无（打开 ActionSheet） | 承载三个发布入口 |
| 4 | 消息 | `MessageCircle` | `/tabs/messages` | 带未读角标，>99 显示 `99+` |
| 5 | 我的 | `UserRound` | `/tabs/profile` | |

约束：

- **Tab 数量必须是 5**，这是 `../design-system/MASTER.md` 的硬性要求。可以换主题、换图标、换标签文案，不能变成 4 个或 6 个。
- 发布入口的"中间凸起圆底按钮 + 动作面板"是当前形态。如果重做成别的形态（比如独立 Tab 或悬浮按钮），仍要保证三个发布流程都能到达。
- 未读角标的无障碍名称必须带上数量（现状是 `消息，共 N 条未读内容`）。
- 非 Tab 页面统一在左上角提供返回，保留返回栈状态。

## 4. 路由规格总表

列的含义：**参照实现**是重建时抄逻辑的文件；**数据源**是该页面直接 import 的 api 模块。权限取值为 `公开` / `需登录` / `仅游客`。

### 4.1 底部 Tab

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 发现 | `DiscoverPage` | `/tabs/discover` | `discover` | 公开 | discovery, engagement |
| 2 | 橱窗 | `ShowcasePage` | `/tabs/showcase` | `showcase` | 公开 | discovery, recommendations |
| 3 | 发布（无入口） | `PublishPage` | `/tabs/publish` | `publish` | 公开 | — |
| 4 | 消息列表 | `MessagesPage` | `/tabs/messages` | `messages` | 需登录 | messages |
| 5 | 我的 | `ProfilePage` | `/tabs/profile` | `profile` | 公开 | discovery, inspirations, orders, projects, social |

### 4.2 内容与详情

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | 作品详情 | `WorkDetailPage` | `/works/:workId` | `work-detail` | 公开 | discovery, engagement, social |
| 7 | 作品图库 | `WorksGalleryPage` | `/works/gallery` | `works-gallery` | 需登录 | discovery |
| 8 | 摄影师主页 | `PhotographerDetailPage` | `/photographers/:userId` | `photographer-detail` | 公开 | dashboard, discovery, social |
| 9 | 方案详情 | `PackageDetailPage` | `/packages/:packageId` | `package-detail` | 公开 | discovery, engagement, social |
| 10 | 企划详情 | `ProjectDetailPage` | `/projects/:projectId` | `project-detail` | 公开 | discovery |
| 11 | 用户作品 | `UserWorksPage` | `/users/:userId/works` | `user-works` | 公开 | discovery |
| 12 | 用户方案 | `UserPackagesPage` | `/users/:userId/packages` | `user-packages` | 公开 | discovery |
| 13 | 用户企划 | `UserProjectsPage` | `/users/:userId/projects` | `user-projects` | 公开 | discovery |

### 4.3 发布与摄影师经营

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 14 | 发布作品 | `WorkPublishPage` | `/publish/work` | `publish-work` | 需登录 | publishing |
| 15 | 编辑作品 | `WorkEditPage` | `/works/:workId/edit` | `work-edit` | 需登录 | discovery, works |
| 16 | 发布方案 | `PackagePublishPage` | `/publish/package` | `publish-package` | 需登录 | packages, publishing |
| 17 | 编辑方案 | `PackagePublishPage` | `/packages/:packageId/edit` | `package-edit` | 需登录 | packages, publishing |
| 18 | 方案管理 | `PackageManagementPage` | `/packages/manage` | `package-management` | 需登录 | packages |
| 19 | 摄影师看板 | `PhotographerDashboardPage` | `/photographer/dashboard` | `photographer-dashboard` | 需登录 | dashboard |
| 20 | 档期与服务能力 | `PhotographerSettingsPage` | `/photographer/settings` | `photographer-settings` | 需登录 | availability |

### 4.4 企划与应邀

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 21 | 发布企划 | `ProjectPublishPage` | `/publish/project` | `publish-project` | 需登录 | discovery, projects, publishing |
| 22 | 编辑企划 | `ProjectPublishPage` | `/projects/:projectId/edit` | `project-edit` | 需登录 | discovery, projects, publishing |
| 23 | 企划与应邀管理 | `ProjectManagementPage` | `/projects/manage` | `project-management` | 需登录 | projects |
| 24 | 应邀报价 | `ProjectApplyPage` | `/projects/:projectId/apply` | `project-apply` | 需登录 | discovery, projects, publishing |
| 25 | 候选人比较 | `ProjectCandidatesPage` | `/projects/:projectId/candidates` | `project-candidates` | 需登录 | discovery, projects |

### 4.5 预约与订单

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 26 | 预约下单 | `BookingPage` | `/booking/:userId?` | `booking` | 需登录 | discovery, orders, recommendations |
| 27 | 订单队列 | `OrdersPage` | `/orders` | `orders` | 需登录 | orders, projects |
| 28 | 订单详情 | `OrderDetailPage` | `/orders/:orderId` | `order-detail` | 需登录 | orders |

> ⚠️ 第 28 条的 `path` 与 `name` 受 §7 的深链契约约束，不要改。

### 4.6 消息与通知

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 29 | 会话 | `ConversationPage` | `/messages/:userId` | `conversation` | 需登录 | messages |
| 30 | 通知中心 | `NotificationsPage` | `/notifications` | `notifications` | 需登录 | notifications（经 store） |

### 4.7 社交与灵感

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 31 | 关注与粉丝 | `SocialPage` | `/social` | `social` | 需登录 | engagement, social |
| 32 | 灵感仓库／地图 | `InspirationsPage` | `/inspirations` | `inspirations` | 需登录 | inspirations |
| 33 | 新建灵感 | `InspirationEditPage` | `/inspirations/new` | `inspiration-new` | 需登录 | inspirations |
| 34 | 编辑灵感 | `InspirationEditPage` | `/inspirations/:inspirationId/edit` | `inspiration-edit` | 需登录 | inspirations |
| 35 | 灵感详情 | `InspirationDetailPage` | `/inspirations/:inspirationId` | `inspiration-detail` | 需登录 | inspirations |

灵感页有一个**页内视图切换**：`仓库`（列表 + 搜索 + 状态筛选）与 `地图`（`InspirationMapPanel`）。重建时保留这个切换，不要拆成两个路由——`../frontend/` 桌面端拆成了独立的 `InspirationRepository` 与 `InspirationMap`，移动端是合并的，这是有意的差异。

### 4.8 账号与身份

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 36 | 登录 | `LoginPage` | `/login` | `login` | 仅游客 | client |
| 37 | 注册 | `RegisterPage` | `/register` | `register` | 仅游客 | auth |
| 38 | 账号与安全 | `AccountSettingsPage` | `/account/settings` | `account-settings` | 需登录 | auth, availability |
| 39 | 摄影师认证 | `PhotographerApplicationPage` | `/photographer/application` | `photographer-application` | 需登录 | photographerApplications |

### 4.9 搜索与 AI

| # | 页面 | 参照实现 | 路由 path | route name | 权限 | 数据源 |
| --- | --- | --- | --- | --- | --- | --- |
| 40 | 搜索结果 | `SearchResultsPage` | `/search` | `search` | 公开 | discovery |
| 41 | AI 助手 | `AIAssistantPage` | `/ai/assistant` | `ai-assistant` | 需登录 | ai, agentTasks, recommendations |

`AIAssistantPage` 是全仓库最大的单页（也是唯一的对话式界面），重建工作量按最大估。

## 5. 权限模型

只有两个 meta 标记，守卫统一写在 `router.beforeEach`：

| meta | 含义 | 未满足时 |
| --- | --- | --- |
| `requiresAuth: true` | 需登录 | 跳 `login`，带 `query.redirect` 记录原目标 |
| `guestOnly: true` | 仅未登录可见 | 已登录时跳 `profile` |

判定依据是 `localStorage` 里有没有 `token`。**注意这只是路由级粗粒度拦截**，不是授权：

- 免登录页面（`/tabs/discover`、`/tabs/profile`、各详情页、`/search`）内部仍可能因未登录而呈现不同内容或无权限态，页面自己要处理。
- 服务端才是授权的最终依据。前端的 `requiresAuth` 只是体验优化，不要用它替代后端校验。
- 角色差异（客户 / 摄影师）不通过路由区分。同一个页面（如 `OrdersPage`、`ProfilePage`）按角色渲染不同内容，重建时不要为了"清晰"拆成两套路由，那会破坏已有的深链。

`/tabs/profile` 与 `PhotographerDetailPage` 等标为"公开"，是因为未登录也能看到基础信息，但登录后内容更多。重建时保留这种"同页分级呈现"。

## 6. 页面状态四态约定

每个涉及网络请求的页面都必须实现四态，缺一不算完成。可复用的组件已存在：

| 状态 | 用什么 | 参照 |
| --- | --- | --- |
| 加载中 | `FeedSkeleton`（列表/卡片）或 `ion-spinner`（局部动作） | `DiscoverPage` |
| 空 | `StatePanel`（无 `tone`），带一个引导性主操作 | `InspirationsPage` |
| 错误 | `StatePanel` `tone="error"`，必须带"重新加载"动作 | `InspirationsPage` |
| 无权限 / 找不到 | `StatePanel` `tone="error"`，文案说明原因 | `InspirationDetailPage` |

其他约定：

- 列表页支持下拉刷新（`ion-refresher`，`pulling-text="下拉刷新"`）。
- 进入页面时用 `onIonViewWillEnter` 而非 `onMounted` 触发加载——Ionic 会缓存页面，`onMounted` 只在首次执行，返回时数据不会刷新。这是本项目里最容易踩的坑。
- 提交类动作要防重复提交（禁用按钮 + 进度），关键写操作要幂等。
- 长表单（发布作品/方案/企划）保留本机文字草稿，离开前有未保存内容要确认。
- 破坏性操作（删除、取消订单、撤回应邀）必须二次确认，确认文案写明后果。

## 7. 深链契约（不可擅自改的部分）

后端会在通知里写入前端路径，这条链路跨三层，改错会**静默**失效（通知点进去跳不动，但没有任何报错）：

```
backend/app/services/notification_service.py:153
  action_url = f"/projects/{aggregate_id}"  或  f"/orders/{aggregate_id}"
        ↓ 写入数据库列 OrderNotification.action_url（backend/app/models/notification.py:45）
        ↓ 由 API 返回（backend/app/schemas/notification.py:17）
        ↓
  移动端：mobile-app/src/utils/notification.ts:55-64
    优先用 order_id / project_id 字段，按 route name 跳转；
    两者都没有时，才用正则 /^\/(orders|projects)\/(\d+)/ 解析 action_url。← 历史通知只有 action_url
        ↓
  桌面端：frontend/src/views/Notifications.vue:58
    router.push(item.action_url)  ← 直接把这个字符串当路径用，
    且桌面路由确实是 /orders/:orderId 与 /projects/:projectId
```

由此得出三条硬约束：

1. **`action_url` 的字符串格式 `/orders/{id}`、`/projects/{id}` 由后端与桌面端共同冻结**，不属于本应用可改范围。新应用不能要求后端改格式。
2. **正则回退分支不能删。** 数据库里已有的历史通知没有 `order_id` / `project_id` 字段，只有 `action_url`；删掉回退它们就失去跳转目标。`../mobile-app/src/utils/notification.test.ts` 覆盖了 `/orders/21` 与 `/projects/11` 两种情况。
3. **新应用可以改自己的路由 `path` 与 `name`**，因为通知走的是 `action_url` → 本应用内的 name 映射。但改 `name` 时必须同步改本应用的 `notification.ts` 解析函数；改 `path` 会让已分享出去的链接失效（通知不受影响）。

除通知外的其他深链入口同样要保留：会话（`/messages/:userId`）、作品（`/works/:workId`）、方案（`/packages/:packageId`）、企划（`/projects/:projectId`）、摄影师主页（`/photographers/:userId`）。这些是分享链接与站内跳转的目标。

## 8. 共享组件盘点

34 个组件是外观重构的**主战场**——改完它们，多数页面的外观自动跟着变。按用途分组：

| 组 | 组件 |
| --- | --- |
| 骨架与导航（4） | `AppTopBar`、`DetailHeader`、`DetailActionBar`、`SegmentSwitch` |
| 状态与占位（3） | `FeedSkeleton`、`StatePanel`、`MediaPlaceholder` |
| 卡片（7） | `WorkCard`、`PackageCard`、`BookablePackageCard`、`ProjectCard`、`PhotographerCard`、`InspirationCard`、`InspirationQuickEntryCard` |
| 互动与媒体（4） | `EngagementPanel`、`AvatarImage`、`ImageCarousel`、`InspirationMapPanel` |
| 表单与发布（8） | `PublishActionSheet`、`PublishMediaPicker`、`PublishAgentPolishButton`、`SelectedFileList`、`TagEditor`、`DiscoveryFilters`、`JointRecommendationFilters`、`SearchField` |
| AI（8） | `AIConversationPanel`、`AIPageContextCard`、`AIShootContextCard`、`AIWebReferenceImages`、`AgentTaskFormCard`、`AgentTaskSummaryCard`、`ImageGenerationCard`、`DetailAgentAction` |

优先顺序建议：**先做 `StatePanel` / `FeedSkeleton` / 卡片组 / `AppTopBar` / `DetailHeader`**，它们覆盖面最广；AI 组的 8 个组件只服务 `AIAssistantPage` 及其详情页嵌入，可以最后做。

注意：`../mobile-app/src/components/` 里有 10 个 `.test.ts`，重建时这些测试要么迁移要么重写，但**不要为了省事直接删**——它们覆盖了交互与无障碍行为，而行为是不变的部分。`../mobile-app/src/api/` 下另有 3 个（`auth`、`photographerApplications`、`recommendations`）。

## 9. 建议的建造顺序

按"先骨架后细节、先消费后生产"排，每步都能独立验证：

1. **骨架**：`src/main.ts`（Ionic `mode: 'ios'` + 主题初始化）、`src/theme/tokens.css`（取自 `DESIGN.md` §13）、`AppTopBar`、`DetailHeader`、`StatePanel`、`FeedSkeleton`、`TabsLayout` 五 Tab。
2. **内容消费**：`DiscoverPage`、`ShowcasePage`、`WorkDetailPage`、`PhotographerDetailPage`、`PackageDetailPage`（含卡片组）。
3. **账号**：`LoginPage`、`RegisterPage`、`ProfilePage`、`AccountSettingsPage`。
4. **交易**：`BookingPage`、`OrdersPage`、`OrderDetailPage`。
5. **生产**：三个发布页 + 两个管理页 + `PhotographerDashboardPage` + `PhotographerSettingsPage`。
6. **企划**：`ProjectPublishPage`、`ProjectManagementPage`、`ProjectApplyPage`、`ProjectCandidatesPage`。
7. **社交与灵感**：`SocialPage`、`InspirationsPage`（含地图视图）、`InspirationEditPage`、`InspirationDetailPage`。
8. **消息与通知**：`ConversationPage`、`MessagesPage`、`NotificationsPage`（先确认 §7 的深链映射已就位）。
9. **AI**：`AIAssistantPage` 及其 8 个专属组件。
10. **收尾**：处理 §2.1 的 `/tabs/publish` 与 §2.2 的两个孤儿页面。

### 9.1 逐页进度

状态口径：**✅ 已完成**＝视觉已重写、路由已接真实组件、接真实数据验证过；**🔄 进行中**；**⏳ 未开始**＝仍是 `PlaceholderPage` 占位。

| 步骤 | 状态 | 页面 |
| --- | --- | --- |
| 1. 骨架 | ✅ | `main.ts` / `tokens.css` / `AppTopBar` / `DetailHeader` / `StatePanel` / `FeedSkeleton` / `TabsLayout` |
| 2. 内容消费 | ✅ | `DiscoverPage` ✅、`ShowcasePage` ✅、`WorkDetailPage` ✅、`PhotographerDetailPage` ✅、`PackageDetailPage` ✅、`SearchResultsPage` ✅ |
| 3. 账号 | ✅ | `LoginPage` ✅、`ProfilePage` ✅、`RegisterPage` ✅、`AccountSettingsPage` ✅ |
| 4. 交易 | ⏳ | `BookingPage`、`OrdersPage`、`OrderDetailPage` |
| 5. 生产 | ⏳ | `WorkPublishPage`、`WorkEditPage`、`PackagePublishPage`、`PackageManagementPage`、`PhotographerDashboardPage`、`PhotographerSettingsPage` |
| 6. 企划 | ⏳ | `ProjectPublishPage`、`ProjectManagementPage`、`ProjectApplyPage`、`ProjectCandidatesPage` |
| 7. 社交与灵感 | ⏳ | `SocialPage`、`InspirationsPage`、`InspirationEditPage`、`InspirationDetailPage` |
| 8. 消息与通知 | ⏳ | `ConversationPage`、`MessagesPage`、`NotificationsPage` |
| 9. AI | ⏳ | `AIAssistantPage` 及其 8 个专属组件 |
| 10. 收尾 | ⏳ | `/tabs/publish` 的形态决定、`PublishPage` 内容、§2.2 的两个孤儿页面 |

**§8 的 34 个共享组件不做单独排期**：跟着用到它的页面一起落地。目前已完成的有 `AppTopBar`、`DetailHeader`、`DetailActionBar`、`DetailAgentAction`、`StatePanel`、`FeedSkeleton`、`SegmentSwitch`、`AvatarImage`、`MediaPlaceholder`、`WorkCard`、`PackageCard`、`ProjectCard`、`PhotographerCard`、`ImageCarousel`、`EngagementPanel`、`DiscoveryFilters`、`PublishActionSheet`。

更新约定：每完成一页就把上表对应项改成 ✅，并同步 `src/router/index.ts` 里该路由从 `placeholder()` 换成真实组件。**两处都要改**——只改页面文件不接路由，页面不会被渲染；只改路由不写页面，就是白屏。

## 10. 验收核对清单

1. §4 的 **41 条路由逐条可达**，且 38 个页面组件全部用上（不多不少）。
2. 四个 Tab 页 + 详情页的**四态**（加载 / 空 / 错误 / 无权限）都实现。
3. 所有需登录页面在未登录时正确跳转，且登录后能回到原目标（`redirect` 生效）。
4. 通知深链可用：造一条只有 `action_url`（无 `order_id`）的通知，点击能到达订单/企划详情。
5. 底部 Tab 是 **5 个**，未读角标的无障碍名称带数量。
6. 返回栈正确：从详情页返回保持列表滚动位置与筛选状态。
7. 使用 `onIonViewWillEnter` 的页面在返回时确实重新加载。
8. 破坏性操作都有二次确认，文案写明后果。
9. `../mobile-app/src/components/` 里 10 个组件测试覆盖的行为在重建中未丢失。
10. 375px 与 768px 下无横向滚动、无截断、底部内容不被 Tab 栏遮住。
