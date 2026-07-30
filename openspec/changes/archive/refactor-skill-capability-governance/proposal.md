## Why

当前农业 AI Agent 的 Skill 数量已增长到 30 个以上，且同时存在 CRUD/API 粒度 Skill 和业务能力粒度 Skill，导致 Tool Selection 容易误选、路由规则持续膨胀、Skill 文档和 Router Registry 重复维护。

现在需要把 Skill 治理从“目录和旧工具名驱动”升级为“Registry + Business Capability 驱动”，让后续 100+ Skill 扩展时仍能保持可解释、可评测、可兼容和可渐进迁移。

## What Changes

- 引入 Registry-first 的 Skill 能力治理方式，以 `skills.yaml`、`aliases.yaml`、`domains.yaml` 作为 Skill 能力、旧工具名兼容、领域治理的事实源。
- 将对外 Skill 治理粒度从 CRUD/API Skill 收敛为 capability + operation，例如 `manage_cost.create_record`、`manage_cost.query_summary`、`manage_crop_cycle.update_stage`。
- 扩展 Router 选择结果，记录 domain、capability、operation、score、evidence、rejected candidates 和 alias 信息。
- 让 Router 使用 Registry 进行 domain shortlist、capability retrieval、operation hint 和 Policy Guard，而不是继续在 Python 规则中堆业务词库。
- 保留旧 Skill 名作为 alias，兼容 pending action、trace replay、测试和历史调用。
- 分阶段迁移，第一阶段只改 Registry、Catalog、Router、metadata、runtime binding 和测试，不重写业务 service，也不一次性移动旧 Skill 目录。
- 增加 Registry 校验和 Router 评测，确保 fallback all、读意图暴露写 operation、高风险误暴露等问题可被 CI 或回归测试发现。

## Capabilities

### New Capabilities

无。此变更不新建独立能力域，而是在现有 Agent Skill、Router 和 Tool Calling 能力上补充治理和路由契约。

### Modified Capabilities

- `skill-capability-governance`: 从单个 Skill metadata/doc contract 扩展为 capability registry、operation metadata、legacy alias 和 governance report 的统一契约。
- `agent-intent-router`: 从旧工具名候选选择扩展为 domain、capability、operation 的可解释 Top-K 路由选择。
- `llm-tool-calling`: 扩展 Tool Executor 和 pending action 对 capability/operation/alias 的兼容执行要求。

## Impact

- 主要影响后端 Agent 路由与工具绑定链路：
  - `backend/app/agent/router/**`
  - `backend/app/agent/skills/metadata.py`
  - `backend/app/agent/skills/__init__.py`
  - `backend/app/agent/runtime/nodes.py`
  - `backend/app/agent/runtime/tool_executor.py`
  - `backend/app/agent/executor/pending_actions.py`
  - `backend/app/agent/skill_coverage.py`
- 新增 Registry 文件：
  - `backend/app/agent/skills/registry/skills.yaml`
  - `backend/app/agent/skills/registry/aliases.yaml`
  - `backend/app/agent/skills/registry/domains.yaml`
- 测试影响：
  - Router、runtime binding、tool executor metadata、pending action、Skill docs、Skill metadata 和 coverage matrix 测试需要同步更新。
- 不改变：
  - 业务 service/API/model 契约。
  - 第一阶段不重写现有 Skill `scripts/main.py`。
  - 第一阶段不要求接入 embedding retrieval。
