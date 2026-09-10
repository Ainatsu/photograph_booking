# reference/ — UI 参考图

把视觉参考图放进本目录，文件名不限。agent 会直接读取这里的图片来对齐设计，而不是靠文字描述猜。

## 怎么用

- **看图**：agent 可以打开 PNG / JPG / WEBP 等图片并看到内容。
- **对照**：启动 `npm run dev` 后 agent 可以自动打开 `http://127.0.0.1:5176` 截图，与这里的参考图逐屏比对。
- **落成 token**：参考图里的颜色、字号、间距、圆角如果与 `DESIGN.md` 现有取值冲突，**先改 `DESIGN.md` 再改代码**，不要把新值直接写进组件。参考图是输入，`DESIGN.md` 仍是唯一执行规格。

## 建议的文件命名

按页面或组件命名，方便 agent 知道每张图对应哪里（名称不必与代码文件名完全一致，能对上就行）：

```text
reference/
├─ discover.png            发现页
├─ showcase.png            橱窗页
├─ work-detail.png         作品详情
├─ package-detail.png      方案详情
├─ order-detail.png        订单详情
├─ profile.png             我的
├─ components/
│  ├─ card.png             卡片样式
│  ├─ button.png           按钮各状态
│  └─ tab-bar.png          底部导航
└─ tokens/
   └─ palette.png          配色板
```

如果一张图覆盖多个页面，或者顺序有意义（比如"改前 / 改后"），在文件名里写清楚，例如 `discover-before.png` / `discover-after.png`。

## 注意

- 本目录**不参与构建**，不会被 Vite 打包进产物。
- 图片体积大时注意别提交过大的文件；参考图进版本库前可以先压一下。
- 参考图只约束**呈现层**。页面集合、路由与行为仍以 `PAGES.md` 为准——图里少画了一个入口，不代表那个入口可以删，见 `PAGES.md` §1。
