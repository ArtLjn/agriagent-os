# 知识与记忆架构梳理设计

> 日期：2026-06-19
> 维护：BlockShip
> 类型：架构梳理（非实施）
> 状态：等待用户审查
> 关联：[docs/farm-manager-design-spec/01_正式设计/04_Memory工程](../../../docs/farm-manager-design-spec/01_正式设计/04_Memory工程.md)、[crop-template-system-library 提案](../../../openspec/changes/crop-template-system-library/proposal.md)、[add-running-summary-compaction 提案](../../../openspec/changes/add-running-summary-compaction/proposal.md)

---

## 1. 背景与动机

农户反馈多轮对话失忆、作物模板不分地域出错、用户喜好无法沉淀。这三个问题在直觉上似乎指向"上一个向量库 / 知识库系统就能解决"，但深入拆解后发现是**三件性质不同的事**：

1. **作物模板地域化**：领域事实型知识（徐州西瓜 90 天 ≠ 海南西瓜 60 天），跨用户共享，结构化，需审核
2. **用户喜好记忆**：个人偏好型记忆（我喜欢下午浇水），用户私有，非结构化，可覆盖
3. **农技问答库**：长文本领域知识（番茄早疫病防治详细说明），跨用户共享，FAQ 型

三者底层架构（数据模型 / 检索方式 / 隐私要求 / 更新方）完全不同。把它们塞进同一个"向量库 + memory"会导致边界混乱、隐私泄漏、过度设计。

本设计的目的是：**在 2C4G + < 10 用户的现状下，把三件事的边界、顺序、触发条件固化下来**，避免局部最优、避免提前上 Qdrant 这种重基础设施。

## 2. 整体边界与架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     用户对话 / Skill 调用                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐
│ ① 作物地域化 │ │ ② 用户喜好   │ │ ③ 农技问答库（暂缓）      │
│              │ │              │ │                          │
│ MySQL:       │ │ MySQL:       │ │ Qdrant（未来）:          │
│ crop_        │ │ memory_      │ │ agri_faq_chunks          │
│ templates    │ │ records      │ │                          │
│ +region_tag  │ │ (5 类)       │ │ RetrievalPort            │
│              │ │              │ │ （现有占位 → 未来实现）   │
│ 跨用户共享   │ │ 用户私有     │ │ 跨用户共享               │
│ (farm_id     │ │ (farm_id     │ │ (无 farm_id)             │
│  IS NULL)    │ │  必填)       │ │                          │
└──────┬───────┘ └──────┬───────┘ └────────────┬─────────────┘
       │                │                      │
       └────────────────┴──────────────────────┘
                        │
                        ▼
              ContextBuilder / MemoryService
                        │
                        ▼
                  LLM (qwen3.6-35b-a3b)
```

### 2.2 三件事的判别准则

| 维度 | ① 作物地域化 | ② 用户喜好 | ③ 农技问答 |
| --- | --- | --- | --- |
| 数据性质 | 领域事实 | 个人偏好 | 长文本知识 |
| 共享范围 | 跨用户（管理员维护） | 用户私有 | 跨用户（内容团队） |
| 更新方 | 管理员 + 用户副本修订 | LLM 抽候选 + 用户确认 | 内容运营录入 |
| 检索方式 | SQL where + region_tag | SQL where + farm_id | 向量检索 |
| 需要向量库 | ❌ | ❌ | ✅（唯一场景） |
| 当前是否做 | ✅ 升级现有提案 | ✅ 落地现有占位 | ❌ 暂缓 |

**核心结论**：Qdrant 当前不上，三件事里只有 ③ 真正需要向量检索，而 ③ 当前无场景无内容。Qdrant 资源不是约束（已调研），约束是**业务驱动 + 内容来源**。

## 3. ① 作物地域化（升级现有提案）

### 3.1 改动定位

**不另起提案**。在现有 [`crop-template-system-library`](../../../openspec/changes/crop-template-system-library/proposal.md) 上叠加 delta 提案 `extend-crop-template-with-region-tag`，对 capability `crop-template-system-library` 增加 region_tag requirement。

### 3.2 数据模型变化

```python
# backend/app/models/crop.py
class CropTemplate(Base):
    # 现有字段...
    region_tag = Column(String(32), nullable=True, index=True)
    # 取值约定：'default' / 'xuzhou' / 'hainan' / 'guangdong' ...
    # NULL 视为 'default'（向后兼容）
```

不新建表，只加字段 + 一个 alembic 迁移。

### 3.3 Seed 数据策略

- **默认种子**：每种作物 1 套 `region_tag='default'`（fallback 用）
- **重点地域变体**：当前业务聚焦"徐州 × 西瓜" → seed 1 套 `region_tag='xuzhou'`，使用 WebSearch 调研后写脚本
- **不批量铺地域**：等业务扩到新地区再补
- **禁止 LLM 生成塞入系统库**：与原提案一致

### 3.4 Skill / API 行为升级

| 入口 | 当前 | 升级后 |
| --- | --- | --- |
| `GET /crops/templates/system?region=xuzhou` | 不存在 | 优先返回 region 命中，不足 fallback 到 default |
| `import_system_template` | 直接复制 | 复制时把 `region_tag` 一并带到用户副本 |
| `create_crop_template` Skill | LLM 兜底 | 推荐系统模板时按用户所在 region 优先匹配 |

### 3.5 用户所在 region 怎么定

复用现有 `UserSettings.default_city` → 映射到 region_tag。
- 徐州 / 徐州下辖县市 → `xuzhou`
- 其他 → `default`
- 映射表 hardcode 即可（城市→region），后期可改 DB

### 3.6 不做什么

- ❌ 不建"作物 × 地域 × 季节"大表（YAGNI）
- ❌ 不做气候带自动推算（学院派）
- ❌ 不让用户填纬度（专业用户才能填准）

## 4. ② 用户喜好（落地现有占位）

### 4.1 改动定位

落地 [docs/farm-manager-design-spec/01_正式设计/04_Memory工程 § 7 长时记忆](../../../docs/farm-manager-design-spec/01_正式设计/04_Memory工程.md)。memory.long_term 目录骨架已存在，**只接通**即可。

### 4.2 数据流

```
Response 节点完成
    ↓
asyncio.create_task(memory_service.extract_observations(...))
    ↓
LLM 抽取（复用 qwen + 现有熔断器）
    ↓
返回 MemoryRecord 候选（type / content / confidence）
    ↓
分流入库：
┌─────────────────────────────────────────┐
│ 高置信（confidence ≥ 0.85）             │
│ + 类型为 preference/habit/alias         │ → 直接写 memory_records
│                                         │   importance=0.5（待升）
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ 中置信 / 任意 confidence 的 fact/event   │ → 写候选队列
│                                         │   importance=0.3
│                                         │   等用户确认或重复 N 次
└─────────────────────────────────────────┘
```

**与 `maybe_summarize` 共用一套异步触发机制**（同一 Response 后台 hook，一次 LLM 调用同时输出 summary + observations，节省成本）。

### 4.3 memory_records 表（新建）

当前 [memory/long_term/store.py](../../../backend/app/memory/long_term/store.py) 是空实现，无表。本次落地新建 `memory_records` 表，按 [04_Memory工程 § 4 5 类](../../../docs/farm-manager-design-spec/01_正式设计/04_Memory工程.md) 设计：

```python
class MemoryRecord(Base):
    __tablename__ = "memory_records"
    id, farm_id, user_id
    type        # preference / habit / alias / event / fact
    content     # 自然语言
    importance  # 0.0-1.0
    status      # candidate / confirmed / superseded / archived
    confidence  # LLM 抽取置信度
    source      # user_explicit / llm_extracted
    superseded_by_id  # 软覆盖指针
    created_at, confirmed_at, last_referenced_at
```

需配套 alembic 迁移。

### 4.4 升级规则（importance 流转）

| 当前状态 | 触发 | 流转 |
| --- | --- | --- |
| candidate (0.3) | 用户主动说"对" / "以后都这样" | confirmed (0.8) |
| candidate (0.3) | 同类候选重复 N=3 次 | confirmed (0.7) |
| confirmed | 用户说"不对" / "改一下" | superseded_by 新记录 |
| 任意 | 90 天未被引用 + importance < 0.5 | archived |

### 4.5 显式 vs 隐式

- **显式**：用户说"记一下我喜欢下午浇水" → `source=user_explicit`，直接 confirmed (0.8)
- **隐式**：LLM 抽取 → `source=llm_extracted`，走候选流程

### 4.6 注入策略

[context/selectors/memory.py](../../../backend/app/context/selectors/memory.py) 的 MemorySelector 扩展查询：

```sql
SELECT * FROM memory_records
WHERE farm_id = :farm_id
  AND status IN ('confirmed', 'candidate')
  AND importance >= 0.3
ORDER BY importance DESC, last_referenced_at DESC
LIMIT 5
```

作为 `memory.long_term` block 注入（priority 介于 conversation_summary 与 retrieval 之间）。

### 4.7 不做什么

- ❌ 不做 embedding 相似检索（事实型偏好不需要语义匹配，SQL where 够）
- ❌ 不让候选队列无限堆积（90 天自动 archive）
- ❌ 不每轮抽取（与 summary 共触发，~12 条阈值）
- ❌ 不上 LLM-as-judge 二次校验（成本不划算，用户确认即可）

## 5. ③ 农技问答库 + Qdrant（暂缓 + 明确触发条件）

### 5.1 改动定位

不动代码。只在 spec 里写明**触发条件**和**实施时的边界**，避免将来"想上就上"。

### 5.2 触发条件（必须同时满足）

| # | 条件 | 当前 | 触达方式 |
| --- | --- | --- | --- |
| 1 | 用户主动问农技长尾问题（"XX 病怎么治"、"XX 药稀释比例"）≥ 周均 20 条 | ❌ 几乎没有 | trace 抽样统计 intent + 关键词 |
| 2 | 有内容运营资源（人工录入或合作方数据授权） | ❌ 没有 | 业务方确认 |
| 3 | 现有结构化表无法覆盖（不在作物模板/账单分类/物候期里） | 部分 | 由 1 推断 |
| 4 | LLM 当前对这类问题满意度 < 60% | 未知 | trace 抽样评分 |

**任一不满足 → 不引入**。

### 5.3 为什么当前不上

- ①②都用 MySQL 表，Qdrant 只能服务 ③——单点引入新基础设施，性价比低
- 当前用户量 < 10，长尾问题频率远未达阈值
- 内容来源没着落（自己爬合规风险，合作方未谈）
- Qdrant 资源不是问题（已调研），但没数据填进去就是空库

### 5.4 当前要保留的"接口位"

[docs/farm-manager-design-spec/01_正式设计/04_Memory工程 § 8 检索（Retrieval，预留）](../../../docs/farm-manager-design-spec/01_正式设计/04_Memory工程.md) 已有 `RetrievalPort` 协议占位：

```python
class RetrievalPort(Protocol):
    async def search(self, query: str, types: list[str], top: int = 5) -> list[MemoryRecord]:
        """当前返回 []，未来接 Qdrant。"""
```

本设计落地后，spec 该章节追加：
- 触发条件表（上面的 4 条）
- 实施时的边界（不动 ContextBuilder / MemoryService，只实现 RetrievalPort）
- 数据所有权（跨用户共享，需内容审核）

### 5.5 触发后的实施路径（预案，现在不做）

1. `docker-compose` 加 Qdrant 服务
2. 实现 `RetrievalPort` 的 Qdrant 适配器（独立模块 `backend/app/memory/retrieval/qdrant_adapter.py`）
3. 内容录入工具（admin web 单独页面）
4. `RetrievalSelector` 已存在 [context/selectors/retrieval.py](../../../backend/app/context/selectors/retrieval.py)，自动消费
5. ContextBuilder 边界不动

### 5.6 不做什么

- ❌ 不预先准备 FAQ 数据（B 方案风险，已否决）
- ❌ 不预先搭 Qdrant 容器（运维负担）
- ❌ 不动 RetrievalPort 接口签名（避免改两次）

## 6. 与已有 OpenSpec 提案衔接

| 已有提案 | 关系 | 动作 |
| --- | --- | --- |
| [`crop-template-system-library`](../../../openspec/changes/crop-template-system-library/proposal.md) | ① 升级其 | 新建 delta 提案 `extend-crop-template-with-region-tag`，对 capability `crop-template-system-library` 增加 region_tag requirement |
| [`add-running-summary-compaction`](../../../openspec/changes/add-running-summary-compaction/) | ② 共享基础设施 | 复用同一异步触发钩子；LLM 调用合并（一次出 summary + observations） |
| [`add-dataflywheel-discovery-layer`](../../../openspec/changes/add-dataflywheel-discovery-layer/) | 无直接关系 | Discovery Layer 关注"风险会话发现"，② 关注"偏好抽取"，互不干扰 |
| 现有 `short-term-memory-policy` spec | ② 长期记忆落地后的边界 | 长时记忆是新 capability `long-term-memory-policy`（候选名）；新建 `memory_records` 表（当前不存在，long_term 是空实现） |

## 7. Spec 文档同步落地

| 文档 | 章节 | 改动 |
| --- | --- | --- |
| [01_正式设计/04_Memory工程.md](../../../docs/farm-manager-design-spec/01_正式设计/04_Memory工程.md) | § 7 长时记忆 | 从"设计意图"补"落地实施"：candidate→confirmed 流转规则、importance 阈值、与 summary 共触发 |
| 同上 | § 8 检索（Retrieval） | 补"触发条件表 + 实施边界" |
| 同上 | § 14 当前状态 | 更新 long_term 状态 |
| 同上 | § 16 相关文档 | 加本 spec 引用 |
| [01_正式设计/02_Skill引擎与契约.md](../../../docs/farm-manager-design-spec/01_正式设计/02_Skill引擎与契约.md) | Skill 清单 | `create_crop_template` 行加注"按 region 优先推荐" |
| [Readme.md](../../../docs/farm-manager-design-spec/README.md) | 变更记录 | 加 v0.5 行 |

## 8. 后续触发点（不在本次范围）

- 业务扩到新地区 → 触发"region_tag 是否够用"复审
- 用户量到 50+ → 触发"长时记忆是否需要分库"
- 长尾农技问题频率达阈值 → 触发 Qdrant 落地 brainstorming
- LLM 抽取准确率 < 70% → 触发抽取 prompt 优化 brainstorming

## 9. 主动剔除的"看似相关"事项

按"避免过度设计"原则，以下事情**不做**：

| 想做但不做 | 理由 |
| --- | --- |
| 跨农场共享偏好（"看看别人怎么记的"） | 隐私 + 价值低 |
| 偏好自动画像（"温和型用户"/"急性子用户"） | 学院派，对农场场景无价值 |
| 多模态记忆（用户上传图片→记忆） | 当前无图片入口 |
| 偏好的偏好（"用户改了偏好后的理由"） | 元数据爆炸 |
| 主动询问"要不要记住" | 打断对话节奏，让 LLM 自然抽取更好 |
| 国际化 region（如越南 / 东南亚） | 当前业务聚焦国内 |

## 10. 开放问题

1. **region_tag 命名规范**：拼音 (`xuzhou`) / 拼音码 (`xz`) / 行政区码 (`32-03`)？倾向拼音，最易读。
2. **memory_records 表是新建**（已核查 [memory/long_term/store.py](../../../backend/app/memory/long_term/store.py) 是空实现）：本次提案包含建表 + alembic 迁移。
3. **summary + observations 合并 LLM 调用的 prompt 设计**：在 `add-running-summary-compaction` 提案 tasks 中扩展，还是单开 task？
4. **候选项的"重复 N 次"识别**：如何判定"同类"？内容相等 / type+关键词 / 嵌入相似（这是唯一可能引入 embedding 的场景，但要先验证 SQL where 不够用）。
