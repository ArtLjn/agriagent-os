## MODIFIED Requirements

### Requirement: 建茬口 Skill（create_crop_cycle）
后端 SHALL 提供 `create_crop_cycle` Skill，Agent 可通过对话创建种植茬口。该 Skill MUST 仅用于创建新茬口；当用户明确表达修改、调整、改成、推迟、提前或更正已有茬口时，Agent MUST 使用更新类 Skill，而不是追问是否新建。

#### Scenario: 完整参数建茬口
- **WHEN** 用户说「帮我建个秋季辣椒茬口」
- **THEN** Agent 提取参数（crop_name=辣椒, season=秋季），查找辣椒模板，向用户确认后创建茬口

#### Scenario: 无匹配模板时引导
- **WHEN** 用户说「帮我建个秋葵茬口」但系统无秋葵模板
- **THEN** Agent 回复「系统还没有秋葵模板，要帮你创建一个吗？需要知道各阶段大概多少天」

#### Scenario: 明确修改已有茬口不触发创建
- **WHEN** 用户说「修改玉米茬口9月1开始」
- **THEN** Agent MUST NOT 使用 `create_crop_cycle`
- **AND** Agent SHALL 进入已有茬口更新流程

### Requirement: 写操作确认机制
所有写操作 Skill 执行前 SHALL 先向用户展示提取的参数、目标对象、修改前后差异、自动推断依据和风险提示，获得用户确认后才执行。确认信息 SHALL 同时提供结构化 context 和兼容文本。

#### Scenario: 用户确认执行
- **WHEN** Agent 提取参数后展示「记一笔：化肥 200元，现金。确认？」，用户回复「确认」
- **THEN** 执行创建记录

#### Scenario: 用户修正参数
- **WHEN** Agent 展示「记一笔：化肥 200元，现金。确认？」，用户回复「是赊账」
- **THEN** Agent 修正参数（subtype=debt），重新展示确认

#### Scenario: 用户取消
- **WHEN** 用户回复「算了」或「取消」
- **THEN** 取消操作，不创建任何记录

#### Scenario: 展示茬口修改差异
- **WHEN** Agent 准备把夏季玉米茬口开始日期从 2026-06-05 修改为 2026-09-01
- **THEN** pending action context SHALL include target cycle, old start date, new start date, inferred crop name, inferred date, and editable fields

### Requirement: 写操作 Skill 通过 skillify 注册
所有写操作 Skill SHALL 和现有只读 Skill 一样通过 skillify 框架注册为 LangChain StructuredTool，复用现有的 Skill 发现和调用机制。注册结果 SHALL 同时包含 Skill runtime metadata，供 Tool Executor、ContextPolicy、Skill Registry 和 Evaluation 使用。

#### Scenario: Skill 注册
- **WHEN** 后端启动
- **THEN** 写操作 Skill 出现在 Agent 可调用的工具列表中
- **AND** 每个写操作 Skill 的 metadata 声明其权限等级为 `write_confirm`
