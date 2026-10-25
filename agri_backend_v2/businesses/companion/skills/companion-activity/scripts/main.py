"""companion-activity：按状态推荐一个轻量关怀动作。"""

from __future__ import annotations

from agent.domains.harness.tools.base import Skill, SkillResult
from agent.domains.harness.tools.context import SkillContext

_ACTIVITIES = {
    "happy": ("把今天让你开心的一件小事记下来，留到以后再看。", "记录一件值得记住的小事"),
    "okay": ("起身喝一杯水，顺手伸展一下肩颈。", "喝水并活动肩颈"),
    "tired": ("放下手里的事，闭眼休息一会儿，让肩膀自然下沉。", "闭眼休息"),
    "low": ("给一个信任的人发一条很短的消息，不需要解释太多。", "联系一个信任的人"),
    "anxious": ("试试缓慢呼吸：吸气四秒，停两秒，呼气六秒，重复几轮。", "缓慢呼吸"),
}


class CompanionActivitySkill(Skill):
    """按心情给出轻量关怀动作。"""

    kind = "local"

    @property
    def name(self) -> str:
        return "companion_activity"

    @property
    def description(self) -> str:
        return (
            "根据用户当前状态推荐一个几分钟内能完成的小关怀动作。"
            "用户疲惫、焦虑、低落或想放松时使用。"
        )

    @property
    def risk_level(self) -> str:
        return "read"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mood": {
                    "type": "string",
                    "enum": ["happy", "okay", "tired", "low", "anxious"],
                    "description": "用户当前状态",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "default": 5,
                    "description": "用户愿意留出的时间，单位分钟",
                },
            },
            "required": ["mood"],
        }

    async def execute(self, params: dict, _ctx: SkillContext) -> SkillResult:
        mood = str(params.get("mood") or "").strip().lower()
        if mood not in _ACTIVITIES:
            return SkillResult(error="mood 必须是 happy / okay / tired / low / anxious")

        raw_minutes = params.get("minutes", 5)
        try:
            minutes = max(1, min(30, int(raw_minutes)))
        except (TypeError, ValueError):
            minutes = 5

        activity, title = _ACTIVITIES[mood]
        return SkillResult(
            data={
                "mood": mood,
                "title": title,
                "activity": activity,
                "duration_minutes": minutes,
                "note": "如果现在不想做也没关系，可以先只是坐一会儿。",
            }
        )


skill = CompanionActivitySkill()
