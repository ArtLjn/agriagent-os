## Why

当前 LLM 输出纯文本，没有 emoji、没有格式美化，在手机端体验干涩。关键场景（天气预报、记账确认、茬口创建、每日建议）返回的数据有结构但展示无层次，农民用户难以快速抓住重点。

## What Changes

- **Prompt 模板** `base.j2` 增加格式规则：要求 LLM 使用 emoji 前缀、Markdown 列表/加粗/标题、口语化短句
- **天气预报** `weather` skill 的 `_format_reply` 改为 Markdown 表格 + emoji 天气图标
- **记账确认** `build_confirm_message` 改为 emoji + 可读格式（💰 记账：化肥 50元）
- **茬口创建结果** `create_crop_cycle` skill 的 `_format_reply` 改为 emoji + 表格展示阶段规划
- **每日建议** 保持 LLM 自由输出，但 prompt 要求 emoji + 列表格式

## Capabilities

### New Capabilities
- `structured-reply-format`: 定义各 skill 场景的 Markdown 格式模板，覆盖天气预报、记账确认、茬口创建结果三个核心场景

### Modified Capabilities

## Impact

- `backend/prompts/base.j2`: 新增【回复风格】段落
- `backend/app/agent/skills/weather/scripts/main.py`: 天气回复格式改为 Markdown 表格
- `backend/app/agent/skills/create-crop-cycle/scripts/main.py`: 茬口创建结果改为 emoji + 列表
- `backend/app/agent/skills/create-cost-record/scripts/main.py`: 记账成功回复加 emoji
- `backend/app/infra/pending_actions.py`: `build_confirm_message` 加 emoji + 可读参数
- 前端无需改动 — 已支持 Markdown 渲染
