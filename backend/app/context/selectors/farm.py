"""农场状态 selector。"""

from sqlalchemy.orm import Session

from app.context.models import ContextBlock
from app.models.farm import Farm
from app.models.user import User


class FarmSelector:
    """选择农场基础状态。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        if farm is None:
            return [
                ContextBlock(
                    key="farm",
                    source="farm",
                    purpose="农场状态",
                    content="农场：未知",
                    priority=90,
                    required=True,
                )
            ]

        display_name = "农友"
        if farm.user_id:
            user = db.query(User).filter(User.id == farm.user_id).first()
            if user and user.nickname:
                display_name = user.nickname

        parts = [f"农场：{farm.name}", f"称呼：{display_name}"]
        if farm.location:
            parts.append(f"位置：{farm.location}")
        return [
            ContextBlock(
                key="farm",
                source="farm",
                purpose="农场状态",
                content="；".join(parts),
                priority=90,
                required=True,
                compressible=False,
                ttl_seconds=300,
                metadata={"display_name": display_name},
            )
        ]


__all__ = ["FarmSelector"]
