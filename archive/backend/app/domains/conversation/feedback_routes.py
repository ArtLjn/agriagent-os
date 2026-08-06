"""反馈 API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.users.dependencies import get_current_user
from app.domains.users.models import User
from app.domains.conversation.feedback_schemas import FeedbackRequest, FeedbackResponse
from app.domains.conversation.feedback_service import get_feedback_stats, submit_feedback

router = APIRouter(prefix="/agent", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """提交 AI 回复评价。"""
    record = submit_feedback(db, user.id, req.message_id, req.rating, req.correction)
    return FeedbackResponse.model_validate(record)


@router.get("/feedback/stats")
def feedback_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取反馈统计。"""
    return get_feedback_stats(db)
