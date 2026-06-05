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
