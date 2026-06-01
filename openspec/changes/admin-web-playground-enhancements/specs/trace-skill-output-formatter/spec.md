## ADDED Requirements

### Requirement: Skill 输出结构化渲染
Trace 节点详情 Drawer 中对 `skill_call` 类型节点的 `output_data` SHALL 进行结构化解析并渲染。

#### Scenario: 正常格式化展示
- **WHEN** 用户点击 `skill_call` 类型节点打开详情 Drawer
- **THEN** 系统 SHALL 解析 `output_data` JSON，提取 `reply_preview` 字段作为首屏内容展示
- **AND** 其余字段折叠在可展开的详情区域中
- **AND** 展示一个「复制格式化内容」按钮

### Requirement: 格式化失败回退
当 `output_data` 无法解析为结构化 JSON 时，系统 SHALL 回退到原始 JSON 字符串展示。

#### Scenario: 解析失败回退
- **WHEN** `output_data` 不是有效 JSON 或不含 `reply_preview` 字段
- **THEN** 系统 SHALL 直接展示原始 `output_data` 字符串
- **AND** 不显示「复制格式化内容」按钮

### Requirement: 一键复制格式化内容
用户 SHALL 能够一键复制 Skill 输出的格式化内容到剪贴板。

#### Scenario: 复制成功
- **WHEN** 用户点击「复制格式化内容」按钮
- **THEN** 系统 SHALL 将 `reply_preview` 内容写入剪贴板
- **AND** 显示成功提示

#### Scenario: 复制失败
- **WHEN** 剪贴板 API 不可用或写入失败
- **THEN** 系统 SHALL 显示错误提示，不抛出异常
