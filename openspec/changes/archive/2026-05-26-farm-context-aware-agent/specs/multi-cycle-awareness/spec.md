## ADDED Requirements

### Requirement: 茬口状态自动计算
系统 SHALL 根据茬口各阶段的起止日期自动计算茬口状态，无需用户手动维护。

#### Scenario: 活跃茬口
- **WHEN** 今天 2026-05-25 落在某茬口任一阶段的 start_date 和 end_date 之间
- **THEN** 该茬口状态自动为 `active`

#### Scenario: 未来茬口
- **WHEN** 某茬口所有阶段的 start_date 都在今天之后
- **THEN** 该茬口状态自动为 `upcoming`

#### Scenario: 已完成茬口
- **WHEN** 某茬口所有阶段的 end_date 都在今天之前
- **THEN** 该茬口状态自动为 `completed`

#### Scenario: 手动暂停覆盖
- **WHEN** 用户手动将茬口标记为 `paused`
- **THEN** 自动计算被覆盖，状态保持 `paused`，直到用户手动解除

### Requirement: 活跃茬口查询
系统 SHALL 提供按状态查询茬口的接口，支持查询农场的所有活跃茬口。

#### Scenario: 查询活跃茬口
- **WHEN** 请求 `GET /cycles?status=active`
- **THEN** 返回该农场所有 `active` 状态的茬口列表，包含当前阶段名称和阶段起止日期

### Requirement: 多茬口并行展示
移动端每日建议页面 SHALL 支持展示多个活跃茬口的建议，每个茬口一个卡片。

#### Scenario: 单作物活跃
- **WHEN** 农场只有一个 `active` 茬口（春季西瓜）
- **THEN** 每日建议页面显示单张卡片，标题"春季西瓜"，内容为该作物的建议

#### Scenario: 多作物并行
- **WHEN** 农场有两个 `active` 茬口（春季西瓜、秋季豆角）
- **THEN** 每日建议页面显示两张卡片，分别展示两种作物的建议，卡片可上下滑动浏览

#### Scenario: 无活跃茬口
- **WHEN** 农场没有 `active` 茬口
- **THEN** 显示提示"当前没有进行中的种植周期，请创建茬口以获取建议"
