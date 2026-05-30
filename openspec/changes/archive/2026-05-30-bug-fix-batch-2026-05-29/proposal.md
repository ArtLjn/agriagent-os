## Why

7 个已确认 bug 影响用户体验，需要在上线前修复。

## What Changes

1. **LLM 输出移动端格式乱** — base.j2 和 report.j2 添加移动端格式约束（禁用表格/代码块/嵌套列表）
2. **watchfiles 日志噪音** — 过滤 "1 change detected" 无关变更日志，缩小监听范围
3. **记账后余额不刷新** — CostListScreen 用 useFocusEffect 替代 useEffect，赊账路径补刷新
4. **种植报告转义字符** — report.j2 添加格式约束 + MarkdownText 预处理 `\n`
5. **首页不用用户昵称** — getGreeting() 读取 settingsStore.displayName
6. **天气 skill 不传用户城市** — system prompt 注入 UserSetting.default_city 而非 Farm.location
7. **记账删除不可用** — 后端补 DELETE /costs/{id} 端点

## Capabilities

### New Capabilities

### Modified Capabilities
- `agent-response-format`: 新增移动端格式约束（禁表格/代码块/嵌套列表）
- `llm-tool-calling`: 天气 skill 城市传递链路修正

## Impact

- `backend/prompts/base.j2` — 格式约束
- `backend/prompts/report.j2` — 格式约束
- `backend/app/core/llm_client_manager.py` — watchfiles 过滤
- `backend/app/agent/graph.py` — 城市注入改用 UserSetting
- `backend/app/api/cost.py` — 新增 DELETE 端点
- `backend/app/services/cost_service.py` — 新增 delete_record
- `FarmManagerMobile/src/components/MarkdownText.tsx` — 转义字符预处理
- `FarmManagerMobile/src/screens/home/HomeScreen.tsx` — 读取昵称
- `FarmManagerMobile/src/screens/cost/CostListScreen.tsx` — useFocusEffect
- `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx` — 赊账路径补刷新
