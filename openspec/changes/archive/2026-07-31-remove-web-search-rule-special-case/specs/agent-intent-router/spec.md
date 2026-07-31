## ADDED Requirements

### Requirement: Read 候选工具门控

SkillRouter 对 read 候选工具 MUST NOT 针对单一工具做关键词二次校验。BM25+向量召回(Layer 1)产出的 read 候选 MUST 直接进入 LLM 自选(Layer 3),Layer 2 硬规则门禁 SHALL 仅用于:写操作风险分级、寒暄/教程兜底、schema token 预算。

#### Scenario: web_search 候选不再被关键词二次过滤

- **WHEN** 用户输入 "今天苏州西瓜价格是" 且 BM25+向量已将 web_search 召回至 top-K
- **THEN** web_search MUST 出现在 LLM 自选的 bind_tools 列表中,MUST NOT 因 `looks_like_web_search` 关键词规则被踢出

#### Scenario: 其他 read 工具行为不变

- **WHEN** 用户输入 "查询我的农场茬口" 且 BM25+向量召回 get_farm_status
- **THEN** 路由结果 SHALL 与删除 web_search 特判前一致,MUST NOT 引入回归

#### Scenario: 写操作门控保留

- **WHEN** 用户输入涉及写操作(如 "帮我记账 200 元")
- **THEN** 仍 MUST 走 write_confirm/write_high 硬规则门禁,本变更 MUST NOT 影响写操作路径
