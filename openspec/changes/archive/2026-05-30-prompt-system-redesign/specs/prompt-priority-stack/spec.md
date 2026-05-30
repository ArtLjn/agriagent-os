## ADDED Requirements

### Requirement: Priority Stack 层级定义
系统 SHALL 定义 4 个优先级层级，按以下顺序递减：P1 Safety（安全护栏）> P2 Accuracy（准确性）> P3 Format（格式规范）> P4 Context（动态上下文）。每个 snippet 文件 SHALL 通过文件名前缀标识所属层级（如 `p1-language.j2`、`p2-role.j2`）。

#### Scenario: priority 前缀识别
- **WHEN** `PromptComposer` 扫描 `snippets/` 目录
- **THEN** 文件名以 `p1-` 开头的 snippet 排在最前，`p4-` 排在最后

#### Scenario: 无效前缀处理
- **WHEN** `snippets/` 目录包含 `px-unknown.j2`（非 p1-p4 前缀）
- **THEN** `PromptComposer` 记录警告日志，将该 snippet 视为最低优先级排在末尾

### Requirement: prompt 中不再出现矛盾的最高优先级标注
重构后的 prompt SHALL 不包含多个互相矛盾的"最高优先级"标注。行为约束（如"禁止编造数据"）归入 P1 Safety 层级，格式规范归入 P3 Format 层级，层级关系由 Priority Stack 定义。

#### Scenario: 渲染结果无矛盾标注
- **WHEN** `composer.compose("system_base")` 渲染完成
- **THEN** 结果文本中不包含"最高优先级"措辞；安全护栏段标注"【安全护栏】"，格式段标注"【回复格式】"
