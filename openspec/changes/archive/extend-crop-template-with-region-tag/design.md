## Context

### 背景

详见 [`crop-template-system-library` proposal](../crop-template-system-library/proposal.md) 与 [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md § 3](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)。

简述：当前作物模板生成不分地域，是用户痛点。`crop-template-system-library` 提案已设计"系统模板库（farm_id IS NULL）+ 副本导入"，本提案在其基础上加 `region_tag` 字段，让系统模板支持地域变体。

### 约束

- 不破坏 `crop-template-system-library` 的字段约定（farm_id IS NULL 标识系统模板）
- 不批量铺地域（当前业务仅"徐州 × 西瓜"），等业务扩张再补
- 禁止 LLM 生成塞入系统库（继承原提案）
- 零回归：现有用户模板（farm_id 非空）行为不变

## Goals / Non-Goals

**Goals**：

- `crop_templates.region_tag` 字段落地 + Alembic 迁移
- 系统模板 API 与 Skill 支持 region 优先匹配 + default fallback
- 1 套"徐州 × 西瓜" seed 数据（WebSearch 调研后人工录入）
- 城市 → region_tag 映射表

**Non-Goals**：

- 不做"作物 × 地域 × 季节"完整矩阵（YAGNI）
- 不做气候带自动推算（学院派）
- 不让用户填纬度
- 不引入向量库（地域匹配用 SQL where）
- 不重写 LLM 生成 prompt（地域化通过系统模板库覆盖，LLM 只兜底）
- 不做跨地域迁移工具（用户换地区属于边界场景）

## Decisions

### D1：`region_tag` 字段而非新表

**选择**：直接在 `crop_templates` 加 `region_tag VARCHAR(32)`。

**理由**：
- 与 `crop-template-system-library` 的 "farm_id IS NULL" 设计正交，互不干扰
- 不需要 join 另一张表
- 通用性够（region 名是字符串，未来扩省市县都能塞）

**Alternatives**：
- 新建 `crop_template_regions` 关联表（rejected：over-engineering，1:1 关系不需要拆表）
- 用 `metadata` JSON 字段塞 region（rejected：JSON 字段不能高效索引，违反 [04_相关规范/03_数据库与迁移规范] 第 2.5 节"JSON 字段不建普通索引"）

### D2：fallback 逻辑用 SQL 层做，不在应用层

**选择**：单次查询返回 region 命中 + default，应用层去重。

```sql
SELECT * FROM crop_templates
WHERE farm_id IS NULL
  AND name = :crop_name
  AND region_tag IN (:user_region, 'default', NULL)
ORDER BY
  CASE region_tag
    WHEN :user_region THEN 0
    WHEN 'default' THEN 1
    ELSE 2
  END
```

**理由**：
- 一次 SQL 拿到候选，避免 N+1
- 应用层取第一条作为"推荐"，剩余作为 fallback 选项

**Alternatives**：
- 两次查询（先 user_region，没有再 default）（rejected：增加 RTT）
- 全部加载到应用层过滤（rejected：违反数据库做筛选的原则）

### D3：NULL 视为 'default'，不做迁移回填

**选择**：现有数据 `region_tag` 默认 NULL，应用层 `NULL OR region_tag = 'default'` 都视为 default。

**理由**：
- 避免大规模 UPDATE
- 向后兼容（老数据无需改动）

**Alternatives**：
- 迁移时把所有 NULL 改为 'default'（rejected：增加迁移风险，无收益）

### D4：用户 region 从 `UserSettings.default_city` 映射

**选择**：城市 → region_tag 映射表 hardcode 在 `backend/app/seeds/region_mapping.py`。

```python
CITY_TO_REGION = {
    "徐州": "xuzhou",
    "铜山": "xuzhou",
    "睢宁": "xuzhou",
    # ... 徐州下辖县市
    # 其他城市默认 fallback 到 'default'
}

def resolve_region(city: str | None) -> str:
    if not city:
        return "default"
    return CITY_TO_REGION.get(city, "default")
```

**理由**：
- 当前业务聚焦少数地区，hardcode 足够
- 后期若地域扩展多，可改 DB 表

**Alternatives**：
- 用户直接填 region_tag（rejected：用户不知道这是什么）
- 调高德 API 反查省市区（rejected：增加外部依赖，且当前需求粒度是"市"级）

### D5：Seed 数据由 WebSearch 调研后人工录入

**选择**：你作为维护者用 WebSearch 调研"徐州 西瓜 生育阶段"，写入 seed 脚本。

**理由**：
- 农业数据需要权威来源，不能 LLM 瞎生成
- 业务聚焦时数据量小（当前 1 套），人工可控

**Alternatives**：
- 让 LLM 生成（rejected：这正是当前 bug 来源）
- 爬虫抓取（rejected：合规风险 + 工作量大）

### D6：Skill 推荐系统模板时按 region 优先

**选择**：`create_crop_template` Skill 流程升级：
1. 精确查重未命中（继承原提案）
2. 按用户 region 查系统模板 → 命中则推荐"是否导入系统模板（徐州版）"
3. 用户拒绝或未命中 → LLM 兜底生成

**理由**：
- 系统模板比 LLM 生成准确
- 给用户选择权（推荐而非强制）

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| `region_tag` 取值约定不统一（拼音 vs 行政区码） | spec 明确"拼音小写"约定，CI 加 lint 检查 |
| Seed 数据准确性 | WebSearch 调研时记录来源链接，写入 seed metadata |
| 现有用户已导入的模板副本没有 region_tag | 副本属于"用户私有修订"，不强求；fallback 到 default 行为可接受 |
| 城市映射漏某个城市 | `resolve_region` 默认返回 `default`，不会抛错；后续按 trace 补映射 |
| Skill 推荐打断用户节奏 | 仅在精确查重未命中时推荐，且明确"或继续生成"选项 |
| 业务扩张到新地区需补 seed | 在 spec 写明"业务扩张触发条件"，避免遗忘 |

## Migration Plan

### 前置

必须先合并 [`crop-template-system-library`](../crop-template-system-library/proposal.md) 提案，否则 `crop_templates.farm_id` 仍是 NOT NULL，本提案的"系统模板"概念不存在。

### 部署步骤

1. Alembic 生成迁移：`alembic revision --autogenerate -m "add region_tag to crop_templates"`
2. 检查迁移脚本（autogenerate 可能不识别 NULL = default 约定，需要手工注释）
3. 应用迁移到开发库 + 测试
4. 实现 service / API / Skill 升级
5. 准备 seed 脚本（WebSearch 调研 → 录入）
6. 跑 seed → 验证徐州西瓜模板可被徐州用户优先匹配
7. 部署生产，feature flag 不需要（向后兼容）

### Rollback

- `alembic downgrade -1` 回滚字段
- 应用层兼容 NULL（即使回滚字段也不会崩）

## Open Questions

1. **region_tag 命名最终约定**：拼音 (`xuzhou`) vs 拼音简写 (`xz`) vs 行政区码 (`32-03`)？倾向拼音，最易读。
2. **Skill 推荐文案**：用"建议导入徐州版系统模板，更准确"还是"我们有现成的徐州西瓜模板，要不要"？后者更口语化。
3. **多 region 共存**：一个农场可能跨区域经营（如农场在徐州但在海南也有基地）。当前不支持，假设一个农场一个 region，后期若需要再加 `farm_region_overrides` 表。
