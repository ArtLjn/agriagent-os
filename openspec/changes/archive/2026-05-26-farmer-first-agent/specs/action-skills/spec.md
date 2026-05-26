## ADDED Requirements

### Requirement: 记账 Skill（create_cost_record）
后端 SHALL 提供 `create_cost_record` Skill，Agent 可通过对话提取记账参数并创建成本/收入记录。

#### Scenario: 现结记账
- **WHEN** 用户说「昨天买了200块化肥」
- **THEN** Agent 提取参数（amount=200, category=化肥, record_date=昨天, subtype=direct），向用户确认后创建记录

#### Scenario: 赊账记账
- **WHEN** 用户说「在农资店老王那赊了3000块大棚膜」
- **THEN** Agent 提取参数（amount=3000, category=大棚膜, subtype=debt, counterparty=农资店老王），向用户确认后创建记录

#### Scenario: 缺少金额时追问
- **WHEN** 用户说「买了化肥」未提金额
- **THEN** Agent 追问「多少块钱的化肥？」，不自动填值

### Requirement: 建茬口 Skill（create_crop_cycle）
后端 SHALL 提供 `create_crop_cycle` Skill，Agent 可通过对话创建种植茬口。

#### Scenario: 完整参数建茬口
- **WHEN** 用户说「帮我建个秋季辣椒茬口」
- **THEN** Agent 提取参数（crop_name=辣椒, season=秋季），查找辣椒模板，向用户确认后创建茬口

#### Scenario: 无匹配模板时引导
- **WHEN** 用户说「帮我建个秋葵茬口」但系统无秋葵模板
- **THEN** Agent 回复「系统还没有秋葵模板，要帮你创建一个吗？需要知道各阶段大概多少天」

### Requirement: 记农事 Skill（log_farm_activity）
后端 SHALL 提供 `log_farm_activity` Skill，Agent 可通过对话记录农事操作。

#### Scenario: 记录农事
- **WHEN** 用户说「今天浇了水施了肥」
- **THEN** Agent 提取参数（activities=[浇水, 施肥], date=今天），向用户确认后创建农事记录

#### Scenario: 指定茬口
- **WHEN** 用户有 2 个活跃茬口（西瓜、豆角），说「给西瓜追肥了」
- **THEN** Agent 关联到西瓜茬口创建记录

### Requirement: 还赊账 Skill（settle_debt）
后端 SHALL 提供 `settle_debt` Skill，Agent 可通过对话结清赊账记录。

#### Scenario: 部分还款
- **WHEN** 用户说「还了老王1000块」
- **THEN** Agent 查找老王的赊账记录，创建还款记录（parent_record_id 指向原记录），更新剩余欠款

#### Scenario: 全额还清
- **WHEN** 用户说「老王的钱全还了」
- **THEN** Agent 查找老王的赊账记录总额，标记为已结清（settled_at=当前时间）

### Requirement: 更新阶段 Skill（update_crop_stage）
后端 SHALL 提供 `update_crop_stage` Skill，Agent 可通过对话更新茬口的生长阶段。

#### Scenario: 推进阶段
- **WHEN** 用户说「西瓜进膨大期了」
- **THEN** Agent 查找西瓜茬口，更新当前阶段为膨大期

### Requirement: 写操作确认机制
所有写操作 Skill 执行前 SHALL 先向用户展示提取的参数，获得用户确认后才执行。

#### Scenario: 用户确认执行
- **WHEN** Agent 提取参数后展示「记一笔：化肥 200元，现金。确认？」，用户回复「确认」
- **THEN** 执行创建记录

#### Scenario: 用户修正参数
- **WHEN** Agent 展示「记一笔：化肥 200元，现金。确认？」，用户回复「是赊账」
- **THEN** Agent 修正参数（subtype=debt），重新展示确认

#### Scenario: 用户取消
- **WHEN** 用户回复「算了」或「取消」
- **THEN** 取消操作，不创建任何记录

### Requirement: pending_action 存储在内存
写操作确认流程中的 pending_action SHALL 存储在内存字典中（farm_id → action），不持久化。

#### Scenario: 重启后清除
- **WHEN** 后端重启
- **THEN** 所有 pending_action 被清除，未确认的操作丢失

### Requirement: 写操作 Skill 通过 skillify 注册
所有写操作 Skill SHALL 和现有只读 Skill 一样通过 skillify 框架注册为 LangChain StructuredTool，复用现有的 Skill 发现和调用机制。

#### Scenario: Skill 注册
- **WHEN** 后端启动
- **THEN** 5 个写操作 Skill 出现在 Agent 可调用的工具列表中
