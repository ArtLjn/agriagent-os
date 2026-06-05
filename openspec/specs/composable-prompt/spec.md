## Purpose

定义 composable-prompt 能力的行为要求。

## Requirements

### Requirement: Snippet 文件组织
所有 prompt 片段 SHALL 存放在 `prompts/snippets/` 目录下，每个文件为一个独立的 snippet。文件名格式为 `<priority>-<name>.j2`（如 `p1-language.j2`、`p3-format.j2`）。每个 snippet 文件 SHALL 只包含一个关注点的 prompt 内容，不超过 15 行。

#### Scenario: snippet 文件存在且可加载
- **WHEN** `prompts/snippets/p1-language.j2` 文件存在
- **THEN** `PromptComposer` 可通过 `snippets["p1-language"]` 获取并渲染该 snippet

#### Scenario: snippet 行数限制
- **WHEN** 检查任意 snippet 文件
- **THEN** 文件行数不超过 15 行

### Requirement: Composer 按场景组合 snippet
系统 SHALL 提供 `PromptComposer` 类，根据 `config.yaml` 中的 `compositions` 配置，按场景组合 snippet 渲染最终 system prompt。组合结果 SHALL 按 priority 排序（P1 → P2 → P3 → P4），同 priority 内按配置顺序排列。

#### Scenario: system_base 场景组合
- **WHEN** 调用 `composer.compose("system_base", variables={"display_name": "老李", "farm_location": "苏州"})`
- **THEN** 按配置的 snippet 列表逐个渲染，按 priority 排序后拼接为完整 system prompt

#### Scenario: cost_parse 场景复用语言 snippet
- **WHEN** 调用 `composer.compose("cost_parse", variables={"description": "人工费300"})`
- **THEN** 渲染结果包含 `p1-language.j2` snippet 的语言规则（与 system_base 共享同一 snippet，无重复定义）

#### Scenario: 未配置场景抛异常
- **WHEN** 调用 `composer.compose("nonexistent_scene")`
- **THEN** 抛出 KeyError，日志记录场景未配置

### Requirement: 场景组合配置
`prompts/config.yaml` SHALL 新增 `compositions` 段，定义每个场景使用的 snippet 列表。每个 composition 包含 `snippets` 数组（snippet 名称列表）和可选的 `separator` 字段。

#### Scenario: config.yaml 包含 compositions
- **WHEN** 查看 `prompts/config.yaml`
- **THEN** 存在 `compositions` 段，包含 `system_base`、`cost_parse`、`crop_template_parse`、`cycle_parse`、`report` 等场景配置

#### Scenario: compositions 引用不存在的 snippet
- **WHEN** `compositions.system_base.snippets` 包含 `"p1-nonexistent"`
- **THEN** `PromptComposer` 初始化时记录警告日志，跳过该 snippet（不崩溃）

### Requirement: Snippet 去重
同一场景内 SHALL 自动去重同名 snippet，避免重复内容。不同场景可引用同一 snippet（如 `p1-language.j2` 被多个场景复用）。

#### Scenario: 场景内重复引用
- **WHEN** `compositions.system_base.snippets` 包含两个 `"p1-language"`
- **THEN** 渲染结果中语言规则只出现一次

#### Scenario: 跨场景共享
- **WHEN** `system_base` 和 `cost_parse` 都引用 `p1-language.j2`
- **THEN** 两个场景各自的渲染结果中都包含语言规则，且内容一致（来自同一文件）
