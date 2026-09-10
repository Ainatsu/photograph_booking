# AGENTS.md — 移动端（本仓库第二个移动端应用）

> 本目录是**新建的空目录**，下面描述的结构与命令是**要按此搭建的目标状态**。
> 动手写代码前，先读 §6 设计契约 和 §9 禁区。
> 目录名 `mobile-app-2/` 是占位名；确定正式名称后请连同本文、Capacitor `appId`、开发端口一起改。

## 1. 这是什么

本目录是本仓库内**第二个移动端应用**，与既有 `../mobile-app/` 并存。

- **同栈**：Ionic Vue + Capacitor + TypeScript。
- **同后端**：复用根目录 FastAPI 服务的既有接口，不新开接口。
- **独立代码**：与仓库内其他三个前端互不复用组件，只共享后端业务能力与数据结构。

| 目录 | 形态 | 与本目录的关系 |
| --- | --- | --- |
| `../frontend/` | Vue 3 + Element Plus 桌面端 | 不共享组件 |
| `../admin-frontend/` | 管理后台 | 不共享组件 |
| `../mobile-app/` | Ionic Vue + Capacitor 移动端 | 不共享组件；是本目录约定的参考实现 |
| `../backend/` | FastAPI | 唯一的接口来源 |

`../mobile-app/` 已实现完整业务闭环。本目录要做的是**同一批后端能力的另一套移动端呈现**，不是新功能。因此：数据怎么取、状态怎么流转，去 `../mobile-app/` 和 `../backend/` 找答案；界面怎么写，按 §6 自己决定。

### 1.1 本次重构要做什么

**把 `../mobile-app/` 的 40 个页面按新的设计语言重做一遍外观——只换皮，不改行为。**

- 页面集合、路由、数据来源、状态流转全部照搬 `../mobile-app/`，逐页对应关系见 `PAGES.md` §4。
- 唯一要改的是呈现层：配色、字体、间距、圆角、阴影、动效、布局。
- 可以重组底部 Tab 的主题与路由的 `path` / `name`（例外见 `PAGES.md` §7 的深链契约），但**页面与功能覆盖不能丢**。

判断标准：**用户看到的可以全变，用户能做的事和做完之后发生什么不能变。**

常见错误，都要避免：

- 把"重构外观"理解成"重新设计产品"，擅自增删功能、改导航结构、换业务规则。
- 觉得某个页面设计得不合理就顺手改掉它的交互逻辑——那是行为，不是外观。
- 照抄 `../mobile-app/` 的实现细节连同它的历史遗留一起搬过来（设计 token 的遗留见 `DESIGN.md` §12，页面级的见 `PAGES.md` §2）。

## 2. 技术栈

| 项 | 选型 |
| --- | --- |
| 框架 | Vue 3.5 + `<script setup>` + TypeScript |
| 移动端 UI | `@ionic/vue` 8，`mode: 'ios'` |
| 路由 | `@ionic/vue-router` + `vue-router` |
| 状态 | Pinia（setup store 写法） |
| 请求 | axios（单一实例 + 拦截器） |
| 图标 | `lucide-vue-next` |
| 构建 | Vite（别名 `@` → `./src`） |
| 测试 | Vitest（jsdom）+ `@vue/test-utils` |
| 原生打包 | Capacitor 7（Android） |
| 包管理 | npm |
| Node | `^20.19.0` 或 `>=22.12.0` |

**不要引入**：Element Plus、Tailwind、任何 React 系、uni-app / Taro、除 axios 外的请求库。

> Capacitor 的 `appId` 与 `../mobile-app/capacitor.config.ts` 的 `com.photographerbooking.mobile` **不同**（现为 `com.photographerbooking.mobile.redesign`），否则两个应用装在同一台设备上会互相覆盖；Android 原生工程也必须各自生成 `android/` 目录。
>
> 若本应用将来要**取代**原移动端，`appId` 必须改回 `com.photographerbooking.mobile` —— 应用商店的更新依赖 appId 稳定。

> `lucide-vue-next@1.0.0` 已被官方弃用（安装时会 warn），官方建议改用 `@lucide/vue`。当前与 `../mobile-app/` 保持一致继续用它；将来若迁移，两个应用一起换，不要只改一边。

## 3. 目录约定

沿用 `../mobile-app/src/` 的结构：

```text
src/
├─ api/          axios 实例（client.ts）+ 按后端领域拆分的接口模块
├─ components/   可复用 UI 组件
├─ composables/  组合式逻辑
├─ layouts/      应用壳（底部 Tab 等）
├─ pages/        页面：一级页 XxxPage.vue、详情页 XxxDetailPage.vue
├─ router/       index.ts —— 路由表与导航守卫
├─ stores/       Pinia store，一个领域一个文件
├─ test/         setup.ts —— Vitest 全局设置
├─ theme/        tokens.css 设计 token + 全局样式
├─ types/        与后端响应对齐的 TS 类型
└─ utils/        纯函数工具
```

命名与引用：

- 组件、页面文件用 PascalCase（`PackageCard.vue`、`DiscoverPage.vue`）。
- `api` / `stores` / `utils` / `types` 文件用 camelCase（`photographerApplications.ts`）。
- 单元测试与源文件**同目录同名**：`src/utils/format.test.ts`、`src/components/PackageCard.test.ts`。
- 跨目录引用一律走别名：`@/api/client`、`@/types/orders`；不要写 `../../` 相对路径。

## 4. 常用命令

```bash
npm install
npm run dev         # 开发服务器 http://127.0.0.1:5176
npm run typecheck   # vue-tsc --noEmit
npm test            # vitest run（CI 用）
npm run test:watch  # 本地开发用
npm run build       # typecheck + vite build
npm run preview
npm run cap:sync    # 同步 Web 产物到 Android 工程
npm run android     # 打开 Android Studio
```

端口与已有前端错开，`strictPort: true`；不要在没有说明理由的情况下改端口。

| 应用 | 端口 |
| --- | --- |
| `frontend` | 5173（Vite 默认） |
| `admin-frontend` | 5174 |
| `mobile-app` | 5175 |
| **本应用** | **5176** |

质量门禁 = `npm run typecheck`、`npm test`、`npm run build` 三条全过。本目录沿用 `../mobile-app/` 的做法**暂不配 ESLint / Prettier**；若要引入，先确认——它会牵扯仓库根配置与 CI。

Vite 配置基线（形状照抄 `../mobile-app/vite.config.ts`）：

```ts
const backendPort = process.env.PHOTOGRAPHER_BACKEND_PORT || '8000'
const backendHttpUrl = `http://127.0.0.1:${backendPort}`
const backendWsUrl = `ws://127.0.0.1:${backendPort}`

server: {
  host: '0.0.0.0',
  port: 5176,
  strictPort: true,
  proxy: {
    '/api':    { target: backendHttpUrl, changeOrigin: true },
    '/static': { target: backendHttpUrl, changeOrigin: true },
    '/ws':     { target: backendWsUrl, ws: true },
  },
},
// test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'] }
```

`src/test/setup.ts` 里 stub 掉 `IonIcon`，避免单测报未注册组件。

## 5. 后端接口与鉴权

启动后端（在仓库根目录）：

```powershell
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

接口全部挂在 `/api/v1`，另有 `/ws` WebSocket。分组：

`auth`、`users`、`photographers`、`photographer_applications`、`photographer_dashboard`、`orders`、`payments`、`projects`、`messages`、`notifications`、`likes`、`favorites`、`comments`、`follows`、`inspirations`、`recommendations`、`analytics`、`ai`、`admin`

约定：

- 所有请求走 `src/api/client.ts` 的**单一 axios 实例**（baseURL 取 `VITE_API_BASE_URL`，默认 `/api/v1`）。不要在组件里直接 `axios.get`，也不要另建实例。
- **鉴权**：登录后 token 存 `localStorage` 的 `token` 键；请求拦截器注入 `Authorization: Bearer <token>`。
- **401**：清除 token 并派发 `window` 上的 `auth:expired` 事件，由 `src/main.ts` 统一跳登录页。不要在页面里各写一套 401 处理。
- **错误文案**统一走 `getApiErrorMessage(error)`，不要直接用 `error.message` 拼提示。
- 后端错误体形状是 FastAPI 的 `{ detail: string | { message: string } }`。
- **类型直接对齐后端字段名**（snake_case，如 `avatar_url`、`display_name`），不做 camelCase 映射层。api 模块只负责解包响应（如 `data.work`），组件不直接消费原始响应对象。

环境变量（`.env.local`，参照 `../mobile-app/.env.example`）：

| 场景 | `VITE_API_BASE_URL` | `VITE_ASSET_BASE_URL` |
| --- | --- | --- |
| 浏览器开发 | `/api/v1` | 留空（走 Vite 代理） |
| Android 模拟器 | `http://10.0.2.2:8000/api/v1` | `http://10.0.2.2:8000` |
| 真机（同一局域网） | `http://<电脑局域网IP>:8000/api/v1` | `http://<电脑局域网IP>:8000` |

本地后端是 HTTP，同步 Android 工程前临时设 `CAPACITOR_LOCAL_HTTP=true`；正式打包连 HTTPS 时不要设，工程会恢复禁止明文与混合内容。

### 本机联调时的登录注意

`../README.md` 里列的演示账号（密码均为 `Demo123456!`）**要用用户名登录，不要用邮箱**：

| 账号 | 可用用户名 | 角色 |
| --- | --- | --- |
| 客户 | `demo_customer` | customer |
| 摄影师 | `demo_photographer` | photographer |

用邮箱登录会返回 401「邮箱或密码错误」，原因是 `authenticate_user` 只认**已验证的**邮箱（`backend/app/services/user_service.py:35`），而当前本地库（根目录 `photographer.db`）里没有 `email_verified` 列，验证状态无从判断。这是后端库结构与代码不同步导致的，**不是前端问题**，不要为此改前端。

另外注意根目录 `photographer.db` 才是活库，`backend/photographer.db` 是空文件。

## 6. 设计契约（强制）

分两份，各管一层，都必读：

| 文件 | 管什么 | 谁优先 |
| --- | --- | --- |
| **本目录 `DESIGN.md`** | token 取值、命名规则、组件状态映射、完整 CSS 定义 | **取值与命名听它** |
| `../design-system/MASTER.md` | 设计原则、导航结构、禁止清单、无障碍要求 | **原则与禁令听它；不得用「DESIGN.md 没写」绕过禁令** |

`src/theme/tokens.css` 的内容直接取 `DESIGN.md` §13，不要自己发明取值。**组件里不得出现写死的十六进制颜色、随机间距或随机圆角**，一律用语义变量。

另外：`DESIGN.md` §12 明确列出了**不继承** `../mobile-app/src/theme/tokens.css` 里的 `--neu-*`（12 个）与 `--d-*`（12 个）两组 token。**不要直接复制那份文件**，也不要复活这两组变量。

必须遵守的硬性约束（完整论述见 MASTER.md，取值见 `DESIGN.md`）：

- 点按目标最小 48×48px；间距用 4/8pt 节奏（4、8、12、16、20、24、32、40、48）。
- 圆角只有四档：8（紧凑）/ 12（控件）/ 16（卡片）/ 22（弹层）。
- 正文 16px 起、行高 ≥1.5；价格与计数用 tabular figures。
- 点按响应在 100ms 内可见；状态过渡 180–300ms；只动 `transform` 与 `opacity`。
- 一屏一个主操作；破坏性操作在空间上分离。
- 底部 Tab 恰好五个；详情页左上角有可预期的返回。
- 摄影内容优先：图像用 `aspect-ratio` 占位防抖动，首屏以下懒加载。
- 支持 `prefers-reduced-motion` / `prefers-reduced-transparency` / `prefers-contrast`；深浅色分别校验对比度（正文 4.5:1，大字号与大图标 3:1）。
- 颜色不得作为唯一的状态信号。

禁止：拟物与重度阴影、装饰性渐变、堆叠半透明表面、用 emoji 当结构图标、hover-only 操作、隐藏标签、任意 z-index、逐屏自造配色。

> ⚠️ 注意区分两份同名文件：`../design-system/MASTER.md` 才是本项目的移动端契约；`../design-system/default/MASTER.md` 是生成器产出的模板（字体 Playfair Display / Source Serif 4），与本项目无关，**不要采用**。

## 7. 代码约定

**各层的完整写法范式与边界见 `CODE.md`**（api / 状态层 / 视图层 / composables 与 utils / 类型 / 测试）。这里只列最容易被忽略、后果最重的几条：

- 组件一律 `<script setup lang="ts">` + 类型化 `defineProps` / `defineEmits`；Pinia 用 setup store。
- **页面加载数据用 `onIonViewWillEnter`，不是 `onMounted`。** Ionic 会缓存页面，`onMounted` 只在首次进入时执行，返回再进就拿不到新数据。
- 请求一律走 `src/api/client.ts` 的单一 axios 实例；错误文案统一走 `getApiErrorMessage`，不要自己拼。
- 异步刷新要带 `requestId` 守卫，防止慢响应覆盖新结果。
- `utils/` 是纯函数（不碰 Vue API、不发请求），必须配同目录测试；`composables/` 才是有状态的复用逻辑。
- 类型字段名照抄后端 snake_case，不引入 camelCase 转换层。
- 列表超过约 50 项要虚拟化或分页增量加载。

## 8. 路由与权限

**页面集合、路由总表、权限与深链契约见 `PAGES.md` §4 / §5 / §7。** 要点：

- 路由表集中在 `src/router/index.ts`，页面组件用 `() => import('@/pages/XxxPage.vue')` 懒加载。
- 权限只用两个 meta 标记（`requiresAuth` / `guestOnly`），守卫统一写在 `router.beforeEach`。这只是路由级粗粒度拦截，**不是授权**——服务端才是最终依据，不要用它替代后端校验。
- 角色差异（客户 / 摄影师）不通过路由区分，同一个页面按角色渲染不同内容。
- 需要登录态数据的页面，先等 `useAuthStore().initialize()` 完成再取数；不要在渲染期直接读 `localStorage`。
- **深链契约（`action_url` 格式与正则回退）不可擅改**，见 `PAGES.md` §7。

## 9. 禁区

- **不改业务行为。** 状态流转、接口调用与提交字段、角色权限、路由守卫语义，全部照搬 `../mobile-app/`。这是换皮，不是重做产品。页面与功能的对应关系见 `PAGES.md` §4。
- **不改深链契约。** 后端通知里的 `action_url` 格式与正则回退分支不能动，见 `PAGES.md` §7。
- **不改 `../backend/`**。接口不够用或字段不对，先说明再动后端，不要在前端用 mock 长期顶着。
- 不 import `../frontend/`、`../admin-frontend/`、`../mobile-app/` 里的任何文件。
- 不引入 §2 列出的禁用依赖；不新增 lint / 格式化工具链（先确认）。
- 不与 `../mobile-app/` 共用 Capacitor `appId`、`android/` 工程或构建产物。
- 不新增全局样式文件；除覆盖 Ionic 基础样式外不碰 Ionic 内部样式。
- 不在组件里拼接口 URL，不在组件里改名消费后端字段，不直接 `localStorage.setItem('token', ...)`（走 auth store）。

## 10. 完成标准

一次改动算完成，需要同时满足：

1. `npm run typecheck` 通过。
2. `npm test` 通过；新增的 `utils` 与关键组件有同目录测试。
3. `npm run build` 通过。
4. 在 375px 与 768px 宽度下自查：无横向滚动、无元素遮挡、无文字截断。
5. 涉及网络请求的页面，四种状态都有实现：加载中 / 空 / 错误（可重试）/ 无权限。
6. 深色模式与 `prefers-reduced-motion` 下自查无异常。
7. `CODE.md` §9 的代码自检清单逐条过（无 `@ts-ignore`、无第二 axios 实例、无自拼错误文案等）。
8. `DESIGN.md` §15 的设计自检清单逐条过。

涉及 Android 打包时追加 `npm run build && npm run cap:sync`。

**不要**在只跑通 dev server 的情况下宣布完成。

## 11. 相关文档

| 文档 | 用途 |
| --- | --- |
| **`DESIGN.md`**（本目录） | **token 取值、命名、组件状态与完整 CSS 定义的唯一执行规格（强制）** |
| **`PAGES.md`**（本目录） | **40 个页面 / 41 条路由 / 权限与深链契约的唯一执行规格（强制）** |
| **`CODE.md`**（本目录） | **api / 状态 / 视图 / utils / 类型 / 测试 各层写法与边界的唯一执行规格（强制）** |
| `../mobile-app/` | 页面与逻辑的参照实现；逐页对应关系见 `PAGES.md` §4 |
| `../design-system/MASTER.md` | 设计原则、导航结构、禁止清单（与 `DESIGN.md` 分工见 §6） |
| `../design-system/default/pages/` | 若存在对应页面文件，其规则**覆盖** MASTER.md |
| `../docs/rules/README.md` | 领域术语对照（方案=套餐=Package、企划=ShootProject、作品、应邀）与业务规则索引 |
| `../docs/rules/*.md` | 订单支付、方案、摄影师、用户、作品、企划的实际规则与数值 |
| `../docs/skills/apple-mobile-ui-SKILL.md` | 设计方法（MASTER.md 即由此推导） |
| `../mobile-app/README.md` | 同栈参考实现的能力清单与 Android 调试步骤 |
| `../backend/app/core/config.py` | 后端数值事实来源（时限、比例、限额） |
| `../README.md` | 整体架构与后端说明 |

界面用中文，术语按 `../docs/rules/README.md` 的对照表，不要自造同义词。文案写产品里会说的话，不要写成参数罗列。
