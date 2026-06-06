"""Skill 上下文隔离测试。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from skillify.models.schemas import ResultStatus, SkillResult

from app.agent.skills import skills_to_langchain_tools

pytestmark = pytest.mark.no_db


class _FakeSkill:
    """记录调用上下文的假 Skill。"""

    def __init__(self):
        self.seen_context = None

    def name(self) -> str:
        return "fake_skill"

    def description(self) -> str:
        return "fake skill"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        self.seen_context = context
        return SkillResult(status=ResultStatus.SUCCESS, reply=params["value"])


class _FakeManager:
    def __init__(self, skill):
        self._skill = skill

    def list_skills(self):
        return [SimpleNamespace(name=self._skill.name())]

    def get_skill(self, name: str):
        if name == self._skill.name():
            return self._skill
        return None


@pytest.mark.asyncio
async def test_langchain_tool_injects_trusted_farm_context(monkeypatch):
    """LangChain 工具执行时应注入服务端可信 farm 上下文。"""
    farm_uid = str(uuid4())
    skill = _FakeSkill()

    def fake_context_builder(farm_id: int, farm_uid: str | None = None):
        return SimpleNamespace(farm_id=farm_id, farm_uid=farm_uid)

    monkeypatch.setattr("app.agent.skills.get_category_enum", lambda _farm_id: [])
    monkeypatch.setattr("app.agent.skills.build_skill_context", fake_context_builder)

    tool = skills_to_langchain_tools(_FakeManager(skill), farm_id=7, farm_uid=farm_uid)[
        0
    ]

    result = await tool.ainvoke({"value": "ok"})

    assert result == "ok"
    assert skill.seen_context.farm_id == 7
    assert skill.seen_context.farm_uid == farm_uid
