"""种植周期 selector。"""

from sqlalchemy.orm import Session

from app.context.models import ContextBlock
from app.models.cycle import CropCycle


class CycleSelector:
    """选择当前活跃茬口。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        cycles = (
            db.query(CropCycle)
            .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
            .order_by(CropCycle.start_date.desc())
            .limit(3)
            .all()
        )
        if not cycles:
            content = "当前无活跃种植周期"
        else:
            parts = []
            for cycle in cycles:
                stage = next(
                    (item for item in cycle.stages if item.is_current == 1),
                    cycle.stages[-1] if cycle.stages else None,
                )
                stage_name = stage.name if stage else "未知阶段"
                parts.append(f"{cycle.name}({stage_name})")
            content = "活跃茬口：" + "、".join(parts)

        return [
            ContextBlock(
                key="cycle",
                source="cycle",
                purpose="当前周期",
                content=content,
                priority=80,
                ttl_seconds=300,
            )
        ]


__all__ = ["CycleSelector"]
