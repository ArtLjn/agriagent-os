## ADDED Requirements

### Requirement: 删除无引用的死代码模块
系统 SHALL 不包含零引用的模块文件。已确认 `core/term_whitelist.py`（`is_whitelisted` 函数和 `_AGRICULTURAL_TERMS` 集合）在整个项目中无任何调用，MUST 被删除。

#### Scenario: term_whitelist.py 已删除
- **WHEN** 检查 `backend/app/core/` 目录
- **THEN** 不存在 `term_whitelist.py` 文件

#### Scenario: 无残留引用
- **WHEN** 全局搜索 `term_whitelist`、`is_whitelisted`、`_AGRICULTURAL_TERMS`
- **THEN** 返回零结果
