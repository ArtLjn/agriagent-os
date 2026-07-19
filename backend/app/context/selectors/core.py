"""Context 轻量 selector 集合。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.context.models import ContextBlock
from app.shared.config import assistant_role_label, normalize_assistant_role
from app.domains.conversation.models import Conversation, ConversationMessage
from app.domains.finance.cost_models import CostRecord
from app.domains.planting.cycle_models import CropCycle
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.settings_models import UserSetting


def _format_amount(amount: Decimal) -> str:
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount.normalize())


class ConversationSelector:
    """选择最近对话。"""

    def select(
        self,
        db: Session | None = None,
        farm_id: int | None = None,
        session_id: str | None = None,
        messages: list[str] | None = None,
        **_kwargs,
    ) -> list[ContextBlock]:
        lines = messages or []
        summary = None
        if not lines and db is not None and farm_id is not None:
            query = db.query(Conversation).filter(Conversation.farm_id == farm_id)
            if session_id:
                query = query.filter(Conversation.session_id == session_id)
            conversation = query.order_by(Conversation.last_active_at.desc()).first()
            if conversation:
                rows = (
                    db.query(ConversationMessage)
                    .filter(ConversationMessage.conversation_id == conversation.id)
                    .order_by(ConversationMessage.id.desc())
                    .limit(6)
                    .all()
                )
                lines = [
                    f"{row.role}：{row.content}"
                    for row in reversed(rows)
                    if row.content
                ]
                summary = conversation.summary

        if not lines:
            return []
        blocks = [
            ContextBlock(
                key="conversation",
                source="conversation",
                purpose="最近对话",
                content="\n".join(lines),
                priority=55,
                compressible=True,
                min_tokens=40,
            )
        ]
        if summary:
            blocks.append(
                ContextBlock(
                    key="conversation_summary",
                    source="conversation.summary",
                    purpose="会话摘要",
                    content=summary,
                    priority=50,
                    compressible=True,
                    min_tokens=64,
                    metadata={"layer": "working", "cache_scope": "session"},
                )
            )
        return blocks


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


class LedgerSelector:
    """选择账务摘要。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        today = date.today()
        total = (
            db.query(func.sum(CostRecord.amount))
            .filter(
                CostRecord.farm_id == farm_id,
                CostRecord.record_type == "cost",
                extract("year", CostRecord.record_date) == today.year,
                extract("month", CostRecord.record_date) == today.month,
            )
            .scalar()
        ) or Decimal("0")
        recent = (
            db.query(CostRecord)
            .filter(CostRecord.farm_id == farm_id)
            .order_by(CostRecord.record_date.desc())
            .limit(3)
            .all()
        )
        recent_text = "、".join(
            f"{item.category}{_format_amount(item.amount)}元" for item in recent
        )
        content = f"本月花费：{_format_amount(total)}元"
        if recent_text:
            content += f"；近期账务：{recent_text}"
        return [
            ContextBlock(
                key="ledger",
                source="ledger",
                purpose="账务摘要",
                content=content,
                priority=65,
                ttl_seconds=300,
            )
        ]


class RetrievalSelector:
    """选择语义检索结果。"""

    def select(self, results: list[str] | None = None, **_kwargs) -> list[ContextBlock]:
        if not results:
            return []
        return [
            ContextBlock(
                key="retrieval",
                source="retrieval",
                purpose="检索结果",
                content="\n".join(results[:5]),
                priority=25,
                compressible=True,
                min_tokens=24,
            )
        ]


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
            role = normalize_assistant_role(setting.assistant_role)
            parts.append(f"助手角色：{assistant_role_label(role)}")
            if setting.default_city:
                parts.append(f"默认城市：{setting.default_city}")
            if coords:
                parts.append(f"坐标：{coords}")
            content = "；".join(parts)
            metadata = {
                "default_city": setting.default_city or "",
                "farm_coords": coords,
                "assistant_role": role,
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


class WeatherSelector:
    """选择天气摘要，默认接收预先计算好的文本。"""

    def select(
        self, weather_summary: str | None = None, **_kwargs
    ) -> list[ContextBlock]:
        if not weather_summary:
            return []
        return [
            ContextBlock(
                key="weather",
                source="weather",
                purpose="天气摘要",
                content=weather_summary,
                priority=60,
                ttl_seconds=300,
            )
        ]


__all__ = [
    "ConversationSelector",
    "CycleSelector",
    "FarmSelector",
    "LedgerSelector",
    "RetrievalSelector",
    "UserSettingsSelector",
    "WeatherSelector",
]
