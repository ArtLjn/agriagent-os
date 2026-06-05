## Purpose

定义 pending-action-context-display 能力的行为要求。

## Requirements

### Requirement: Confirmation message shows three-layer context
The pending action confirmation message SHALL include three layers of information: (1) the user's original message understanding, (2) the extracted parameters, and (3) the action to be executed.

#### Scenario: Complete context display for cost record
- **WHEN** the user says "昨天买了200块化肥"
- **AND** a pending action is generated for `create_cost_record`
- **THEN** the confirmation message SHALL be:
  - Line 1: "💰 确认记账：化肥 200元（支出）"
  - Line 2: "📝 理解：您说的是'昨天买了200块化肥'"
  - Line 3: "📋 参数：金额=200, 分类=化肥, 日期=2026-06-02"

#### Scenario: Note for closest-match category
- **WHEN** the user says "买了200块复合肥"
- **AND** the system matched it to "化肥" (closest existing label)
- **THEN** the confirmation message SHALL include:
  - "⚠️ 注：您说的是'复合肥'，系统中暂无此分类，已归入'化肥'。可在设置中添加新分类。"

### Requirement: Structured pending action response
The `PendingActionResponse` API response SHALL include a `context` field containing the original user message, extracted parameters, and any notes or warnings.

#### Scenario: API response includes context
- **WHEN** the frontend receives a pending action for `create_cost_record`
- **THEN** the response SHALL include:
  - `context.original_input`: "昨天买了200块化肥"
  - `context.extracted_params`: {"amount": 200, "category": "化肥"}
  - `context.notes`: [] (or notes about closest-match if applicable)
