## Context

7 个已确认 bug，涉及后端 4 个、前端 3 个、Prompt 2 个。均为独立修复，无交叉依赖。

## Goals / Non-Goals

**Goals:**
- 修复全部 7 个 bug
- 每个修复独立可测试

**Non-Goals:**
- 不做 Markdown 渲染引擎升级
- 不做记账模块重构

## Decisions

### D1: 移动端格式约束放 Prompt 层

**选择**：在 base.j2 和 report.j2 中添加格式约束，而非改 MarkdownText 组件。

**理由**：从源头约束 LLM 输出比在前端兜底更有效。约束内容：禁用 Markdown 表格、禁用代码块、禁用多级嵌套列表、用扁平短句。

### D2: watchfiles 日志过滤

**选择**：给 watchfiles logger 设 WARNING 级别 + 监听范围不变（已经按文件名过滤）。

**理由**：`start_file_watcher` 内部已有 `if Path(changed_path).name == config_path.name` 过滤，只是 watchfiles 自身的日志没控制。设 logger 级别最简单。

### D3: CostListScreen 用 useFocusEffect

**选择**：用 `@react-navigation/native` 的 `useFocusEffect` 替代 `useEffect`。

**理由**：React Navigation 从其他页面返回时不一定重新挂载组件，`useFocusEffect` 在每次获得焦点时触发，确保数据新鲜。

### D4: 天气城市改用 UserSetting

**选择**：graph.py 中注入 `UserSetting.default_city` 到 system prompt，而非 `Farm.location`。

**理由**：用户在设置中配置的城市是明确的偏好，Farm.location 可能为空或不准确。Weather skill 的降级机制已工作，只需让 LLM 知道城市即可。

### D5: 后端补 DELETE 端点

**选择**：在 cost_service 和 cost_api 中新增 delete_record，软删除（标记 deleted_at）。

**理由**：前端已完整实现删除 UI 和 API 调用，只差后端。

## Risks / Trade-offs

- Prompt 格式约束可能影响某些复杂回复的质量 → 约束只禁极端格式，不影响正常内容组织
- 软删除比硬删除安全但占存储 → 对 3-4 用户可忽略
