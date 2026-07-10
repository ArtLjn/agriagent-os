## ADDED Requirements

### Requirement: Capability-based Skill routing
The Router SHALL select candidate tools by domain, capability, and operation using Registry metadata rather than exposing all enabled tools or relying only on legacy tool names.

#### Scenario: Cost creation routes to capability operation
- **WHEN** the user says "今天买了100元化肥"
- **THEN** the Router selects the `finance` domain
- **AND** the Router selects `manage_cost` as the capability
- **AND** the Router records `create_record` as the operation hint

#### Scenario: Cost query does not expose write operation
- **WHEN** the user says "这个月花了多少钱"
- **THEN** the Router selects a read operation under `manage_cost`
- **AND** the Router does not expose delete, settlement, or create write operations for that request

### Requirement: Explainable router decision
The Router SHALL record score and evidence for domain selection, capability retrieval, operation selection, rejected candidates, fallback, and clarification decisions.

#### Scenario: Router trace includes evidence
- **WHEN** the Router selects `manage_cost.create_record`
- **THEN** the Router trace includes matched examples, matched tags, matched entities, domain score, capability score, operation score, selected tools, and rejected candidates

#### Scenario: Ambiguous write produces clarification
- **WHEN** the user asks for a write operation but the target or action is ambiguous
- **THEN** the Router does not bind a write tool
- **AND** the Router returns a clarification reason in the decision

### Requirement: Progressive disclosure budget
The Router SHALL enforce a progressive disclosure budget that prevents fallback-all behavior and keeps normal tool binding small.

#### Scenario: Normal read request stays within budget
- **WHEN** the user asks a normal read request
- **THEN** the Router selects no more than two tools unless the request contains multiple explicit intents

#### Scenario: Fallback all is forbidden
- **WHEN** no candidate reaches the routing threshold
- **THEN** the Router returns no tools, a safe read fallback, or a clarification
- **AND** the Router does not return all enabled tools

### Requirement: Multi-intent write planning
The Router SHALL represent multiple dependent write intents as ordered plan frames instead of binding multiple write tools directly.

#### Scenario: Worker and work order become a plan
- **WHEN** the user says "招了一个工人王大妈工资100一天，早上让她去5号棚收水稻"
- **THEN** the Router creates one frame for `manage_workers.create_worker`
- **AND** the Router creates one dependent frame for `manage_work_orders.create_work_order`
- **AND** the write operations are stored as a pending plan requiring confirmation
