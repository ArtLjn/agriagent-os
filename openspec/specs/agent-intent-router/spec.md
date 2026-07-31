## Purpose

定义 agent-intent-router 能力的行为要求。
## Requirements
### Requirement: Intent-based routing for user input
The system SHALL route user input based on intent classification: greetings/chitchat SHALL receive direct replies without tool calling; data queries SHALL prefer read skills; write operations SHALL follow the full tool calling flow.

#### Scenario: Greeting bypasses tool calling
- **WHEN** the user says "你好" or "在吗"
- **THEN** the system SHALL reply with a greeting directly
- **AND** the system SHALL NOT invoke the LangGraph agent
- **AND** the response latency SHALL be < 100ms

#### Scenario: Statistics query uses read skills
- **WHEN** the user says "上个月花了多少钱"
- **THEN** the system SHALL route to the LangGraph agent
- **AND** the agent SHALL prefer read skills (cost summary, analytics) over write skills
- **AND** if no read skill is available, the agent SHALL answer from its knowledge

#### Scenario: Write operation uses full flow
- **WHEN** the user says "记一笔账"
- **THEN** the system SHALL route to the LangGraph agent
- **AND** the agent SHALL use the full write skill flow including pending confirmation

### Requirement: Conservative routing default
When intent classification is ambiguous, the system SHALL default to the full LangGraph agent flow rather than risk missing a legitimate request.

#### Scenario: Ambiguous input goes to agent
- **WHEN** the user says "看看我的账"
- **AND** the intent is ambiguous between "query" and "unsure"
- **THEN** the system SHALL route to the LangGraph agent
- **AND** the agent SHALL determine the appropriate response

### Requirement: Registered Skill selection coverage
The system SHALL ensure every enabled registered Skill has an explicit selection path.

#### Scenario: Work order creation selected
- **WHEN** the user says "今天东大棚4个工人给西瓜授粉，每人200，先付老王200"
- **THEN** tool selection SHALL include `create_operation_work_order`
- **AND** the Agent SHALL enter the write confirmation flow

#### Scenario: Labor payable query selected
- **WHEN** the user says "老王还欠多少人工钱"
- **THEN** tool selection SHALL include `get_labor_payables`
- **AND** the Agent SHALL prefer the labor payable query Skill over generic cost summary

#### Scenario: Work order update selected
- **WHEN** the user says "刚才那条授粉记录不是付老王，是付老李200"
- **THEN** tool selection SHALL include `update_operation_work_order`
- **AND** the Agent SHALL create a pending action after target resolution

#### Scenario: Labor settlement selected
- **WHEN** the user says "给老王补付300人工"
- **THEN** tool selection SHALL include `settle_labor_payment`
- **AND** the Agent SHALL create a pending action showing affected labor entries

### Requirement: Selection audit parity with registry
The system SHALL provide a selection audit that compares registered enabled Skills with selector and chain policy coverage.

#### Scenario: Registered Skill omitted from selector
- **WHEN** a registered enabled Skill has no selector rule, classifier target, or declared fallback path
- **THEN** the audit SHALL report the Skill name and fail CI

#### Scenario: Disabled Skill omitted intentionally
- **WHEN** a Skill is registered but disabled by configuration
- **THEN** selector SHALL NOT return it
- **AND** the audit SHALL treat the omission as valid only if the disabled reason is declared

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

