"""Agent 建议与报告 use case。"""

import asyncio
import logging
import time

from sqlalchemy.orm import Session

from app.application.chat_use_case import new_request_id
from app.models.farm import Farm
from app.schemas.agent import DailyAdviceResponse, ReportRequest, ReportResponse
from app.services.agent_service import (
    generate_report,
    get_daily_advice,
    refresh_daily_advice,
)

logger = logging.getLogger(__name__)


async def get_daily(
    db: Session, farm: Farm, cycle_id: int | None
) -> DailyAdviceResponse:
    """获取每日农事建议。"""
    rid = new_request_id()
    logger.info("[%s] GET /agent/daily | cycle_id=%s", rid, cycle_id)
    start = time.perf_counter()
    result = await _run_service_in_worker(
        get_daily_advice(db, farm_id=farm.id, cycle_id=cycle_id, user_id=farm.user_id)
    )
    logger.info("[%s] /agent/daily 完成 | 耗时 %.2fs", rid, time.perf_counter() - start)
    return result


async def refresh_daily(
    db: Session, farm: Farm, cycle_id: int | None
) -> DailyAdviceResponse:
    """强制刷新每日农事建议。"""
    rid = new_request_id()
    logger.info("[%s] POST /agent/daily/refresh | cycle_id=%s", rid, cycle_id)
    start = time.perf_counter()
    result = await _run_service_in_worker(
        refresh_daily_advice(
            db, farm_id=farm.id, cycle_id=cycle_id, user_id=farm.user_id
        )
    )
    logger.info(
        "[%s] /agent/daily/refresh 完成 | 耗时 %.2fs",
        rid,
        time.perf_counter() - start,
    )
    return result


async def create_report(
    db: Session, farm: Farm, report_request: ReportRequest
) -> ReportResponse:
    """生成种植周期报告。"""
    rid = new_request_id()
    logger.info(
        "[%s] POST /agent/report | type=%s cycle_id=%s",
        rid,
        report_request.report_type,
        report_request.cycle_id,
    )
    start = time.perf_counter()
    result = await _run_service_in_worker(
        generate_report(
            db,
            farm_id=farm.id,
            cycle_id=report_request.cycle_id,
            report_type=report_request.report_type,
        )
    )
    logger.info(
        "[%s] /agent/report 完成 | 耗时 %.2fs", rid, time.perf_counter() - start
    )
    return result


async def _run_service_in_worker(coro):
    """避免同步 service 内的 Mongo bridge 在主事件循环里同步阻塞。"""
    return await asyncio.to_thread(lambda: asyncio.run(coro))
