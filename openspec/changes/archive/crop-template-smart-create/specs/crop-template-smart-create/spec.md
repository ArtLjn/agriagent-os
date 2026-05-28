## ADDED Requirements

### Requirement: 自然语言解析作物模板
The system SHALL expose a `POST /crops/templates/parse` endpoint that accepts a natural language description and returns structured crop template data without persisting it.

#### Scenario: Parse crop description
- **WHEN** user sends a POST request to `/crops/templates/parse` with body `{ "description": "我想种8424西瓜" }`
- **THEN** the system MUST call an LLM to extract crop name, variety, and growth stages
- **AND** return a JSON response containing `name`, `variety`, and `stages` array

#### Scenario: Parse with variety
- **WHEN** user sends description containing a variety name like "圣女果番茄"
- **THEN** the system MUST separate crop name ("番茄") from variety ("圣女果")
- **AND** include both in the response

#### Scenario: Parse failure fallback
- **WHEN** the LLM fails to generate valid stages
- **THEN** the system MUST return a 422 error with a clear message
- **AND** MUST NOT create any database records

### Requirement: 手动创建作物模板
The system SHALL allow users to create crop templates via `POST /crops/templates` with manually provided data.

#### Scenario: Create template with stages
- **WHEN** user sends a POST request with `name`, optional `variety`, and `stages` array
- **THEN** the system MUST create a crop template with the specified growth stages
- **AND** return the created template with assigned IDs

#### Scenario: Validate stage data
- **WHEN** a stage has `duration_days` less than 1 or greater than 365
- **THEN** the system MUST reject the request with a 422 validation error

### Requirement: 移动端智能创建界面
The mobile app SHALL provide a smart creation interface that allows natural language input to pre-fill the crop template form.

#### Scenario: Smart input pre-fills form
- **WHEN** user types "我想种8424西瓜" in the smart input field and submits
- **THEN** the app MUST call `POST /crops/templates/parse`
- **AND** pre-fill the form with the parsed name, variety, and stages

#### Scenario: Edit parsed results
- **WHEN** the form is pre-filled with AI-generated stages
- **THEN** user MUST be able to edit stage names, durations, and key tasks
- **AND** user MUST be able to add or remove stages

#### Scenario: Submit from pre-filled form
- **WHEN** user reviews and confirms the pre-filled form
- **THEN** the app MUST call `POST /crops/templates` to create the template
- **AND** navigate back to the template list on success

### Requirement: 移动端手动创建界面
The mobile app SHALL provide a manual creation interface for users who prefer direct form input.

#### Scenario: Empty form creation
- **WHEN** user chooses manual creation mode
- **THEN** the app MUST display an empty form with fields for name and variety
- **AND** an empty stages list with an "add stage" button

#### Scenario: Add growth stage
- **WHEN** user taps the "add stage" button
- **THEN** the app MUST add a new empty stage row with fields for name, duration_days, and key_tasks
- **AND** auto-assign the next order_index

#### Scenario: Remove growth stage
- **WHEN** user taps the remove button on a stage row
- **THEN** the app MUST remove that stage from the list
- **AND** renumber remaining stages' order_index sequentially
