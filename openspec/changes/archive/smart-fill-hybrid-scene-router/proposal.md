## Why

当前智能填写的场景识别存在两个问题：

1. **mobile-app 工作台写死 `scene="ledger.record"`**（`mobile-app/lib/features/record_flow/record_flow_controller.dart:15`），用户输入"招个工人"或"种 5 亩番茄"会被强行按记账场景解析，4 个场景注册表只有 1 个真正被使用。
2. **admin-web 用前端正则识别场景**（`admin-web/src/pages/Operations/smartCreateModel.ts:70-88`），但正则覆盖不全，自然说法频繁 miss。例如用户输入"我家来了一个人王树 100 工资"，因 worker 正则未匹配"来了一个人"，且"工资"在 ledger 词表中，被错误路由到 `ledger.record`。

需要在保留正则快速路径的同时，引入 LLM 兜底识别，提升召回率并统一两端路由逻辑。

## What Changes

- **新增** `smart-fill-scene-router` 后端服务：先跑正则规则集，命中直接路由；正则 miss 时调用 LLM 做场景分类（输出 `{scene, confidence}`，仅 4 个枚举值 + `unsupported`）。
- **修改** `/smart-fill/parse` 接口：客户端不再传 `scene`（向后兼容——客户端传了就用客户端的，不传走自动识别）。
- **修改** admin-web 的 `inferSmartFillScene`：补充 worker 自然说法正则（如 `来了.{0,4}人`、`招.{0,3}人`），并将"识别失败"分支从"前端拦截"改为"调后端 LLM 兜底"。
- **修改** mobile-app 工作台：去掉写死的 `scene="ledger.record"`，改为不传 scene 让后端自动路由。
- **新增** LLM 兜底路由的幂等缓存：相同文本 + farm_id 24 小时内复用上次识别结果，避免重复消耗 token。
- **新增** 场景路由可观测指标：日志记录每条请求走正则还是 LLM、识别耗时、识别结果，方便后续迭代正则规则集。

不在本次范围内：

- 不改 4 个场景的具体解析 Prompt 和 validator（保留现有 `cost_parse.j2` / `cycle_parse.j2` / `worker_parse.j2` / `crop_template_parse.j2`）。
- 不改幂等缓存的存储结构（沿用 `IdempotencyKey` 表）。
- 不改前端确认页和落库链路（仍是用户确认后按 scene 路由到各业务 create 接口）。

## Capabilities

### New Capabilities
- `smart-fill-scene-routing`: 定义智能填写场景路由的契约——如何在 4 个业务场景（`ledger.record` / `crop.template` / `crop.cycle` / `labor.worker`）中选择正确的解析路径，包含正则快速路径、LLM 兜底路径、未识别 fallback 三个分支。

### Modified Capabilities

（无——本次只新增场景路由契约，4 个场景的具体解析行为不在 spec 范围内）

## Impact

**后端**：

- 新增 `backend/app/agent/application/smart_fill_scene_router.py`
- 修改 `backend/app/agent/application/smart_fill.py` 的 `parse_smart_fill` 入口，前置调用 scene router
- 新增 `backend/prompts/scene_classify.j2`
- 新增场景路由幂等缓存键空间（复用 `IdempotencyKey` 表）
- 新增场景路由结构化日志埋点（route_source=regex/llm、duration_ms、scene）

**前端 admin-web**：

- 修改 `admin-web/src/pages/Operations/smartCreateModel.ts` 的 `inferSmartFillScene` 补充正则
- 修改 `admin-web/src/pages/Operations/index.tsx` 的 `inferredScene === 'unsupported'` 分支：改为调 `/smart-fill/parse` 不传 scene 让后端兜底

**前端 mobile-app**：

- 修改 `mobile-app/lib/features/record_flow/record_flow_controller.dart` 去掉写死 scene
- 修改 `mobile-app/lib/data/repositories/workbench_repository.dart` 的 `parseSmartFill` 签名（scene 改为可选）

**API 兼容性**：

- `/smart-fill/parse` 的 `scene` 参数从必填改为可选，旧客户端继续工作
- 新增日志和指标，对客户端透明

**测试**：

- 后端：`backend/tests/agent/test_smart_fill_scene_router.py`（正则命中 / LLM 兜底 / LLM 失败 fallback 三个分支）
- admin-web：补充 `smartCreateModel.test.ts` 的 worker 自然说法 case
- mobile-app：补充工作台自动路由的 widget test

**依赖**：

- 复用现有 LLM 实例（`app.agent.llm.get_llm`）
- 复用现有 prompt composer（`app.prompt.composer.get_composer`）
- 不引入新依赖
