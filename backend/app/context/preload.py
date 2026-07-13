"""Context 预热兼容适配。"""

import asyncio
import logging

logger = logging.getLogger(__name__)

PRELOAD_MAP: dict[str, list[str]] = {
    "get_weather_forecast": ["weather"],
    "manage_cost": ["cost_summary", "cost_analytics"],
    "get_farm_status": ["farm_status"],
    "get_crop_cycle_info": ["crop_cycle"],
    "get_recent_farm_logs": ["farm_logs"],
}

DEPENDENCY_PRELOAD_MAP: dict[str, str] = {
    "weather": "weather",
    "crop_cycle": "crop_cycle",
    "crop_cycles": "crop_cycle",
    "active_cycles": "crop_cycle",
    "workers": "workers",
    "planting_units": "planting_units",
    "ledger": "cost_summary",
    "recent_operations": "farm_logs",
}


def dependencies_to_preload_types(dependencies: list[str]) -> list[str]:
    """将 Router context_dependencies 转为预热数据类型。"""
    data_types: list[str] = []
    for dependency in dependencies:
        data_type = DEPENDENCY_PRELOAD_MAP.get(dependency)
        if data_type is None or data_type in data_types:
            continue
        data_types.append(data_type)
    return data_types


async def warm_tool_caches(
    selected_names: list[str],
    farm_id: int,
    farm_ctx: dict,
    context_dependencies: list[str] | None = None,
) -> None:
    """并行预热已选 tool 的底层缓存，失败不影响主流程。"""
    tasks = []
    preload_types = dependencies_to_preload_types(context_dependencies or [])
    for name in selected_names:
        for data_type in PRELOAD_MAP.get(name, []):
            if data_type not in preload_types:
                preload_types.append(data_type)

    for data_type in preload_types:
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
        logger.info(
            "缓存预热完成 | tools=%s dependencies=%s tasks=%d",
            selected_names,
            context_dependencies or [],
            len(tasks),
        )
    except asyncio.TimeoutError:
        logger.warning("缓存预热超时 2s | tools=%s", selected_names)


__all__ = [
    "DEPENDENCY_PRELOAD_MAP",
    "PRELOAD_MAP",
    "dependencies_to_preload_types",
    "warm_tool_caches",
]
