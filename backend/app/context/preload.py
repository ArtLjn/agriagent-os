"""Context 预热兼容适配。"""

import asyncio
import logging

logger = logging.getLogger(__name__)

PRELOAD_MAP: dict[str, list[str]] = {
    "get_weather_forecast": ["weather"],
    "get_cost_summary": ["cost_summary"],
    "get_debt_summary": ["cost_summary"],
    "get_cost_analytics": ["cost_analytics"],
    "get_farm_status": ["farm_status"],
    "get_crop_cycle_info": ["crop_cycle"],
    "get_recent_farm_logs": ["farm_logs"],
}


async def warm_tool_caches(
    selected_names: list[str],
    farm_id: int,
    farm_ctx: dict,
) -> None:
    """并行预热已选 tool 的底层缓存，失败不影响主流程。"""
    tasks = []
    for name in selected_names:
        data_types = PRELOAD_MAP.get(name, [])
        for data_type in data_types:
            if data_type == "weather" and farm_ctx.get("farm_location"):
                try:
                    from app.services.weather_service import fetch_weather

                    coords = farm_ctx.get("farm_coords", "")
                    lat = float(coords.split(",")[0]) if coords else None
                    lon = float(coords.split(",")[-1]) if coords else None
                    tasks.append(
                        fetch_weather(
                            location=farm_ctx["farm_location"],
                            lat=lat,
                            lon=lon,
                        )
                    )
                except ImportError:
                    pass

    if not tasks:
        return

    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=2.0,
        )
        logger.info("缓存预热完成 | tools=%s tasks=%d", selected_names, len(tasks))
    except asyncio.TimeoutError:
        logger.warning("缓存预热超时 2s | tools=%s", selected_names)


__all__ = ["PRELOAD_MAP", "warm_tool_caches"]
