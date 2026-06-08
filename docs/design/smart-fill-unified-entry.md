---
last_updated: 2026-06-08
status: implemented
---

# Feature: 统一智能填写入口

## 目标
将记账、作物模板、茬口等自然语言智能填写能力收敛到统一场景入口，避免每个业务继续新增独立解析接口。

## 非目标
- 不通过智能填写接口直接写入业务数据。
- 不移除旧的 `/costs/parse`、`/crops/templates/parse`、`/cycles/parse` 兼容入口。
- 不改变 Agent Skill 的写确认机制。

## 技术方案

### 涉及的模块
- `app/schemas/smart_fill.py`：统一请求、响应和场景列表 schema。
- `app/agent/application/smart_fill.py`：场景注册表、prompt 变量构建、LLM 结构化解析、JSON fallback、幂等缓存和业务校验。
- `app/api/smart_fill.py`：新增统一 HTTP 入口。
- `app/api/cost.py`、`app/api/crop.py`、`app/api/cycle.py`：旧 parse 接口转调统一服务并保持原响应格式。

### 数据模型变更
无新增数据表。统一入口复用 `idempotency_keys` 表存储解析结果缓存，缓存 key 使用 `smart_fill:{scene}:{X-Idempotency-Key}` 前缀隔离不同场景。

### API 变更
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/smart-fill/scenarios` | 查询已注册的智能填写场景 |
| POST | `/smart-fill/parse` | 按场景解析自然语言并返回表单草稿 |

请求/响应体：
```json
{
  "request": {
    "scene": "ledger.record",
    "text": "今天买复合肥128.5元，记到春季西瓜",
    "context": {}
  },
  "response": {
    "scene": "ledger.record",
    "draft": {
      "record_type": "cost",
      "category": "肥料",
      "amount": "128.50",
      "record_date": "2026-06-08",
      "note": "买复合肥"
    },
    "missing_fields": [],
    "warnings": [],
    "trace_id": null
  }
}
```

## 验收标准
- [x] `/smart-fill/scenarios` 返回 `ledger.record`、`crop.template`、`crop.cycle` 三个初始场景。
- [x] `/smart-fill/parse` 统一返回 `scene + draft + missing_fields + warnings + trace_id`。
- [x] 旧 parse 接口继续可用，内部转调统一智能填写服务。
- [x] 新增场景只需要注册 `SmartFillScenario`、prompt、schema 和测试。

## 依赖
- Prompt 组合器和 `backend/prompts/config.yaml` 中现有 `cost_parse`、`crop_template_parse`、`cycle_parse` 场景。
- LLM structured output 能力和 `safe_parse_json` fallback。
