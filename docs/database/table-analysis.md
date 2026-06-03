# Farm Manager 旧 SQLite 表结构分析

> 生成时间：2026-05-27
> 数据库：SQLite（farm_manager.db，历史快照；生产已迁移到 MySQL）
> 共 17 张表

---

## 一、表总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        表依赖关系图                                   │
│                                                                     │
│   farms ──────────┬─────────────────────────────────────────────┐   │
│                   │                                             │   │
│                   ├─► crop_templates ──► growth_stages          │   │
│                   │                                             │   │
│                   ├─► crop_cycles ──► cycle_stages              │   │
│                   │       │                                     │   │
│                   │       ├─► farm_logs                         │   │
│                   │       ├─► advice_records                    │   │
│                   │       └─► report_records                    │   │
│                   │                                             │   │
│                   ├─► cost_records（自引用 parent_record_id）    │   │
│                   ├─► cost_categories                           │   │
│                   ├─► conversations ──► conversation_messages   │   │
│                   │                                             │   │
│                   └─（无外键但引用 farm_id）                      │   │
│                       ├─► guardrails_logs                       │   │
│                       ├─► trace_records                         │   │
│                       └─► token_daily_stats                     │   │
│                                                                     │
│   独立表（无外键）：                                                 │   │
│       idempotency_keys                                              │   │
│       agent_traces（旧表，已被 trace_records 替代？）               │   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、逐表分析

### 1. farms — 农场（顶层租户）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| name | String NOT NULL | 农场名称 |
| owner_name | String | 农场主姓名 |
| location | String | 所在地（如"苏州"） |
| display_name | String | AI 称呼（默认"农友"） |
| created_at | DateTime | 创建时间 |

**作用：** 多租户隔离的顶层实体，所有业务表通过 `farm_id` 关联。

**问题：**
- `owner_name` 和 `display_name` 语义重叠（一个是"真实姓名"，一个是"AI 称呼"）
- 缺少用户认证信息（手机号/密码等），无法支持真正的多用户登录
- `location` 只是一个字符串，没有经纬度，天气查询靠 Nominatim 地理编码
- 没有头像、性别、年龄等用户画像字段

---

### 2. crop_templates — 作物模板

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer FK → farms | 所属农场 |
| name | String NOT NULL | 作物名（如"西瓜"） |
| variety | String | 品种（如"8424"） |
| created_at | DateTime | 创建时间 |

**关联：** 1 个 template 有多个 growth_stages

**作用：** 定义一种作物的基本信息，作为创建种植周期的模板。

**问题：**
- `farm_id` 意味着每个农场各自维护模板，但作物模板本质上是公共知识（西瓜的生长期全国一样）。应该分"系统模板"和"自定义模板"。

---

### 3. growth_stages — 生长阶段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| crop_template_id | Integer FK → crop_templates | 所属作物模板 |
| name | String NOT NULL | 阶段名（如"育苗期"） |
| duration_days | Integer NOT NULL | 持续天数 |
| order_index | Integer NOT NULL | 排序序号 |
| key_tasks | String | 关键农事（逗号分隔） |

**作用：** 定义作物各生长阶段的时间和任务，供创建茬口时复制。

---

### 4. crop_cycles — 种植周期（茬口）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer FK → farms | 所属农场 |
| name | String NOT NULL | 茬口名（如"春季西瓜"） |
| crop_template_id | Integer FK → crop_templates | 关联作物模板 |
| start_date | Date NOT NULL | 开始日期 |
| field_name | String | 地块名 |
| status | String | 状态（默认"active"） |
| created_at | DateTime | 创建时间 |

**关联：** 1 个 cycle 有多个 cycle_stages、farm_logs、advice_records、report_records

**作用：** 记录一次具体的种植活动，是农事记录的核心聚合根。

---

### 5. cycle_stages — 茬口阶段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| cycle_id | Integer FK → crop_cycles | 所属茬口 |
| name | String NOT NULL | 阶段名 |
| start_date | Date NOT NULL | 开始日期 |
| end_date | Date NOT NULL | 结束日期 |
| order_index | Integer NOT NULL | 排序 |
| duration_days | Integer NOT NULL | 持续天数 |
| key_tasks | String | 关键农事 |
| is_current | Integer | 是否当前阶段（0/1） |

**作用：** 从模板复制到具体茬口的阶段实例，记录实际时间。

---

### 6. farm_logs — 农事日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer FK → farms | 所属农场 |
| cycle_id | Integer FK → crop_cycles | 关联茬口 |
| operation_type | String NOT NULL | 操作类型 |
| operation_date | Date NOT NULL | 操作日期 |
| operation_time | DateTime | 操作时间 |
| note | String | 备注 |
| photo_urls | String | 照片 URL |
| created_at | DateTime | 创建时间 |

**作用：** 记录农事操作（施肥、浇水、打药等）。

**问题：**
- `photo_urls` 是 String 而非 JSON/关联表，多张图片怎么存？
- `operation_type` 没有枚举约束，自由文本

---

### 7. cost_records — 成本记账

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer FK → farms | 所属农场 |
| cycle_id | Integer | 关联茬口（无 FK） |
| record_type | String NOT NULL | cost/income |
| category | String NOT NULL | 分类 |
| amount | Numeric(10,2) NOT NULL | 金额 |
| record_date | Date NOT NULL | 记账日期 |
| note | String | 备注 |
| record_subtype | String | 子类型（欠款/结算） |
| counterparty | String | 往来对象 |
| due_date | Date | 应付日期 |
| settled_at | DateTime | 结清时间 |
| parent_record_id | Integer FK → cost_records | 父记录（欠款关联） |
| created_at | DateTime | 创建时间 |

**作用：** 记录种植成本和收入，支持欠款/结算追踪。

**问题：**
- `cycle_id` 没有 FK 约束（可能是历史原因）
- `category` 是自由字符串，和 `cost_categories` 表没有 FK 关联

---

### 8. cost_categories — 成本分类

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer NOT NULL | 所属农场（无 FK） |
| name | String(50) NOT NULL | 分类名 |
| type | String(10) NOT NULL | cost/income |
| icon | String(50) | 图标 |
| sort_order | Integer | 排序 |
| is_default | Boolean | 是否系统默认 |
| created_at | DateTime | 创建时间 |

**作用：** 定义成本/收入的分类标签。

**问题：**
- `farm_id` 没有 FK 约束

---

### 9. advice_records — Agent 建议记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer FK → farms | 所属农场 |
| cycle_id | Integer FK → crop_cycles | 关联茬口（可空） |
| advice_type | String NOT NULL | chat/daily/report |
| content | Text NOT NULL | 建议内容 |
| created_at | DateTime | 创建时间 |

**作用：** 保存 LLM 生成的历史回复，用于缓存和回看。

**问题：**
- `advice_type` 混用了 chat、daily、report 三种完全不同的类型，和 report_records 表有语义重叠
- 不存用户输入，只有 AI 输出（用户输入在 conversation_messages 里）

---

### 10. report_records — 报告记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer FK → farms | 所属农场 |
| cycle_id | Integer FK → crop_cycles | 关联茬口（可空） |
| report_type | String NOT NULL | weekly/monthly |
| content | Text NOT NULL | 报告内容 |
| created_at | DateTime | 创建时间 |

**作用：** 保存周期报告。

**问题：**
- 和 `advice_records` 结构几乎一样，只是 type 命名不同，可以合并

---

### 11. conversations — 会话

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer FK → farms | 所属农场 |
| session_id | String UNIQUE | 前端生成的会话标识 |
| status | String | active/closed |
| created_at | DateTime | 创建时间 |
| last_active_at | DateTime | 最后活跃时间 |

**关联：** 1 个 conversation 有多个 conversation_messages

**作用：** 多轮对话会话管理，24h 自动过期。

---

### 12. conversation_messages — 会话消息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| conversation_id | Integer FK → conversations | 所属会话（CASCADE） |
| role | String NOT NULL | user/assistant |
| content | Text NOT NULL | 消息内容 |
| created_at | DateTime | 创建时间 |

**作用：** 持久化每轮对话的用户输入和 AI 回复。

---

### 13. trace_records — 链路追踪

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| request_id | String(16) | 请求标识 |
| session_id | String(64) | 会话标识 |
| farm_id | Integer | 农场 ID |
| round_index | Integer | 轮次 |
| node_type | String(20) | llm_call/skill_call/prompt_render |
| node_name | String(100) | 节点名 |
| input_data | Text | 输入 JSON |
| output_data | Text | 输出 JSON |
| start_time | String(32) | 开始时间 ISO |
| end_time | String(32) | 结束时间 ISO |
| duration_ms | Integer | 耗时毫秒 |
| token_usage | Text | Token 用量 JSON |
| status | String(10) | success/error |
| error_message | Text | 错误信息 |
| created_at | DateTime | 创建时间 |

**作用：** 记录每次 LLM/Skill 调用的详细链路，用于调试和性能分析。

---

### 14. token_daily_stats — Token 日统计

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer | 农场 ID |
| date | String(10) | 日期 YYYY-MM-DD |
| model | String(100) | 模型名 |
| call_type | String(20) | chat/daily_advice/report |
| prompt_tokens | Integer | 输入 Token |
| completion_tokens | Integer | 输出 Token |
| total_tokens | Integer | 总 Token |
| request_count | Integer | 请求次数 |
| estimated_cost_cny | Numeric(10,6) | 预估费用（元） |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

**唯一约束：** (farm_id, date, model, call_type)

**作用：** 按 farm/日期/模型汇总 Token 用量，用于配额和成本追踪。

---

### 15. guardrails_logs — 安全拦截日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| farm_id | Integer | 农场 ID |
| trigger_type | String(50) | 触发类型 |
| trigger_detail | Text | 触发详情 |
| source_text | Text | 原始文本 |
| created_at | DateTime | 创建时间 |

**作用：** 记录输入/输出安全拦截事件。

---

### 16. idempotency_keys — 幂等键

| 字段 | 类型 | 说明 |
|------|------|------|
| key | String(64) PK | 幂等键 |
| response | Text NOT NULL | 缓存响应 |
| created_at | DateTime | 创建时间 |

**作用：** 防止记账等写操作重复提交。24h 自动清理。

---

### 17. agent_traces — 旧链路追踪（疑似废弃）

数据库中存在此表，但代码中已无对应模型。可能是旧版 trace 实现的残留。

---

## 三、问题汇总

### 架构层面

| 编号 | 问题 | 影响 |
|------|------|------|
| A1 | **缺少用户表** — farms 既是"农场"又是"用户"，没有认证/登录体系 | 无法支持多用户，无法做用户画像 |
| A2 | **farms 职责过重** — 承担了农场信息 + 用户信息 + AI 偏好三重角色 | 字段膨胀，扩展困难 |
| A3 | **owner_name vs display_name 语义模糊** | 不清楚哪个是"真实姓名"、哪个是"AI 称呼" |
| A4 | **所有 farm_id 硬编码为 1** — `_llm_node`、`_parallel_tool_node` 等多处写死 | 多用户上线后会全局混乱 |

### 数据一致性

| 编号 | 问题 | 影响 |
|------|------|------|
| D1 | `cost_records.cycle_id` 无 FK 约束 | 可能产生孤儿记录 |
| D2 | `cost_categories.farm_id` 无 FK 约束 | 同上 |
| D3 | `cost_records.category` 是字符串，和 cost_categories 无 FK | 数据一致性靠应用层保证 |
| D4 | `advice_records` 和 `report_records` 结构雷同 | 维护两张表成本高 |

### 可清理项

| 编号 | 问题 | 建议 |
|------|------|------|
| C1 | `agent_traces` 表无代码引用 | 确认后删除 |
| C2 | `advice_records` 中 report 类型和 `report_records` 重叠 | 合并或拆清边界 |
