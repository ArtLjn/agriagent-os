## 1. 后端 scene router 核心实现

- [ ] 1.1 新建 `backend/app/agent/application/smart_fill_scene_router.py`，定义 `SceneRoutingResult` dataclass（scene / route_source / duration_ms / llm_reason）
- [ ] 1.2 把 admin-web 的 `inferSmartFillScene` 正则规则集迁移到 Python（含 worker 自然说法补充：`来了.{0,4}人` / `招.{0,3}人` / `雇.{0,3}人` / `请.{0,3}人`）
- [ ] 1.3 实现 `route_scene(text, farm_id)` 函数：正则命中直接返回；miss 调 `_classify_with_llm`；LLM 失败返回 `unsupported`
- [ ] 1.4 新建 `backend/prompts/scene_classify.j2`，输出 schema `{scene, confidence, reason}`
- [ ] 1.5 实现 LLM 分类调用：复用 `get_llm()` + `with_structured_output`，2s 超时；fallback 到 `safe_parse_json`
- [ ] 1.6 实现幂等缓存：cache_key=`smart-fill-scene:{farm_id}:{sha256(normalized_text)}`，TTL 24h，复用 `IdempotencyKey` 表
- [ ] 1.7 在 `route_scene` 中埋点结构化日志：`route_source` / `scene` / `duration_ms` / `farm_id` / `llm_reason`，不记录原始 text

## 2. 后端 API 接入

- [ ] 2.1 修改 `backend/app/schemas/smart_fill.py` 的 `SmartFillParseRequest`：`scene` 改为 Optional，加校验注释
- [ ] 2.2 修改 `backend/app/agent/application/smart_fill.py` 的 `parse_smart_fill`：`scene is None` 时调 `route_scene` 获取 scene；`scene` 不为 None 时走老路径并记 `route_source=client_override`
- [ ] 2.3 更新 `GET /smart-fill/scenarios` 响应，注明 `scene` 现在可选（文档字段说明）
- [ ] 2.4 在 `/smart-fill/parse` 失败路径补充 422 响应：`scene=unsupported` 时返回 `missing_fields=["scene"]` + warning

## 3. 后端测试

- [ ] 3.1 新建 `backend/tests/agent/test_smart_fill_scene_router.py`
- [ ] 3.2 Meta 测试：覆盖正则规则覆盖矩阵（4 个场景各 3+ case）
- [ ] 3.3 Normal 测试：worker 自然说法 case（"我家来了一个人王树 100 工资" / "招了个师傅日薪 200"）
- [ ] 3.4 Normal 测试：LLM 兜底 case（正则 miss 的"建个番茄档案" / "搞个春茬试试"）
- [ ] 3.5 Error 测试：LLM 超时 / LLM 返回非法 schema / LLM 返回未知 scene
- [ ] 3.6 Cache 测试：相同文本二次请求命中缓存；文本微调不命中
- [ ] 3.7 Log 测试：断言日志结构含必需字段且不含原始 text
- [ ] 3.8 集成测试：`/smart-fill/parse` 不传 scene 的端到端流程

## 4. admin-web 接入

- [ ] 4.1 修改 `admin-web/src/api/smartFill.ts` 的 `parseSmartFill` 签名：`scene` 改为可选
- [ ] 4.2 修改 `admin-web/src/pages/Operations/smartCreateModel.ts` 的 `inferSmartFillScene`：补充 worker 自然说法正则
- [ ] 4.3 修改 `admin-web/src/pages/Operations/index.tsx`：`inferredScene === 'unsupported'` 时不再前端拦截，改为不传 scene 调后端
- [ ] 4.4 调整 UI：前端预判 unsupported 时移除"无法识别"warning，改为 loading 状态等后端响应
- [ ] 4.5 更新 `admin-web/src/api/smartFill.test.ts`：覆盖 scene 可选场景
- [ ] 4.6 更新 `admin-web/src/pages/Operations/smartCreateModel.test.ts`：补充 worker 自然说法 case
- [ ] 4.7 更新 `admin-web/src/pages/Costs/costSmartFill.test.ts`：兼容 scene 可选签名

## 5. mobile-app 接入

- [ ] 5.1 修改 `mobile-app/lib/data/api/api_models.dart` 的 `SmartFillResult`：scene 字段语义更新（注释）
- [ ] 5.2 修改 `mobile-app/lib/data/repositories/workbench_repository.dart` 的 `parseSmartFill`：scene 参数改为可选
- [ ] 5.3 修改 `mobile-app/lib/features/record_flow/record_flow_controller.dart:15`：去掉默认 `scene="ledger.record"`
- [ ] 5.4 检查 `RecordAiConfirmScreen` 的展示逻辑：确认能正确展示后端返回的 scene（不再是写死的 ledger）
- [ ] 5.5 检查 `controller.save(draft)` 的 scene 路由分支：确认 4 个场景都能正确路由到对应业务 create 接口
- [ ] 5.6 新增 widget test：覆盖工作台输入不同场景文本的端到端流程
- [ ] 5.7 检查 mobile-app 现有的 3 个 create page（farm_log / ledger_manual / wage_create）：智能填写按钮是否需要单独接入（如需要，列入后续任务）

## 6. 文档与可观测性

- [ ] 6.1 更新 `docs/design/smart-fill-unified-entry.md`：补充"场景自动路由"章节，链接到本次 change
- [ ] 6.2 在 `docs/architecture/overview.md` 中补充 scene router 模块的位置（如果该文件有 smart-fill 相关章节）
- [ ] 6.3 在后端日志查询文档中补充 scene router 日志字段说明（route_source / scene / duration_ms / llm_reason）
- [ ] 6.4 运行 `bash scripts/check-doc-freshness.sh` 确认文档同步
- [ ] 6.5 准备一份 eval set（20-30 条真实/构造输入），人工标注期望 scene，作为后续迭代的回归基线

## 7. 验收

- [ ] 7.1 后端：`poetry run pytest backend/tests/agent/test_smart_fill_scene_router.py -v` 全绿
- [ ] 7.2 后端：`poetry run pytest backend/tests/ -v` 整体回归无破坏
- [ ] 7.3 后端：`ruff check . && ruff format .` 通过
- [ ] 7.4 admin-web：`pnpm test` 通过
- [ ] 7.5 admin-web：手动测试 "我家来了一个人王树 100 工资" 识别为 labor.worker
- [ ] 7.6 mobile-app：`flutter test` 通过
- [ ] 7.7 mobile-app：手动测试工作台输入 4 种场景文本，均能正确路由
- [ ] 7.8 端到端：观察生产/预发日志 24h，确认 route_source 分布合理（regex 占比应 > 70%）
- [ ] 7.9 验证旧客户端兼容：模拟 mobile-app 旧版本（仍传 scene=ledger.record）请求，正常工作
