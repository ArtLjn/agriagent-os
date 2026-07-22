"""Load ORM models for metadata registration."""

from app.agent.guardrails.models import GuardrailsLog
from app.agent.models import AgentRecord
from app.agent.pending_plan_models import AgentPendingPlan, AgentPendingPlanStep
from app.agent.turn_models import AgentTurn
from app.context.task_state_models import AgentTaskState
from app.domains.conversation.feedback_models import FeedbackRecord
from app.domains.conversation.models import Conversation, ConversationMessage
from app.domains.farm.models import Farm
from app.domains.finance.cost_category_models import CostCategory
from app.domains.finance.cost_models import CostRecord
from app.domains.planting.crop_models import CropTemplate, GrowthStage
from app.domains.planting.cycle_models import CropCycle, CycleStage
from app.domains.planting.log_models import FarmLog
from app.domains.planting.models import (
    LaborEntry,
    OperationWorkOrder,
    OperationWorkOrderUnit,
    PlantingUnit,
    Worker,
)
from app.domains.users.models import User
from app.domains.users.settings_models import UserSetting
from app.platforms.data_flywheel.models import (
    AgentCaseDraft,
    AgentDataFlywheelLabel,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.platforms.evaluation.token_stats_models import TokenDailyStats
from app.platforms.evaluation.trace_models import TraceRecord
from app.platforms.simulation.orm_models import SimulationResultRecord, SimulationRun
from app.shared.idempotency_models import IdempotencyKey
from app.shared.mongo_compensation_models import MongoCompensationTask

__all__ = [
    "AgentCaseDraft",
    "AgentDataFlywheelLabel",
    "AgentDataFlywheelPrelabel",
    "AgentPendingPlan",
    "AgentPendingPlanStep",
    "AgentRecord",
    "AgentRepairPack",
    "AgentTaskState",
    "AgentReviewIssueChain",
    "AgentTurn",
    "Conversation",
    "ConversationMessage",
    "CostCategory",
    "CostRecord",
    "CropCycle",
    "CropTemplate",
    "CycleStage",
    "Farm",
    "FarmLog",
    "FeedbackRecord",
    "GrowthStage",
    "GuardrailsLog",
    "IdempotencyKey",
    "LaborEntry",
    "MongoCompensationTask",
    "OperationWorkOrder",
    "OperationWorkOrderUnit",
    "PlantingUnit",
    "SimulationResultRecord",
    "SimulationRun",
    "TokenDailyStats",
    "TraceRecord",
    "User",
    "UserSetting",
    "Worker",
]
