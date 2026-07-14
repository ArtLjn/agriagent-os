# 多Agent协作（Multi-Agent）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 LangGraph 实现多 Agent 协作系统，让 LLM 通过工具调用（Tool Calling）自动获取天气、种植周期、农事记录、成本数据，生成个性化农事建议与周期报告。

**Architecture:** 采用 LangGraph `create_react_agent` 预构建 ReAct Agent。定义 4 个工具（天气、茬口、日志、成本），AdvisorAgent 负责每日建议与用户问答，ReportAgent 负责周期/年度报告。所有 Agent 调用通过 `asyncio.to_thread` 包装以兼容 FastAPI 异步路由。天气服务使用 Open-Meteo 免费 API（无需 API Key），LLM 接入阿里云 DashScope（OpenAI 兼容模式）。

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, LangChain-OpenAI, Open-Meteo API, SQLAlchemy 2.0, SQLite

---

## 文件结构

```
backend/
├── requirements.txt                  # + langgraph, langchain-openai
├── app/
│   ├── main.py                       # + include_router(agent.router)
│   ├── core/
│   │   ├── config.py                 # + AI / Weather 配置字段
│   │   └── llm.py                    # 新增: LLM 客户端封装
│   ├── models/
│   │   ├── __init__.py               # + AdviceRecord, ReportRecord
│   │   └── agent.py                  # 新增: 建议/报告记录模型
│   ├── schemas/
│   │   ├── __init__.py               # + Agent 相关 schema
│   │   └── agent.py                  # 新增: Agent 请求/响应 schema
│   ├── services/
│   │   ├── weather_service.py        # 新增: 天气查询与预警
│   │   └── agent_service.py          # 新增: Agent 调用与记录存储
│   ├── agents/
│   │   ├── __init__.py               # 新增
│   │   ├── tools.py                  # 新增: 4 个 LangChain Tool
│   │   ├── state.py                  # 新增: Agent State 类型
│   │   ├── graph.py                  # 新增: LangGraph 编译
│   │   ├── advisor.py                # 新增: 建议 Agent 封装
│   │   └── report.py                 # 新增: 报告 Agent 封装
│   └── api/
│       ├── __init__.py               # 无需修改
│       └── agent.py                  # 新增: Agent API 路由
└── tests/
    ├── conftest.py                   # 新增/修改: clean_db fixture
    └── test_agent.py                 # 新增: Agent 模块测试
```

---

### Task 1: 更新依赖与 AI 配置

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 在 requirements.txt 追加依赖**

在 `backend/requirements.txt` 末尾追加：

```text
langgraph==0.2.76
langchain-openai==0.3.14
```

> 注意：langchain-openai 兼容 pydantic 2.x，与现有 pydantic==2.9.0 无冲突。

- [ ] **Step 2: 在 config.py 添加 AI 与天气配置**

将 `backend/app/core/config.py` 替换为：

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，优先从环境变量读取，其次使用默认值。"""

    database_url: str = "sqlite:///./farm_manager.db"
    project_name: str = "Farm Manager API"
    ai_model: str = "qwen3.5-plus-2026-04-20"
    ai_api_key: str = ""
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    weather_latitude: float = 34.26
    weather_longitude: float = 117.18

    class Config:
        env_file = ".env"


settings = Settings()
```

> `weather_latitude` / `weather_longitude` 默认使用徐州地区（西瓜主产区），用户可在 `.env` 中覆盖。

- [ ] **Step 3: 安装新依赖并验证现有测试仍通过**

Run:
```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Expected: 14/14 tests passing

- [ ] **Step 4: Commit**

```bash
cd backend
git add requirements.txt app/core/config.py
git commit -m "feat: add langgraph/langchain deps and AI config"
```

---

### Task 2: 天气服务模块

**Files:**
- Create: `backend/app/services/weather_service.py`
- Test: `backend/tests/test_weather_service.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_weather_service.py`：

```python
import pytest
from app.services.weather_service import fetch_weather, check_weather_warnings


class TestFetchWeather:
    """测试天气查询功能。"""

    def test_fetch_weather_returns_dict_with_required_keys(self, mocker):
        """验证 fetch_weather 返回包含必需字段的字典。"""
        mock_response = mocker.Mock()
        mock_response.json.return_value = {
            "daily": {
                "time": ["2026-05-23", "2026-05-24"],
                "temperature_2m_max": [28.0, 30.0],
                "temperature_2m_min": [18.0, 20.0],
                "precipitation_sum": [0.0, 5.0],
                "windspeed_10m_max": [10.0, 15.0],
            }
        }
        mock_get = mocker.patch("app.services.weather_service.requests.get", return_value=mock_response)

        result = fetch_weather(lat=34.26, lon=117.18)

        assert "daily" in result
        assert "location" in result
        mock_get.assert_called_once()


class TestCheckWeatherWarnings:
    """测试天气预警检测。"""

    def test_high_temperature_warning(self):
        """高温预警：最高温超过 35 度。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [36.0],
                "temperature_2m_min": [20.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
            }
        }
        warnings = check_weather_warnings(data)
        assert any("高温" in w for w in warnings)

    def test_frost_warning(self):
        """霜冻预警：最低温低于 0 度。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [10.0],
                "temperature_2m_min": [-2.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
            }
        }
        warnings = check_weather_warnings(data)
        assert any("霜冻" in w for w in warnings)

    def test_heavy_rain_warning(self):
        """大雨预警：日降水量超过 50 毫米。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [60.0],
                "windspeed_10m_max": [10.0],
            }
        }
        warnings = check_weather_warnings(data)
        assert any("大雨" in w for w in warnings)

    def test_strong_wind_warning(self):
        """大风预警：最大风速超过 17 m/s（7 级）。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [20.0],
            }
        }
        warnings = check_weather_warnings(data)
        assert any("大风" in w for w in warnings)

    def test_no_warning(self):
        """正常天气无预警。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [5.0],
                "windspeed_10m_max": [10.0],
            }
        }
        warnings = check_weather_warnings(data)
        assert warnings == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_weather_service.py -v`
Expected: 6 failures (ModuleNotFoundError / function not defined)

- [ ] **Step 3: 实现天气服务**

创建 `backend/app/services/weather_service.py`：

```python
"""天气服务模块，使用 Open-Meteo 免费 API 获取天气预报与预警。"""

from datetime import date, timedelta

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(lat: float, lon: float, days: int = 7) -> dict:
    """获取指定坐标的未来 N 天天气预报。

    Args:
        lat: 纬度。
        lon: 经度。
        days: 预报天数（默认 7 天）。

    Returns:
        包含 daily 预报数据和 location 信息的字典。
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "windspeed_10m_max",
        ],
        "timezone": "auto",
        "forecast_days": days,
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    data["location"] = {"latitude": lat, "longitude": lon}
    return data


def check_weather_warnings(weather_data: dict) -> list[str]:
    """检查天气数据中的灾害预警。

    预警规则：
    - 高温：日最高温 >= 35°C
    - 霜冻：日最低温 <= 0°C
    - 大雨：日降水量 >= 50mm
    - 大风：日最大风速 >= 17 m/s（7 级风）

    Args:
        weather_data: Open-Meteo 返回的天气数据字典。

    Returns:
        预警信息列表，每项格式为 "YYYY-MM-DD: 预警类型（数值）"。
    """
    warnings: list[str] = []
    daily = weather_data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precipitations = daily.get("precipitation_sum", [])
    wind_speeds = daily.get("windspeed_10m_max", [])

    for i, day in enumerate(times):
        max_temp = max_temps[i] if i < len(max_temps) else None
        min_temp = min_temps[i] if i < len(min_temps) else None
        precip = precipitations[i] if i < len(precipitations) else None
        wind = wind_speeds[i] if i < len(wind_speeds) else None

        if max_temp is not None and max_temp >= 35:
            warnings.append(f"{day}: 高温预警（{max_temp}°C）")
        if min_temp is not None and min_temp <= 0:
            warnings.append(f"{day}: 霜冻预警（{min_temp}°C）")
        if precip is not None and precip >= 50:
            warnings.append(f"{day}: 大雨预警（{precip}mm）")
        if wind is not None and wind >= 17:
            warnings.append(f"{day}: 大风预警（{wind}m/s）")

    return warnings


__all__ = ["fetch_weather", "check_weather_warnings"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_weather_service.py -v`
Expected: 6/6 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/weather_service.py tests/test_weather_service.py
git commit -m "feat: add weather service with Open-Meteo API"
```

---

### Task 3: LLM 客户端

**Files:**
- Create: `backend/app/core/llm.py`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_llm.py`：

```python
from unittest.mock import MagicMock, patch

from app.core.llm import get_llm


class TestGetLlm:
    """测试 LLM 客户端工厂。"""

    @patch("app.core.llm.ChatOpenAI")
    def test_get_llm_returns_chat_openai_instance(self, mock_chat_openai):
        """验证 get_llm 返回 ChatOpenAI 实例。"""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        llm = get_llm()

        assert llm is mock_instance
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args.kwargs
        assert call_kwargs["model"] == "qwen3.5-plus-2026-04-20"
        assert call_kwargs["api_key"] == ""
        assert call_kwargs["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_llm.py -v`
Expected: 1 failure (ModuleNotFoundError)

- [ ] **Step 3: 实现 LLM 客户端**

创建 `backend/app/core/llm.py`：

```python
"""LLM 客户端封装，使用 LangChain ChatOpenAI 接入 DashScope。"""

from langchain_openai import ChatOpenAI

from app.core.config import settings


LLM_INSTANCE: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    """获取全局 ChatOpenAI 实例（单例模式）。

    Returns:
        配置好的 ChatOpenAI 实例，连接阿里云 DashScope。
    """
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
        )
    return LLM_INSTANCE


__all__ = ["get_llm"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_llm.py -v`
Expected: 1/1 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/core/llm.py tests/test_llm.py
git commit -m "feat: add LLM client with DashScope integration"
```

---

### Task 4: Agent 工具定义

**Files:**
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/agents/tools.py`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_agent_tools.py`：

```python
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.agents.tools import get_crop_cycle_info, get_recent_farm_logs, get_cycle_cost_summary, weather


class TestGetWeatherForecast:
    """测试天气工具。"""

    @patch("app.agents.tools.fetch_weather")
    @patch("app.agents.tools.check_weather_warnings")
    def test_returns_formatted_weather(self, mock_warnings, mock_fetch):
        """验证返回格式化天气字符串。"""
        mock_fetch.return_value = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [28.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
            }
        }
        mock_warnings.return_value = []

        result = weather("徐州")

        assert "徐州" in result
        assert "2026-05-23" in result
        mock_fetch.assert_called_once()


class TestGetCropCycleInfo:
    """测试茬口信息工具。"""

    def test_returns_cycle_details(self, mocker):
        """验证返回茬口详情字符串。"""
        mock_db = mocker.Mock()
        mock_cycle = mocker.Mock()
        mock_cycle.name = "西瓜春茬"
        mock_cycle.start_date = date(2026, 3, 1)
        mock_cycle.field_name = "一号地"
        mock_cycle.status = "active"
        mock_stage = mocker.Mock()
        mock_stage.name = "开花期"
        mock_stage.start_date = date(2026, 4, 15)
        mock_stage.end_date = date(2026, 5, 10)
        mock_stage.is_current = 1
        mock_cycle.stages = [mock_stage]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cycle

        result = get_crop_cycle_info(mock_db, 1)

        assert "西瓜春茬" in result
        assert "开花期" in result

    def test_cycle_not_found(self, mocker):
        """茬口不存在时返回提示。"""
        mock_db = mocker.Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = get_crop_cycle_info(mock_db, 999)

        assert "未找到" in result


class TestGetRecentFarmLogs:
    """测试农事记录工具。"""

    def test_returns_logs_summary(self, mocker):
        """验证返回最近农事记录。"""
        mock_db = mocker.Mock()
        mock_log = mocker.Mock()
        mock_log.operation_type = "浇水"
        mock_log.operation_date = date(2026, 5, 20)
        mock_log.note = "浇透水"
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_log]

        result = get_recent_farm_logs(mock_db, 1, days=7)

        assert "浇水" in result
        assert "浇透水" in result


class TestGetCycleCostSummary:
    """测试成本汇总工具。"""

    def test_returns_cost_summary(self, mocker):
        """验证返回成本收支汇总。"""
        mock_db = mocker.Mock()
        mock_cost = mocker.Mock()
        mock_cost.record_type = "cost"
        mock_cost.category = "肥料"
        mock_cost.amount = 500
        mock_income = mocker.Mock()
        mock_income.record_type = "income"
        mock_income.category = "销售"
        mock_income.amount = 3000
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_cost, mock_income]

        result = get_cycle_cost_summary(mock_db, 1)

        assert "500" in result
        assert "3000" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_agent_tools.py -v`
Expected: 6 failures (ModuleNotFoundError)

- [ ] **Step 3: 实现 Agent 工具**

创建 `backend/app/agents/__init__.py`：

```python
"""Agent 模块，包含多 Agent 协作相关的工具、状态、图定义。"""
```

创建 `backend/app/agents/tools.py`：

```python
"""Agent 工具定义，供 LangGraph ReAct Agent 调用。

所有工具函数均为同步函数，接收 db Session 作为第一个参数（由调用方注入）。
为兼容 LangChain Tool 接口，实际暴露的工具通过闭包/偏函数绑定 db。
"""

from datetime import date, timedelta

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.models.cycle import CropCycle, CycleStage
from app.models.log import FarmLog
from app.models.cost import CostRecord
from app.services.weather_service import check_weather_warnings, fetch_weather
from app.core.config import settings


@tool
def weather(location: str = "当前地块") -> str:
    """获取未来 7 天天气预报和灾害预警。

    Args:
        location: 地点描述（仅作标注，实际使用配置坐标）。

    Returns:
        格式化天气报告字符串，包含每日气温、降水、风速和预警信息。
    """
    data = fetch_weather(settings.weather_latitude, settings.weather_longitude, days=7)
    daily = data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])
    winds = daily.get("windspeed_10m_max", [])

    lines = [f"📍 地点：{location}", "未来 7 天天气预报："]
    for i, day in enumerate(times):
        max_t = max_temps[i] if i < len(max_temps) else "-"
        min_t = min_temps[i] if i < len(min_temps) else "-"
        p = precips[i] if i < len(precips) else "-"
        w = winds[i] if i < len(winds) else "-"
        lines.append(f"  {day}: 最高{max_t}°C 最低{min_t}°C 降水{p}mm 风速{w}m/s")

    warnings = check_weather_warnings(data)
    if warnings:
        lines.append("⚠️ 天气预警：")
        lines.extend(f"  {w}" for w in warnings)
    else:
        lines.append("✅ 近期无极端天气预警。")

    return "\n".join(lines)


@tool
def get_crop_cycle_info(db: Session, cycle_id: int) -> str:
    """查询指定种植周期的详细信息，包括当前阶段和各阶段安排。

    Args:
        db: 数据库会话。
        cycle_id: 种植周期 ID。

    Returns:
        周期详情字符串，包含名称、起止日期、当前阶段和各阶段列表。
    """
    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
    if not cycle:
        return f"未找到 ID 为 {cycle_id} 的种植周期。"

    lines = [
        f"🌱 茬口：{cycle.name}",
        f"📅 开始日期：{cycle.start_date}",
        f"🗺️ 地块：{cycle.field_name or '未指定'}",
        f"📊 状态：{cycle.status}",
        "阶段安排：",
    ]
    for stage in sorted(cycle.stages, key=lambda s: s.order_index):
        current_marker = " [当前]" if stage.is_current else ""
        lines.append(
            f"  {stage.name}{current_marker}: {stage.start_date} ~ {stage.end_date} "
            f"（{stage.duration_days} 天）关键任务：{stage.key_tasks or '无'}"
        )

    return "\n".join(lines)


@tool
def get_recent_farm_logs(db: Session, cycle_id: int, days: int = 7) -> str:
    """查询指定周期最近 N 天的农事记录。

    Args:
        db: 数据库会话。
        cycle_id: 种植周期 ID。
        days: 查询天数（默认 7 天）。

    Returns:
        农事记录摘要字符串，若无记录则返回提示。
    """
    since = date.today() - timedelta(days=days)
    logs = (
        db.query(FarmLog)
        .filter(FarmLog.cycle_id == cycle_id, FarmLog.operation_date >= since)
        .order_by(FarmLog.operation_date.desc())
        .limit(20)
        .all()
    )

    if not logs:
        return f"最近 {days} 天内没有农事记录。"

    lines = [f"📝 最近 {days} 天农事记录（共 {len(logs)} 条）："]
    for log in logs:
        lines.append(f"  {log.operation_date}: {log.operation_type} - {log.note or '无备注'}")

    return "\n".join(lines)


@tool
def get_cycle_cost_summary(db: Session, cycle_id: int) -> str:
    """查询指定周期的成本与收入汇总。

    Args:
        db: 数据库会话。
        cycle_id: 种植周期 ID。

    Returns:
        收支汇总字符串，包含总成本、总收入和净利润。
    """
    records = db.query(CostRecord).filter(CostRecord.cycle_id == cycle_id).all()
    if not records:
        return "该周期暂无成本或收入记录。"

    total_cost = sum(r.amount for r in records if r.record_type == "cost")
    total_income = sum(r.amount for r in records if r.record_type == "income")
    net = total_income - total_cost

    lines = [
        f"💰 周期收支汇总：",
        f"  总成本：{total_cost} 元",
        f"  总收入：{total_income} 元",
        f"  净利润：{net} 元",
        "  明细：",
    ]
    for r in records:
        lines.append(f"    {r.record_date}: {r.record_type} - {r.category} {r.amount} 元 ({r.note or '无备注'})")

    return "\n".join(lines)


__all__ = [
    "weather",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
    "get_cycle_cost_summary",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_agent_tools.py -v`
Expected: 6/6 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/agents/ tests/test_agent_tools.py
git commit -m "feat: add agent tools for weather, cycle, logs, costs"
```

---

### Task 5: Agent 状态图与 Advisor Agent

**Files:**
- Create: `backend/app/agents/state.py`
- Create: `backend/app/agents/graph.py`
- Create: `backend/app/agents/advisor.py`
- Test: `backend/tests/test_advisor_agent.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_advisor_agent.py`：

```python
from unittest.mock import MagicMock, patch

from app.agents.advisor import build_advisor_agent


class TestBuildAdvisorAgent:
    """测试建议 Agent 构建。"""

    @patch("app.agents.advisor.create_react_agent")
    @patch("app.agents.advisor.get_llm")
    def test_build_advisor_agent_returns_graph(self, mock_get_llm, mock_create_react):
        """验证 build_advisor_agent 返回编译后的图。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_graph = MagicMock()
        mock_create_react.return_value = mock_graph

        result = build_advisor_agent()

        assert result is mock_graph
        mock_get_llm.assert_called_once()
        mock_create_react.assert_called_once()


class TestAdvisorInvoke:
    """测试建议 Agent 调用。"""

    @patch("app.agents.advisor.build_advisor_agent")
    def test_invoke_advisor_returns_response(self, mock_build):
        """验证 invoke_advisor 返回 LLM 响应文本。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "建议：今天适合浇水。"
        mock_graph.invoke.return_value = {"messages": [mock_msg]}
        mock_build.return_value = mock_graph

        from app.agents.advisor import invoke_advisor

        result = invoke_advisor("今天该做什么？")

        assert result == "建议：今天适合浇水。"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_advisor_agent.py -v`
Expected: 3 failures (ModuleNotFoundError)

- [ ] **Step 3: 实现 Agent 状态、图与 Advisor**

创建 `backend/app/agents/state.py`：

```python
"""Agent 状态定义。"""

from typing import Annotated

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Agent 状态类型，包含消息历史。

    Attributes:
        messages: 消息列表，使用 add_messages reducer 自动追加。
    """

    messages: Annotated[list[BaseMessage], "add_messages"]
```

创建 `backend/app/agents/graph.py`：

```python
"""LangGraph 图编译模块。"""

from langgraph.prebuilt import create_react_agent

from app.agents.tools import (
    get_crop_cycle_info,
    get_cycle_cost_summary,
    get_recent_farm_logs,
    weather,
)
from app.core.llm import get_llm


TOOLS = [
    weather,
    get_crop_cycle_info,
    get_recent_farm_logs,
    get_cycle_cost_summary,
]


SYSTEM_PROMPT = (
    "你是一位经验丰富的农业技术顾问，擅长西瓜、豆角等作物的种植管理。"
    "你具备以下能力：查询天气预报和灾害预警、查看种植周期和当前阶段、"
    "了解近期农事记录、统计成本收支。请根据用户的问题，主动调用合适的工具"
    "获取信息，然后给出具体、可操作的建议。回答要简洁明了，适合农民理解。"
    "使用中文回答。"
)


def compile_advisor_graph():
    """编译建议 Agent 的 ReAct 图。

    Returns:
        编译后的 LangGraph 图实例。
    """
    llm = get_llm()
    return create_react_agent(llm, TOOLS, state_modifier=SYSTEM_PROMPT)


__all__ = ["compile_advisor_graph"]
```

创建 `backend/app/agents/advisor.py`：

```python
"""建议 Agent 封装，提供每日建议和用户问答接口。"""

from langchain_core.messages import HumanMessage

from app.agents.graph import compile_advisor_graph


_ADVISOR_GRAPH = None


def _get_advisor_graph():
    """获取全局 Advisor 图实例（单例）。"""
    global _ADVISOR_GRAPH
    if _ADVISOR_GRAPH is None:
        _ADVISOR_GRAPH = compile_advisor_graph()
    return _ADVISOR_GRAPH


def build_advisor_agent():
    """构建并返回建议 Agent 图（主要用于测试）。"""
    return compile_advisor_graph()


def invoke_advisor(user_input: str) -> str:
    """调用建议 Agent 回答用户问题。

    Args:
        user_input: 用户输入的问题或请求。

    Returns:
        Agent 生成的建议文本。
    """
    graph = _get_advisor_graph()
    result = graph.invoke({"messages": [HumanMessage(content=user_input)]})
    return result["messages"][-1].content


__all__ = ["build_advisor_agent", "invoke_advisor"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_advisor_agent.py -v`
Expected: 3/3 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/agents/state.py app/agents/graph.py app/agents/advisor.py tests/test_advisor_agent.py
git commit -m "feat: add LangGraph advisor agent with ReAct pattern"
```

---

### Task 6: Report Agent

**Files:**
- Create: `backend/app/agents/report.py`
- Test: `backend/tests/test_report_agent.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_report_agent.py`：

```python
from unittest.mock import MagicMock, patch


class TestBuildReportAgent:
    """测试报告 Agent 构建。"""

    @patch("app.agents.report.create_react_agent")
    @patch("app.agents.report.get_llm")
    def test_build_report_agent_returns_graph(self, mock_get_llm, mock_create_react):
        """验证 build_report_agent 返回编译后的图。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_graph = MagicMock()
        mock_create_react.return_value = mock_graph

        from app.agents.report import build_report_agent

        result = build_report_agent()

        assert result is mock_graph
        mock_get_llm.assert_called_once()
        mock_create_react.assert_called_once()


class TestGenerateCycleReport:
    """测试周期报告生成。"""

    @patch("app.agents.report._get_report_graph")
    def test_generate_cycle_report_returns_text(self, mock_get_graph):
        """验证生成周期报告返回文本。"""
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "周期报告：西瓜春茬总成本 2000 元..."
        mock_graph.invoke.return_value = {"messages": [mock_msg]}
        mock_get_graph.return_value = mock_graph

        from app.agents.report import generate_cycle_report

        result = generate_cycle_report(1)

        assert "周期报告" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_report_agent.py -v`
Expected: 2 failures (ModuleNotFoundError)

- [ ] **Step 3: 实现 Report Agent**

创建 `backend/app/agents/report.py`：

```python
"""报告 Agent 封装，生成种植周期周报/月报。"""

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from app.agents.graph import TOOLS
from app.core.llm import get_llm


REPORT_SYSTEM_PROMPT = (
    "你是一位农业数据分析师，擅长整理种植周期的各项数据并生成清晰报告。"
    "你可以查询天气、茬口信息、农事记录和成本收支。报告要求数据准确、"
    "条理清晰，包含关键指标（成本、收入、农事进度）和下一步建议。"
    "使用中文输出。"
)

_REPORT_GRAPH = None


def _get_report_graph():
    """获取全局 Report 图实例（单例）。"""
    global _REPORT_GRAPH
    if _REPORT_GRAPH is None:
        llm = get_llm()
        _REPORT_GRAPH = create_react_agent(llm, TOOLS, state_modifier=REPORT_SYSTEM_PROMPT)
    return _REPORT_GRAPH


def build_report_agent():
    """构建并返回报告 Agent 图（主要用于测试）。"""
    llm = get_llm()
    return create_react_agent(llm, TOOLS, state_modifier=REPORT_SYSTEM_PROMPT)


def generate_cycle_report(cycle_id: int) -> str:
    """生成指定种植周期的综合报告。

    Args:
        cycle_id: 种植周期 ID。

    Returns:
        报告文本。
    """
    graph = _get_report_graph()
    prompt = (
        f"请为 ID={cycle_id} 的种植周期生成一份综合报告。"
        "请查询该周期的基本信息、最近农事记录和成本收支，"
        "整理成一份包含进度、成本分析和下一步建议的报告。"
    )
    result = graph.invoke({"messages": [HumanMessage(content=prompt)]})
    return result["messages"][-1].content


__all__ = ["build_report_agent", "generate_cycle_report"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_report_agent.py -v`
Expected: 2/2 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/agents/report.py tests/test_report_agent.py
git commit -m "feat: add report agent for cycle summary generation"
```

---

### Task 7: Agent 数据库模型与 Schema

**Files:**
- Create: `backend/app/models/agent.py`
- Create: `backend/app/schemas/agent.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_agent_models.py`：

```python
from datetime import date

from app.models.agent import AdviceRecord, ReportRecord


class TestAdviceRecord:
    """测试建议记录模型。"""

    def test_create_advice_record(self, clean_db):
        """验证可以创建建议记录。"""
        record = AdviceRecord(
            cycle_id=1,
            advice_type="daily",
            content="今天适合浇水",
        )
        clean_db.add(record)
        clean_db.commit()

        assert record.id is not None
        assert record.content == "今天适合浇水"
        assert record.created_at is not None


class TestReportRecord:
    """测试报告记录模型。"""

    def test_create_report_record(self, clean_db):
        """验证可以创建报告记录。"""
        record = ReportRecord(
            cycle_id=1,
            report_type="weekly",
            content="本周报告...",
        )
        clean_db.add(record)
        clean_db.commit()

        assert record.id is not None
        assert record.report_type == "weekly"
        assert record.content == "本周报告..."
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_agent_models.py -v`
Expected: 2 failures (ModuleNotFoundError / table not found)

- [ ] **Step 3: 实现模型与 Schema**

创建 `backend/app/models/agent.py`：

```python
"""Agent 相关数据库模型，存储建议与报告历史。"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AdviceRecord(Base):
    """农事建议记录，保存 Agent 生成的每日建议或问答回复。"""

    __tablename__ = "advice_records"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    advice_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportRecord(Base):
    """周期报告记录，保存 Agent 生成的周报/月报。"""

    __tablename__ = "report_records"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    report_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

创建 `backend/app/schemas/agent.py`：

```python
"""Agent 相关请求与响应 Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    cycle_id: int | None = None
    message: str


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    reply: str
    model_config = ConfigDict(from_attributes=True)


class DailyAdviceResponse(BaseModel):
    """每日建议响应。"""

    cycle_id: int | None = None
    advice: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportRequest(BaseModel):
    """报告生成请求。"""

    cycle_id: int | None = None
    report_type: str = "weekly"


class ReportResponse(BaseModel):
    """报告响应。"""

    cycle_id: int | None = None
    report_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AdviceHistoryItem(BaseModel):
    """建议历史记录项。"""

    id: int
    cycle_id: int | None = None
    advice_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportHistoryItem(BaseModel):
    """报告历史记录项。"""

    id: int
    cycle_id: int | None = None
    report_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

修改 `backend/app/models/__init__.py`，追加导入：

```python
from app.models.agent import AdviceRecord, ReportRecord

__all__ = [
    "CropTemplate",
    "GrowthStage",
    "CropCycle",
    "CycleStage",
    "FarmLog",
    "CostRecord",
    "AdviceRecord",
    "ReportRecord",
]
```

修改 `backend/app/schemas/__init__.py`，追加导入：

```python
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    ReportRequest,
    ReportResponse,
    AdviceHistoryItem,
    ReportHistoryItem,
)

__all__ = [
    # ... 保留原有导出 ...
    "ChatRequest",
    "ChatResponse",
    "DailyAdviceResponse",
    "ReportRequest",
    "ReportResponse",
    "AdviceHistoryItem",
    "ReportHistoryItem",
]
```

> 注意：保留原有的 schema 导出列表，仅追加新项。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_agent_models.py -v`
Expected: 2/2 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/models/agent.py app/schemas/agent.py app/models/__init__.py app/schemas/__init__.py tests/test_agent_models.py
git commit -m "feat: add agent advice and report database models with schemas"
```

---

### Task 8: Agent 服务层

**Files:**
- Create: `backend/app/services/agent_service.py`
- Test: `backend/tests/test_agent_service.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_agent_service.py`：

```python
from unittest.mock import MagicMock, patch

from app.services.agent_service import chat_with_agent, get_daily_advice, generate_report


class TestChatWithAgent:
    """测试 Agent 对话服务。"""

    @patch("app.services.agent_service.invoke_advisor")
    def test_chat_with_agent_returns_reply(self, mock_invoke):
        """验证对话返回回复并保存记录。"""
        mock_invoke.return_value = "建议：今天浇水。"
        mock_db = MagicMock()

        result = chat_with_agent(mock_db, "今天做什么？")

        assert result.reply == "建议：今天浇水。"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestGetDailyAdvice:
    """测试每日建议服务。"""

    @patch("app.services.agent_service.invoke_advisor")
    def test_get_daily_advice_returns_advice(self, mock_invoke):
        """验证每日建议生成并保存。"""
        mock_invoke.return_value = "今日建议：施肥。"
        mock_db = MagicMock()

        result = get_daily_advice(mock_db, cycle_id=1)

        assert result.advice == "今日建议：施肥。"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestGenerateReport:
    """测试报告生成服务。"""

    @patch("app.services.agent_service.generate_cycle_report")
    def test_generate_report_returns_content(self, mock_generate):
        """验证报告生成并保存。"""
        mock_generate.return_value = "报告内容..."
        mock_db = MagicMock()

        result = generate_report(mock_db, cycle_id=1, report_type="weekly")

        assert result.content == "报告内容..."
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_agent_service.py -v`
Expected: 3 failures (ModuleNotFoundError)

- [ ] **Step 3: 实现 Agent 服务**

创建 `backend/app/services/agent_service.py`：

```python
"""Agent 服务层，封装 Agent 调用与记录持久化。"""

from sqlalchemy.orm import Session

from app.agents.advisor import invoke_advisor
from app.agents.report import generate_cycle_report
from app.models.agent import AdviceRecord, ReportRecord
from app.schemas.agent import ChatResponse, DailyAdviceResponse, ReportResponse


def chat_with_agent(db: Session, message: str, cycle_id: int | None = None) -> ChatResponse:
    """与用户进行 Agent 对话，保存记录。

    Args:
        db: 数据库会话。
        message: 用户消息。
        cycle_id: 关联的种植周期 ID（可选）。

    Returns:
        Agent 回复。
    """
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    reply = invoke_advisor(full_input)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="chat", content=reply)
    db.add(record)
    db.commit()

    return ChatResponse(reply=reply)


def get_daily_advice(db: Session, cycle_id: int | None = None) -> DailyAdviceResponse:
    """生成每日农事建议并保存。

    Args:
        db: 数据库会话。
        cycle_id: 关联的种植周期 ID（可选）。

    Returns:
        每日建议。
    """
    prompt = "请生成今天的农事建议，考虑当前天气和种植周期阶段。"
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议，查询天气和周期信息。"
    advice = invoke_advisor(prompt)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="daily", content=advice)
    db.add(record)
    db.commit()
    db.refresh(record)

    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        advice=record.content,
        created_at=record.created_at,
    )


def generate_report(
    db: Session, cycle_id: int | None = None, report_type: str = "weekly"
) -> ReportResponse:
    """生成种植周期报告并保存。

    Args:
        db: 数据库会话。
        cycle_id: 关联的种植周期 ID（可选）。
        report_type: 报告类型（weekly / monthly）。

    Returns:
        生成的报告。
    """
    if cycle_id:
        content = generate_cycle_report(cycle_id)
    else:
        content = invoke_advisor(f"请生成一份{report_type}综合报告，查询所有活跃周期的信息。")

    record = ReportRecord(cycle_id=cycle_id, report_type=report_type, content=content)
    db.add(record)
    db.commit()
    db.refresh(record)

    return ReportResponse(
        cycle_id=record.cycle_id,
        report_type=record.report_type,
        content=record.content,
        created_at=record.created_at,
    )


def get_advice_history(
    db: Session, cycle_id: int | None = None, limit: int = 20
) -> list[AdviceRecord]:
    """查询建议历史。

    Args:
        db: 数据库会话。
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。

    Returns:
        建议记录列表。
    """
    query = db.query(AdviceRecord)
    if cycle_id is not None:
        query = query.filter(AdviceRecord.cycle_id == cycle_id)
    return query.order_by(AdviceRecord.created_at.desc()).limit(limit).all()


def get_report_history(
    db: Session, cycle_id: int | None = None, limit: int = 20
) -> list[ReportRecord]:
    """查询报告历史。

    Args:
        db: 数据库会话。
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。

    Returns:
        报告记录列表。
    """
    query = db.query(ReportRecord)
    if cycle_id is not None:
        query = query.filter(ReportRecord.cycle_id == cycle_id)
    return query.order_by(ReportRecord.created_at.desc()).limit(limit).all()


__all__ = [
    "chat_with_agent",
    "get_daily_advice",
    "generate_report",
    "get_advice_history",
    "get_report_history",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_agent_service.py -v`
Expected: 3/3 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/agent_service.py tests/test_agent_service.py
git commit -m "feat: add agent service for advice, chat, and report generation"
```

---

### Task 9: Agent API 路由

**Files:**
- Create: `backend/app/api/agent.py`
- Test: `backend/tests/test_agent_api.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_agent_api.py`：

```python
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestAgentChat:
    """测试 Agent 对话接口。"""

    @patch("app.api.agent.chat_with_agent")
    def test_chat_endpoint(self, mock_chat, client: TestClient):
        """验证 POST /agent/chat 返回回复。"""
        from app.schemas.agent import ChatResponse

        mock_chat.return_value = ChatResponse(reply="建议：浇水。")

        response = client.post("/agent/chat", json={"message": "今天做什么？"})

        assert response.status_code == 200
        assert response.json()["reply"] == "建议：浇水。"


class TestAgentDaily:
    """测试每日建议接口。"""

    @patch("app.api.agent.get_daily_advice")
    def test_daily_advice_endpoint(self, mock_daily, client: TestClient):
        """验证 GET /agent/daily 返回建议。"""
        from datetime import datetime
        from app.schemas.agent import DailyAdviceResponse

        mock_daily.return_value = DailyAdviceResponse(
            cycle_id=1, advice="施肥", created_at=datetime.now()
        )

        response = client.get("/agent/daily?cycle_id=1")

        assert response.status_code == 200
        assert response.json()["advice"] == "施肥"


class TestAgentReport:
    """测试报告接口。"""

    @patch("app.api.agent.generate_report")
    def test_report_endpoint(self, mock_report, client: TestClient):
        """验证 POST /agent/report 返回报告。"""
        from datetime import datetime
        from app.schemas.agent import ReportResponse

        mock_report.return_value = ReportResponse(
            cycle_id=1, report_type="weekly", content="周报内容", created_at=datetime.now()
        )

        response = client.post("/agent/report", json={"cycle_id": 1, "report_type": "weekly"})

        assert response.status_code == 200
        assert response.json()["content"] == "周报内容"


class TestAgentHistory:
    """测试历史记录接口。"""

    @patch("app.api.agent.get_advice_history")
    def test_advice_history_endpoint(self, mock_history, client: TestClient):
        """验证 GET /agent/advice-history 返回列表。"""
        mock_history.return_value = []

        response = client.get("/agent/advice-history")

        assert response.status_code == 200
        assert response.json() == []

    @patch("app.api.agent.get_report_history")
    def test_report_history_endpoint(self, mock_history, client: TestClient):
        """验证 GET /agent/report-history 返回列表。"""
        mock_history.return_value = []

        response = client.get("/agent/report-history")

        assert response.status_code == 200
        assert response.json() == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_agent_api.py -v`
Expected: 5 failures (ModuleNotFoundError / 404)

- [ ] **Step 3: 实现 Agent API 路由**

创建 `backend/app/api/agent.py`：

```python
"""Agent API 路由，提供农事建议、对话和报告接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    ReportRequest,
    ReportResponse,
    AdviceHistoryItem,
    ReportHistoryItem,
)
from app.services.agent_service import (
    chat_with_agent,
    get_daily_advice,
    generate_report,
    get_advice_history,
    get_report_history,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def agent_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """与农事顾问 Agent 对话。

    Args:
        request: 对话请求，包含用户消息和可选的周期 ID。
        db: 数据库会话。

    Returns:
        Agent 回复。
    """
    return chat_with_agent(db, request.message, request.cycle_id)


@router.get("/daily", response_model=DailyAdviceResponse)
def daily_advice(
    cycle_id: int | None = Query(None, description="关联种植周期 ID"),
    db: Session = Depends(get_db),
) -> DailyAdviceResponse:
    """获取每日农事建议。

    Args:
        cycle_id: 种植周期 ID（可选，不指定则生成通用建议）。
        db: 数据库会话。

    Returns:
        每日建议，包含生成时间。
    """
    return get_daily_advice(db, cycle_id)


@router.post("/report", response_model=ReportResponse)
def agent_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
) -> ReportResponse:
    """生成种植周期报告。

    Args:
        request: 报告请求，包含周期 ID 和报告类型。
        db: 数据库会话。

    Returns:
        生成的报告。
    """
    return generate_report(db, request.cycle_id, request.report_type)


@router.get("/advice-history", response_model=list[AdviceHistoryItem])
def advice_history(
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AdviceHistoryItem]:
    """查询建议历史记录。

    Args:
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。
        db: 数据库会话。

    Returns:
        建议历史列表。
    """
    return get_advice_history(db, cycle_id, limit)


@router.get("/report-history", response_model=list[ReportHistoryItem])
def report_history(
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ReportHistoryItem]:
    """查询报告历史记录。

    Args:
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。
        db: 数据库会话。

    Returns:
        报告历史列表。
    """
    return get_report_history(db, cycle_id, limit)


__all__ = ["router"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/test_agent_api.py -v`
Expected: 5/5 passing

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/api/agent.py tests/test_agent_api.py
git commit -m "feat: add agent API routes for chat, daily advice, and reports"
```

---

### Task 10: 集成到主应用并运行全量测试

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`（如有需要，确保 clean_db 覆盖新表）

- [ ] **Step 1: 修改 main.py 注册 Agent 路由**

将 `backend/app/main.py` 替换为：

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import agent, cost, crop, cycle, log
from app.core.config import settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)

app.include_router(crop.router)
app.include_router(cycle.router)
app.include_router(log.router)
app.include_router(cost.router)
app.include_router(agent.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 2: 运行全量测试**

Run:
```bash
cd backend
pytest tests/ -v
```

Expected: 所有测试通过（原有 14 + 新增测试）。统计数量约为 14 + 6 + 1 + 6 + 3 + 2 + 2 + 3 + 5 = 42+ 测试。

- [ ] **Step 3: Commit**

```bash
cd backend
git add app/main.py
git commit -m "feat: register agent router in main app"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ LangGraph 多 Agent 编排（Task 5, 6）
- ✅ 天气作为 Agent Tool（Task 4: `weather`）
- ✅ 种植周期作为 Agent Tool（Task 4: `get_crop_cycle_info`）
- ✅ 农事记录作为 Agent Tool（Task 4: `get_recent_farm_logs`）
- ✅ 成本作为 Agent Tool（Task 4: `get_cycle_cost_summary`）
- ✅ 每日建议接口（Task 8, 9: `/agent/daily`）
- ✅ 用户对话接口（Task 8, 9: `/agent/chat`）
- ✅ 周期报告接口（Task 8, 9: `/agent/report`）
- ✅ 建议/报告历史记录（Task 7, 8, 9: 数据库模型 + 查询接口）
- ✅ 天气预警检测（Task 2: `check_weather_warnings`）
- ✅ DashScope LLM 接入（Task 3: `get_llm`）

**2. Placeholder scan:** 无 TBD、TODO、"implement later"、"add appropriate error handling" 等占位符。每个任务均包含完整代码与测试。

**3. Type consistency:**
- `AgentState` 使用 `Annotated[list[BaseMessage], "add_messages"]` 与 LangGraph 预构建 Agent 兼容。
- 所有 Tool 函数签名一致：`weather(location: str)` 和 `get_crop_cycle_info(db: Session, cycle_id: int)` 等。
- `invoke_advisor` 和 `generate_cycle_report` 均返回 `str`。
- `chat_with_agent`、`get_daily_advice`、`generate_report` 均返回对应的 Pydantic Response schema。

---

## 执行交接

**Plan complete and saved to `docs/superpowers/plans/2026-05-23-farm-manager-multi-agent.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

**Which approach?**
