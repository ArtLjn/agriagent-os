# FC Tool Selection Fix 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 Python Skill description 和 system prompt，提升 qwen3.6-flash 的 Function Calling tool selection 准确率，修复"我的余额"、"帮我创建春茬种植西瓜"等明确 skill 请求不触发 tool call 的回归。

**Architecture:** 不改路由机制，只优化 LLM "看到的信息"——将 description 从"功能说明+触发词列表"改为"意图场景描述"，在 system prompt 注入可用工具映射表。小模型通过 description 中的关键词匹配用户意图，通过 prompt 映射表确认 tool 名称。

**Tech Stack:** Python 3.11, LangChain StructuredTool, Jinja2 prompt template, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/agent/skills/cost-summary/scripts/main.py` | **修改** | `description` 属性：补充余额、花了多少等口语词 |
| `backend/app/agent/skills/cost-analytics/scripts/main.py` | **修改** | `description` 属性：改为意图场景描述格式 |
| `backend/app/agent/skills/create-crop-cycle/scripts/main.py` | **修改** | `description` 属性：补充创建、种植、春茬等词 |
| `backend/app/agent/skills/create-cost-record/scripts/main.py` | **修改** | `description` 属性：改为意图场景描述格式 |
| `backend/app/agent/skills/weather/scripts/main.py` | **修改** | `description` 属性：改为意图场景描述格式 |
| `backend/app/agent/skills/crop-cycle/scripts/main.py` | **修改** | `description` 属性：补充茬口状态、当前阶段等 |
| `backend/app/agent/skills/farm-logs/scripts/main.py` | **修改** | `description` 属性：改为意图场景描述格式 |
| `backend/app/agent/skills/log-farm-activity/scripts/main.py` | **修改** | `description` 属性：改为意图场景描述格式 |
| `backend/app/agent/skills/update-crop-stage/scripts/main.py` | **修改** | `description` 属性：改为意图场景描述格式 |
| `backend/app/agent/skills/settle-debt/scripts/main.py` | **修改** | `description` 属性：改为意图场景描述格式 |
| `backend/prompts/base.j2` | **修改** | 新增【可用工具】映射表 |
| `backend/tests/skills/test_create_cost_record.py` | **修改** | 更新 `test_description_contains_trigger_words` |
| `backend/tests/skills/test_create_crop_cycle.py` | **修改** | 更新 `test_description_contains_trigger_words` |
| `backend/tests/skills/test_log_farm_activity.py` | **修改** | 更新 `test_description_contains_trigger_words` |
| `backend/tests/skills/test_update_crop_stage.py` | **修改** | 更新 `test_description_contains_trigger_words` |
| `backend/tests/skills/test_settle_debt.py` | **修改** | 更新 `test_description_contains_trigger_words` |
| `backend/tests/test_skills.py` | **修改** | 为 cost_summary/cost_analytics 新增元信息测试 |

**不改动的文件：**
- `app/agent/graph.py` — LangGraph 图定义不变
- `app/agent/skills/__init__.py` — Skill 注册逻辑不变
- 各 Skill 的 `parameters_schema()` — 参数 schema 不变
- 各 Skill 的 `execute()` 方法 — 执行逻辑不变

---

### Task 1: 优化 cost-summary Skill description

**Files:**
- Modify: `backend/app/agent/skills/cost-summary/scripts/main.py:22-26`
- Modify: `backend/tests/test_skills.py`

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/cost-summary/scripts/main.py` 第 22-26 行的 `description` 方法从：

```python
    def description(self) -> str:
        return (
            "查询农场成本与收入汇总，支持按周期、日期范围、分类、记录类型筛选，"
            "并可按分类或月份分组。触发词: 成本、收入、利润、收支"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "查询农场收支汇总数据。当用户问余额、花了多少、赚了多少、"
            "收支情况、成本多少、利润、账单、近期收支时，调用此工具获取真实数据。"
            "支持按日期、分类筛选和分组。"
        )
```

- [ ] **Step 2: 在 `backend/tests/test_skills.py` 顶部添加元信息测试**

在 `backend/tests/test_skills.py` 的 import 块后（现有 `TestCostSummarySkill` 类之前），添加以下测试类：

```python
class TestCostSummarySkillMeta:
    def test_name(self):
        from app.agent.skills.cost_summary.scripts.main import CostSummarySkill
        skill = CostSummarySkill()
        assert skill.name() == "get_cost_summary"

    def test_description_contains_trigger_words(self):
        from app.agent.skills.cost_summary.scripts.main import CostSummarySkill
        skill = CostSummarySkill()
        desc = skill.description()
        assert "余额" in desc
        assert "花了" in desc
        assert "收支" in desc

    def test_parameters_schema(self):
        from app.agent.skills.cost_summary.scripts.main import CostSummarySkill
        skill = CostSummarySkill()
        schema = skill.parameters_schema()
        assert "cycle_id" in schema["properties"]
        assert "group_by" in schema["properties"]


class TestCostAnalyticsSkillMeta:
    def test_name(self):
        from app.agent.skills.cost_analytics.scripts.main import CostAnalyticsSkill
        skill = CostAnalyticsSkill()
        assert skill.name() == "get_cost_analytics"

    def test_description_contains_trigger_words(self):
        from app.agent.skills.cost_analytics.scripts.main import CostAnalyticsSkill
        skill = CostAnalyticsSkill()
        desc = skill.description()
        assert "趋势" in desc
        assert "对比" in desc

    def test_parameters_schema(self):
        from app.agent.skills.cost_analytics.scripts.main import CostAnalyticsSkill
        skill = CostAnalyticsSkill()
        schema = skill.parameters_schema()
        assert "compare_period" in schema["properties"]
```

- [ ] **Step 3: 运行测试验证**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_skills.py::TestCostSummarySkillMeta tests/test_skills.py::TestCostAnalyticsSkillMeta -v`
Expected: 6 个 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/skills/cost-summary/scripts/main.py backend/tests/test_skills.py
git commit -m "feat: 优化 cost-summary description，补充余额等口语触发词"
```

---

### Task 2: 优化 cost-analytics Skill description

**Files:**
- Modify: `backend/app/agent/skills/cost-analytics/scripts/main.py:22-26`

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/cost-analytics/scripts/main.py` 第 22-26 行从：

```python
    def description(self) -> str:
        return (
            "全局收支趋势分析，支持同比环比对比。"
            "触发词: 分析、趋势、对比、比去年、比上月"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "分析农场收支趋势与对比。当用户问收支趋势、比去年花了多少、"
            "比上月赚了多少、成本分析、同比环比时，调用此工具获取趋势数据。"
            "支持按月、去年同期对比。"
        )
```

- [ ] **Step 2: 运行测试验证**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_skills.py::TestCostAnalyticsSkillMeta -v`
Expected: 3 个 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/skills/cost-analytics/scripts/main.py
git commit -m "feat: 优化 cost-analytics description，使用意图场景描述格式"
```

---

### Task 3: 优化 create-crop-cycle Skill description

**Files:**
- Modify: `backend/app/agent/skills/create-crop-cycle/scripts/main.py:24-29`
- Modify: `backend/tests/skills/test_create_crop_cycle.py`（更新触发词测试）

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/create-crop-cycle/scripts/main.py` 第 24-29 行从：

```python
    def description(self) -> str:
        return (
            "创建一个新的种植茬口。当用户说建茬口、种什么、"
            "开始种某作物时使用。"
            "触发词: 建茬口、种、开始种"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "创建一个新的种植茬口（种植周期）。当用户说创建茬口、种植某作物、"
            "建茬口、开始种西瓜/番茄/辣椒等、春茬种什么、秋茬种什么时，"
            "调用此工具。需要提供作物名称，可选提供季节和开始日期。"
        )
```

- [ ] **Step 2: 更新测试中的触发词断言**

将 `backend/tests/skills/test_create_crop_cycle.py` 中 `TestCreateCropCycleMeta` 类的 `test_description_contains_trigger_words` 方法从：

```python
    def test_description_contains_trigger_words(self):
        skill = CreateCropCycleSkill()
        desc = skill.description()
        assert "建茬口" in desc
        assert "种" in desc
```

改为：

```python
    def test_description_contains_trigger_words(self):
        skill = CreateCropCycleSkill()
        desc = skill.description()
        assert "创建" in desc
        assert "种植" in desc
        assert "茬口" in desc
```

- [ ] **Step 3: 运行测试验证**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/skills/test_create_crop_cycle.py::TestCreateCropCycleMeta -v`
Expected: 3 个 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/skills/create-crop-cycle/scripts/main.py backend/tests/skills/test_create_crop_cycle.py
git commit -m "feat: 优化 create-crop-cycle description，补充创建/种植/春茬等触发词"
```

---

### Task 4: 优化 create-cost-record Skill description

**Files:**
- Modify: `backend/app/agent/skills/create-cost-record/scripts/main.py:22-27`
- Modify: `backend/tests/skills/test_create_cost_record.py`（更新触发词测试）

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/create-cost-record/scripts/main.py` 第 22-27 行从：

```python
    def description(self) -> str:
        return (
            "创建一笔成本或收入记录。当用户提到买了什么东西花了多少钱、"
            "或者卖了什么赚了多少钱时使用。"
            "触发词: 记了一笔、花多少、买多少、卖多少、赚多少、花了、买了、卖了、记账、赊账、收入了、支出了、万、块"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "记录一笔农场支出或收入。当用户说记一笔、买了化肥200块、"
            "卖了西瓜赚了5000、花了多少钱、赊账记账时，调用此工具。"
            "需要提供金额和分类，可选提供日期、类型、备注。"
        )
```

- [ ] **Step 2: 更新测试中的触发词断言**

将 `backend/tests/skills/test_create_cost_record.py` 中 `TestCreateCostRecordSkillMeta` 类的 `test_description_contains_trigger_words` 方法从：

```python
    def test_description_contains_trigger_words(self):
        skill = CreateCostRecordSkill()
        desc = skill.description()
        assert "记账" in desc
        assert "花了" in desc
```

改为：

```python
    def test_description_contains_trigger_words(self):
        skill = CreateCostRecordSkill()
        desc = skill.description()
        assert "记账" in desc
        assert "花了" in desc
        assert "买了" in desc
```

- [ ] **Step 3: 运行测试验证**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/skills/test_create_cost_record.py::TestCreateCostRecordSkillMeta -v`
Expected: 3 个 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/skills/create-cost-record/scripts/main.py backend/tests/skills/test_create_cost_record.py
git commit -m "feat: 优化 create-cost-record description，使用意图场景描述格式"
```

---

### Task 5: 优化 weather Skill description

**Files:**
- Modify: `backend/app/agent/skills/weather/scripts/main.py:69`

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/weather/scripts/main.py` 第 69 行从：

```python
    def description(self) -> str:
        return "获取未来7天天气预报和灾害预警。触发词: 天气、预报、降雨"
```

改为：

```python
    def description(self) -> str:
        return (
            "获取未来7天天气预报和灾害预警。当用户问天气怎么样、明天天气、"
            "最近有雨吗、气温多少、有没有极端天气时，调用此工具获取真实天气数据。"
        )
```

- [ ] **Step 2: 运行 ruff 检查**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && ruff check app/agent/skills/weather/scripts/main.py`
Expected: 无 error

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/skills/weather/scripts/main.py
git commit -m "feat: 优化 weather description，使用意图场景描述格式"
```

---

### Task 6: 优化 crop-cycle Skill description

**Files:**
- Modify: `backend/app/agent/skills/crop-cycle/scripts/main.py:18-22`

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/crop-cycle/scripts/main.py` 第 18-22 行从：

```python
    def description(self) -> str:
        return (
            "查询指定种植周期的详细信息，包括当前阶段和各阶段安排。"
            "触发词: 周期、阶段、茬口"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "查询种植周期的详细信息。当用户问茬口状态、当前阶段、"
            "周期进度、茬口详情、西瓜长到哪了时，调用此工具获取真实数据。"
            "需要提供周期 ID。"
        )
```

- [ ] **Step 2: 运行 ruff 检查**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && ruff check app/agent/skills/crop-cycle/scripts/main.py`
Expected: 无 error

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/skills/crop-cycle/scripts/main.py
git commit -m "feat: 优化 crop-cycle description，补充茬口状态/当前阶段等触发词"
```

---

### Task 7: 优化 farm-logs Skill description

**Files:**
- Modify: `backend/app/agent/skills/farm-logs/scripts/main.py:19`

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/farm-logs/scripts/main.py` 第 19 行从：

```python
    def description(self) -> str:
        return "查询指定周期最近N天的农事记录。触发词: 记录、日志、农事"
```

改为：

```python
    def description(self) -> str:
        return (
            "查询最近几天的农事操作记录。当用户问最近干了啥、查看农事记录、"
            "最近的操作日志、这几天做了什么农活时，调用此工具获取真实记录。"
            "需要提供周期 ID。"
        )
```

- [ ] **Step 2: 运行 ruff 检查**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && ruff check app/agent/skills/farm-logs/scripts/main.py`
Expected: 无 error

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/skills/farm-logs/scripts/main.py
git commit -m "feat: 优化 farm-logs description，使用意图场景描述格式"
```

---

### Task 8: 优化 log-farm-activity Skill description

**Files:**
- Modify: `backend/app/agent/skills/log-farm-activity/scripts/main.py:22-25`
- Modify: `backend/tests/skills/test_log_farm_activity.py`（更新触发词测试）

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/log-farm-activity/scripts/main.py` 第 22-25 行从：

```python
    def description(self) -> str:
        return (
            "记录一条农事操作。当用户说做了什么农活、浇了水、施了肥、"
            "打药时使用。触发词: 记农事、浇水、施肥、打药、干了啥"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "记录一条农事操作。当用户说今天浇了水、施了肥、打了药、"
            "干了什么农活、记录农事操作时，调用此工具。"
            "需要提供操作类型（如浇水、施肥、打药），可选关联茬口。"
        )
```

- [ ] **Step 2: 更新测试中的触发词断言**

将 `backend/tests/skills/test_log_farm_activity.py` 中 `TestLogFarmActivityMeta` 类的 `test_description_contains_trigger_words` 方法从：

```python
    def test_description_contains_trigger_words(self):
        skill = LogFarmActivitySkill()
        desc = skill.description()
        assert "浇水" in desc
        assert "施肥" in desc
        assert "打药" in desc
        assert "记农事" in desc
```

改为：

```python
    def test_description_contains_trigger_words(self):
        skill = LogFarmActivitySkill()
        desc = skill.description()
        assert "浇水" in desc
        assert "施肥" in desc
        assert "打药" in desc
        assert "农事" in desc
```

- [ ] **Step 3: 运行测试验证**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/skills/test_log_farm_activity.py::TestLogFarmActivityMeta -v`
Expected: 3 个 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/skills/log-farm-activity/scripts/main.py backend/tests/skills/test_log_farm_activity.py
git commit -m "feat: 优化 log-farm-activity description，使用意图场景描述格式"
```

---

### Task 9: 优化 update-crop-stage Skill description

**Files:**
- Modify: `backend/app/agent/skills/update-crop-stage/scripts/main.py:22-25`
- Modify: `backend/tests/skills/test_update_crop_stage.py`（更新触发词测试）

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/update-crop-stage/scripts/main.py` 第 22-25 行从：

```python
    def description(self) -> str:
        return (
            "更新茬口的生长阶段。当用户说进XX期了、到XX阶段了时使用。"
            "触发词: 进XX期、到XX阶段、阶段更新"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "更新茬口的生长阶段。当用户说西瓜进苗期了、到开花期了、"
            "阶段更新、进入下一阶段时，调用此工具更新当前阶段。"
            "需要提供目标阶段名称，可选指定茬口 ID。"
        )
```

- [ ] **Step 2: 更新测试中的触发词断言**

将 `backend/tests/skills/test_update_crop_stage.py` 中 `TestUpdateCropStageMeta` 类的 `test_description_contains_trigger_words` 方法从：

```python
    def test_description_contains_trigger_words(self):
        skill = UpdateCropStageSkill()
        desc = skill.description()
        assert "阶段" in desc
        assert "进" in desc
```

改为：

```python
    def test_description_contains_trigger_words(self):
        skill = UpdateCropStageSkill()
        desc = skill.description()
        assert "阶段" in desc
        assert "进" in desc
        assert "更新" in desc
```

- [ ] **Step 3: 运行测试验证**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/skills/test_update_crop_stage.py::TestUpdateCropStageMeta -v`
Expected: 3 个 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/skills/update-crop-stage/scripts/main.py backend/tests/skills/test_update_crop_stage.py
git commit -m "feat: 优化 update-crop-stage description，使用意图场景描述格式"
```

---

### Task 10: 优化 settle-debt Skill description

**Files:**
- Modify: `backend/app/agent/skills/settle-debt/scripts/main.py:27-30`
- Modify: `backend/tests/skills/test_settle_debt.py`（触发词测试不变，确认仍通过）

- [ ] **Step 1: 修改 description 属性**

将 `backend/app/agent/skills/settle-debt/scripts/main.py` 第 27-30 行从：

```python
    def description(self) -> str:
        return (
            "还赊账，结清欠款。当用户说还钱、还账、还了XX时使用。"
            "触发词: 还钱、还账、还款、清账"
        )
```

改为：

```python
    def description(self) -> str:
        return (
            "还赊账、结清欠款。当用户说还钱、还账、还款、清账、"
            "还了老王多少钱、把欠的账结了时，调用此工具。"
            "需要提供债权人名称，可选提供还款金额。"
        )
```

- [ ] **Step 2: 运行测试验证**（现有测试断言"还钱"、"还账"、"还款"、"清账"都在新 description 中）

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/skills/test_settle_debt.py::TestSettleDebtSkillMeta::test_description_contains_trigger_words -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/skills/settle-debt/scripts/main.py
git commit -m "feat: 优化 settle-debt description，使用意图场景描述格式"
```

---

### Task 11: 在 system prompt 注入可用工具映射表

**Files:**
- Modify: `backend/prompts/base.j2:25-29`

- [ ] **Step 1: 在【工具调用规则】后新增【可用工具】段落**

将 `backend/prompts/base.j2` 第 25-29 行从：

```
【工具调用规则】（最高优先级，违反则回答无效）
- 禁止凭记忆回答天气、成本、农事记录、茬口状态等实时数据。
- 遇到上述信息时，必须先调用对应工具获取真实数据，再回答。
- 如果不确定信息是否最新，一律调用工具确认。
- 回答要简洁明了，适合农民理解。
```

改为：

```
【工具调用规则】（最高优先级，违反则回答无效）
- 禁止凭记忆回答天气、成本、农事记录、茬口状态等实时数据。
- 遇到上述信息时，必须先调用对应工具获取真实数据，再回答。
- 如果不确定信息是否最新，一律调用工具确认。
- 回答要简洁明了，适合农民理解。

【可用工具】（根据用户意图选择对应工具）
- weather: 天气、预报、降雨、温度、极端天气
- get_cost_summary: 余额、收支、成本、利润、花了多少、赚了多少、账单
- get_cost_analytics: 趋势、对比、比去年、比上月、收支分析
- create_cost_record: 记账、花了、买了、卖了、赊账、记一笔
- create_crop_cycle: 创建茬口、种植、种西瓜、春茬、秋茬、建茬口
- get_crop_cycle_info: 茬口状态、当前阶段、周期进度、茬口详情
- get_recent_farm_logs: 农事记录、最近操作、日志、干了啥
- log_farm_activity: 记农事、浇水、施肥、打药、记录操作
- update_crop_stage: 进苗期了、到开花期了、阶段更新、进XX期
- settle_debt: 还钱、还账、清账、还款、结清欠款
```

- [ ] **Step 2: 运行已有 prompt 相关测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/test_prompt_registry.py tests/test_function_calling_e2e.py -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/prompts/base.j2
git commit -m "feat: system prompt 新增可用工具映射表，提升小模型 tool selection 准确率"
```

---

### Task 12: 最终验证

- [ ] **Step 1: ruff 全量检查**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && ruff check app/agent/skills/ tests/skills/ tests/test_skills.py`
Expected: 无 error

- [ ] **Step 2: 全量测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && source .venv/bin/activate && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 3: 验证所有 description 已更新**

Run: `cd /Users/ljn/Documents/demo/explore/backend && grep -rn "触发词:" app/agent/skills/*/scripts/main.py`
Expected: 无匹配（空输出，说明所有旧格式已清除）

- [ ] **Step 4: 验证 prompt 包含工具映射表**

Run: `cd /Users/ljn/Documents/demo/explore/backend && grep "get_cost_summary" prompts/base.j2`
Expected: 有匹配

- [ ] **Step 5: 最终 commit**

```bash
git add -A
git commit -m "chore: FC tool selection fix 最终验证通过"
```
