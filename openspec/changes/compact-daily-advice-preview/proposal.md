## Why

当前首页的 AI 农事建议卡片（AdviceCard）将所有建议条目平铺展示，导致卡片高度过高，首屏内容被严重挤压，WeatherCard 下方的建议卡片只能显示部分内容，视觉上杂乱且不符合"首屏聚焦"的设计原则。需要将建议卡片改为紧凑预览模式，点击后跳转到独立页面查看完整内容。

## What Changes

- **前端**：将首页 `AdviceCard` 替换为紧凑型预览卡片（`CompactAdviceCard`），高度控制在 ~100px，只显示一句天气/农事总结 + 建议数量
- **前端**：新建 `AdviceDetailScreen` 页面，展示完整的建议列表（带天气灵宠 Emoji、优先级标签、展开动画）
- **前端**：导航栈新增 `AdviceDetail` 路由，从首页点击预览卡片可跳转
- **后端**：`DailyAdviceResponse` 新增 `preview` 字段（≤20 字），由 LLM 在生成建议时一并返回
- **后端**：修改 Prompt 模板，要求 LLM 返回 JSON 包含 `preview` + `items` 结构
- **后端**：更新 `_parse_advice_items` 解析逻辑，支持新的 JSON 结构（兼容旧格式 fallback）

## Capabilities

### New Capabilities
- `daily-advice-preview`: 首页紧凑预览卡片与详情页展示

### Modified Capabilities
- `structured-daily-advice`: LLM 输出格式扩展，新增 `preview` 字段；Schema 和解析逻辑更新

## Impact

- **前端**: `HomeScreen.tsx`, `AdviceCard.tsx`, 新增 `CompactAdviceCard.tsx` + `AdviceDetailScreen.tsx`, 导航配置更新
- **后端**: `app/schemas/agent.py`, `app/services/agent_service.py`, `app/api/agent.py`（DailyAdviceResponse 序列化）
- **API 兼容**: 旧版客户端仍可通过 `advice` computed_field 获取拼接文本，无 BREAKING
- **数据库**: 无需迁移，缓存的 JSON 文本在刷新后自动采用新格式
