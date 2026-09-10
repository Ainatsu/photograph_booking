# CODE.md — 代码约定与写法范式

> 本文件是本应用**代码层面的唯一执行规格**：每层怎么写、边界在哪、什么时候用哪个工具。
>
> 权威边界：
> - **技术栈选型、依赖清单、目录结构、常用命令** → `AGENTS.md` §2 / §3 / §4。本文件不重复。
> - **每层的写法与边界**（api / store / 视图 / composables / utils / types / 测试） → 以本文件为准。
> - **样式与 token** → 以 `DESIGN.md` 为准。
> - **页面、路由与权限** → 以 `PAGES.md` 为准。
>
> 所有范式都取自 `../mobile-app/` 的实际代码，不是理想化建议。照着写就和现有代码库同构。

## 1. TypeScript 与工程配置

`tsconfig.json` 的关键项（照抄）：

| 项 | 值 | 说明 |
| --- | --- | --- |
| `strict` | `true` | 目标状态。不要为了绕开报错关掉它 |
| `target` | `ES2022` | |
| `moduleResolution` | `Bundler` | |
| `paths` | `@/*` → `src/*` | 与 Vite alias 保持一致，改一处要同时改两处 |
| `types` | `node`, `vite/client`, `vitest/globals` | |
| `include` | `src/**/*`、`vite.config.ts`、`capacitor.config.ts` | |

**本目录不配 ESLint / Prettier。** 这不是遗漏，是沿用 `../mobile-app/` 的做法——所以：

- 质量门禁只有三条：`npm run typecheck`、`npm test`、`npm run build`。
- 因为没有 lint，**格式与命名的一致性完全靠人**。写之前先看同目录的既有文件，跟着它的写法走。
- 想引入 lint 工具链要先确认，它会牵扯仓库根配置与 CI。

## 2. api 层

### 2.1 唯一实例

所有请求走 `src/api/client.ts` 里的单一 axios 实例。**组件与 store 里不允许出现 `axios.*`，也不允许再建实例。**

- `baseURL` 取 `VITE_API_BASE_URL`，默认 `/api/v1`；超时 12 秒。
- 请求拦截器注入 `Authorization: Bearer <token>`（token 取自 `localStorage.token`）。
- 响应拦截器处理 401：清 token 并派发 `window` 的 `auth:expired` 事件，由 `src/main.ts` 统一跳登录。**页面里不要再写一套 401 处理。**

### 2.2 模块组织

一个后端领域一个文件，文件名用 camelCase 复数或领域名：`auth.ts`、`orders.ts`、`messages.ts`、`photographerApplications.ts`。

每个文件的结构固定：

```ts
import api from './client'              // 注意：api 内部用相对路径引 client
import type { WorkItem } from '@/types/discovery'   // 其他一律用 @ 别名

export async function updateWorkMetadata(
  workId: string,
  metadata: WorkPublishMetadata,
): Promise<WorkItem> {
  const { data } = await api.put<WorkPublishResponse>(`/photographers/works/${workId}`, metadata)
  return data.work                      // 解包到调用方真正要的东西
}
```

规则：

- **函数名动词开头**：`getNotifications`、`markAllNotificationsRead`、`uploadCurrentUserAvatar`、`updateCurrentWork`。
- **显式标注返回类型**，响应结构用泛型写死在调用处：`api.post<{ access_token: string }>(...)`。
- **解包响应**：`const { data } = await api.x<T>(...)`。后端有信封结构时在 api 层拆开（`return data.work`），**组件不直接消费原始响应对象**。
- **不在 api 层 catch**。错误原样抛出，由调用方统一用 `getApiErrorMessage(error)` 转文案（见 §2.4）。
- `client` 用相对路径 `./client` 引入，其他模块从外部用 `@/api/client`——这是现有代码的既有写法，保持一致。

### 2.3 特殊请求形态

| 场景 | 写法 |
| --- | --- |
| 表单登录 | `new URLSearchParams()` + 显式 `headers: { 'Content-Type': 'application/x-www-form-urlencoded' }` |
| 文件上传 | `FormData` + `form.append('file', file)`，不要手动设 Content-Type |
| 查询参数 | 用 `params` 选项传对象，不要自己拼 querystring |

请求体字段名**直接用后端的 snake_case**（`challenge_id`、`verification_token`、`phone_verification_token`），**不做 camelCase 转换**。全仓库没有映射层，类型定义也照抄后端字段名。

### 2.4 错误文案

统一走 `src/api/client.ts` 导出的 `getApiErrorMessage(error)`：

```ts
import { getApiErrorMessage } from '@/api/client'
```

它已经处理了这些情况并给出中文文案：超时（`ECONNABORTED`）、无响应（提示后端是否在 8000 端口运行）、401、FastAPI 的 `{ detail: string | { message: string } }` 两种形状。

**不要在各页面自己拼 `error.message`。** 需要新增一类文案时改 `client.ts`，不要就地写。

## 3. 状态层（Pinia）

### 3.1 setup store 模式

一律 `defineStore('name', () => {...})`，不用 Options 写法：

```ts
export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<NotificationRecord[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const loaded = ref(false)

  let requestId = 0        // 非响应式句柄用普通 let，不要塞进 ref
  let revision = 0

  async function refresh() { /* ... */ }

  return { items, unreadCount, loading, loaded, refresh }
})
```

硬规则：

- **非响应式的东西用普通 `let`**：WebSocket 实例、定时器 id、请求序号、修订号。放进 `ref` 会造成无谓的响应式开销，也容易写出监听自身的 bug。
- 每个异步动作配 `loading` ref，并在 `finally` 里复位。需要区分"首次加载"和"刷新"时再加 `loaded`。
- **返回对象显式列出**要暴露的状态与方法，不要 `return { ...toRefs(state) }`。

### 3.2 并发与竞态

这是现有 store 里最容易被忽略、也最值得照抄的部分。异步刷新一律带序号守卫，防止慢响应覆盖新结果：

```ts
async function refresh() {
  const currentRequestId = ++requestId
  const startingRevision = revision
  loading.value = true
  try {
    const [nextItems, nextUnreadCount] = await Promise.all([...])
    if (currentRequestId !== requestId) return          // 已有更新的请求，丢弃本次结果
    items.value = startingRevision === revision
      ? mergeNotificationRecords(nextItems)
      : mergeNotificationRecords(nextItems, items.value) // 期间被本地改动过，不能整体覆盖
    loaded.value = true
  } finally {
    if (currentRequestId === requestId) loading.value = false
  }
}
```

两种守卫解决的问题不同，都要：

- `requestId` 防**旧响应覆盖新响应**。
- `revision` 防**服务端结果覆盖期间的本地改动**（比如乐观更新的已读状态被刷新冲掉）。

### 3.3 跨 store 与模块解耦

- store 之间直接调用：在 setup 里 `const auth = useAuthStore()`。
- 需要让互不相关的模块感知事件时，**派发 window CustomEvent**，常量导出供监听方复用：

```ts
export const MESSAGE_SOCKET_EVENT = 'messages:socket'
window.dispatchEvent(new CustomEvent(MESSAGE_SOCKET_EVENT, { detail: payload }))
```

现有的事件名：`messages:socket`、`auth:expired`。新增事件沿用 `域:动作` 命名。

- WebSocket 的**连接、重连、心跳全部收在 store 里**，不要下沉到页面。页面只读状态、只调方法。

## 4. 视图层

### 4.1 组件写法

- 一律 `<script setup lang="ts">`，不用 Options API。
- `defineProps` / `defineEmits` 用**类型化**写法，不要运行时对象写法。
- 样式写在 `<style scoped>`；全局样式只放 `src/theme/`。
- 图标用 `lucide-vue-next`，不用 emoji。图标按钮必须有 `aria-label`。

### 4.2 生命周期：必须用 Ionic 钩子

**这是本项目最容易踩的坑。** Ionic 会缓存页面实例，`onMounted` 只在首次进入时执行一次。用它会得到"第一次进页面有数据，返回再进就空"的 bug。

| 场景 | 用什么 |
| --- | --- |
| 页面进入（含缓存返回）时加载数据 | `onIonViewWillEnter` |
| 页面离开时清理 | `onIonViewWillLeave` / `onIonViewDidLeave` |
| 纯组件内部逻辑（不涉及页面激活） | `onMounted` 可用 |

```ts
import { onIonViewWillEnter } from '@ionic/vue'
onIonViewWillEnter(() => void load())
```

### 4.3 状态四态

每个网络页面都要实现加载 / 空 / 错误 / 无权限四态，用现成组件：`FeedSkeleton`（加载）、`StatePanel`（空、错误、无权限）。错误态必须带"重新加载"动作。详见 `PAGES.md` §6。

## 5. composables 与 utils 的边界

两者最容易混。判定标准只有一条：

| | `src/utils/` | `src/composables/` |
| --- | --- | --- |
| 是什么 | **纯函数** | **有状态的逻辑单元** |
| 能不能用 Vue API | **不能**（不 import `vue`、不读 `route`） | 可以（`ref`/`computed`/`useRoute`/`useRouter`） |
| 能不能发请求 | 不能 | 可以 |
| 返回 | 值 | `ref` + 方法的对象 |
| 必须有测试 | **是**，同目录同名 | 建议有 |

### 5.1 utils

纯计算与格式化，无副作用。用 `Intl` 做本地化，**不引日期库**：

```ts
const currencyFormatter = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' })
export function formatCurrency(value?: number | null): string {
  return currencyFormatter.format(Number(value || 0))
}
```

- 格式化函数要有**中文兜底文案**，不要返回 `''` 或 `'-'`：`return '时长面议'` / `'预算面议'` / `'时间待沟通'`。
- 共享的 `Intl.*Formatter` 提到模块顶层构造一次，不要每次调用都 new。
- 待测的纯逻辑必须放进 utils，不要埋在页面里。

### 5.2 composables

把跨页面复用的**有状态**逻辑抽到这里。现有只有一个 `useAgentTaskHandoff.ts`，范式是：命名 `use*`，内部取 `route`/`router`，维护 `loading` / `error` ref，返回 `{ 状态, 方法 }`；出错时**设置 `error` ref 而不抛**，让页面渲染错误态。

不要为了"看起来整洁"把只用在一个页面的逻辑抽成 composable——那会分散阅读成本。

## 6. 类型

- 按领域一个文件放在 `src/types/`：`auth.ts`、`discovery.ts`、`orders.ts`、`messages.ts`、`inspiration.ts`、`publishing.ts`、`photographerApplication.ts`、`notifications.ts`、`engagement.ts`、`social.ts`、`agentTask.ts`、`agentForm.ts`。
- **字段名照抄后端 snake_case**（`avatar_url`、`display_name`、`normalized_username`、`phone_verification_token`），请求体也一样。全仓没有 camelCase 映射层，不要引入。
- 响应类型与请求体类型放同一个领域文件里（如 `UserProfile` 与 `RegisterPayload` 都在 `types/auth.ts`）。
- 宽松字段用联合类型显式列出已知取值再兜底：`role: 'customer' | 'photographer' | string`。
- 枚举值用字符串字面量联合，不要用 TS `enum`。

## 7. 测试

现有 36 个测试文件（`src/**/*.test.ts`），全部遵循同一套约定：

| 约定 | 说明 |
| --- | --- |
| 位置 | **与源文件同目录同名**：`src/utils/format.ts` ↔ `src/utils/format.test.ts`；`src/components/AppTopBar.vue` ↔ `src/components/AppTopBar.test.ts` |
| 导入被测对象 | 相对路径 `./AppTopBar.vue`、`./format` |
| 环境 | jsdom；`globals: true` 且 `vitest/globals` 在 tsconfig `types` 里 |
| **但显式导入** | 36/36 个文件都写 `import { describe, expect, it } from 'vitest'`。**即使配了 globals 也不要依赖它**，保持一致 |
| 用例名 | 中文，描述行为：「点击搜索按钮后切换栏变为搜索输入框」 |
| 组件测试 | `mount` from `@vue/test-utils`；断言优先打 `aria-label` 等可访问属性，不要靠内部 class 名耦合 |
| 需要真实 DOM | 加 `attachTo: document.body`，并在用例末尾 `wrapper.unmount()` 清理（`AppTopBar.test.ts`、`ImageGenerationCard.test.ts` 是范例） |
| 需要 mock | `vi.fn` / `vi.mock`（8 个文件在用） |
| 全局 stub | `src/test/setup.ts` 里 stub 掉 `IonIcon`，避免"未注册组件"报错 |
| **页面级测试** | 必须让 stub 透传插槽，见下 |

要点：

- **`renderStubDefaultSlot` 必须打开。** VTU 的默认 stub 会**把插槽内容整块吃掉**，`{ ion-page: true }` 会让 `ion-page-stub` 变成空元素，里面的表单一个都找不到。`src/test/setup.ts` 里已设 `config.global.renderStubDefaultSlot = true`。这是写页面级测试时最容易踩的坑。
- 页面级测试用 `createMemoryHistory` 建真实 router，把断言落在 `router.currentRoute.value.path` 上，比 spy `router.push` 更接近真实行为。
- Ionic 容器组件（`IonPage` / `IonContent` / `IonSpinner`）和依赖 Ionic 上下文的组件（`DetailHeader`）在 jsdom 里都要 stub，只断言自己写的逻辑。
- **优先测 `utils` 与数据转换**，它们是纯函数、成本最低、最容易覆盖边界（空值、0、超长文本、非法日期）。
- **组件测试测行为，不测样式**。样式由 `DESIGN.md` 约束，不写断言。
- 断言优先打 `aria-label`、`aria-invalid`、`aria-describedby` 这类可访问属性，而不是内部 class 名——前者是契约，后者是实现细节。
- **被测行为如果"看起来像 bug"，先确认参照实现怎么写的。** 这是换皮项目，参照实现的既有行为要用测试钉住，而不是顺手改好。范例见 `src/pages/LoginPage.test.ts` 里关于提交校验短路的三个用例。
- 测试数量不是目标。`PAGES.md` §8 提到的 10 个组件测试覆盖的是**交互与无障碍行为**——这些行为在重构中不能丢，所以这些测试要么迁移要么重写，不要直接删。

## 8. 依赖引入规则

- 已定选型见 `AGENTS.md` §2。**不要引入** Element Plus、Tailwind、React 系、uni-app / Taro、除 axios 外的请求库。
- 日期格式化用 `Intl`，不引 dayjs / date-fns。
- 新增任何依赖前先确认：这会进 `package.json`，影响构建体积与供应链。
- 该自己写的就自己写。`debounce` 这类二十行的工具没必要引包（现有 `src/utils/debounce.ts` 就是自己写的，带中文 JSDoc）。

## 9. 自检清单

提代码前逐条过：

1. `npm run typecheck` 通过，且**没有为了过检而加 `@ts-ignore` / `as any`**。
2. 没有在组件或 store 里直接 `axios.*`；没有第二个 axios 实例。
3. 没有在页面里自己拼错误文案，错误都走 `getApiErrorMessage`。
4. 页面数据加载用的是 `onIonViewWillEnter`，不是 `onMounted`。
5. 异步刷新动作带 `requestId` 守卫；涉及本地改动的带 `revision` 守卫。
6. 纯逻辑在 `utils/` 且有同目录测试；有状态复用逻辑在 `composables/`。
7. 类型字段名与后端一致（snake_case），没有引入转换层。
8. 测试用中文用例名、显式 `from 'vitest'`；用 `attachTo` 的用例有 `unmount()`。
9. 新增依赖前已确认过（见 §8）。
10. 没有为了"整洁"重构既有代码的组织方式——这是换皮项目，行为与结构都保持稳定。
