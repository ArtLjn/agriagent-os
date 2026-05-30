## Context

当前 10 个 skill 的回复都是纯文本拼接，没有 emoji、没有 Markdown 格式。前端 `MarkdownText` 组件已支持标题、列表、表格、粗体、引用块、代码块等完整 Markdown 渲染，但后端没有利用这些能力。

LLM 是 qwen3.6-flash（弱模型），直接在 prompt 里要求格式化输出不可靠。因此采用 **代码生成格式 + prompt 引导** 的混合策略。

## Goals / Non-Goals

**Goals:**
- 天气预报、记账确认、茬口创建结果三个场景用代码生成固定 Markdown 格式（100% 可靠）
- prompt 引导 LLM 在闲聊和建议场景加 emoji + 格式
- 所有格式在前端 react-native-markdown-display 正常渲染

**Non-Goals:**
- 不引入 HTML/CSS 富文本
- 不改前端代码
- 不改 SSE 协议

## Decisions

### Decision 1: skill _format_reply 生成 Markdown

各 skill 的 `_format_reply` 方法直接输出 Markdown 格式文本，而非纯文本。LLM 不需要二次格式化。

**理由**: skill 返回的 reply 直接透传给用户（通过 ToolMessage → AIMessage），中间没有 LLM 处理环节，所以格式必须在 skill 层面生成。

### Decision 2: 天气预报用 Markdown 表格

```
📍 苏州 · 未来 3 天预报

| 日期 | 天气 | 最高 | 最低 | 降水 |
|------|------|------|------|------|
| 5/28 | ☀️ | 28℃ | 18℃ | 0mm |
| 5/29 | 🌧️ | 22℃ | 16℃ | 8mm |

⚠️ 明天有降雨，注意排水
```

**理由**: 表格在手机端横向可滚动，数据对齐清晰。只展示 3 天（非 7 天）减少信息量。

### Decision 3: 记账确认用 emoji + 列表

```
💰 确认记账信息：
- **分类**：化肥
- **金额**：50 元
- **类型**：支出

确认后将记录，回复「确认」执行。
```

**理由**: 列表格式在 MarkdownText 中有蓝色圆点，视觉层次好。

### Decision 4: 茬口创建结果用阶段列表

```
✅ 茬口「春季西瓜」已创建！

📋 **阶段规划**
1. 播种期（5/28 ~ 6/3，7天）
2. 苗期（6/4 ~ 6/23，20天）
3. 伸蔓期（6/24 ~ 7/18，25天）
4. 开花期（7/19 ~ 8/2，15天）
5. 结果期（8/3 ~ 9/1，30天）
```

**理由**: 有序列表比表格更适合展示阶段顺序，emoji 标记成功状态。

### Decision 5: Prompt 增加【回复风格】段落

在 `base.j2` 加一段格式引导：
- 每条建议加 emoji 前缀（🌱💡⚠️📊 等）
- 用 Markdown 列表和加粗组织内容
- 保持口语化、短句

**理由**: 只影响 LLM 自由生成的场景（闲聊、建议），不影响 skill 格式化输出。

## Risks / Trade-offs

- [弱模型不遵守 prompt 格式指令] → 只在非关键场景依赖 prompt，核心场景用代码生成
- [天气表格在窄屏溢出] → 前端已有 `ScrollView` 横向滚动处理表格
- [emoji 兼容性] → react-native 支持 Unicode emoji，无兼容问题
