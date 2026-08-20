# LLM 输出格式美化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 4 个核心场景（天气预报、记账确认、茬口创建、作物模板创建）的纯文本回复改为 emoji + Markdown 格式，提升手机端阅读体验。

**Architecture:** 采用代码生成格式（非依赖 LLM）策略。各 skill 的 `_format_reply` 方法直接输出 Markdown 文本，`build_confirm_message` 为每个写操作 skill 生成带 emoji 的确认文案。Prompt 模板 `base.j2` 新增格式引导段落影响 LLM 自由输出。

**Tech Stack:** Python 3.12 / Jinja2 / 纯字符串拼接 / pytest

---

## 文件变更地图

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/prompts/base.j2` | 修改 | 新增【回复风格】段落 |
| `backend/app/agent/skills/weather/scripts/main.py` | 修改 | 天气回复改为 Markdown 表格 + emoji |
| `backend/app/infra/pending_actions.py` | 修改 | `build_confirm_message` 改为 emoji 格式 |
| `backend/app/agent/skills/create-crop-cycle/scripts/main.py` | 修改 | `_format_reply` 改为 emoji + 有序列表 |
| `backend/app/agent/skills/create-crop-template/scripts/main.py` | 修改 | 成功回复改为 emoji + 有序列表 |
| `backend/app/agent/skills/create-cost-record/scripts/main.py` | 修改 | `_format_reply` 改为 emoji 格式 |
| `backend/tests/skills/test_weather_format.py` | 创建 | 天气格式化测试 |
| `backend/tests/test_pending_actions.py` | 修改 | 更新 `build_confirm_message` 断言 |
| `backend/tests/skills/test_create_cost_record.py` | 修改 | 更新 `_format_reply` 断言 |
| `backend/tests/skills/test_create_crop_cycle.py` | 修改 | 更新 `_format_reply` 断言 |

---

### Task 1: Prompt 模板增加【回复风格】段落

**Files:**
- Modify: `backend/prompts/base.j2:10-16`（在【回复格式】段之后插入新段落）

- [ ] **Step 1: 在 `base.j2` 的【回复格式】段之后添加【回复风格】段落**

在 `backend/prompts/base.j2` 第 16 行（`- 用「你」不用「您」，口语化`）之后，第 18 行（空行）之前插入：

```
【回复风格】
- 每条建议加 emoji 前缀（🌱💡⚠️📊💰等），让内容更醒目
- 用 Markdown 列表和加粗组织内容（如 **关键信息**）
- 保持口语化短句，不要写长段落
```

- [ ] **Step 2: 验证模板语法正确**

Run: `cd backend && python -c "from jinja2 import Environment; Environment().from_string(open('prompts/base.j2').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/prompts/base.j2
git commit -m "feat: add emoji and Markdown format guidance to prompt template"
```

---

### Task 2: 天气预报格式化为 Markdown 表格

**Files:**
- Modify: `backend/app/agent/skills/weather/scripts/main.py:73-89`（`execute` 方法的回复生成部分）
- Create: `backend/tests/skills/test_weather_format.py`

- [ ] **Step 1: 编写天气格式化失败测试**

创建 `backend/tests/skills/test_weather_format.py`：

```python
"""天气预报格式化测试 — 验证 Markdown 表格输出。"""

import importlib
from unittest.mock import MagicMock, patch

import pytest

_weather_mod = importlib.import_module(
    "app.agent.skills.weather.scripts.main"
)
WeatherSkill = _weather_mod.WeatherSkill


def _make_weather_data(days=3) -> dict:
    """构造模拟天气数据（3天）。"""
    return {
        "daily": {
            "time": ["2026-05-28", "2026-05-29", "2026-05-30"],
            "temperature_2m_max": [28, 22, 25],
            "temperature_2m_min": [18, 16, 17],
            "precipitation_sum": [0, 8, 2.5],
            "windspeed_10m_max": [5, 12, 8],
        }
    }


class TestWeatherFormatMarkdown:
    """验证天气回复使用 Markdown 表格格式。"""

    def test_reply_starts_with_location_emoji(self):
        """回复以 📍 emoji + 地点开头。"""
        data = _make_weather_data()
        # 直接测试 execute 的输出
        skill = WeatherSkill()
        # 用 _format 测试而非整个 execute
        reply = _build_weather_reply("苏州", data)
        assert reply.startswith("📍")

    def test_reply_contains_markdown_table(self):
        """回复包含 Markdown 表格（| 分隔符）。"""
        data = _make_weather_data()
        reply = _build_weather_reply("苏州", data)
        assert "|" in reply
        assert "---" in reply

    def test_reply_contains_weather_emoji(self):
        """天气列包含 emoji 图标。"""
        data = _make_weather_data()
        reply = _build_weather_reply("苏州", data)
        # 0mm 降水应为 ☀️，8mm 应为 🌧️
        assert "☀️" in reply
        assert "🌧️" in reply

    def test_date_format_m_d(self):
        """日期格式为 M/D（如 5/28）。"""
        data = _make_weather_data()
        reply = _build_weather_reply("苏州", data)
        assert "5/28" in reply
        assert "5/29" in reply

    def test_only_three_days_shown(self):
        """只展示 3 天数据。"""
        data = _make_weather_data()
        reply = _build_weather_reply("苏州", data)
        # 不应出现第 4 天
        assert "5/31" not in reply

    def test_warning_appended_after_table(self):
        """预警信息在表格之后。"""
        data = _make_weather_data()
        data["daily"]["temperature_2m_max"][0] = 38  # 触发高温预警
        reply = _build_weather_reply("苏州", data)
        assert "⚠️" in reply
        # 预警应在表格之后
        table_end = reply.rindex("|")
        warning_pos = reply.index("⚠️")
        assert warning_pos > table_end

    def test_no_warning_shows_no_alert(self):
        """无预警时不出现 ⚠️。"""
        data = _make_weather_data()
        reply = _build_weather_reply("苏州", data)
        assert "⚠️" not in reply

    def test_no_data_returns_fallback(self):
        """无数据时返回友好提示。"""
        reply = _build_weather_reply("苏州", {"daily": {}})
        assert "🌤️" in reply


def _build_weather_reply(location: str, weather_data: dict) -> str:
    """直接调用 weather skill 内部的回复构建逻辑。

    测试通过 import 模块后直接调用 _format_weather_reply 函数。
    """
    # 先尝试调用模块级函数，如果不存在则调用类方法
    format_fn = getattr(_weather_mod, "_format_weather_reply", None)
    if format_fn:
        return format_fn(location, weather_data)
    # 兜底：直接构造 WeatherSkill 并调用
    raise AttributeError(
        "_format_weather_reply not found — implement it in weather skill first"
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/skills/test_weather_format.py -v`
Expected: FAIL（`_format_weather_reply` 不存在）

- [ ] **Step 3: 在 weather skill 中实现天气 emoji 映射和 Markdown 格式化**

在 `backend/app/agent/skills/weather/scripts/main.py` 中，将 `execute` 方法的回复生成逻辑（第 73-89 行）替换为调用新的模块级函数。

首先在文件顶部（`WeatherSkill` 类定义之前）添加天气 emoji 映射函数和格式化函数：

```python
def _weather_emoji(precip: float, max_temp: float) -> str:
    """根据降水量和温度返回天气 emoji。"""
    if precip >= 20:
        return "⛈️"
    if precip >= 5:
        return "🌧️"
    if precip >= 0.5:
        return "🌦️"
    if max_temp >= 35:
        return "☀️"
    if max_temp <= 5:
        return "❄️"
    return "🌤️"


def _format_date_m_d(date_str: str) -> str:
    """将 YYYY-MM-DD 转为 M/D 格式。"""
    parts = date_str.split("-")
    return f"{int(parts[1])}/{int(parts[2])}"


def _format_weather_reply(location: str, data: dict) -> str:
    """将天气数据格式化为 Markdown 表格回复。"""
    daily = data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])

    if not times:
        return "🌤️ 暂时获取不到天气数据，请稍后再试。"

    # 只展示前 3 天
    count = min(3, len(times))

    lines = [f"📍 {location} · 未来 {count} 天预报", ""]
    lines.append("| 日期 | 天气 | 最高 | 最低 | 降水 |")
    lines.append("|------|------|------|------|------|")

    for i in range(count):
        day = _format_date_m_d(times[i])
        max_t = max_temps[i] if i < len(max_temps) else "-"
        min_t = min_temps[i] if i < len(min_temps) else "-"
        p = precips[i] if i < len(precips) else 0
        emoji = _weather_emoji(float(p), float(max_t) if max_t != "-" else 20)
        lines.append(f"| {day} | {emoji} | {max_t}℃ | {min_t}℃ | {p}mm |")

    from app.services.weather_service import check_weather_warnings

    warnings = check_weather_warnings(data)
    if warnings:
        lines.append("")
        for w in warnings:
            lines.append(f"⚠️ {w}")

    return "\n".join(lines)
```

然后修改 `execute` 方法中第 73-89 行，将整个回复生成部分替换为：

```python
        data = fetch_weather(lat, lon, days=3)
        reply = _format_weather_reply(location, data)
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
```

同时删除 `execute` 方法中不再使用的 `winds` 变量（第 72 行）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/skills/test_weather_format.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 运行既有天气相关测试确认无回归**

Run: `cd backend && python -m pytest tests/ -v -k weather`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/skills/weather/scripts/main.py backend/tests/skills/test_weather_format.py
git commit -m "feat: weather forecast reply uses Markdown table with emoji"
```

---

### Task 3: Pending Action 确认文案增加 emoji

**Files:**
- Modify: `backend/app/infra/pending_actions.py:25-32`（`_SKILL_DISPLAY` 字典）和第 108-117 行（`build_confirm_message` 函数）
- Modify: `backend/tests/test_pending_actions.py`

- [ ] **Step 1: 编写 `build_confirm_message` 的新格式失败测试**

在 `backend/tests/test_pending_actions.py` 中新增测试类：

```python
class TestBuildConfirmMessageFormat:
    """测试 build_confirm_message 的 emoji + 可读格式。"""

    @pytest.mark.parametrize(
        "skill_name,params,expected_parts",
        [
            (
                "create_cost_record",
                {"amount": 50, "category": "化肥", "record_type": "cost"},
                ["💰", "化肥", "50元", "支出"],
            ),
            (
                "create_crop_cycle",
                {"crop_name": "西瓜", "season": "春季"},
                ["🌱", "西瓜", "春季"],
            ),
            (
                "create_crop_template",
                {"crop_name": "玉米"},
                ["📋", "玉米"],
            ),
            (
                "log_farm_activity",
                {"operation_type": "浇水"},
                ["📝", "浇水"],
            ),
            (
                "settle_debt",
                {"counterparty": "老王", "amount": 500},
                ["💳", "老王", "500元"],
            ),
            (
                "update_crop_stage",
                {"stage_name": "开花期"},
                ["🔄", "开花期"],
            ),
        ],
    )
    def test_confirm_message_has_emoji_and_readable_params(
        self, skill_name, params, expected_parts
    ):
        """确认文案包含 emoji 和可读参数。"""
        from app.infra.pending_actions import build_confirm_message

        msg = build_confirm_message(skill_name, params)
        for part in expected_parts:
            assert part in msg, f"expected '{part}' in '{msg}'"

    def test_confirm_message_ends_with_question(self):
        """确认文案以问号结尾。"""
        from app.infra.pending_actions import build_confirm_message

        msg = build_confirm_message(
            "create_cost_record",
            {"amount": 50, "category": "化肥", "record_type": "cost"},
        )
        assert msg.rstrip("。").endswith("确认吗？") or msg.endswith("？")

    def test_unknown_skill_uses_default_format(self):
        """未知 skill 使用默认格式。"""
        from app.infra.pending_actions import build_confirm_message

        msg = build_confirm_message("unknown_skill", {"foo": "bar"})
        assert "确认" in msg
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_pending_actions.py::TestBuildConfirmMessageFormat -v`
Expected: FAIL（新格式未实现）

- [ ] **Step 3: 修改 `_SKILL_DISPLAY` 和 `build_confirm_message`**

在 `backend/app/infra/pending_actions.py` 中：

将 `_SKILL_DISPLAY` 字典（第 25-32 行）替换为：

```python
_SKILL_DISPLAY: dict[str, str] = {
    "create_cost_record": "记账",
    "create_crop_cycle": "创建茬口",
    "create_crop_template": "创建作物模板",
    "log_farm_activity": "记录农事",
    "settle_debt": "还款",
    "update_crop_stage": "更新阶段",
}

_SKILL_EMOJI: dict[str, str] = {
    "create_cost_record": "💰",
    "create_crop_cycle": "🌱",
    "create_crop_template": "📋",
    "log_farm_activity": "📝",
    "settle_debt": "💳",
    "update_crop_stage": "🔄",
}

_SKILL_PARAM_FORMAT: dict[str, list[str]] = {
    "create_cost_record": ["category", "amount"],
    "create_crop_cycle": ["crop_name", "season"],
    "create_crop_template": ["crop_name"],
    "log_farm_activity": ["operation_type"],
    "settle_debt": ["counterparty", "amount"],
    "update_crop_stage": ["stage_name"],
}
```

将 `build_confirm_message` 函数（第 108-117 行）替换为：

```python
def build_confirm_message(skill_name: str, params: dict) -> str:
    emoji = _SKILL_EMOJI.get(skill_name, "❓")
    action = _SKILL_DISPLAY.get(skill_name, skill_name)

    param_keys = _SKILL_PARAM_FORMAT.get(skill_name, list(params.keys()))
    parts = []
    for k in param_keys:
        v = params.get(k)
        if v is not None:
            if k == "amount":
                parts.append(f"{v}元")
            elif k == "record_type":
                label = "收入" if v == "income" else "支出"
                parts.append(label)
            else:
                parts.append(str(v))

    detail = " ".join(parts) if parts else ""
    if detail:
        return f"{emoji} 确认{action}：{detail}，确认吗？"
    return f"{emoji} 确认{action}，确认吗？"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_pending_actions.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/pending_actions.py backend/tests/test_pending_actions.py
git commit -m "feat: pending action confirm message uses emoji and readable params"
```

---

### Task 4: 茬口创建结果格式化

**Files:**
- Modify: `backend/app/agent/skills/create-crop-cycle/scripts/main.py:123-133`（`_format_reply` 函数）
- Modify: `backend/tests/skills/test_create_crop_cycle.py`

- [ ] **Step 1: 编写茬口格式化失败测试**

在 `backend/tests/skills/test_create_crop_cycle.py` 中新增测试：

```python
class TestCropCycleFormatReply:
    """验证茬口创建回复使用 emoji + 有序列表格式。"""

    def test_reply_starts_with_success_emoji(self):
        """回复以 ✅ 开头。"""
        cycle = _make_cycle(name="春季西瓜")
        reply = _create_cycle_mod._format_reply(cycle)
        assert reply.startswith("✅")

    def test_reply_contains_cycle_name(self):
        """回复包含茬口名称。"""
        cycle = _make_cycle(name="春季西瓜")
        reply = _create_cycle_mod._format_reply(cycle)
        assert "春季西瓜" in reply

    def test_reply_contains_ordered_list(self):
        """阶段使用有序列表（1. 2. 3.）。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        assert "1." in reply
        assert "2." in reply
        assert "3." in reply

    def test_reply_date_format_m_d(self):
        """日期格式为 M/D。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        # start_date=2026-05-26 → 5/26
        assert "5/26" in reply

    def test_reply_contains_duration_days(self):
        """每个阶段包含天数。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        assert "30天" in reply
        assert "60天" in reply

    def test_reply_contains_stage_emoji(self):
        """包含阶段规划标题 emoji。"""
        cycle = _make_cycle()
        reply = _create_cycle_mod._format_reply(cycle)
        assert "📋" in reply
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/skills/test_create_crop_cycle.py::TestCropCycleFormatReply -v`
Expected: FAIL

- [ ] **Step 3: 重写 `_format_reply` 函数**

在 `backend/app/agent/skills/create-crop-cycle/scripts/main.py` 中，将 `_format_reply` 函数（第 123-133 行）替换为：

```python
def _format_date_m_d(date_val) -> str:
    """将 date 对象或字符串转为 M/D 格式。"""
    from datetime import date as date_type

    if isinstance(date_val, str):
        parts = date_val.split("-")
        return f"{int(parts[1])}/{int(parts[2])}"
    if isinstance(date_val, date_type):
        return f"{date_val.month}/{date_val.day}"
    return str(date_val)


def _format_reply(cycle) -> str:
    """格式化成功回复，使用 emoji + 有序列表展示阶段。"""
    sorted_stages = sorted(cycle.stages, key=lambda s: s.order_index)
    stage_lines = [
        f"{i+1}. {s.name}（{_format_date_m_d(s.start_date)} ~ "
        f"{_format_date_m_d(s.end_date)}，{s.duration_days}天）"
        for i, s in enumerate(sorted_stages)
    ]
    stages_text = "\n".join(stage_lines)
    return (
        f"✅ 茬口「{cycle.name}」已创建！\n\n"
        f"📋 **阶段规划**\n{stages_text}"
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/skills/test_create_crop_cycle.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/skills/create-crop-cycle/scripts/main.py backend/tests/skills/test_create_crop_cycle.py
git commit -m "feat: crop cycle creation reply uses emoji and ordered list"
```

---

### Task 5: 作物模板创建结果格式化

**Files:**
- Modify: `backend/app/agent/skills/create-crop-template/scripts/main.py:89-93`（成功回复生成）
- Modify: `backend/tests/skills/test_create_crop_template.py`（如果存在）

- [ ] **Step 1: 修改作物模板成功回复为 emoji + 有序列表**

在 `backend/app/agent/skills/create-crop-template/scripts/main.py` 中，将第 89-93 行：

```python
            stage_lines = [
                f"  {s.name}（{s.duration_days}天）{s.key_tasks or ''}"
                for s in sorted(created.stages, key=lambda s: s.order_index)
            ]
            reply = f"已创建{crop_name}模板，生长阶段：\n" + "\n".join(stage_lines)
```

替换为：

```python
            stage_lines = [
                f"{i+1}. {s.name}（{s.duration_days}天）"
                + (f"— {s.key_tasks}" if s.key_tasks else "")
                for i, s in enumerate(sorted(created.stages, key=lambda s: s.order_index))
            ]
            stages_text = "\n".join(stage_lines)
            reply = f"✅ {crop_name}模板已创建！\n\n📋 **生长阶段**\n{stages_text}"
```

同时将已存在模板的回复（第 70-72 行）也加上 emoji：

```python
                return SkillResult(
                    status=ResultStatus.SUCCESS,
                    reply=f"📋 {crop_name}模板已存在，阶段：{stage_names}。可以直接建茬口了。",
                )
```

- [ ] **Step 2: 运行既有测试确认无回归**

Run: `cd backend && python -m pytest tests/ -v -k "crop_template or create_crop_template" 2>/dev/null; echo "exit: $?"`
Expected: 无测试失败（如果无相关测试则 exit 0）

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/skills/create-crop-template/scripts/main.py
git commit -m "feat: crop template creation reply uses emoji and ordered list"
```

---

### Task 6: 记账成功回复格式化

**Files:**
- Modify: `backend/app/agent/skills/create-cost-record/scripts/main.py:129-139`（`_format_reply` 方法）
- Modify: `backend/tests/skills/test_create_cost_record.py`

- [ ] **Step 1: 编写记账格式化失败测试**

在 `backend/tests/skills/test_create_cost_record.py` 中新增测试类：

```python
class TestCostRecordFormatReply:
    """验证记账回复使用 emoji + Markdown 格式。"""

    def test_reply_starts_with_money_emoji(self):
        """回复以 💰 开头。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert reply.startswith("💰")

    def test_reply_contains_bold_category(self):
        """回复包含加粗分类。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "**化肥**" in reply

    def test_reply_contains_amount(self):
        """回复包含金额。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "200元" in reply

    def test_income_reply_shows_income_label(self):
        """收入记录显示「收入」标签。"""
        record = MagicMock(
            record_type="income",
            category="番茄销售",
            amount=Decimal("5000"),
            record_date=date(2026, 5, 26),
            note=None,
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "收入" in reply

    def test_debt_reply_shows_debt_label(self):
        """赊账记录显示「赊账」标签。"""
        record = MagicMock(
            record_type="cost",
            category="大棚膜",
            amount=Decimal("3000"),
            record_date=date(2026, 5, 26),
            note="赊账-农资店老王",
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "赊账" in reply

    def test_reply_contains_note_when_present(self):
        """有备注时显示备注。"""
        record = MagicMock(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date(2026, 5, 25),
            note="赊账-农资店老王",
        )
        reply = CreateCostRecordSkill._format_reply(record)
        assert "农资店老王" in reply
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/skills/test_create_cost_record.py::TestCostRecordFormatReply -v`
Expected: FAIL

- [ ] **Step 3: 重写 `_format_reply` 方法**

在 `backend/app/agent/skills/create-cost-record/scripts/main.py` 中，将 `_format_reply` 方法（第 129-139 行）替换为：

```python
    @staticmethod
    def _format_reply(record) -> str:
        """格式化成功回复消息。"""
        type_label = "收入" if record.record_type == "income" else "支出"
        lines = [f"💰 已记账：**{record.category}** {record.amount}元（{type_label}）"]
        if record.note:
            if "赊账" in record.note:
                lines.append(f"📝 {record.note}")
            else:
                lines.append(f"📝 备注：{record.note}")
        lines.append(f"📅 {record.record_date}")
        return "\n".join(lines)
```

- [ ] **Step 4: 更新既有测试的断言**

在 `backend/tests/skills/test_create_cost_record.py` 中，`TestCreateCostRecordNormal` 的 `test_basic_cost_record` 断言不变（仍然检查 "化肥" 和 "200"），`test_income_record` 断言不变（检查 "收入" 和 "5000"），`test_debt_record_with_counterparty` 断言不变（检查 "大棚膜"、"3000"、"赊账"）。

这些测试的断言是子串匹配，新格式仍包含这些子串，所以不需要修改。

- [ ] **Step 5: 运行全部记账测试确认通过**

Run: `cd backend && python -m pytest tests/skills/test_create_cost_record.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/skills/create-cost-record/scripts/main.py backend/tests/skills/test_create_cost_record.py
git commit -m "feat: cost record reply uses emoji and bold formatting"
```

---

### Task 7: 全量回归测试

**Files:** 无新文件

- [ ] **Step 1: 运行全量后端测试**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 2: 检查 graph 集成测试中的确认文案断言**

Run: `cd backend && python -m pytest tests/test_pending_actions.py::TestGraphToolNodeIntegration -v`
Expected: PASS（`test_write_skill_intercepted` 检查 "确认" 或 "记录" 是否在 content 中，新格式仍包含 "确认"）

- [ ] **Step 3: 最终 Commit（如有 lint 修复）**

```bash
cd backend && ruff check . && ruff format .
git add -A
git commit -m "chore: lint fixes for output format polish"
```

---

## 自查清单

### 1. Spec 覆盖

| Spec 需求 | 对应 Task |
|-----------|----------|
| 天气预报 Markdown 表格 + emoji + 3天 | Task 2 |
| 天气预警 ⚠️ 附加 | Task 2 |
| 天气无数据友好提示 | Task 2 |
| 记账确认 emoji + 可读参数（6个 skill） | Task 3 |
| 茬口创建结果 ✅ + 有序列表 | Task 4 |
| Prompt 【回复风格】段落 | Task 1 |
| 作物模板创建结果 emoji + 有序列表 | Task 5 |
| 记账成功回复 emoji + 加粗 | Task 6 |

### 2. Placeholder 扫描

无 TBD、TODO、"implement later" 等占位符。每步都包含完整代码。

### 3. 类型一致性

- `_format_weather_reply(location: str, data: dict) -> str` — Task 2 定义，测试通过 `_build_weather_reply` 间接调用
- `_format_reply(cycle) -> str` — Task 4 定义，返回格式一致
- `build_confirm_message(skill_name: str, params: dict) -> str` — Task 3 定义，签名不变
- `CreateCostRecordSkill._format_reply(record) -> str` — Task 6 定义，签名不变
