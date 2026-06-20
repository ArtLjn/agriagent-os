# 开发路线图

## 已完成（已归档）

| # | Change | 状态 |
|---|--------|------|
| 0 | prompt-governance | done |
| 0 | skill-engine-with-cache-and-circuit-breaker | done |
| 0 | robustness-and-admin-completeness | done |
| 0 | mobile-four-tab-redesign | done |
| 0 | farmer-first-agent | done |
| 0 | enable-function-calling | done |
| 0 | farm-context-aware-agent | done |

## 待实施（按优先级排序）

共 6 个未归档提案。优先级按「用户痛点 × 阻塞性 × ROI」综合排序：

| 优先级 | Change | 痛点 | 工作量 | 依赖 |
|--------|--------|------|--------|------|
| **P0** | [add-running-summary-compaction](changes/add-running-summary-compaction/proposal.md) | 多轮失忆（高频终端用户痛点） | 中 | 无 |
| **P1** | [smart-fill-hybrid-scene-router](changes/smart-fill-hybrid-scene-router/proposal.md) | 场景路由错（mobile-app 写死 + admin-web 正则不全） | 中 | 无 |
| **P1** | [crop-template-system-library](changes/crop-template-system-library/proposal.md) | 新用户冷启动 + 模板查重不一致 | 中 | 无 |
| **P2** | [extend-crop-template-with-region-tag](changes/extend-crop-template-with-region-tag/proposal.md) | 作物模板不分地域 | 低（delta） | crop-template-system-library |
| **P2** | [add-dataflywheel-discovery-layer](changes/add-dataflywheel-discovery-layer/proposal.md) | 标注员效率低（不影响终端用户） | **低（4.5 人日）** | 无 |
| **P3** | [add-ai-assisted-password-recovery](changes/add-ai-assisted-password-recovery/proposal.md) | 忘记密码恢复（小范围熟人） | 低 | 无 |

详细方案见各 `proposal.md`。

### 排序理由

- **P0 `add-running-summary-compaction`**：终端用户高频痛点。spec（`short-term-memory-policy` / `conversation-management`）早已声明，但代码侧 `MemoryService.set_session_summary()` 是死接口、`memory/long_term/` 空实现。一个 LLM 调用同时输出 summary + observations，成本低收益高。
- **P1 `smart-fill-hybrid-scene-router`**：mobile-app 工作台场景写死 `scene="ledger.record"`，admin-web 正则不全，直接影响记账/招工体验。引入 LLM 兜底识别统一两端路由。
- **P1 `crop-template-system-library`**：新用户冷启动 + 现有查重逻辑分散且错误（API 层不查重，Skill 层 ilike 模糊匹配）。也是 P2 `extend-crop-template-with-region-tag` 的前置。
- **P2 `extend-crop-template-with-region-tag`**：在 P1 之上加 `region_tag` 字段，让徐州西瓜和海南西瓜拿到不同阶段天数。作为 delta 提案，紧随 P1 之后做。
- **P2 `add-dataflywheel-discovery-layer`**：不影响终端用户，但是数据飞轮从「能跑」到「能转」的关键升级。**工作量小（4.5 人日），适合作为 P0/P1 之间的"穿插任务"**。详细设计见 [design-spec 01.06 § 9](../farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md)。
- **P3 `add-ai-assisted-password-recovery`**：用户群小、密码恢复事件少。工作量低，可随时穿插。

## 依赖关系

```
add-running-summary-compaction (P0, 独立)
        │
        ▼
smart-fill-hybrid-scene-router (P1, 独立)
        │
        ├────────────────────┐
        ▼                    ▼
crop-template-system-library (P1, 独立)
        │
        ▼
extend-crop-template-with-region-tag (P2)

add-dataflywheel-discovery-layer (P2, 穿插, 独立)
add-ai-assisted-password-recovery (P3, 穿插, 独立)
```

P0 完成后 P1 两项可并行；P2 region 依赖 P1 system-library；P2 discovery 与 P3 password 可在任意间隙穿插，不阻塞主路径。

## 各 Change 规模估算

| Change | 改动文件数 | 核心模块 | 风险 |
|--------|-----------|---------|------|
| add-running-summary-compaction | ~8 | MemoryService, conversations 表写入, summary+observations 触发 | 中（DB 字段已存在但未启用） |
| smart-fill-hybrid-scene-router | ~6 | mobile-app record_flow, admin-web smartCreateModel, 后端场景路由 | 中（两端协议统一） |
| crop-template-system-library | ~10 | DB 迁移 + system templates seed, /crops/templates 查重, Skill 查重逻辑 | 中（数据迁移） |
| extend-crop-template-with-region-tag | ~4 | crop_templates 加 region_tag, region 匹配, LLM prompt | 低（delta） |
| add-dataflywheel-discovery-layer | ~8 | agent_turns 加字段, rule engine, judge worker, 工作台前端 | 低（不引入新基础设施） |
| add-ai-assisted-password-recovery | ~5 | auth API, 密码恢复 token, admin 审批 | 低（独立模块） |
