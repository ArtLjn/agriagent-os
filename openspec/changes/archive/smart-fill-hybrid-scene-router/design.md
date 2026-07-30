## Context

智能填写（smart-fill）当前对外提供 4 个业务场景解析能力：`ledger.record` / `crop.template` / `crop.cycle` / `labor.worker`。所有场景共享同一个 `/smart-fill/parse` 端点，但**场景识别方式两端不一致且各有缺陷**：

| 端 | 识别方式 | 关键文件 | 问题 |
|---|---|---|---|
| mobile-app | 写死 `scene="ledger.record"` | `record_flow_controller.dart:15` | 4 个场景里只有 1 个被使用，非记账输入全部误解析 |
| admin-web | 前端的 5 条关键词正则按优先级匹配 | `smartCreateModel.ts:70-88` | 自然说法覆盖不全，"来了一个人"等表达频繁 miss |

后端 `parse_smart_fill`（`backend/app/agent/application/smart_fill.py:70`）目前**不做场景识别**——它信任客户端传入的 `scene` 字段，按 scene 查注册表分发。这意味着改进场景识别的责任完全在前端，而前端正则无法覆盖自然语言的长尾表达。

约束：

- 工作台是高频零摩擦入口，每次额外延迟会显著影响体验
- 4 个场景是封闭枚举，不是开放式分类
- LLM 调用有成本（token + 延迟），需要节制
- 现有 `IdempotencyKey` 表已经为解析结果提供 24h 幂等缓存基础
- 4 个场景的具体 Prompt 和 validator 已经稳定，不在本次重构范围

## Goals / Non-Goals

**Goals:**

- 让 mobile-app 工作台支持全部 4 个场景的智能填写（去掉写死的 `ledger.record`）
- 提升 admin-web 自然说法的识别召回率（worker 场景补充正则 + 全场景 LLM 兜底）
- 把场景识别收敛到后端单点，前后端共享同一套路由逻辑
- 控制成本：高频 case 走正则零成本，长尾才走 LLM
- 保留可观测性，能持续迭代正则规则集

**Non-Goals:**

- 不改 4 个场景的 Prompt 模板和 validator
- 不改前端确认页（`RecordAiConfirmScreen`）和落库链路
- 不引入新 LLM 模型或新依赖
- 不做"用户主动选场景"的 UI 改造（保持零摩擦入口）
- 不实现复合场景（一次输入识别为多个 scene，如"种了番茄，化肥 500"）——本次只做单场景识别

## Decisions

### Decision 1: 选 C 混合方案，不选 B 单次合并

**选择**：正则先跑 → 命中直接路由；正则 miss → 调 LLM 做场景分类；LLM 也失败 → 返回 `unsupported` 让用户补字段。

**理由**：

- **成本可控**：85%+ 高频 case 走正则零 token 消耗，仅长尾（约 15%）走 LLM
- **延迟友好**：正则命中场景零额外延迟，仅长尾多 +500ms
- **可观测**：正则判错时可以 grep 出是哪条规则中招，LLM 判错时通过日志也能追溯（confidence 字段）
- **prompt 工程量小**：B 方案需要把 4 个场景的 schema 融合进一次结构化输出，prompt 工程复杂度高且 4 个场景的字段会相互干扰；C 方案的 LLM 兜底只判 scene（4 选 1），prompt 极简

**Alternatives considered**:

- **B 单次合并**：LLM 一次出 scene + draft。优点是架构干净，缺点是 prompt 重构工作量大、4 个场景字段互相干扰、判错时连锁影响整个 draft。后续如果场景识别稳定，可以演进到 B。
- **A 两阶段独立调用**：小模型先判 scene，再走主解析。优点是解耦清晰，缺点是必多 1 次 RTT（即使是高频 case），且需要部署额外的轻量模型路由。

### Decision 2: 场景路由下沉到后端，不在前端做 LLM 兜底

**选择**：admin-web 和 mobile-app 都不做 LLM 兜底，统一由后端 `parse_smart_fill` 入口负责。

**理由**：

- **逻辑单点**：避免两端各自维护一套 LLM 兜底逻辑（prompt、缓存、超时）
- **正则规则集也下沉**：当前 admin-web 的正则在 TS 里，迁移到后端 Python 后，两端共用；新增场景只需改一处
- **mobile-app 工作量更小**：去掉写死的 scene 后，mobile-app 只需把 `scene` 改为可选参数，不引入 LLM 调用代码

**Alternatives considered**:

- 前端各自实现 LLM 兜底：违反"逻辑单点"，且 mobile-app 引入 LLM client 增加包体积和复杂度

### Decision 3: 正则规则集迁移到后端 Python，admin-web 保留薄薄一层"快速预判"

**选择**：

- 后端新增 `smart_fill_scene_router.py`，包含完整的正则规则集 + LLM 兜底
- admin-web 保留 `inferSmartFillScene` 但简化为"乐观预判"——前端命中后**仍然把 scene 传给后端**（让后端校验），未命中则不传 scene 让后端兜底
- 这样前端能立即给出"看起来是 XX 场景"的 UI 提示，后端是最终事实来源

**理由**：

- 前端预判能优化 UX（用户输入时立即看到场景 hint），但前端永远不能"否决"后端的判断
- 完全去掉前端正则会让 admin-web 失去即时反馈能力

### Decision 4: LLM 兜底的 prompt 极简，输出 `{scene, confidence}`

**选择**：新建 `scene_classify.j2`，prompt 只描述 4 个场景的关键特征 + 输出 schema（`scene` 枚举 + `confidence` 0-1）。

**理由**：

- 4 选 1 的封闭分类任务，prompt 短（< 200 token），调用快
- `confidence` 用于日志观测和未来阈值控制（本次不基于 confidence 做路由，仅记录）

**输出 schema**:

```json
{
  "scene": "ledger.record" | "crop.template" | "crop.cycle" | "labor.worker" | "unsupported",
  "confidence": 0.0,
  "reason": "简短中文解释，用于日志"
}
```

### Decision 5: 幂等缓存复用 `IdempotencyKey` 表，新增 cache_key 命名空间

**选择**：

- 不新建表，沿用 `IdempotencyKey`
- cache_key 命名空间：`smart-fill-scene:{farm_id}:{sha256(normalized_text)}`
- TTL：24 小时
- 缓存对象：仅缓存 LLM 兜底的结果（正则命中不缓存，因为正则是确定性的零成本）

**理由**：

- 正则命中本身可重复执行且零成本，无需缓存
- LLM 兜底结果可能因模型版本变化，但 24h 内对同一文本通常应该一致
- 复用现有表降低迁移成本

### Decision 6: 客户端传 scene 时后端不覆盖，向后兼容

**选择**：`/smart-fill/parse` 的 `scene` 参数从必填改为可选。客户端传了就用客户端的（不调 scene router），不传才走 scene router。

**理由**：

- 兼容旧客户端（旧 mobile-app 写死传 `ledger.record` 时，升级前的版本仍能工作）
- 让客户端可以"强制指定场景"作为逃生通道（极少使用，但保留）
- admin-web 升级后可以选择不传 scene 走自动路由，或传 scene 走显式指定

### Decision 7: 不基于 confidence 做路由分支，只记录

**选择**：LLM 返回 confidence 但本次不基于阈值切换路由（即使 confidence=0.3 也采用 LLM 的判断）。

**理由**：

- 4 选 1 任务中 LLM 通常 confidence 高，引入阈值反而引入复杂度
- 通过日志观察一段时间后，如果发现低 confidence case 真有质量问题，再加阈值
- YAGNI——本次范围内不做

## Risks / Trade-offs

- **[Risk] LLM 兜底误判比正则更难 trace** → 通过日志记录 `route_source=regex|llm` + LLM 的 `reason` 字段，能复现每次判断。后续可加 eval set 持续度量准确率。
- **[Risk] LLM 兜底延迟拖慢长尾请求** → 设置 2s 超时；超时后 fallback 到 `unsupported` 让用户手动选；同时复用幂等缓存，相同文本二次请求走缓存。
- **[Risk] 正则规则迁移到后端后，前端预判逻辑可能漂移** → 接受这个 trade-off：前端预判只是 UX hint，后端是事实来源；前端预判错了不影响数据正确性。
- **[Risk] mobile-app 去掉写死 scene 后，历史用户的工作台行为变化** → 这是预期的行为改进，不需要灰度；但需要在发版说明里提示"工作台现在支持记账/工人/作物模板/种植周期 4 种智能填写"。
- **[Trade-off] 后端 scene router 增加了 `parse_smart_fill` 的复杂度** → 用独立模块 + 单测隔离，主流程仍清晰。
- **[Trade-off] 同时存在正则和 LLM 两套路由逻辑** → 接受双轨制，因为正则零成本是核心价值；未来如果场景表达足够稳定，可以演进到纯 LLM（B 方案）。

## Migration Plan

**阶段 1：后端 scene router 落地（不破坏现有行为）**

1. 新增 `smart_fill_scene_router.py` + `scene_classify.j2`
2. 新增单测覆盖正则命中 / LLM 兜底 / LLM 失败三个分支
3. `/smart-fill/parse` 的 `scene` 改为可选；客户端传了就走老路径，不传才走 scene router
4. 部署后端——此时所有旧客户端继续工作

**阶段 2：admin-web 接入 LLM 兜底**

1. 补充 `inferSmartFillScene` 的 worker 正则（`来了.{0,4}人` / `招.{0,3}人` 等）
2. 修改 `Operations/index.tsx`：`inferredScene === 'unsupported'` 时不再前端拦截，改为调 `/smart-fill/parse` 不传 scene
3. 补充前端测试 case（"我家来了一个人王树 100 工资" 应识别为 `labor.worker`）
4. 发布 admin-web

**阶段 3：mobile-app 去掉写死 scene**

1. `record_flow_controller.dart` 去掉默认 `scene="ledger.record"`
2. `workbench_repository.dart` 的 `parseSmartFill` 签名调整（scene 改为可选）
3. 补充 widget test 覆盖 4 种场景
4. 发布 mobile-app

**回滚策略**：

- 后端 scene router 出问题 → 通过 feature flag 关闭，所有请求 fallback 到"客户端必须传 scene"的旧行为
- 前端出问题 → 独立回滚前端版本，后端兼容旧行为
- 数据库无 schema 变更，无需回滚迁移

## Open Questions

- **正则规则集是否要做成可配置（DB 表）？** 本次范围保持硬编码（Python 常量），观察半年后如果迭代频繁再考虑配置化。
- **LLM 兜底选哪个模型？** 默认走 `get_llm()` 返回的主模型；后续可以加 eval 对比小模型（如 haiku）的准确率，若有显著差异再切换。
- **confidence 阈值是否需要？** 本次不引入，先观察日志中 confidence 分布再决定。
