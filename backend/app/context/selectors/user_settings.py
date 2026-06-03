"""用户设置 selector。"""

from sqlalchemy.orm import Session

from app.context.models import ContextBlock
from app.models.farm import Farm
from app.models.user_setting import UserSetting


class UserSettingsSelector:
    """选择用户偏好和默认位置。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        setting = None
        if farm and farm.user_id:
            setting = (
                db.query(UserSetting)
                .filter(UserSetting.user_id == farm.user_id)
                .first()
            )

        if setting is None:
            content = "用户设置：未配置默认位置"
            metadata = {}
        else:
            coords = ""
            if setting.default_lat is not None and setting.default_lon is not None:
                coords = f"{setting.default_lat:.4f},{setting.default_lon:.4f}"
            parts = ["用户设置"]
            if setting.default_city:
                parts.append(f"默认城市：{setting.default_city}")
            if coords:
                parts.append(f"坐标：{coords}")
            content = "；".join(parts)
            metadata = {
                "default_city": setting.default_city or "",
                "farm_coords": coords,
            }

        return [
            ContextBlock(
                key="user_settings",
                source="user_settings",
                purpose="用户偏好",
                content=content,
                priority=75,
                ttl_seconds=300,
                metadata=metadata,
            )
        ]


__all__ = ["UserSettingsSelector"]
