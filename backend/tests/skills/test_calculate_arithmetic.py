"""确定性算术 Skill 测试。"""

import importlib

import pytest
from skillify.core.context import SkillContext

from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db

_calculate_mod = importlib.import_module("app.skills.calculate-arithmetic.scripts.main")
CalculateArithmeticSkill = _calculate_mod.CalculateArithmeticSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1, user_id="test-user-001")


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name


@pytest.mark.asyncio
async def test_calculate_arithmetic_handles_farm_cost_expression(ctx):
    result = await CalculateArithmeticSkill().execute(
        {
            "expression": "36 * 1000 * 1.5",
            "unit": "元",
            "precision": 2,
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "54,000.00 元" in result.reply
    assert "36 * 1000 * 1.5 = 54000.00" in result.reply


@pytest.mark.asyncio
async def test_calculate_arithmetic_rejects_unsafe_expression(ctx):
    result = await CalculateArithmeticSkill().execute(
        {"expression": "__import__('os').system('echo bad')"},
        ctx,
    )

    assert result.status.value == "failed"
    assert "code=UNSUPPORTED_EXPRESSION" in result.reply


def test_router_selects_calculator_for_price_math_request():
    decision = SkillRouter().route(
        "滴灌带36公里，1.5元一米，总价是多少钱",
        [_Tool("calculate_arithmetic"), _Tool("manage_cost"), _Tool("get_farm_status")],
    )

    assert decision.selected_tools == ["calculate_arithmetic"]
    assert decision.frames[0].intent == "calculate_arithmetic"
