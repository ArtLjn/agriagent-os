# V4 字体排版修复计划

## 问题分析

### 问题1: "AI 助手"标签截断
- 原因：section 的 padding-top 不够，标题区域被上方内容覆盖
- 修复：增加 AI 助手 section 的 padding-top 到 140px

### 问题2: 大标题换行不合理
- 原因：font-size 用 clamp(2rem, 5vw, 4.5rem) 在小屏幕过大，且没有中文换行控制
- 修复：
  - 调整 clamp 范围让标题更合理
  - 添加 `word-break: keep-all` 防止中文在半字处换行
  - 添加 `overflow-wrap: break-word` 作为回退
  - 控制标题 max-width 让换行更自然

### 问题3: 描述文字换行尴尬
- 原因：文字区域太宽，导致长句子被拆到不自然的位置
- 修复：给描述文字设置合理的 max-width（600-700px），让行长控制在舒适范围

### 全局字体优化
- 确保所有中文标题都有 keep-all
- 确保描述文字有合适的 max-width
- 确保 section 之间有足够的间距
- 检查所有区块的 padding 是否充足
