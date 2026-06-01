## ADDED Requirements

### Requirement: Trace 列表显示分类耗时
Trace 列表的每条记录头部 SHALL 显示该 trace 的各类型节点耗时汇总信息。

#### Scenario: 展开 trace 后显示耗时汇总
- **WHEN** 用户展开一条 trace 记录
- **THEN** 系统 SHALL 在列表头部该行内展示一个「复制耗时」按钮
- **AND** 按钮 SHALL 在 timeline 数据加载完成后可用

### Requirement: 一键复制耗时分析
用户 SHALL 能够一键将 trace 的详细耗时分析复制为 Markdown 表格格式。

#### Scenario: 复制耗时分析
- **WHEN** 用户点击「复制耗时」按钮
- **THEN** 系统 SHALL 遍历该 trace 的所有节点，按 `node_type` 分组累加 `duration_ms`
- **AND** 生成包含以下列的 Markdown 表格：节点类型、累计耗时(ms)、占比、节点数
- **AND** 表格底部 SHALL 包含总耗时行
- **AND** 将 Markdown 文本写入剪贴板
- **AND** 显示成功提示

#### Scenario: 复制失败
- **WHEN** 剪贴板 API 不可用或写入失败
- **THEN** 系统 SHALL 显示错误提示
- **AND** 按钮 SHALL 保持可用状态

### Requirement: 耗时按钮状态管理
「复制耗时」按钮 SHALL 仅在 timeline 数据加载完成后可用，加载中时显示禁用状态。

#### Scenario: timeline 加载中
- **WHEN** 用户展开 trace 但 timeline 仍在加载
- **THEN** 「复制耗时」按钮 SHALL 显示为禁用状态
- **AND** 加载完成后 SHALL 自动变为可用
