"""companion-checkin：按当前时段生成温和的陪伴问候。"""

from __future__ import annotations

from datetime import datetime

from agent.domains.harness.tools.base import Skill, SkillResult
from agent.domains.harness.tools.context import SkillContext

_PERIODS = (
    (5, 9, "清晨", "早上好。新的一天不用一下子进入状态，先让自己缓一缓。"),
    (9, 12, "上午", "上午好。忙起来的时候，也记得给自己留一点空隙。"),
    (12, 18, "下午", "下午好。今天已经走了这么远，可以稍微停一下。"),
    (18, 23, "晚上", "晚上好。今天不管过得怎样，现在可以先把自己放下来。"),
)
_NIGHT = ("深夜", "已经很晚了。如果还醒着，先把屏幕放远一点，给身体一个休息的机会。")
_QUESTION = "现在更想聊聊心情，还是只想安静待一会儿？"


def _greeting(hour: int) -> tuple[str, str]:
    for start, end, period, message in _PERIODS:
        if start <= hour < end:
            return period, message
    return _NIGHT


class CompanionCheckinSkill(Skill):
    """按本地时间生成陪伴问候。"""

    kind = "local"

    @property
    def name(self) -> str:
        return "companion_checkin"

    @property
    def description(self) -> str:
        return (
            "生成一段温和的陪伴问候和一个开放式问题。"
            "用户想被关心、想聊几句或不知道说什么时使用。"
        )

    @property
    def risk_level(self) -> str:
        return "read"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, params: dict, _ctx: SkillContext) -> SkillResult:
        period, message = _greeting(datetime.now().hour)
        return SkillResult(
            data={
                "period": period,
                "message": message,
                "question": _QUESTION,
            }
        )


skill = CompanionCheckinSkill()
