# 05 — Prompt 工程

> 状态：草稿 | 维护：BlockShip | 关联：[01_Agent平台架构](./01_Agent平台架构.md)、[03_Context工程](./03_Context工程.md)、权威 [04_相关规范/01_Prompt与人设规范](../04_相关规范/01_Prompt与人设规范.md)

---

## 1. 为什么需要 Prompt 工程

裸写 prompt 会：
- 没有版本控制（改一次回滚困难）
- 没有 A/B（不知道新版好不好）
- 没有复用（同一段系统提示在多处重复）
- 没有快照测试（改了 prompt 不知道哪些 case 会退化）

Prompt 工程的目标：**把 prompt 当代码一样治理**。

## 2. 核心组件

```
prompt/
├── registry.py             # Prompt Registry：注册所有 prompt
├── composer.py             # Composer：把 snippets 组合成最终 prompt
├── renderer.py             # Renderer：Jinja2 渲染
├── policy.py               # 策略：何时用哪个 prompt 版本
├── models.py               # PromptInput / PromptOutput 模型
├── cache.py                # Prompt Cache（同输入复用）
└── replay.py               # 回放：用历史 trace 重放 prompt

backend/prompts/
└── snippets/               # Jinja2 片段文件
    ├── system/
    │   ├── agent_role.md.j2
    │   ├── farm_facts.md.j2
    │   ├── user_settings.md.j2
    │   └── ...
    ├── skills/
    │   ├── cost_record_summary.md.j2
    │   └── ...
    └── persona/
        ├── warm.md.j2
        ├── professional.md.j2
        └── creative.md.j2
```

**禁止**：在 `app/prompt/snippets/` 放空包；真实片段文件在 `backend/prompts/snippets/`。

## 3. Prompt 结构

最终 system prompt 由以下 snippet 组合而成：

```
1. agent_role            — Agent 身份（农场管家）
2. persona               — 人设（professional / warm / creative）
3. farm_facts            — 农场基础信息
4. user_settings         — 用户偏好
5. cycle_facts           — 当前茬口（如有）
6. ledger_snapshot       — 账务快照（如有）
7. weather_snapshot      — 天气（如有）
8. memory_view           — 短时记忆 + 长时记忆摘要
9. conversation_summary  — 最近对话摘要
10. skill_catalog        — 候选 Skill 摘要（第一层）
11. skill_detail         — load_skill 时注入（第二层）
12. output_format        — 输出格式约束
13. behavior_rules       — 行为准则（Pending、确认话术）
```

## 4. Composer 工作流程

```python
class PromptComposer:
    def compose(self, request: PromptInput) -> str:
        """
        PromptInput:
          - persona: str
          - context_bundle: ContextBundle
          - intent: Intent
          - candidates: list[str]  # 候选 Skill
          - tool_results: list[ToolMessage]  # 当前轮工具结果
        """
        snippets = []
        snippets.append(self.registry.render("system/agent_role"))
        snippets.append(self.registry.render(f"persona/{request.persona}"))
        snippets.append(self.registry.render("system/farm_facts", request.context_bundle.farm))
        # ... 其他 snippet
        snippets.append(self.registry.render("system/skill_catalog", {"skills": request.candidates}))
        snippets.append(self.registry.render("system/output_format"))
        return "\n\n---\n\n".join(snippets)
```

## 5. 人设（Persona）

参考 `prompts/assistant_roles.yaml`：

| 人设 ID | 标签 | 适用场景 | 风格 | 温度 |
| --- | --- | --- | --- | --- |
| `professional` | 专业型 | 商务用户、严肃场景 | 简洁、准确、不寒暄 | 0.3 |
| `warm`（默认） | 温馨型 | 主流农户 | 亲切、关怀、口语化 | 0.5 |
| `creative` | 创意型 | 年轻用户、新农人 | 活泼、有梗、有建议 | 0.7 |

**切换方式**：用户在 App 设置中切换；持久化到 `user_settings.assistant_role`。

详细人设 prompt 见 [04_相关规范/01_Prompt与人设规范](../04_相关规范/01_Prompt与人设规范.md)。

## 6. Skill Catalog 注入（第一层）

每个 Skill 在 `skill.md` 中的 `description` + `triggers` 被提取，组合成 system prompt 的一段「Skill 路由表」：

```markdown
## 可用技能（部分）

| Skill | 触发词 | 用途 |
| --- | --- | --- |
| create_cost_record | 记账、买了、卖了、赊账 | 记一笔账 |
| get_cost_summary | 这个月花了多少 | 查询成本汇总 |
| ...

如需详细调用规范，使用 load_skill 工具加载。
```

第一层只放摘要（每个 Skill ≤ 50 token），节省 system prompt。

## 7. Skill Detail 注入（第二层）

LLM 调用 `load_skill(skill_name)` 时，Executor 把完整 skill.md 内容注入为 tool_result：

```python
async def load_skill(skill_name: str) -> str:
    skill = self.registry.get(skill_name)
    return f"# {skill.name}\n\n{skill.full_prompt}\n\n## 工具\n{skill.tools_schema}"
```

第二层是按需加载，避免一开始就塞全量 Skill。

## 8. Prompt Caching

Anthropic Prompt Caching 把 system prompt 缓存，命中可节省 90% 的处理成本。

```python
class CachedPrompt:
    def to_anthropic(self) -> list[dict]:
        return [{
            "type": "text",
            "text": self.content,
            "cache_control": {"type": "ephemeral"},
        }]
```

**缓存策略**：
- system prompt 骨架（agent_role + persona + output_format）→ 静态，cache TTL 长
- ContextBundle 部分 → 动态，不 cache
- 用户偏好 → 半静态，cache 5 分钟

## 9. Prompt 版本治理

```
每个 snippet 文件带 frontmatter：
---
version: 1.2
last_updated: 2026-06-19
changelog:
  - v1.2: 增加 Pending Action 说明
  - v1.1: 优化人设切换文案
  - v1.0: 初版
---

prompt 内容...
```

**版本策略**：
- 同一 snippet 的不同版本通过 git tag 管理
- 重构 prompt 必须保留旧版本号 30 天
- Evaluation 跑回归时优先用 latest，可指定版本

## 10. Replay（回放）

```python
class PromptReplay:
    def replay(self, trace_id: str) -> ReplayResult:
        """根据 trace_id 还原当时的 system prompt + messages + tool_results。"""
```

用途：
- 调试：为什么这次回复是这样？
- Evaluation：跑历史 trace 看新 prompt 是否退化
- DataFlywheel：标注 bad case 时看完整 prompt

## 11. 边界与禁止

- Composer 不直接查数据库（通过 ContextBundle 输入）
- Composer 不调 LLM
- Snippets 不硬编码业务数据（用变量）
- 同一逻辑只有一处 snippet 实现（不重复）
- Prompt 中的敏感词由 `filter_output` 兜底，不在 prompt 里写黑名单

## 12. 当前状态

- ✅ Registry / Composer / Renderer 骨架
- ✅ Cache 适配 Anthropic SDK
- ✅ Snippets 模板文件（system / persona / skills）
- ✅ Replay 接口
- 🚧 版本治理细化（changelog、A/B）
- 🚧 Snapshot 测试（捕获 prompt 退化）

## 13. 相关文档

- [01_Agent平台架构](./01_Agent平台架构.md)
- [03_Context工程](./03_Context工程.md)
- [02_Skill引擎与契约](./02_Skill引擎与契约.md)
- [04_相关规范/01_Prompt与人设规范](../04_相关规范/01_Prompt与人设规范.md)
