"""农场 CRUD 服务（从 archive farm/service.py 复用并适配 agri_backend_v2）。

提供农场基本信息管理：
  - create_default_farm: 注册时创建默认农场
  - get_farm_by_user_id / get_farm_by_id / get_farm_with_user
  - update_farm_location: 更新农场位置（同步 UserSetting）
  - update_farm_info: 更新农场基本信息

与 archive 的差异：
  - 去掉 app.context.runtime / app.infra.skill_cache / weather_cache 依赖
  - 去掉 invalidate_farm_location_caches（agri_backend_v2 缓存层 TODO）
  - 去掉 clear_daily_advice_cache（agent_record 暂不实现）
  - city_coords 解析委托给 agri_backend_v2 的 location_service.find_coords
"""
from __future__ import annotations

from datetime import datetime
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from business.models import Farm, UserSetting
from business.services import location_service

logger = logging.getLogger(__name__)


def create_default_farm(db: Session, user_id: str, nickname: str) -> Farm:
    """为新用户创建默认农场。

    Args:
        db: 数据库会话（由上层 session_scope 提供）
        user_id: 用户 ID
        nickname: 用户昵称（用于生成默认农场名）

    Returns:
        Farm 实例（已 flush，含 id）
    """
    farm = Farm(
        uid=str(uuid.uuid4()),
        name=f"{nickname}的农场",
        user_id=user_id,
        location="苏州",  # 默认地区，用户可后续修改
    )
    db.add(farm)
    db.flush()  # 拿到 farm.id
    return farm


def get_farm_by_id(db: Session, farm_id: int) -> Farm | None:
    """通过 farm_id 查询农场。"""
    return db.get(Farm, farm_id)


def get_farm_by_uid(db: Session, farm_uid: str) -> Farm | None:
    """通过对外稳定 UID 查询农场，内部再使用自增 farm.id。"""
    return db.query(Farm).filter(Farm.uid == farm_uid).first()


def get_farm_by_user_id(db: Session, user_id: str) -> Farm | None:
    """通过 user_id 查询关联农场。"""
    return db.query(Farm).filter(Farm.user_id == user_id).first()


def get_farm_with_user(db: Session, farm_id: int) -> dict[str, Any] | None:
    """获取农场 + 用户基本信息（用于 /api/farms/{id} 接口）。"""
    farm = get_farm_by_id(db, farm_id)
    if farm is None:
        return None
    result = {
        "id": farm.id,
        "uid": farm.uid,
        "name": farm.name,
        "location": farm.location,
        "user_id": farm.user_id,
        "created_at": farm.created_at.isoformat() if farm.created_at else None,
    }
    # 解析坐标（便于天气查询）
    if farm.location:
        coords = location_service.find_coords(farm.location)
        if coords:
            result["lat"], result["lon"] = coords
    return result


def update_farm_info(
    db: Session, farm_id: int, *, name: str | None = None
) -> Farm | None:
    """更新农场基本信息（名称等）。"""
    farm = get_farm_by_id(db, farm_id)
    if farm is None:
        return None
    if name is not None:
        farm.name = name
    db.flush()
    return farm


def update_farm_location(
    db: Session,
    *,
    farm_id: int,
    location: str,
    lat: float | None = None,
    lon: float | None = None,
) -> Farm:
    """更新农场经营地区，并同步 UserSetting.default_city。

    Args:
        db: 数据库会话
        farm_id: 农场 ID
        location: 新地区名称
        lat: 纬度（可选，未提供则从 location_service 解析）
        lon: 经度（可选）

    Returns:
        更新后的 Farm 实例

    Raises:
        ValueError: 农场不存在
    """
    farm = get_farm_by_id(db, farm_id)
    if farm is None:
        raise ValueError(f"农场 {farm_id} 不存在")

    farm.location = location.strip()

    # 同步 UserSetting（如有）
    if farm.user_id:
        setting = (
            db.query(UserSetting)
            .filter(UserSetting.user_id == farm.user_id)
            .first()
        )
        if setting is None:
            setting = UserSetting(user_id=farm.user_id, updated_at=datetime.now())
            db.add(setting)
        setting.default_city = farm.location

    # 解析坐标（如未传入）
    if (lat is None or lon is None) and farm.location:
        coords = location_service.find_coords(farm.location)
        if coords:
            lat, lon = coords
    if setting is not None:
        setting.default_lat = lat
        setting.default_lon = lon

    db.flush()
    logger.info("农场地区更新 | farm_id=%s location=%s", farm_id, farm.location)
    return farm


def backfill_default_farm_location(
    db: Session, *, user_id: str
) -> Farm | None:
    """当默认农场缺少地区时，用旧用户设置城市回填一次。

    用于历史数据兼容，archive 在用户登录时会调用。
    """
    farm = get_farm_by_user_id(db, user_id)
    if farm is None or (farm.location and farm.location.strip()):
        return farm

    setting = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
    if setting and setting.default_city and setting.default_city.strip():
        farm.location = setting.default_city.strip()
        db.flush()
    return farm


__all__ = [
    "create_default_farm",
    "get_farm_by_id",
    "get_farm_by_uid",
    "get_farm_by_user_id",
    "get_farm_with_user",
    "update_farm_info",
    "update_farm_location",
    "backfill_default_farm_location",
]
