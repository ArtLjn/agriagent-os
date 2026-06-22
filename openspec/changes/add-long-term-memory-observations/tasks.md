## 1. 配置与基础设施

- [ ] 1.1 在 `backend/app/core/config.py` 的 `AIConfig` 新增字段：`enable_long_term_memory: bool = False`、`long_term_memory_candidate_repeat_threshold: int = 3`、`long_term_memory_inject_limit: int = 5`
- [ ] 1.2 在 `backend/config.yaml` 与 `backend/config.yaml.example` 的 `ai:` 段补对应字段及注释
- [ ] 1.3 在 `backend/app/api/admin_config.py` 暴露 `enable_long_term_memory` 到 admin 读取接口（便于线上热关闭）

## 2. 长期记忆数据模型与迁移

- [ ] 2.1 新建 `backend/app/models/memory_record.py`，定义 `MemoryRecord` 模型（字段：id / farm_id / user_id / type / content / importance / status / confidence / source / superseded_by_id / created_at / confirmed_at / last_referenced_at）
- [ ] 2.2 索引：`idx_memory_records_farm_id`、`idx_memory_records_status_importance`、`idx_memory_records_last_referenced`
- [ ] 2.3 Alembic 生成迁移：`alembic revision --autogenerate -m "add memory_records table"`
- [ ] 2.4 检查迁移脚本，确认 `superseded_by_id` 外键、status 枚举约束（candidate/confirmed/superseded/archived）
- [ ] 2.5 应用到开发库，验证表结构与索引

## 3. Extractor 实现

- [ ] 3.1 新建 `backend/app/memory/extractor.py`，定义 `async def extract_observations(llm, current_summary, recent_messages) -> list[ObservationCandidate]`
- [ ] 3.2 新建 `backend/app/memory/prompts/observations.md`，要求 LLM 输出 JSON 数组 `[{type, content, confidence}]`，5 类枚举，confidence 0-1
- [ ] 3.3 失败 / 超时 / JSON 不合法 → 返回空数组，不抛错
- [ ] 3.4 通过熔断器记录成功失败；超阈值后短时间内跳过抽取
- [ ] 3.5 记录 trace 事件 `observations_extracted` / `observations_skipped`

## 4. MemoryService 长期记忆方法

- [ ] 4.1 `extract_observations(...)`：调用 extractor，按 confidence + type 分流入库（高置信 preference/habit/alias → candidate importance=0.5；其他 → candidate importance=0.3）
- [ ] 4.2 `confirm_observation(record_id, user_id)`：用户显式确认 → status=confirmed, importance=0.8, confirmed_at=now()
- [ ] 4.3 `record_explicit(user_id, farm_id, type, content)`：用户显式说"记一下"→ 直接 status=confirmed, importance=0.8, source=user_explicit
- [ ] 4.4 `check_implicit_repeat(record)`：写入前查同 type + content 前 50 字符 hash，若已存在 2 条 candidate，本次升级为 confirmed (importance=0.7)，旧候选 superseded
- [ ] 4.5 `archive_stale()`：定时任务（每日凌晨）扫 `importance < 0.5 AND last_referenced_at < now-90d` → status=archived
- [ ] 4.6 `supersede(old_id, new_id)`：偏好软覆盖（type != fact 时），写 superseded_by_id

## 5. Response 节点接入

- [ ] 5.1 在 `backend/app/agent/runtime/nodes.py` Response 节点末尾异步触发长期记忆流程，受 `ai.enable_long_term_memory` 控制
- [ ] 5.2 显式记忆触发词检测（"记一下"、"记住"、"以后都"）→ 优先调 `record_explicit`，不走 extractor
- [ ] 5.3 用户确认触发词检测（"对"、"是的"、"以后都这样"）→ 调 `confirm_observation` 升级最近一条候选
- [ ] 5.4 普通对话达到抽取条件时异步调用 extractor，失败不影响主流程
- [ ] 5.5 单测覆盖：普通抽取 / 显式记忆 / 用户确认 / feature flag 关闭 / 异常吞掉 5 个场景

## 6. MemorySelector 注入长期记忆

- [ ] 6.1 修改 `backend/app/context/selectors/memory.py`，扩展查询：`SELECT * FROM memory_records WHERE farm_id=:farm_id AND status IN ('confirmed','candidate') AND importance >= 0.3 ORDER BY importance DESC, last_referenced_at DESC LIMIT 5`
- [ ] 6.2 注入为 ContextBlock（key=`memory_long_term`、source=`memory.long_term`、priority=45、compressible=True、min_tokens=64、metadata={layer:working, cache_scope:farm}）
- [ ] 6.3 注入时更新 `last_referenced_at = now()`
- [ ] 6.4 单测：confirmed 优先 / candidate 后 / 无记忆不注入 / farm_id 隔离

## 7. 单元测试

- [ ] 7.1 新建 `backend/tests/memory/test_extractor.py`：3 类测试（Meta / Normal / Error），覆盖 prompt 渲染、LLM 输出解析、失败/超时/空响应
- [ ] 7.2 新建 `backend/tests/memory/test_long_term_flow.py`：覆盖 candidate→confirmed 显式升级 / 隐式重复升级 / 偏好软覆盖 / fact 不被覆盖 / 90 天 archive / 跨农场隔离
- [ ] 7.3 扩展 `backend/tests/context/selectors/test_memory_selector.py`：覆盖 memory_long_term block 注入

## 8. 集成测试与仿真

- [ ] 8.1 在 `backend/tests/agent/test_advisor_flow.py` 增加多轮场景：用户说"记一下我用万元" → 后续对话验证 memory_long_term block 被注入 + Agent 用万元单位
- [ ] 8.2 在 `backend/simulation/cases/` 新增 1 条用例：用户先说"喜欢下午浇水"，3 轮后问"什么时候给我浇水建议" → 验证 Agent 回答含"下午"
- [ ] 8.3 跑 `python -m app.simulation.run --suite smoke` 通过

## 9. 可观测性

- [ ] 9.1 trace 事件 `observations_extracted`（含 type / confidence / count）、`observations_skipped{reason}`（timeout / invalid_output / circuit_open / below_threshold / feature_disabled）
- [ ] 9.2 metrics 计数器：`memory_observations_extracted_total{type}`、`memory_observations_confirmed_total{source}`（user_explicit / llm_repeat）、`memory_observations_archived_total`
- [ ] 9.3 Admin Web Trace 详情页可查看 observations_extracted 事件

## 10. 文档同步

- [ ] 10.1 `farm-manager-design-spec/01_正式设计/04_Memory工程.md` § 14 当前状态：long_term 从 🚧 改为 ✅
- [ ] 10.2 `farm-manager-design-spec/Readme.md` 变更记录加长期记忆落地行
- [ ] 10.3 `farm-manager-design-spec/04_相关规范/03_数据库与迁移规范.md` 表清单加 `memory_records`

## 11. 上线与验证

- [ ] 11.1 合并 PR 到 main，CI 七道门全部通过
- [ ] 11.2 部署 staging，feature flag `ai.enable_long_term_memory=false`，观察 2 小时
- [ ] 11.3 staging 开启 feature flag，跑 24 小时；trace 抽检：抽取准确率（人工评分）≥ 70%
- [ ] 11.4 部署生产，feature flag 默认 false → 开启 5 个内测农户 → 观察 1 周 → 全量开启
- [ ] 11.5 上线 1 周后核查单户月增成本，确认在预算内
