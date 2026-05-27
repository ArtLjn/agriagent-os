"""更新阶段 Skill — 对话式推进茬口生长阶段。

场景: 「西瓜进膨大期了」→ 查找西瓜茬口，更新当前阶段为膨大期。
"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.models.cycle import CropCycle, CycleStage


class UpdateCropStageSkill(Skill):
    """更新茬口的生长阶段。

    Agent 通过对话提取阶段名称后，查找对应茬口并更新当前阶段。
    """

    def name(self) -> str:
        return "update_crop_stage"

    def description(self) -> str:
        return (
            "更新茬口的生长阶段。当用户说进XX期了、到XX阶段了时使用。"
            "触发词: 进XX期、到XX阶段、阶段更新"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口ID（可选，不传则自动匹配）",
                },
                "stage_name": {
                    "type": "string",
                    "description": "目标阶段名称，如'膨大期'、'伸蔓期'、'开花期'",
                },
            },
            "required": ["stage_name"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        """执行阶段更新操作。"""
        stage_name = params.get("stage_name")
        if not stage_name or not isinstance(stage_name, str) or not stage_name.strip():
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="更新阶段失败：请提供目标阶段名称。",
            )

        stage_name = stage_name.strip()
        cycle_id = params.get("cycle_id")
        farm_id = getattr(context, "farm_id", 1) or 1

        db = SessionLocal()
        try:
            # 1. 获取茬口：指定 ID 或自动匹配
            if cycle_id:
                cycle = _get_cycle_by_id(db, cycle_id, farm_id)
                if not cycle:
                    return SkillResult(
                        status=ResultStatus.FAILED,
                        reply=f"未找到 ID 为 {cycle_id} 的茬口。",
                    )
            else:
                cycle = _auto_match_cycle(db, farm_id)
                if isinstance(cycle, str):
                    # 返回的是 NEED_CLARIFY 消息
                    return SkillResult(
                        status=ResultStatus.NEED_CLARIFY,
                        reply=cycle,
                    )
                if cycle is None:
                    return SkillResult(
                        status=ResultStatus.FAILED,
                        reply="当前没有活跃的茬口，请先创建茬口。",
                    )

            # 2. 在阶段列表中查找目标阶段
            if not cycle.stages:
                return SkillResult(
                    status=ResultStatus.FAILED,
                    reply=f"茬口「{cycle.name}」还没有阶段数据。",
                )

            target = _find_stage(cycle.stages, stage_name)
            if not target:
                available = "、".join(s.name for s in cycle.stages)
                return SkillResult(
                    status=ResultStatus.FAILED,
                    reply=f"茬口「{cycle.name}」中没有「{stage_name}」阶段。"
                    f"可用阶段：{available}",
                )

            # 3. 清除旧的 is_current，设置目标阶段为当前
            for s in cycle.stages:
                if s.is_current:
                    s.is_current = 0
            target.is_current = 1
            db.commit()

            # 4. 返回成功消息
            reply = f"已将茬口「{cycle.name}」的阶段更新为「{target.name}」。"
            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"更新阶段失败：{exc}",
            )
        finally:
            db.close()


def _get_cycle_by_id(db, cycle_id: int, farm_id: int) -> CropCycle | None:
    """根据 ID 获取指定农场的茬口。"""
    return (
        db.query(CropCycle)
        .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
        .first()
    )


def _auto_match_cycle(db, farm_id: int) -> CropCycle | None | str:
    """自动匹配活跃茬口。

    Returns:
        CropCycle: 唯一匹配的茬口
        None: 没有活跃茬口
        str: 多个活跃茬口时返回 NEED_CLARIFY 消息
    """
    active_cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .all()
    )

    if not active_cycles:
        return None

    if len(active_cycles) == 1:
        return active_cycles[0]

    # 多个活跃茬口，返回让用户指定的提示
    cycle_list = "\n".join(f"  - {c.name}（ID: {c.id}）" for c in active_cycles)
    return f"当前有多个活跃茬口，请指定要更新哪一个：\n{cycle_list}"


def _find_stage(stages: list, name: str) -> CycleStage | None:
    """在阶段列表中查找匹配的阶段。

    先精确匹配，再模糊匹配（包含关系）。
    """
    # 精确匹配
    for s in stages:
        if s.name == name:
            return s

    # 模糊匹配：阶段名包含输入，或输入包含阶段名
    for s in stages:
        if name in s.name or s.name in name:
            return s

    return None
