# DESIGN.md — 移动端设计契约（token 与组件状态规格）

> 本文件是本应用 **token 取值、命名与组件状态**的唯一执行规格。
>
> 权威边界：
> - **取值、命名、组件状态映射** → 以本文件为准。
> - **设计原则、导航结构、禁止清单、无障碍要求** → 以 [`../design-system/MASTER.md`](../design-system/MASTER.md) 为准；本文件是它的执行层细化，不重复其原则论述。
> - 两者冲突时：数值与命名听本文件，原则与禁令听 MASTER.md，且**不得用「本文件没写」绕过禁令**。
>
> 视觉方向取自 `reference/` 里的 10 张截图（米画师 / 约稿交易平台形态）：**纯白底、描边卡片、亮蓝主色、橙色价格、胶囊徽章与筛选 chip**。这套取值按 WCAG AA 校准过，与截图的原始取值有出入的地方见 §3.4 —— 截图里的亮蓝与亮橙在白底上都不达 4.5:1，不能照抄。
>
> `../mobile-app/` 的 Apple 系浅灰底配色**不再沿用**；它只作为行为与结构的参照实现，token 处置见 §12。
>
> 若本应用要走不同视觉方向，只改本文件的取值即可，不影响 `../mobile-app/`。

## 1. 设计方向

一句话：**照片填满画面，界面退成白底与细线。**

- 页面底色是**纯白**，靠 **1px 细描边**分隔卡片与列表，不靠阴影、不靠灰底。
- 蓝色只用于**可操作项与选中态**；橙色只用于**价格与评分**。两者都不做装饰。
- 灰底（`--surface-secondary`）只出现在三类地方：搜索框、筛选 chip、参数/信息小卡。
- 留白靠 4/8pt 节奏与分段标题建立层级，不用装饰性渐变或色块填空白。
- 文案写产品里会说的话，不写参数罗列。

完整的原则论述、导航结构与无障碍要求见 `../design-system/MASTER.md`。

### 1.1 从截图提炼的布局范式

`reference/` 里的界面反复出现这几种结构，重建时按需复用，不要另创一套：

| 范式 | 说明 | 出现的页面 |
| --- | --- | --- |
| 顶部分段导航 | 2–4 个文字段，选中项加粗 + 蓝色下划线，不用滑块底色 | 发现、橱窗、搜索、摄影师主页 |
| 搜索框 | 通栏、圆角、灰底、放大镜图标、无描边 | 发现、橱窗、搜索 |
| 筛选 chip 行 | 横向排列的胶囊，可带下拉箭头或图标，横向可滚动 | 发现、橱窗、搜索 |
| 双列卡片 | 图 + 作者行 + 标题（两行截断）+ 价格/已售 | 橱窗（方案） |
| 三列缩略图 | 方图密排，间距 2–8px，可带角标 | 摄影师主页、搜索 |
| 左文右图列表行 | 左侧标题/描述/徽章/价格，右侧方图 | 橱窗（企划） |
| 瀑布流 | 双列、间距 4–8px、图高不等 | 发现（作品） |
| 详情分段 | 粗体小节标题 + 参数定义列表 + 提示色块 + 时间线 | 方案详情、企划详情 |
| 底部动作条 | 固定在底部的胶囊按钮，1 个主操作或 2 个并列 | 摄影师主页、方案详情、企划详情 |
| 图上圆形浮钮 | 半透明圆底（`--surface-overlay`）+ 图标，压在通栏图上（返回 / 分享 / 更多） | 摄影师主页、方案详情 |

### 1.2 明确不做的

**促销横幅不做。** 截图里发现页与橱窗页顶部有两块粉紫/橙渐变的运营卡（"近期开稿"、"价目表"）。**决定（2026-09-10）：不实现。** 原因：

- `../design-system/MASTER.md` 的禁止清单里有两条直接冲突——禁止装饰性渐变，禁止在业务应用里放营销式 hero 区块。
- 它不在 `PAGES.md` 的页面清单里，属于页内运营位，删掉不损失任何功能与数据。
- 为了它给 MASTER.md 开一条窄口子不划算：运营位的样式会随活动变化，开了口子就会持续渗进来。

如果将来确实要做运营位，先改 MASTER.md 的禁止清单，再在本节登记新的形态约束；不要临时在页面里插一块渐变卡。

## 2. Token 分层与命名规则

三层，组件只准消费中间层：

| 层 | 例子 | 谁可以用 |
| --- | --- | --- |
| 原始值 primitive | `#0a67d0`、`16px` | 只有 `src/theme/tokens.css` 的 token 定义 |
| 语义 semantic | `--brand`、`--ink-secondary`、`--space-4` | 所有组件 |
| 组件 component | `--btn-primary-bg` | 仅该组件的 `<style scoped>` |

规则：

- **组件里不得出现写死的十六进制色值、像素字号、像素间距、像素圆角。** 唯一例外是 `1px` 描边与 `0`。
- 新增语义 token 前，先确认现有 token 无法表达；新增必须**同时补 light 与 dark 两套取值**。
- 命名用「角色 + 层级」（`--surface-secondary`），不用外观描述（`--gray-light`）或位置（`--left-panel-bg`）。
- **禁止为单个页面开一套色板。**

## 3. 颜色

### 3.1 语义颜色 token

| Token | Light | Dark | 用途 |
| --- | --- | --- | --- |
| `--paper` | `#FFFFFF` | `#000000` | 页面底色 |
| `--surface-solid` | `#FFFFFF` | `#1C1C1E` | 卡片、列表、底部动作条（浅色下与底色同色，靠描边区分） |
| `--surface-secondary` | `#F5F6F8` | `#2C2C2E` | 搜索框、筛选 chip、参数/信息小卡 |
| `--surface-tertiary` | `#EEEFF2` | `#3A3A3C` | 按下态、更深一层灰底 |
| `--surface-overlay` | `rgba(0,0,0,.45)` | `rgba(0,0,0,.55)` | 压在通栏图上的圆形浮钮底色 |
| `--ink` | `#1A1A1A` | `#F5F5F7` | 标题与正文 |
| `--ink-secondary` | `#666C78` | `#C7C7CC` | 次要正文、说明、作者名 |
| `--ink-tertiary` | `#8A8F99` | `#98989D` | 元信息、时间、计数（**限用途，见 §3.4**） |
| `--brand` | `#0870C9` | `#409CFF` | 可操作项、选中态、链接、选中下划线 |
| `--brand-strong` | `#065DA8` | `#64ADFF` | 按下态、强调 |
| `--brand-soft` | `#EEF7FF` | `#102D4F` | 品牌浅底（徽章、选中 chip） |
| `--on-brand` | `#FFFFFF` | `#000000` | 品牌色底上的文字/图标 |
| `--price` | `#D95E00` | `#FFA94D` | 价格、评分数值（**仅大字，见 §3.4**） |
| `--price-ink` | `#B85100` | `#FFA94D` | 价格/评分需要小字时的替代色 |
| `--price-soft` | `#FFF6EC` | `#3A2408` | 价格系浅底（如「优选」徽章） |
| `--success` | `#0F7B6C` | `#30D158` | 成功、认证类徽章（实名认证） |
| `--success-soft` | `#E4F5F2` | `#12391D` | 成功浅底 |
| `--warning` | `#8A5A00` | `#FFD60A` | **待处理 / 未保存提醒**：待验证的联系方式、未保存改动提示。不是错误，不得用 `--danger` 代替 |
| `--warning-soft` | `#FFF3D6` | `#3D3200` | 警告浅底 |
| `--danger` | `#D70015` | `#FF453A` | 破坏性操作、错误 |
| `--danger-soft` | `#FFEAED` | `#2E0F0E` | 危险浅底 |
| `--border` | `#E8E8EC` | `#303034` | 卡片与列表的 1px 描边（**装饰性**，见 §3.5） |
| `--border-strong` | `#D9DAE0` | `#4A4A4F` | 需要更清楚边界时（chip 描边、分隔线） |
| `--scrim` | `rgba(0,0,0,.45)` | 同左 | 模态遮罩 |

没有 `--accent`：这套视觉里只有「蓝＝可操作」「橙＝价格」两个彩色角色，不需要第三个点缀色。

### 3.2 状态色使用规则

- `--*-soft` 只能作底，其上的文字与图标必须用同族指定色（见 §3.3 的徽章配色表）。
- **颜色不得作为唯一状态信号**：错误必须同时有文字说明，选中必须同时有字重或下划线变化。
- 破坏性操作不得使用品牌色，也不得使用价格橙。
- 同一屏内状态色最多出现一种。
- **橙色只表示价格与评分**，不要拿它做促销、提醒或强调——那会让价格语义失效。

### 3.3 徽章与 chip 配色

截图里反复出现的胶囊徽章，只用这四组配对（全部实测）：

| 语义 | 底 | 文字 | 实测 |
| --- | --- | --- | --- |
| 品牌类（价目表、档期空闲） | `--brand-soft` | `--brand` | 4.65:1 |
| 认证类（实名认证、优选） | `--success-soft` | `--success` | 4.58:1 |
| 价格类（优选画师、稿费） | `--price-soft` | `--price-ink` | 4.66:1 |
| 中性类（信誉优良） | `--surface-secondary` | `--ink-secondary` | 4.88:1 |

胶囊本身：高 28–32px，圆角 `--radius-pill`，字号 `--text-xs`，字重 700，内边距 4px 10px。

### 3.4 与截图的出入（**必须按本表，不要照抄截图**）

截图里有两处配色达不到 WCAG AA，直接照抄会做出不可读的界面：

| 截图取值 | 实测 | 本契约的取值 | 说明 |
| --- | --- | --- | --- |
| 亮蓝 `#2E9BFF` / `#1F9BFF` | 白底 **2.90:1** | `--brand: #0870C9` | 截图那个蓝做文字不合格，**做按钮填充配白字同样不合格**（同一对色，2.90:1）。要达标就只能压深到 `#0870C9`（5.03:1，双向都过） |
| 亮橙 `#FF7A00` | 白底 **2.61:1** | `--price: #D95E00` | 压深后 3.78:1，只够大字 |
| 浅灰元信息 `#8A8F99` | 白底 **3.25:1** | 降级为 `--ink-tertiary` | 不能用于正文 |

由此产生两条**硬性用途约束**，是本契约与截图最大的差别：

1. **价格与评分用 `--price` 时，字号必须 ≥20px 且字重 700。** 20px/700 属于 WCAG 的「大字号」，门槛是 3:1，`3.78:1` 通过。任何小于 20px 或非粗体的价格文字必须改用 `--price-ink`（白底 4.98:1）。
2. **`--ink-tertiary` 只能用于非正文信息**（计数、时间、图标），或 ≥20px 的字。要作为正文说明文字，用 `--ink-secondary`。

### 3.5 描边的可访问性说明（有意保留的取舍）

截图里的界面几乎不使用阴影，卡片边界靠 1px 浅描边。`--border #E8E8EC` 在白底上只有 **1.15:1**，远低于 WCAG 1.4.11 对「识别组件边界」要求的 3:1。

- **卡片、列表行**：描边是装饰性的，卡片靠内容与间距即可识别，不要求 3:1。
- **输入框、chip 这类交互控件**：边界改由**灰底填充**表达（`--surface-secondary`），这是截图的做法；纯填充同样低于 3:1，因此**必须配合 §10 的强焦点环**来满足「状态可识别」的要求。
- 不得为了凑对比度把描边加深到明显发灰——那会破坏这套视觉的干净感。这是有意的取舍，写在这里备案，不要当成待修的 bug。

### 3.6 已核对的对比度

浅色（底 `--paper` / `--surface-solid` 均为 `#FFFFFF`）：

| 组合 | 实测 | 判定 |
| --- | --- | --- |
| `--ink` | 17.40:1 | 通过 |
| `--ink-secondary` | 5.27:1 | 通过（在 `--surface-secondary` 上 4.88:1，也通过） |
| `--ink-tertiary` | **3.25:1** | **不达 4.5:1，见 §3.4 约束 2** |
| `--brand` | 5.03:1 | 通过（做填充配白字同为 5.03:1） |
| `--brand` on `--brand-soft` | 4.65:1 | 通过 |
| `--price` | **3.78:1** | **仅 ≥20px/700，见 §3.4 约束 1** |
| `--price-ink` | 4.98:1 | 通过 |
| `--price-ink` on `--price-soft` | 4.66:1 | 通过 |
| `--success` | 5.16:1 | 通过 |
| `--success` on `--success-soft` | 4.58:1 | 通过 |
| `--danger` | 5.38:1 | 通过 |
| `--danger` on `--danger-soft` | 4.68:1 | 通过 |

深色（底 `#000000`）：

| 组合 | 实测 | 判定 |
| --- | --- | --- |
| `--ink` | 19.29:1 | 通过 |
| `--ink-secondary` | 12.47:1 | 通过 |
| `--ink-tertiary` | 7.31:1 | 通过（深色下无 §3.4 的限制） |
| `--brand` | 7.42:1 | 通过 |
| `--on-brand`（黑）on `--brand` | 7.42:1 | 通过 |
| `--brand` on `--brand-soft` | 4.91:1 | 通过 |
| `--price` | 11.03:1 | 通过（深色下无字号限制） |
| `--price` on `--price-soft` | 7.69:1 | 通过 |
| `--success` | 10.39:1 | 通过 |
| `--success` on `--success-soft` | 6.38:1 | 通过 |
| `--danger` | 6.16:1 | 通过 |
| `--danger` on `--danger-soft` | 5.18:1 | 通过 |

`--border` / `--border-strong` 未做对比度校验，理由见 §3.5。

以上为实测值（WCAG 2.x 相对亮度公式）。新增配色组合必须实测后写进本表，不得凭感觉判断。

## 4. 字体与字号

字体栈不引入 Web Font，只用系统字：

```css
--font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
             "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
```

| Token | 值 | 用途 | 行高 | 字重 |
| --- | --- | --- | --- | --- |
| `--text-2xs` | 11px | 仅角标内的数字。**不得用于任何文字标签** | 1.3 | 500 |
| `--text-xs` | 12px | 标签、辅助说明 | 1.4 | 400 |
| `--text-sm` | 14px | 次要信息、表单项 | 1.5 | 400 |
| `--text-base` | 16px | 正文（**下限**） | 1.5 | 400 |
| `--text-lg` | 20px | 区块标题 | 1.4 | 600 |
| `--text-xl` | 28px | 大标题 | 1.25 | 700 |
| `--text-2xl` | 34px | 仅真正的页面级标题 | 1.15 | 700 |

导航栏标题（Ionic toolbar）固定 17px / 600，不进上表。

规则：

- 正文不得小于 16px；`--text-sm` 只承载次要信息，不能承载页面主要阅读内容。
- 价格、数量、计数、倒计时用 `font-variant-numeric: tabular-nums`。
- 中文字间距保持 `0`，不要用负字间距。
- 布局必须在系统字号放大到 200% 时仍不截断、不重叠。

## 5. 间距与布局

| Token | 值 | | Token | 值 |
| --- | --- | --- | --- | --- |
| `--space-1` | 4px | | `--space-6` | 24px |
| `--space-2` | 8px | | `--space-8` | 32px |
| `--space-3` | 12px | | `--space-10` | 40px |
| `--space-4` | 16px | | `--space-12` | 48px |
| `--space-5` | 20px | | | |

- **只用这套刻度。** 5px、10px、18px 这类刻度外取值一律不接受。
- 页面左右内边距统一 `--space-4`；内容区宽度 `min(100%, var(--content-max))` 居中。
- 触控目标最小 `--touch-target`（48px）。视觉上更小的图标必须保留完整的 48px 命中区。
- 底部固定栏高度 `--bottom-nav-height`（64px），偏移 `--bottom-nav-offset`（10px）。页面内容底部留白 = `--bottom-nav-height + --bottom-nav-offset + env(safe-area-inset-bottom) + --space-4`。
- 必须用 `env(safe-area-inset-*)` 处理刘海与 Home Indicator，不得用固定 padding 顶替。
- 页面之间不出现横向滚动。

## 6. 圆角与阴影

| Token | 值 | 用在哪 |
| --- | --- | --- |
| `--radius-sm` | 8px | 紧凑控件：标签、小按钮 |
| `--radius-md` | 12px | 常规控件：按钮、输入框 |
| `--radius-lg` | 16px | 卡片、图片容器 |
| `--radius-xl` | 22px | 底部弹层、浮层 |
| `--radius-pill` | 999px | 胶囊标签、头像 |

| Token | 用在哪 |
| --- | --- |
| `--shadow-1` | 弹层内的次级浮起（下拉、Popover） |
| `--shadow-2` | 底部弹层、ActionSheet |
| `--shadow-3` | 模态对话框 |

- **卡片与列表行不用阴影，用 `--border` 的 1px 描边。** 截图里的界面靠细线分块，加阴影会显得脏。
- 阴影只用于**真正浮起的东西**（弹层、下拉），不用来做装饰、也不用来强化卡片。
- 卡片不得嵌套卡片；分组信息之间用 `--border` 或分区标题分隔。
- 同一屏内不要混用超过两种圆角档位。

## 7. 顶栏与底栏（不使用模糊）

截图里的顶栏、底栏、详情页头部都是**不透明面 + 一条 1px 细线**，不使用毛玻璃。

| Token | 用途 |
| --- | --- |
| `--material-thin` | 粘性头（发现 / 橱窗 / 搜索的顶部分段导航） |
| `--material-regular` | 底部 Tab 栏、详情页头部 |
| `--material-thick` | 底部弹层前景 |
| `--material-blur` | `none` —— 本视觉不用模糊 |

- 这四个 token 在 `tokens.css` 里都是不透明取值，保留只为让既有组件样式里的变量引用继续成立，**不要在此基础上重新引入 `backdrop-filter`**。
- 顶栏与底栏各压一条 `--border` 细线作为边界，不用阴影。
- 因为不再有半透明面，`prefers-reduced-transparency` 已无对象（`tokens.css` 里已移除该媒体查询）。

## 8. 动效

| Token | 值 | 用在哪 |
| --- | --- | --- |
| `--motion-instant` | 100ms | 点按反馈 |
| `--motion-fast` | 180ms | 颜色、描边、透明度等状态过渡 |
| `--motion-normal` | 300ms | 位移、展开收起 |
| `--motion-slow` | 400ms | 页面级转场 |
| `--spring-ui` | `cubic-bezier(.2,.8,.2,1)` | 默认缓动 |
| `--motion-spring` | `cubic-bezier(.34,1.56,.64,1)` | 仅惯性手势（下拉刷新、滑动回弹） |

- 只动 `transform` 与 `opacity`；不要动 `width` / `height` / `top` / `left`。
- 按下反馈：`transform: scale(.97)`，`--motion-instant`，且**不得引起布局位移**。
- 响应必须在 100ms 内可见。
- 任何过渡都必须能被用户输入打断，不要用不可中断的固定时长动画锁住交互。
- `prefers-reduced-motion: reduce` 时：位移改为 ≤120ms 的交叉淡入，或直接切状态。
- 触觉反馈只用于有意义的提交、选中、成功、失败。

## 9. 层级

| Token | 值 | 用途 |
| --- | --- | --- |
| `--layer-content` | 0 | 常规内容 |
| `--layer-sticky` | 20 | 粘性头、底部 Tab |
| `--layer-dropdown` | 40 | 下拉、气泡、Toast |
| `--layer-modal` | 100 | 模态、弹层、遮罩 |

**禁止在组件里写任意 z-index**（如 `9999`）。需要新层先在本表加一档。

## 10. 触控与无障碍

- 所有可点元素 ≥48×48px，相邻可点元素间距 ≥`--space-2`。
- 焦点环：`outline: 3px solid var(--focus-ring); outline-offset: 2px`，只在 `:focus-visible` 出现。**不得为美观去掉**。
- 正文对比度 ≥4.5:1；大字号（≥20px，或 ≥16px 且 700 字重）与图标 ≥3:1。
- 图片必须有 `alt`；纯装饰图用 `alt=""`；图标按钮必须有 `aria-label`。
- 表单每个字段有**可见 label**，placeholder 只作补充；用正确的 `type` 与 `inputmode`。
- 尊重 `prefers-reduced-motion` / `prefers-reduced-transparency` / `prefers-contrast`。
- 深色与浅色必须**分别核对**，不得只做一套再反转。

## 11. 组件状态映射

### 按钮

| 变体 / 状态 | 背景 | 文字 | 其他 |
| --- | --- | --- | --- |
| 主要 · 默认 | `--brand` | `--on-brand` | `--radius-md`，高 ≥48px |
| 主要 · 按下 | `--brand-strong` | `--on-brand` | `transform: scale(.97)`，`--motion-instant` |
| 主要 · 禁用 | `--brand` | `--on-brand` | `opacity: .42`，不响应交互 |
| 次要 · 默认 | `--surface-secondary` | `--brand` | 无描边 |
| 破坏 · 默认 | `--danger-soft` | `--danger` | 与主操作**空间分离** |
| 图标按钮 | 透明 | `--ink` | 必须有 `aria-label`，命中区 48px |

一屏只有一个主要按钮。

### 表单

- 输入框高 ≥48px，底 `--surface-tertiary`，`--radius-md`；聚焦时 `outline: 3px solid var(--focus-ring)`。
- 校验在 blur 或提交时触发；错误文案在字段下方，用 `--danger`，并给出恢复路径。
- 异步提交时禁用提交按钮并显示进度。
- 长表单保留草稿，离开前有未保存内容要二次确认。

### 卡片与列表

- 卡片：底 `--surface-solid`，`--radius-lg`，`--shadow-1`，内边距 `--space-4`。
- 图片容器用 `aspect-ratio` 占位防止布局抖动；首屏以下 `loading="lazy"`。
- 元信息紧凑可扫读，用 `--ink-secondary`；`--ink-tertiary` 只放非正文信息。
- 超过约 50 项的复杂列表要虚拟化或分页增量加载。

### 弹层与模态

- 遮罩 `--scrim`，前景 `--material-thick`，上圆角 `--radius-xl`。
- 从底部进、向底部退，与其来源方向一致。
- 关闭控件始终可见；有未保存内容要确认。
- 动效只用 `transform` 与 `opacity`；reduced-motion 下换成短暂交叉淡入。

## 12. 参照实现的 token 处置

`../mobile-app/src/theme/tokens.css` 里的 token 逐组判定如下。**这是本节存在的理由：不要直接复制那份文件。**

| Token / 组 | 处置 | 原因 |
| --- | --- | --- |
| `--neu-light` 等 `--neu-*`（12 个） | **不带** | 文件内自注为「页面样式迁移期间的兼容别名」，是迁移脚手架；`--neu-` 命名源自 Neumorphism，而 MASTER.md 禁止清单第一条就是拟物与重度阴影 |
| `--d-page` 等 `--d-*`（12 个） | **不带** | 自注为详情页专用色板（`#111827` / `#2563eb` 一套独立灰蓝），属于**逐屏自造色板**，MASTER.md 明令禁止 `per-screen color palettes`；且 `--d-pad: 20px`、`--d-title: 21px` 都是间距与字号刻度外取值 |
| `--glow-brand` | **不带** | 装饰性发光，MASTER.md 禁止装饰效果 |
| `--paper-light` / `--paper-deep` / `--white` | **不带** | 与 `--surface-solid` / `--surface-secondary` 语义重复；原始白值不应被组件直接消费（用 `--on-brand` 或 `--surface-solid`） |
| `--font-serif` | **不带** | 取值等于 `var(--font-sans)`，空别名 |
| **Apple 系配色整体** | **不沿用，已换掉** | 参照实现是「浅灰底 `#F2F2F7` + 白卡片 + 毛玻璃」；本契约按 `reference/` 截图改为「纯白底 + 描边卡片 + 不透明栏」。对应 token（`--paper`、`--surface-*`、`--ink*`、`--brand`、`--border`/`--divider`、`--material-*`）**取值全部重定**，见 §3 与 §13 |
| `--accent` | **删除** | 新视觉不需要独立的点缀色；「蓝＝可操作」「橙＝价格」已经覆盖 |
| `--warning` / `--warning-soft` | **删除后又加回** | 一度按「只有两个彩色角色」删除，但账号设置这类页面确实需要「待处理 / 未保存」的中间态，用 `--danger` 表达会把「待验证」误报成错误。加回时的取值做过对比度校验：浅色 `#8A5A00`（白底 5.9:1、`--warning-soft` 底 5.37:1），深色 `#FFD60A`（黑底 14.88:1）。用法严格限制在待处理与未保存提醒，不得用于促销或强调 |
| `--divider` / `--separator-opaque` | **合并为** `--border` / `--border-strong` | 原来两个语义区分不清，实际使用中总是混用；合并成「装饰性细线」与「需更清楚边界」两档 |
| 间距、圆角、字体、布局、动效、层级、Ionic 映射骨架 | **保留** | 与 MASTER.md 一致，是本契约的稳定底座 |
| `--on-brand` | **新增** | 深色下品牌底上的文字是黑色，需要一个独立语义 token 表达 |
| `--price` / `--price-ink` / `--price-soft` | **新增** | 截图里价格与评分是橙色，是这套视觉的核心语义；因对比度原因拆成「大字用」与「小字用」两个 |
| `--surface-overlay` | **新增** | 压在通栏图上的圆形浮钮需要一个独立底色 |
| `--chip-height` / `--avatar-sm` / `--avatar-md` | **新增** | 徽章、筛选 chip、作者行头像在截图里反复出现，尺寸收进刻度而不是各页面自己写 |
| `--motion-spring` | **新增** | MASTER.md 允许惯性手势回弹，参照实现缺对应 token |
| `--leading-tight/snug/normal` | **新增** | 行高此前散落在页面样式里，收进刻度 |

另外 `../mobile-app/src/theme/neumorphism.css`（226 行）与 `--neu-*` 同源，**不要带过来**。

## 13. token 定义

**完整的 token 定义在 `src/theme/tokens.css`，那是唯一实现。** 本文件只维护其中**易变的部分——颜色**，便于在改版时集中复核；间距、圆角、字体、布局、动效、层级这些稳定项不在此重复，避免两处漂移。

新增 token 前先确认 `tokens.css` 里现有取值无法表达；新增**必须同时补 light 与 dark 两套**。

### 13.1 颜色（与 `tokens.css` 必须逐字一致）

```css
:root {
  color-scheme: light dark;

  /* ---- 表面：纯白底，卡片与底色同色，靠描边区分 ---- */
  --paper: #ffffff;
  --surface-solid: #ffffff;
  --surface-secondary: #f5f6f8;
  --surface-tertiary: #eeeff2;
  --surface-overlay: rgba(0, 0, 0, 0.45);

  /* ---- 文字 ---- */
  --ink: #1a1a1a;
  --ink-secondary: #666c78;
  --ink-tertiary: #8a8f99; /* 仅非正文或 ≥20px，见 §3.4 */

  /* ---- 品牌：可操作项、选中态、链接 ---- */
  --brand: #0870c9;
  --brand-strong: #065da8;
  --brand-soft: #eef7ff;
  --on-brand: #ffffff;

  /* ---- 价格与评分：橙色只表达这两个语义 ---- */
  --price: #d95e00;      /* 仅 ≥20px 且 700 字重 */
  --price-ink: #b85100;  /* 需要小字时用这个 */
  --price-soft: #fff6ec;

  /* ---- 状态 ---- */
  --success: #0f7b6c;
  --success-soft: #e4f5f2;
  --warning: #8a5a00; /* 待处理 / 未保存提醒，不是错误 */
  --warning-soft: #fff3d6;
  --danger: #d70015;
  --danger-soft: #ffeaed;

  /* ---- 线 ---- */
  --border: #e8e8ec;
  --border-strong: #d9dae0;
  --scrim: rgba(0, 0, 0, 0.45);
}

:root[data-theme='dark'] {
  --paper: #000000;
  --surface-solid: #1c1c1e;
  --surface-secondary: #2c2c2e;
  --surface-tertiary: #3a3a3c;
  --surface-overlay: rgba(0, 0, 0, 0.55);

  --ink: #f5f5f7;
  --ink-secondary: #c7c7cc;
  --ink-tertiary: #98989d;

  --brand: #409cff;
  --brand-strong: #64adff;
  --brand-soft: #102d4f;
  /* 深色下品牌色是亮蓝，其上的文字必须是黑色（7.42:1），不能用白 */
  --on-brand: #000000;

  --price: #ffa94d;
  --price-ink: #ffa94d;
  --price-soft: #3a2408;

  --success: #30d158;
  --success-soft: #12391d;
  --warning: #ffd60a;
  --warning-soft: #3d3200;
  --danger: #ff453a;
  --danger-soft: #2e0f0e;

  --border: #303034;
  --border-strong: #4a4a4f;
}
```

### 13.2 顶栏与底栏材料

本视觉**不使用模糊**。`--material-thin/regular/thick` 在 `tokens.css` 里都等于不透明面（浅色 `#FFFFFF`、深色 `#1C1C1E`），`--material-blur` 为 `none`。三个别名保留是为了让 `TabsLayout` / `AppTopBar` / `DetailHeader` / `PublishActionSheet` 里既有的变量引用继续成立，不是鼓励继续用「材料」这个概念。

因此 `prefers-reduced-transparency` 已无对象，`tokens.css` 里不再有该媒体查询；`prefers-contrast: more` 保留。

### 13.3 高度

阴影只给真正浮起的东西（弹层、下拉）。卡片与列表行用 `--border` 描边，**不用阴影**；这也与 §3.5 的说明一致。

## 14. 落地方式

- `src/theme/tokens.css` 是 token 的唯一实现（§13 只镜像其中的颜色块）。全局样式只放重置、`.page-shell`、`.sr-only`、`.pressable` 这类基础类，不要按页面拆全局样式文件。
- 主题切换：`document.documentElement.dataset.theme` + `documentElement.style.colorScheme` + `meta[name="theme-color"]`（浅 `#FFFFFF` / 深 `#000000`），持久化到 `localStorage`。**必须在挂载 Vue 之前执行**，否则首屏会先闪一次默认主题。
- `index.html` 里的 `theme-color` 首屏值必须与上面一致，改配色时三处一起改（`tokens.css`、`utils/theme.ts`、`index.html`）。
- Ionic 变量映射写在 `tokens.css` 内，不要散落到页面里。
- `color-scheme: light dark` 已在 `:root` 声明；不要额外给表单控件写 `color-scheme`。

## 15. 自检清单

改完 UI 逐条过：

1. 组件里没有写死的十六进制色值、像素字号、像素间距、像素圆角（`1px` / `0` 除外）。
2. 用到的颜色都能在 §3 找到，且浅深两套都已核对。
3. **价格/评分用 `--price` 时确实 ≥20px 且 700 字重**；小字场合用的是 `--price-ink`（§3.4 约束 1）。
4. **`--ink-tertiary` 没有用在正文上**（§3.4 约束 2）。
5. 橙色只出现在价格与评分上，没有被拿去做促销或强调（§3.2）。
6. 卡片与列表行用的是 `--border` 描边，**没有加阴影**；阴影只出现在弹层/下拉（§6）。
7. 徽章与 chip 用的是 §3.3 那四组配对之一，没有自创底色。
8. 所有可点元素 ≥48×48px；图标按钮有 `aria-label`。
9. 只用 §5 的间距刻度与 §6 的圆角档位。
10. 动效只动 `transform` / `opacity`，且 `prefers-reduced-motion` 下有替代。
11. z-index 只用 §9 的四档。
12. 没有卡片套卡片、没有装饰性渐变、没有复活 `--neu-*` / `--d-*` / Apple 系浅灰底、没有在 `--material-*` 上重新引入 `backdrop-filter`。
13. 375px 与 768px 下无横向滚动、无文字截断、底部内容不被 Tab 栏遮住。
