## REMOVED Requirements

### Requirement: looks_like_web_search 关键词规则函数

阶段 0 已删除 web_search 工具级特判(`_allow_model_choice_read_candidate` 中分支),`looks_like_web_search` 函数在整个仓库无调用方。本变更彻底删除该函数及其测试,让 web_search 与其他 read 工具完全平等。

#### Scenario: 函数不存在

- **WHEN** 任何代码路径尝试调用 `looks_like_web_search`
- **THEN** 该函数不存在,ImportError 阻塞编译(防止任何残留引用)
