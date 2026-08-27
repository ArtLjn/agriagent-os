"""农场资料与概览路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from business.api.deps import get_current_user, require_permission
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import farm_crud_service, farm_service
from shared.roles import Permission

router = APIRouter(prefix="/farms", tags=["farms"])


class UpdateFarmRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=100)


class UpdateLocationRequest(StrictRequest):
    location: str = Field(min_length=1, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


def _require_current_farm(farm_id: int, user: dict) -> None:
    if farm_id != user["farm_id"]:
        raise HTTPException(status_code=403, detail="无权访问其他农场")


def _farm_out(farm) -> dict:
    return {
        "id": farm.id,
        "uid": farm.uid,
        "name": farm.name,
        "location": farm.location,
        "user_id": farm.user_id,
        "created_at": farm.created_at.isoformat() if farm.created_at else None,
    }


@router.get("/my", dependencies=[Depends(require_permission(Permission.FARM_READ))])
def my_farm(user: dict = Depends(get_current_user)) -> dict:
    result = farm_service.build_summary_by_user(user["user_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="农场不存在")
    return result


@router.get("/{farm_id}")
def get_farm(
    farm_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_current_farm(farm_id, user)
    result = farm_crud_service.get_farm_with_user(db, farm_id)
    if result is None:
        raise HTTPException(status_code=404, detail="农场不存在")
    return result


@router.patch("/{farm_id}")
def update_farm(
    farm_id: int,
    request: UpdateFarmRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_current_farm(farm_id, user)
    farm = farm_crud_service.update_farm_info(db, farm_id, name=request.name)
    if farm is None:
        raise HTTPException(status_code=404, detail="农场不存在")
    return _farm_out(farm)


@router.patch("/{farm_id}/location")
def update_farm_location(
    farm_id: int,
    request: UpdateLocationRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_current_farm(farm_id, user)
    try:
        farm = farm_crud_service.update_farm_location(
            db,
            farm_id=farm_id,
            location=request.location,
            lat=request.lat,
            lon=request.lon,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _farm_out(farm)


@router.get("/{farm_id}/overview")
def farm_overview(
    farm_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    _require_current_farm(farm_id, user)
    return farm_service.build_summary(farm_id)
