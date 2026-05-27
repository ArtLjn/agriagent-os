## Why

后端 `app/core/` 目录堆积 19 个模块（1,526 行），职责混杂：基础设施（config/database/logger）和业务逻辑（guardrails/prompt_registry/pending_actions）混在一起。同时存在多处死代码和重复数据源，增加维护负担和理解成本。在 storage-redesign 多用户改造之前，先清理冗余代码、整理目录职责，避免在混乱的基础上叠加新功能。

## What Changes

1. 删除已确认的死代码（`term_whitelist.py` 零引用）
2. 消除 `prompt_registry.py` 中 `_DEFAULT_PROMPTS` 与 `prompts/*.j2` 文件的重复，统一为文件单一数据源
3. 将 `core/` 中的 Agent 专属模块（llm、guardrails、prompt 相关）移入 `agent/` 包，让 core 只保留真正的基础设施
4. 建立 `infra/` 包承载可观测性和运维模块（trace、circuit_breaker、limiter）

## Capabilities

### New Capabilities
<!-- 无新增功能 -->

### Modified Capabilities
- `prompt-management`: 删除 `_DEFAULT_PROMPTS` 硬编码副本，统一使用 `prompts/` 目录文件作为唯一数据源；模板加载失败时明确报错而非返回过时内容

## Impact

- **代码删除**：`core/term_whitelist.py` 整文件删除
- **代码修改**：`core/prompt_registry.py`（删除 `_DEFAULT_PROMPTS`、移除 `get_fallback`）、`core/prompt_renderer.py`（移除 fallback 逻辑改为异常抛出）
- **文件移动**：~8 个模块从 `core/` 移至 `agent/` 或 `infra/`
- **import 更新**：所有引用被移动模块的文件需更新 import 路径（约 30+ 处）
- **测试更新**：对应测试文件的 import 路径同步更新
- **无 API 变化**：所有改动均为内部重组，不影响外部接口
