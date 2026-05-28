## Context

当前系统状态：
- 后端已有完整的作物模板 CRUD API（`POST/GET/PUT/DELETE /crops/templates`）
- 后端已有 `create-crop-template` skill，通过 LLM 自动生成生长阶段并直接入库
- 后端已有 `POST /costs/parse` 作为自然语言解析的模式参考
- 移动端 `CropTemplateScreen` 仅实现列表查看，"+"按钮弹出 Alert（"后续开放"）
- 移动端 `HomeScreen` 有4个快捷功能按钮，其中3个为跳转到 `AgentChat` 的占位按钮

## Goals / Non-Goals

**Goals:**
- 用户可通过自然语言描述快速生成作物模板草稿，经确认后创建
- 用户可通过传统表单手动创建作物模板
- 首页快捷功能仅保留有实际独立页面的入口

**Non-Goals:**
- 不修改 `create-crop-template` skill 的行为（保持AI聊天中直接创建的能力）
- 不做生长阶段的拖拽排序（增删改即可）
- 不做作物模板的图片上传
- 不改首页其他区域（天气卡片、AI简报等保持原样）

## Decisions

### 1. 新增独立 parse 端点，而非复用 skill

**方案A**：复用 `create-crop-template` skill，先创建再展示给用户编辑
**方案B**：新增 `POST /crops/templates/parse` 端点，只解析不入库

**选择方案B**。理由：
- 方案A会导致"先创建再编辑"，如果用户取消则产生垃圾数据
- 方案B与 `POST /costs/parse` 模式一致，前端认知成本低
- 方案B给用户完整的控制权，AI生成只是预填建议

### 2. 前端解析调用直接走 HTTP API，不走 Agent 聊天

**方案A**：通过 Agent 聊天流式返回解析结果
**方案B**：前端直接调用 `POST /crops/templates/parse` REST API

**选择方案B**。理由：
- 解析是一次性请求，不需要流式响应
- REST API 更可控，错误处理更简单
- 与智能记账（CostCreateScreen）的 `parseCost` 调用模式一致

### 3. 一个页面内双模式切换，非多步骤向导

**方案A**：分步向导（Step 1 选模式 → Step 2 填写 → Step 3 确认）
**方案B**：单页面内上下分区，顶部智能输入、底部分表单

**选择方案B**。理由：
- 参考智能记账截图的交互：顶部输入区 + 下面表单区，输入后自动填充
- 手动创建时用户可直接编辑表单，不需要额外步骤
- 页面结构更简单，代码量更少

### 4. prompt 复用 skill 的 system prompt，微调输出格式

`create-crop-template` skill 中的 `_SYSTEM_PROMPT` 已经过验证，可直接复用。只需确保输出格式明确包含 `variety` 字段。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| LLM 解析结果不稳定，阶段名称/天数不合理 | 前端提供编辑能力，用户可修改；后端设置合理的校验范围（如天数 1-365） |
| 与 `create-crop-template` skill 的 prompt 维护双份 | 将 prompt 提取到 `app/agent/prompt_registry.py` 统一管理 |
| 生长阶段编辑交互复杂（增删改） | 使用 FlatList + 每行一个阶段卡片，提供 +/- 按钮和输入框 |
| 幂等键缓存与 costs/parse 冲突 | 使用独立的 prompt key（如 `crop_template_parse`），IdempotencyKey 按 key 隔离 |

## Migration Plan

无需数据迁移。本次为纯新增功能：
1. 部署后端新增 API
2. 部署移动端新版本
3. 现有用户数据不受影响

## Open Questions

- 是否需要为 parse API 也添加幂等键缓存？（参考 costs/parse，建议加上）
- 生长阶段数量上限设多少合适？（建议 10 个）
