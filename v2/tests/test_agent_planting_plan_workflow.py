from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.core import react
from agent.core.turn import Turn
from agent.infra.trace import collector
from agent.skills import loader
from agent.skills.base import Skill, SkillResult


class _PrepareSkill(Skill):
    """prepare_planting_plan：返回 ready + 指纹 + plan，声明 commit 后继动作。"""

    _meta = {
        "name": "prepare_planting_plan",
        "description": "准备完整种植计划并返回审批摘要，不写入业务实体。",
        "risk_level": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "crop_name": {"type": "string"},
                "total_area_mu": {"type": "number"},
                "field_name": {"type": "string"},
                "start_date": {"type": "string"},
            },
            "required": ["crop_name", "total_area_mu", "field_name", "start_date"],
        },
    }

    # 固定的准备结果，测试用它断言 commit 收到的参数
    prepared_result: dict = {
        "status": "ready",
        "client_request_id": "req-abc-123",
        "approval_fingerprint": "sha256:dummy-fingerprint",
        "plan": {
            "crop_name": "西瓜",
            "template_action": "create_custom",
            "template": {"id": None, "name": "西瓜", "stages": [{"name": "育苗期"}]},
            "cycle": {
                "name": "西瓜种植计划",
                "start_date": "2026-08-10",
                "total_area_mu": 5,
            },
            "planting_unit": {
                "name": "东棚",
                "area_mu": 5,
                "planted_date": "2026-08-10",
            },
        },
        "approval_summary": "将创建自定义模板、1 个西瓜茬口和 1 个 5 亩种植单元。",
    }

    @property
    def approval_followup(self) -> dict | None:
        return {
            "tool_name": "commit_planting_plan",
            "arguments_from_result": [
                "client_request_id",
                "approval_fingerprint",
                "plan",
            ],
        }

    async def execute(self, params: dict, ctx) -> SkillResult:
        return SkillResult(data=dict(self.prepared_result))


class _CommitSkill(Skill):
    """commit_planting_plan：记录收到的参数，返回 committed 或业务错误。

    expose_to_model=false：模型看不到它，只能由 Runtime 在 prepare 审批通过后驱动。
    """

    _meta = {
        "name": "commit_planting_plan",
        "description": "提交用户已批准的完整种植计划。",
        "risk_level": "write_confirm",
        "finalize_after_success": True,
        "parameters": {
            "type": "object",
            "properties": {
                "client_request_id": {"type": "string"},
                "approval_fingerprint": {"type": "string"},
                "plan": {"type": "object"},
            },
            "required": ["client_request_id", "approval_fingerprint", "plan"],
        },
    }

    def __init__(self) -> None:
        self.received_args: dict | None = None
        self.call_count = 0

    @property
    def exposed(self) -> bool:
        return False

    async def execute(self, params: dict, ctx) -> SkillResult:
        self.call_count += 1
        self.received_args = dict(params)
        return SkillResult(
            data={
                "status": "committed",
                "idempotent_replay": False,
                "template": {"id": 12, "name": "西瓜"},
                "cycle": {"id": 31, "name": "西瓜种植计划"},
                "planting_unit": {"id": 44, "name": "东棚", "area_mu": 5.0},
            }
        )


class _BusinessClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass


def _patch_react_runtime(
    monkeypatch: pytest.MonkeyPatch,
    fake_chat_stream,
    prepare_skill: Skill | None = None,
    commit_skill: Skill | None = None,
) -> tuple[Skill, Skill]:
    """注入测试用 prepare/commit skill，保留真实 to_openai_tools 过滤逻辑。"""
    prepare = prepare_skill or _PrepareSkill()
    commit = commit_skill or _CommitSkill()
    monkeypatch.setattr(react, "BusinessClient", _BusinessClient)
    monkeypatch.setattr(react, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(react.skill_loader, "load_all", lambda: [prepare, commit])
    # 不再 patch to_openai_tools，让真实实现按 exposed 过滤（commit 不暴露给模型）
    monkeypatch.setattr(react.memory, "snapshot", lambda conversation_id: {})
    monkeypatch.setattr(react.memory, "save_messages", lambda *args: None)
    monkeypatch.setattr(react, "increment_step", lambda: None)
    monkeypatch.setattr(react, "trace_llm_call", lambda **kwargs: None)
    monkeypatch.setattr(react, "trace_tool_call", lambda *args, **kwargs: None)
    monkeypatch.setattr(react, "trace_commit_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        react.tokenizer,
        "compute_usage",
        lambda messages: SimpleNamespace(
            used=1, total=100, percent=1, level="ok"
        ),
    )
    monkeypatch.setattr(react.tokenizer, "must_compress", lambda usage: False)
    monkeypatch.setattr(react.tokenizer, "should_compress", lambda usage: False)
    return prepare, commit


async def _approve(turn_id: str) -> tuple[bool, str]:
    return True, "同意"


async def _reject(turn_id: str) -> tuple[bool, str]:
    return False, "用户取消"


def _prepare_call() -> dict:
    return {
        "id": "call-1",
        "name": "prepare_planting_plan",
        "arguments": {
            "crop_name": "西瓜",
            "total_area_mu": 5,
            "field_name": "东棚",
            "start_date": "2026-08-10",
        },
    }


def test_manage_planting_plan_declares_followup_and_hides_commit() -> None:
    skill_dir = Path(loader.__file__).resolve().parent / "manage-planting-plan"
    source = loader._load_skill(skill_dir)
    assert source is not None
    operations = {skill.name: skill for skill in source.operation_skills()}

    prepare = operations["prepare_planting_plan"]
    assert prepare.mcp_tool == "prepare_planting_plan"
    followup = prepare.approval_followup
    assert followup is not None
    assert followup["tool_name"] == "commit_planting_plan"
    assert followup["arguments_from_result"] == [
        "client_request_id",
        "approval_fingerprint",
        "plan",
    ]

    commit = operations["commit_planting_plan"]
    assert commit.mcp_tool == "commit_planting_plan"
    assert commit.finalize_after_success is True
    assert commit._inject_operation is False
    # commit 不暴露给模型，由 Runtime 在审批通过后自动驱动
    assert commit.exposed is False


def test_commit_planting_plan_not_exposed_to_model() -> None:
    skills = loader.load_all()
    names = {s.name for s in skills}
    # commit 在 skill registry 中（Runtime 可按名查找驱动）
    assert "commit_planting_plan" in names
    # 但不在 OpenAI tools schema 中（模型看不到）
    tool_names = {
        t["function"]["name"] for t in loader.to_openai_tools(skills)
    }
    assert "prepare_planting_plan" in tool_names
    assert "commit_planting_plan" not in tool_names


@pytest.mark.asyncio
async def test_prepare_ready_drives_approval_and_commit_in_same_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_chat_stream(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield {"type": "done", "tool_calls": [_prepare_call()]}
            return
        # 收尾轮：tools 已清空
        assert tools == []
        yield {"type": "text", "delta": "种植计划已创建完成。"}
        yield {"type": "done", "tool_calls": []}

    _, commit = _patch_react_runtime(monkeypatch, fake_chat_stream)

    turn = Turn(user_input="种 5 亩西瓜，建东棚", max_steps=1)
    events = [event async for event in react.run_turn(turn, _approve)]
    event_types = [event["type"] for event in events]

    # prepare ready 后同一 turn 产生一次审批
    assert event_types.count("approval_required") == 1
    # 审批展示内容来自 prepare 返回值
    approval_ev = next(e for e in events if e["type"] == "approval_required")
    assert approval_ev["data"]["summary"] == _PrepareSkill.prepared_result["approval_summary"]
    assert approval_ev["data"]["plan"]["crop_name"] == "西瓜"
    # approve 后只调用一次 commit（prepare 1 次 action + commit 1 次 action）
    assert event_types.count("action") == 2
    assert commit.call_count == 1
    # Business 返回 committed 后产生一次 operation_committed
    assert event_types.count("operation_committed") == 1
    assert event_types.count("final_answer") == 1
    assert turn.status == "completed"
    assert turn.step_count == 2
    assert not any(
        event.get("data", {}).get("code") == "max_steps" for event in events
    )


@pytest.mark.asyncio
async def test_commit_uses_prepare_arguments_not_model_reconstructed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_chat_stream(messages, tools):
        yield {"type": "done", "tool_calls": [_prepare_call()]}
        return

    _, commit = _patch_react_runtime(monkeypatch, fake_chat_stream)

    turn = Turn(user_input="种 5 亩西瓜", max_steps=1)
    _ = [event async for event in react.run_turn(turn, _approve)]

    # commit 收到的参数必须与 prepare 返回值深度相等，不能是模型重建的
    expected = _PrepareSkill.prepared_result
    assert commit.received_args == {
        "client_request_id": expected["client_request_id"],
        "approval_fingerprint": expected["approval_fingerprint"],
        "plan": expected["plan"],
    }
    assert commit.call_count == 1


@pytest.mark.asyncio
async def test_approval_stale_ends_turn_without_further_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """commit 返回不可重试业务错误时立即结束 turn，不让 LLM 选其他工具。"""

    class _StaleCommit(_CommitSkill):
        async def execute(self, params: dict, ctx) -> SkillResult:
            self.call_count += 1
            self.received_args = dict(params)
            return SkillResult(
                data={
                    "status": "failed",
                    "error": "approval_stale",
                    "code": "approval_stale",
                    "message": "审批后的种植计划内容已发生变化，请重新准备并确认",
                },
                error="审批后的种植计划内容已发生变化，请重新准备并确认",
            )

    llm_calls = 0

    async def fake_chat_stream(messages, tools):
        nonlocal llm_calls
        llm_calls += 1
        if llm_calls == 1:
            yield {"type": "done", "tool_calls": [_prepare_call()]}
            return
        # 不应该到达收尾轮：错误必须终止 turn
        raise AssertionError("approval_stale 后不应再调用 LLM")

    _, commit = _patch_react_runtime(
        monkeypatch, fake_chat_stream, commit_skill=_StaleCommit()
    )

    turn = Turn(user_input="种 5 亩西瓜", max_steps=5)
    events = [event async for event in react.run_turn(turn, _approve)]
    event_types = [event["type"] for event in events]

    assert turn.status == "failed"
    assert turn.error == "approval_stale"
    assert commit.call_count == 1
    # 错误后不再调用天气、城市、搜索或其他写工具
    assert llm_calls == 1
    assert "operation_committed" not in event_types
    assert any(e.get("data", {}).get("code") == "approval_stale" for e in events)


@pytest.mark.asyncio
async def test_prepare_result_incomplete_ends_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """prepare 返回 ready 但缺少提交所需字段时，返回 prepare_result_incomplete。"""

    class _BrokenPrepare(_PrepareSkill):
        async def execute(self, params: dict, ctx) -> SkillResult:
            data = dict(self.prepared_result)
            data.pop("approval_fingerprint")  # 缺关键字段
            return SkillResult(data=data)

    async def fake_chat_stream(messages, tools):
        yield {"type": "done", "tool_calls": [_prepare_call()]}
        return

    _, commit = _patch_react_runtime(
        monkeypatch, fake_chat_stream, prepare_skill=_BrokenPrepare()
    )

    turn = Turn(user_input="种 5 亩西瓜", max_steps=5)
    events = [event async for event in react.run_turn(turn, _approve)]

    assert turn.status == "failed"
    assert turn.error == "prepare_result_incomplete"
    # 缺字段时不得进入审批，也不得调用 commit
    assert commit.call_count == 0
    assert not any(e["type"] == "approval_required" for e in events)


@pytest.mark.asyncio
async def test_rejected_approval_ends_turn_without_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_chat_stream(messages, tools):
        yield {"type": "done", "tool_calls": [_prepare_call()]}
        return

    _, commit = _patch_react_runtime(monkeypatch, fake_chat_stream)

    turn = Turn(user_input="种 5 亩西瓜", max_steps=5)
    events = [event async for event in react.run_turn(turn, _reject)]
    event_types = [event["type"] for event in events]

    # 用户拒绝：不调用 commit，直接结束 turn
    assert commit.call_count == 0
    assert "operation_committed" not in event_types
    assert event_types.count("final_answer") == 1
    assert "已取消" in (turn.final_answer or "")


@pytest.mark.asyncio
async def test_direct_commit_call_blocked_without_pending_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有 pending approval 时，模型生成的 commit 调用必须被阻止。

    用新聊天 turn 发送 ok 模拟：模型若尝试直接调用 commit（不应发生，因 commit 未暴露），
    Runtime 也要防御性拒绝，不能绕过审批执行写入。
    """

    class _NoPrepare(Skill):
        _meta = {
            "name": "prepare_planting_plan",
            "description": "prepare",
            "risk_level": "read",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

        async def execute(self, params, ctx) -> SkillResult:
            raise AssertionError("ok turn 不应触发 prepare")

    async def fake_chat_stream(messages, tools):
        # 模型尝试直接调用 commit（commit 未暴露，但防御性测试）
        yield {
            "type": "done",
            "tool_calls": [
                {
                    "id": "call-x",
                    "name": "commit_planting_plan",
                    "arguments": {
                        "client_request_id": "forged",
                        "approval_fingerprint": "forged",
                        "plan": {"crop_name": "西瓜"},
                    },
                }
            ],
        }
        return

    _, commit = _patch_react_runtime(
        monkeypatch, fake_chat_stream, prepare_skill=_NoPrepare()
    )

    turn = Turn(user_input="ok", max_steps=3)
    events = [event async for event in react.run_turn(turn, _approve)]
    observations = [
        e for e in events if e["type"] == "observation" and e["data"].get("error")
    ]

    # commit 被阻止，不执行写入
    assert commit.call_count == 0
    assert observations, "应返回 tool_not_exposed 错误观察"
    assert any("不可直接调用" in (o["data"].get("error") or "") for o in observations)


@pytest.mark.asyncio
async def test_committed_write_uses_structured_fallback_when_reply_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_chat_stream(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield {"type": "done", "tool_calls": [_prepare_call()]}
            return
        # 收尾 LLM 失败
        yield {"type": "error", "message": "模型连接中断"}

    _, commit = _patch_react_runtime(monkeypatch, fake_chat_stream)

    turn = Turn(user_input="种 5 亩西瓜", max_steps=1)
    events = [event async for event in react.run_turn(turn, _approve)]
    event_types = [event["type"] for event in events]

    assert turn.status == "completed"
    assert event_types.count("operation_committed") == 1
    assert event_types.count("write_committed_reply_failed") == 1
    assert event_types.count("final_answer") == 1
    assert "西瓜种植计划" in (turn.final_answer or "")


def test_frontend_records_final_answer_once() -> None:
    index_path = Path(__file__).resolve().parents[1] / "agent" / "static" / "index.html"
    source = index_path.read_text(encoding="utf-8")
    assert "type !== 'final_answer'" in source
    assert source.count("state.currentTurnEvents.push({ type, data:") == 2


def test_trace_distinguishes_committed_write_from_reply_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict] = []
    monkeypatch.setattr(
        collector,
        "record",
        lambda **kwargs: recorded.append(kwargs),
    )

    collector.trace_commit_state(
        {"status": "committed", "cycle": {"id": 31}},
        reply_generated=False,
    )

    assert recorded[0]["node_type"] == "commit_state"
    assert recorded[0]["output_data"]["business_committed"] is True
    assert recorded[0]["output_data"]["reply_generated"] is False
