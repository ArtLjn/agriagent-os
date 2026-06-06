## Context

当前系统已经具备 skillify 注册、LangChain StructuredTool 转换、Tool Executor、pending action、trace、admin skill 列表和初步评测能力。运行时真实注册了 19 个 Skill，覆盖账务、茬口、农事、作业单、人工结算、天气和搜索。

短板集中在治理闭环而不是单点实现：部分已注册 Skill 没有进入 `tool_selector` 和 `TOOL_CHAIN_MAP`，多数旧 Skill 仍依赖默认 metadata，外部网络 Skill 注册但被硬编码禁用，系统 API/Service 功能没有一张明确的 Skill 覆盖矩阵。结果是 LLM 可调用能力不可预测，新增功能也缺少“是否应该有 Skill”的判断标准。

## Goals / Non-Goals

**Goals:**

- 让所有已注册且启用的 Skill 都能被 LLM 稳定发现、选择、执行、诊断和评测。
- 建立系统功能到 Skill capability 的覆盖矩阵，明确普通用户 Skill、Admin Skill、禁止 LLM 调用和无需 Skill 的边界。
- 用 metadata 驱动权限、写确认、缓存失效、外部网络许可和评测标签，减少硬编码名单。
- 为新增 Skill 建立文档、schema、测试、诊断和回归评测的准入门槛。
- 优先补齐普通农场用户高频业务功能，再按权限补齐管理员能力。

**Non-Goals:**

- 不创建万能 API 调用 Skill。
- 不要求所有内部维护接口都暴露给 LLM；敏感或低价值功能可标记为禁止 LLM 调用。
- 不在本变更中重写 skillify SDK 或 LangGraph 架构。
- 不改变现有 HTTP API 的兼容行为。

## Decisions

### 1. 以覆盖矩阵作为总账

为 API route、service method、model domain 和现有 Skill 建立 `SkillCoverageEntry`。每个条目包含 domain、operation、source endpoint/service、coverage_status、skill_name、permission_level、risk_level、reason、priority 和 test_status。

替代方案是直接按 API 批量生成 Skill。这个方案覆盖速度快，但会把权限和自然语言语义混在一个低质量工具层里。覆盖矩阵先让系统知道“哪些该暴露、哪些不该暴露”，后续补 Skill 才有边界。

### 2. 现有 19 个 Skill 先达到闭环，再扩展新 Skill

第一批工作不追求立刻覆盖所有 API，而是让现有 Skill 在 selector、chain map、metadata、docs、evaluation 和 diagnostics 中完全一致。新增审计测试会把“注册了但不可发现”“写操作未确认”“metadata incomplete 长期存在”等问题变成可见失败。

替代方案是边补新 Skill 边修治理。风险是缺口继续扩散，新 Skill 也会复制旧问题。

### 3. Tool selection 使用注册表派生审计，不完全手写同步

短期继续保留 `WRITE_PATTERNS`、`QUERY_TRIGGERS` 和 `TOOL_CHAIN_MAP`，但新增测试对照运行时注册表，要求每个启用 Skill 至少有一种选择入口。中期可把触发词、domain、permission 和 chain hints 放进 Skill metadata/doc，再由注册表生成 selector 输入。

替代方案是完全依赖 LLM intent classifier。它可以降低维护量，但稳定性、成本和可测性不如显式规则。

### 4. 权限以 metadata 为准，硬编码名单只作为 legacy fallback

Tool Executor 对 `permission_level` 做统一决策：`read` 直接执行，`write_confirm` 创建 pending action，`admin` 校验用户角色，`external_network` 校验配置开关和网络许可。`WRITE_SKILLS` 只保留给缺 metadata 的 legacy Skill 兜底，并通过 coverage audit 推动清零。

替代方案是继续维护写操作硬编码名单。当前已经出现部分写 Skill 不在名单中的偏差，长期会带来误执行风险。

### 5. 外部网络 Skill 默认受开关治理

`web_search` 和天气等外部访问 Skill 使用 `external_network` 权限。是否启用由配置和健康状态决定；禁用时 selector 不应返回该 Skill，诊断报告必须说明禁用原因。启用后需要超时、失败降级和评测用 mock/provider。

### 6. Admin Skill 必须显式隔离

管理员能力可以通过 LLM Skill 覆盖，但必须是 `permission_level=admin`，不可混入普通用户工具集合。候选能力包括 trace 查询、配额查询/调整、配置查看、缓存清理和 prompt reload。用户管理和状态修改类能力需要更高风险确认 schema。

## Risks / Trade-offs

- 覆盖矩阵过大 → 先生成机器可审计的最小字段，普通用户业务优先，Admin 能力分批补齐。
- selector 规则膨胀 → 增加注册表审计和 Skill 文档触发词，后续逐步由 metadata 生成候选输入。
- 新增 Skill 误操作数据 → 所有写/Admin Skill 必须有 schema 校验、确认上下文、trace 和回归用例。
- 外部网络不稳定 → 使用配置开关、超时、禁用原因诊断和 mock provider 评测。
- metadata incomplete 清零影响旧 Skill → 分阶段执行，先对新增 Skill 强制完整，旧 Skill 通过任务逐个迁移。

## Migration Plan

1. 添加覆盖审计和注册表对照测试，先记录当前缺口。
2. 补齐现有 19 个 Skill 的 selector、chain map、metadata、docs 和评测。
3. 引入覆盖矩阵生成器，输出待补功能清单。
4. 按普通用户高频业务域新增缺失 Skill。
5. 按 Admin 权限新增管理 Skill 或标记禁止 LLM 调用。
6. 运行 `ruff check . && ruff format .`、后端 pytest、OpenSpec validate 和 harness 检查。

回滚策略：新增 Skill 和 selector 扩展可通过配置禁用；覆盖矩阵和审计测试不改变运行时行为；Admin 和 external network Skill 默认不进入普通用户候选集。

## Open Questions

- 管理员能力是否要全部进入 LLM Skill 覆盖，还是只覆盖只读诊断和配额查询。
- `web_search` 的默认状态是继续禁用，还是配置可用时自动启用。
- 覆盖矩阵是否需要持久化为仓库文档，还是由测试动态生成报告。
