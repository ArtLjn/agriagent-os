"""Context 旧 Runtime 兼容入口。"""

from sqlalchemy.orm import Session

from app.context.selectors import CycleSelector
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.settings_models import UserSetting
from app.shared.config import (
    DEFAULT_ASSISTANT_ROLE,
    assistant_role_prompt,
    normalize_assistant_role,
)


def build_farm_runtime_context(db: Session, farm_id: int) -> dict:
    """兼容 Agent Runtime 的旧 farm context 字典形状。"""
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    display_name = "农友"
    user_city = ""
    user_lat = None
    user_lon = None
    active_crops = ""
    assistant_role = DEFAULT_ASSISTANT_ROLE

    if farm and farm.user_id:
        user = db.query(User).filter(User.id == farm.user_id).first()
        if user and user.nickname:
            display_name = user.nickname
        setting = (
            db.query(UserSetting).filter(UserSetting.user_id == farm.user_id).first()
        )
        if setting:
            user_city = setting.default_city or ""
            user_lat = setting.default_lat
            user_lon = setting.default_lon
            assistant_role = normalize_assistant_role(setting.assistant_role)

        cycle_block = CycleSelector().select(db=db, farm_id=farm_id)[0]
        active_crops = (
            cycle_block.content.removeprefix("活跃茬口：")
            if "活跃茬口：" in cycle_block.content
            else ""
        )

    farm_location = user_city or (farm.location if farm and farm.location else "")
    farm_coords = ""
    if isinstance(user_lat, int | float) and isinstance(user_lon, int | float):
        farm_coords = f"{user_lat:.4f},{user_lon:.4f}"

    return {
        "farm_location": farm_location,
        "farm_coords": farm_coords,
        "display_name": display_name,
        "active_crops": active_crops,
        "assistant_role": assistant_role,
        "assistant_role_prompt": assistant_role_prompt(assistant_role),
    }


__all__ = ["build_farm_runtime_context"]
