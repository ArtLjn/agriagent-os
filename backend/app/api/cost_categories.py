"""成本分类 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cost_category import CostCategoryCreate, CostCategoryResponse
from app.services import cost_category_service

router = APIRouter(prefix="/cost-categories", tags=["分类管理"])


@router.get("", response_model=list[CostCategoryResponse])
def get_categories(
    farm_id: int = Query(1, description="农场 ID"), db: Session = Depends(get_db)
):
    """获取农场分类列表，空农场自动初始化预设分类。"""
    categories = cost_category_service.get_categories(db, farm_id)
    if not categories:
        cost_category_service.init_default_categories(db, farm_id)
        categories = cost_category_service.get_categories(db, farm_id)
    return categories


@router.post("", response_model=CostCategoryResponse, status_code=201)
def create_category(
    farm_id: int = Query(1, description="农场 ID"),
    data: CostCategoryCreate,
    db: Session = Depends(get_db),
):
    """创建用户自定义分类。"""
    return cost_category_service.create_category(db, data, farm_id)


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
):
    """删除分类，禁止删除系统预设分类。"""
    try:
        cost_category_service.delete_category(db, category_id, farm_id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
