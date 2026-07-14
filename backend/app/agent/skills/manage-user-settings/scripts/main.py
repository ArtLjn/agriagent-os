"""用户设置管理 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.application.context_invalidation import invalidate_user_farm_context
from app.agent.assistant_roles import (
    DEFAULT_ASSISTANT_ROLE,
    assistant_role_label,
    normalize_assistant_role,
)
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.models.user import User
from app.models.user_setting import UserSetting


class ManageUserSettingsSkill(Skill):
    """查询或更新当前用户设置。"""

    def name(self) -> str:
        return "manage_user_settings"

    def description(self) -> str:
        return "查询或更新当前用户显示名、默认天气城市、默认经纬度和助手回复角色。只允许处理当前登录用户自己的设置。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["query_settings", "update_settings"],
                    "description": "操作类型：query_settings 查询设置，update_settings 更新设置。缺省时按参数自动推断。",
                },
                "display_name": {"type": "string", "description": "显示名"},
                "default_city": {"type": "string", "description": "默认天气城市"},
                "default_lat": {"type": "number", "description": "默认纬度"},
                "default_lon": {"type": "number", "description": "默认经度"},
                "assistant_role": {
                    "type": "string",
                    "enum": ["professional", "warm", "creative"],
                    "description": "助手回复角色：professional 冷静专业型，warm 温暖陪伴型，creative 灵感创意型",
                },
            },
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["user"],
            "cache_invalidation": ["get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["display_name", "default_city", "assistant_role"],
                "changed_fields": ["default_lat", "default_lon"],
                "editable_fields": [
                    "display_name",
                    "default_city",
                    "default_lat",
                    "default_lon",
                    "assistant_role",
                ],
                "risk_notes": ["设置只会修改当前登录用户，不接受任意用户 ID。"],
            },
            "evaluation_tags": ["write", "user_settings"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        operation = _resolve_operation(params)
        if operation == "query_settings":
            return await self._query_settings(context)
        if operation != "update_settings":
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="请说明要查询还是修改用户设置。",
            )
        return await self._update_settings(params, context)

    async def _query_settings(self, context) -> SkillResult:
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

    async def _update_settings(self, params: dict, context) -> SkillResult:
        user_id = _get_user_id(context)
        if not user_id:
            return SkillResult(
                status=ResultStatus.FAILED, reply="更新用户设置需要登录用户上下文。"
            )
        if not any(params.get(key) is not None for key in _SETTING_FIELDS):
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY, reply="请说明要修改的设置项。"
            )
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user is None:
                return SkillResult(
                    status=ResultStatus.FAILED, reply="更新用户设置失败：用户不存在。"
                )
            if params.get("display_name") is not None:
                user.nickname = str(params["display_name"]).strip()

            setting = (
                db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
            )
            has_location_update = any(
                params.get(key) is not None
                for key in ("default_city", "default_lat", "default_lon")
            )
            has_role_update = params.get("assistant_role") is not None
            if setting is None and (has_location_update or has_role_update):
                setting = UserSetting(
                    user_id=user_id,
                    assistant_role=DEFAULT_ASSISTANT_ROLE,
                )
                db.add(setting)
            if setting is not None:
                if params.get("default_city") is not None:
                    setting.default_city = str(params["default_city"]).strip()
                if params.get("default_lat") is not None:
                    setting.default_lat = float(params["default_lat"])
                if params.get("default_lon") is not None:
                    setting.default_lon = float(params["default_lon"])
                if params.get("assistant_role") is not None:
                    setting.assistant_role = normalize_assistant_role(
                        str(params["assistant_role"]).strip()
                    )

            db.commit()
            invalidate_user_farm_context(db, user_id)
            city = setting.default_city if setting else None
            role = normalize_assistant_role(setting.assistant_role if setting else None)
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=(
                    f"已更新用户设置：显示名 {user.nickname or '农友'}，"
                    f"默认城市 {city or '未设置'}，助手角色 {assistant_role_label(role)}。"
                ),
            )
        except Exception as exc:
            db.rollback()
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"更新用户设置失败：{exc}"
            )
        finally:
            db.close()


_SETTING_FIELDS = (
    "display_name",
    "default_city",
    "default_lat",
    "default_lon",
    "assistant_role",
)


def _resolve_operation(params: dict) -> str | None:
    operation = params.get("operation")
    if operation:
        return str(operation).strip()
    has_write_field = any(params.get(key) is not None for key in _SETTING_FIELDS)
    return "update_settings" if has_write_field else "query_settings"


def _get_user_id(context) -> str | None:
    for attr in ("farm_uid", "user_id"):
        value = getattr(context, attr, None)
        if value:
            return str(value)
    return None
