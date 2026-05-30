## 1. 基础设施：Snippet 目录与文件

- [ ] 1.1 创建 `prompts/snippets/` 目录，拆分 base.j2 为 7 个 snippet 文件：`p1-language.j2`、`p1-tool-guardrails.j2`、`p2-role.j2`、`p2-capability.j2`、`p3-format.j2`、`p3-style.j2`、`p4-context.j2`
- [ ] 1.2 在 `config.yaml` 新增 `compositions` 段，配置 `system_base`、`cost_parse`、`crop_template_parse`、`cycle_parse`、`report` 五个场景的 snippet 组合列表

## 2. Composer 核心实现

- [ ] 2.1 新增 `app/agent/prompt_composer.py`，实现 `PromptComposer` 类：加载 snippets、按 priority 排序、渲染拼接、去重
- [ ] 2.2 `PromptComposer` 支持从 `config.yaml` 的 `compositions` 段读取场景配置，支持 Jinja2 变量统一注入后分发给各 snippet

## 3. 接入层切换

- [ ] 3.1 修改 `advisor.py`：从 `render_prompt("system_base")` 切换为 `composer.compose("system_base")`
- [ ] 3.2 修改 cost_parse / crop_template_parse / cycle_parse / report 的调用方式，使用 Composer 组合（消除各 .j2 中重复的语言规则块）

## 4. 清理冗余

- [ ] 4.1 确认 base.j2 中 12 条工具触发规则已移除（Spike 已完成），确认【农场状态查询】段已移除
- [ ] 4.2 移除 base.j2 中三个互相矛盾的"最高优先级"标注，改为各 snippet 内的层级标注
- [ ] 4.3 清理 cost_parse.j2 / crop_template_parse.j2 / cycle_parse.j2 中重复的语言规则块，改为通过 Composer 引用 `p1-language.j2`

## 5. 测试更新

- [ ] 5.1 新增 `tests/test_prompt_composer.py`：覆盖 snippet 加载、priority 排序、场景组合、去重、缺失场景异常
- [ ] 5.2 更新 `tests/test_context_engineering_e2e.py`：确认已有 Spike 验证测试（`test_base_prompt_no_hardcoded_tool_routing`、`test_tool_chain_handles_farm_status_routing`）通过
- [ ] 5.3 新增 Priority Stack 测试：验证渲染结果不包含"最高优先级"矛盾标注，验证 priority 排序正确

## 6. 文档同步

- [ ] 6.1 更新 `docs/architecture/backend-architecture.md` 中 Agent 内部架构图和 prompt 管理模块描述
