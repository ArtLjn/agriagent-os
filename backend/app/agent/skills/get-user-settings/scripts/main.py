"""用户设置查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.assistant_roles import assistant_role_label, normalize_assistant_role
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.models.user import User
from app.models.user_setting import UserSetting


class GetUserSettingsSkill(Skill):
    """查询当前用户设置。"""

    def name(self) -> str:
        return "get_user_settings"

    def description(self) -> str:
        return "查询当前用户的显示名、默认天气城市/经纬度和助手回复角色设置。"

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["user"],
            "evaluation_tags": ["read", "user_settings"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        user_id = _get_user_id(context)
        if not user_id:
            return SkillResult(
                status=ResultStatus.FAILED, reply="查询用户设置需要登录用户上下文。"
            )
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user is None:
                return SkillResult(
                    status=ResultStatus.FAILED, reply="查询用户设置失败：用户不存在。"
                )
            setting = (
                db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
            )
            display_name = user.nickname or "农友"
            city = setting.default_city if setting else None
            lat = setting.default_lat if setting else None
            lon = setting.default_lon if setting else None
            role = normalize_assistant_role(setting.assistant_role if setting else None)
            location_text = city or "未设置"
            if lat is not None and lon is not None:
                location_text = f"{location_text}（{lat}, {lon}）"
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=(
                    f"当前设置：显示名 {display_name}，默认天气位置 {location_text}，"
                    f"助手角色 {assistant_role_label(role)}。"
                ),
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"查询用户设置失败：{exc}"
            )
        finally:
            db.close()


def _get_user_id(context) -> str | None:
    for attr in ("farm_uid", "user_id"):
        value = getattr(context, attr, None)
        if value:
            return str(value)
    return None
