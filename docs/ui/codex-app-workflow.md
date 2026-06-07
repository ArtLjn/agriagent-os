# Codex App 应用设计工作流

> 目标：让 Codex 做 App UI 时不再凭空发挥，而是围绕设计源、实现边界、视觉验收和复用沉淀稳定交付。

## 适用范围

本流程适用于 FarmManager Mobile 的页面设计、页面重构、交互补全、视觉还原和移动端体验检查。后端能力、数据模型、权限策略等需求仍走 OpenSpec 变更流程。

## 核心原则

1. 先有设计源，再让 Codex 写代码。
2. 一次只做一个页面、一个流程或一个明确组件组。
3. Codex 负责工程落地，审美判断必须来自参考图、设计规范、截图验收和人工 review。
4. 所有 UI 改动必须覆盖加载、空状态、错误状态和移动端窄屏状态。
5. 页面完成不等于编译通过，必须有真实截图或设备验证。

## 标准流程

### 1. 定义任务边界

每次 UI 任务开始前，先填写 `docs/ui/ui-task-brief-template.md`。最少需要明确：

- 页面或流程名称
- 目标用户
- 用户在这个页面要完成什么
- 必须展示的数据
- 必须支持的操作
- 不能改动的业务逻辑
- 参考图或参考页面
- 验收方式

不接受的任务描述：

- "把页面做高级一点"
- "参考苹果风格随便发挥"
- "整体优化一下 UI"
- "做得像现代 App"

可接受的任务描述：

- "重构记账创建页，只改视觉和交互，不改提交 API；参考 docs/ui/cost-create-redesign-preview/cost-create-redesign-preview.png；保留现有 category、amount、note、date 字段；完成后提供 Android 截图。"

### 2. 建立设计源

按优先级选择设计源：

1. Figma frame 或设计稿截图
2. 项目已有 UI 预览图，例如 `docs/ui/app/ui.png`
3. ImageGen 生成的高保真 mockup
4. 真实竞品截图
5. 文字规范，仅在没有图像时使用

设计源必须说明：

- 哪些地方要严格复刻
- 哪些地方可以按现有组件调整
- 哪些地方只是氛围参考

如果没有设计源，先生成或制作 mockup，不直接进入代码实现。

### 3. 设计到代码交接

设计图进入实现前，必须先按 `docs/ui/design-to-code-handoff.md` 拆解。交接不完整时，不应开始写代码。

交接最少要回答：

- 页面结构如何拆分
- 哪些组件固定，哪些组件滚动
- 颜色、圆角、字号、阴影分别映射到哪些 token
- 默认、加载、空、错误、长文本和键盘状态如何表现
- 哪些视觉效果在 React Native / Android 上有实现风险
- 每个高风险效果的降级方案是什么

### 4. 读取项目设计资产

Codex 开始实现前必须读取：

- `docs/ui/app/ui.md`
- `FarmManagerMobile/src/theme/colors.ts`
- `FarmManagerMobile/src/theme/designTokens.ts`
- 目标页面现有源码
- 同类组件源码

如果页面属于历史 OpenSpec 改造范围，还应读取相关 `openspec/changes/*/design.md` 和 `tasks.md`。

### 5. 输出实现计划

实现前先写 5 到 8 条短计划，说明：

- 会改哪些文件
- 会新增哪些组件
- 哪些业务逻辑保持不变
- 会如何复用 theme tokens
- 会如何验证

计划里必须包含"不做什么"，例如不改 API、不改导航、不改数据结构。

### 6. 小步实现

推荐切分方式：

1. 先抽出页面结构和数据映射。
2. 再实现主题、间距、排版。
3. 再实现组件状态。
4. 最后补动效、边缘状态和截图验收。

每一步都避免大范围重构。单个页面超过 500 行时，应优先拆分组件，而不是继续堆在页面文件里。

### 7. 视觉验收

实现后按 `docs/ui/visual-qa-checklist.md` 检查。最少需要覆盖：

- 默认状态
- 空状态
- 加载状态
- 错误状态
- 小屏 Android
- 长文本
- 无网络或接口失败
- 键盘弹出后的表单布局

Web 页面使用 Playwright 截图。React Native 页面优先用模拟器或真机截图，截图保存到 `FarmManagerMobile/docs/screenshots/YYYY-MM-DD/`。

### 8. 修正循环

截图验收后，按问题清单逐项修正：

- P0：无法完成核心任务、崩溃、提交错误
- P1：元素重叠、文字溢出、按钮不可点击、键盘遮挡输入
- P2：视觉层级不清、间距不一致、状态缺失
- P3：细节 polish，例如微动效、阴影、过渡

修正时不要重新设计整页，只修验收发现的问题。

### 9. 沉淀复用

同一类 UI 工作重复出现 3 次后，沉淀到：

- `docs/ui/`：设计规范、截图、验收清单
- `.codex/` 或 `.agents/skills/`：可复用 Codex Skill
- `FarmManagerMobile/src/components/`：稳定通用组件
- `FarmManagerMobile/src/theme/`：稳定 token

## Codex App 任务模板

把下面这段作为每次开工提示词的基础：

```text
你要做的是 FarmManager Mobile 的 UI 实现任务，不要自由发挥视觉风格。

请先读取：
- docs/ui/ui-task-brief-template.md 中本次填写的任务 brief
- docs/ui/design-to-code-handoff.md
- docs/ui/app/ui.md
- FarmManagerMobile/src/theme/colors.ts
- FarmManagerMobile/src/theme/designTokens.ts
- 目标页面源码
- 同类组件源码

实现约束：
- 先完成设计图到代码的结构拆解，再写代码
- 只改本次页面和必要组件
- 不改后端 API
- 不改数据模型
- 不引入新依赖，除非先说明必要性和替代方案
- 使用现有 colors、gradients、radii、typography、shadowV2、animationTiming
- 覆盖 loading、empty、error、long text、keyboard 状态
- 禁止 console.log / print 调试

完成后：
- 运行 lint / test 中和本次相关的命令
- 启动 App 或页面
- 生成截图
- 按 docs/ui/visual-qa-checklist.md 给出验收结论
```

## 常见失败模式

| 失败模式 | 处理方式 |
|---------|---------|
| 页面变成通用卡片堆叠 | 回到设计源，明确首屏层级和主任务 |
| 大面积渐变和装饰抢内容 | 降低背景存在感，只保留业务有意义的强调 |
| 只做默认状态 | 补齐 loading、empty、error、长文本 |
| 桌面预览好看，手机拥挤 | 以目标 Android 设备截图为准 |
| 引入新 UI 库解决小问题 | 先用现有组件和 theme tokens |
| 视觉和现有 App 不一致 | 对照 `docs/ui/app/ui.md` 和 `src/theme` 修正 |

## 推荐验收口径

一个 UI 任务只有同时满足以下条件，才算完成：

- 目标用户能完成核心操作。
- 页面和参考图的布局、层级、语气一致。
- 代码复用项目 theme tokens。
- 没有文本溢出、元素重叠、键盘遮挡。
- 覆盖默认、加载、空、错误状态。
- 相关 lint/test 已运行，失败项已说明。
- 已提供截图或设备验证结论。
