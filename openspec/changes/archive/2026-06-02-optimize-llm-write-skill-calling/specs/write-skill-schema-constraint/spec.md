## ADDED Requirements

### Requirement: Category parameter must use existing user labels
The `create_cost_record` skill's `category` parameter SHALL be constrained to values from the user's `cost_categories` table. The system SHALL NOT allow LLM to freely create new category labels during write operations.

#### Scenario: Successful constrained category selection
- **WHEN** the user says "买了200块化肥"
- **AND** the user's existing labels include "化肥"
- **THEN** the LLM SHALL select "化肥" from the enum list
- **AND** the tool call SHALL succeed validation

#### Scenario: Closest match for non-existent category
- **WHEN** the user says "买了200块复合肥"
- **AND** the user's existing labels include "化肥" but not "复合肥"
- **THEN** the LLM SHALL select "化肥" (the closest match) from the enum list
- **AND** the pending action SHALL include a note: "您说的是'复合肥'，系统中暂无此分类，已归入'化肥'"

#### Scenario: Rejection of category creation by LLM
- **WHEN** the user says "买了200块无人机租赁费"
- **AND** the user's existing labels do not include any similar category
- **THEN** the LLM SHALL select the closest available category (e.g., "其他")
- **AND** the system SHALL NOT automatically create a new category
- **AND** the pending action SHALL prompt the user to manually add the new category in settings

### Requirement: Dynamic enum loading from database
The system SHALL dynamically load the user's cost category labels from the database and inject them into the skill's JSON Schema enum field when generating LangChain tools.

#### Scenario: Fresh tool generation with current labels
- **WHEN** a conversation starts for a farm
- **THEN** the system SHALL query the `cost_categories` table for that farm
- **AND** generate the `create_cost_record` tool schema with `category.enum` populated from the query results

#### Scenario: No labels exist yet
- **WHEN** a farm has no cost categories configured
- **THEN** the system SHALL use a sensible default enum: ["化肥", "种子", "农药", "人工", "其他"]
- **AND** the pending action SHALL prompt the user to configure their categories in settings

### Requirement: Pydantic parameter validation with self-correction
The system SHALL validate tool call parameters using Pydantic before they reach the skill execution layer. Validation failures SHALL be returned to the LLM as structured error messages, allowing the LLM to self-correct in the next reasoning step.

#### Scenario: Missing required parameter triggers self-correction
- **WHEN** the LLM calls `create_cost_record` without providing `amount`
- **THEN** the Pydantic validator SHALL reject the call with error: "amount: 必填参数缺失"
- **AND** the error SHALL be returned to the LLM as a ToolMessage
- **AND** the LLM SHALL generate a new tool call with the missing parameter
- **AND** the user SHALL NOT see a pending action with invalid parameters

#### Scenario: Invalid parameter type triggers self-correction
- **WHEN** the LLM calls `create_cost_record` with `amount="两百"` (string instead of number)
- **THEN** the Pydantic validator SHALL reject the call with error: "amount: 必须是数字"
- **AND** the error SHALL be returned to the LLM for correction
