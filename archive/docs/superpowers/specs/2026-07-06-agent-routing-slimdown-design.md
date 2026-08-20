# Agent Routing Slimdown Design

## Goal

简化 Agent 工具选择链路：普通读请求交给主模型通过 Function Calling 选择工具，规则系统退回安全护栏位置。

## Current Problem

当前工具选择同时经过 `RuleIntentClassifier`、`SkillRouter`、`select_tools`、`direct_routing` 和 runtime 绑定逻辑。多层规则都会影响最终工具集合，导致普通查询需要不断追加中文关键词，链路排查也难以判断到底是哪一层覆盖了模型判断。

`skillify-sdk` 仍被 Skill 注册、Skill 基类和结果模型依赖，本次不删除。删除 SDK 需要先迁移 `SkillManager`、`Skill`、`SkillResult` 和 `ResultStatus`，属于二期。

## Scope

本次只瘦工具选择链路：

- 普通读请求绑定 enabled read tools，`tool_choice=auto`。
- 写操作继续使用规则识别和 pending action 确认。
- 保留禁用工具过滤、工具调用白名单过滤、已有工具结果后的 final answer 不重绑工具。
- 移除查询类 `force_binding` 对 runtime 的影响。
- 移除普通读请求的 deterministic direct routing 快通道。
- 移除 `LLMIntentClassifier` 小模型兜底入口。

不在本次做：

- 不迁移或删除 `backend/skillify-sdk`。
- 不重写 Skill 执行器。
- 不改 Context、Memory、DataFlywheel 主链路。

## Target Flow

```text
用户输入
  -> Runtime 判断 pending action / 已有工具结果
  -> 写操作：规则识别 + 确认护栏
  -> 普通读请求：绑定 enabled read tools
  -> 主模型 Function Calling 选择工具
  -> Tool Executor 白名单过滤并执行
  -> Final answer
```

## Testing Contract

- 普通读请求不再要求某个 query skill 出现在 `force_binding`。
- 普通读请求应绑定只读工具池，并保持 `tool_choice=auto`。
- 写操作请求仍能产生需要确认的 `RouterDecision`。
- 禁用工具不应暴露给模型。
- 已有普通 `ToolMessage` 的 final answer 轮不重新绑定工具。
