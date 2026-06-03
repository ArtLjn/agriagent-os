"""LangGraph 图编译模块 — 自定义 StateGraph 实现并行 Skill 执行。"""

import asyncio
import json
import logging
import re
import threading
from datetime import date
import time as _time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from app.agent.llm import get_llm
from app.agent.state import AgentState
from app.infra.pending_actions import (
    PENDING_MARKER,
    is_write_skill,
    is_pending_tool_message,
    build_confirm_message,
    store_pending,
)
from app.agent.prompt_composer import get_composer
from app.agent.prompt_cache import get_farm_ctx_cache, get_prompt_cache
from app.core.date_context import get_request_date
from app.core.database import SessionLocal
from app.core.config import settings
from app.infra.trace_collector import get_collector
from app.infra.trace_context import increment_round
from app.models.farm import Farm
from app.models.user import User
from app.models.user_setting import UserSetting
from app.services.quota_service import check_quota
from app.agent.skills import get_langchain_tools
from app.agent.tool_selector import expand_by_chain, select_tools, LLMIntentClassifier

logger = logging.getLogger(__name__)

_LLM_SEMAPHORE = asyncio.Semaphore(5)

_classifier: LLMIntentClassifier | None = None
_classifier_lock = threading.Lock()


def _get_classifier() -> LLMIntentClassifier | None:
    global _classifier
    if _classifier is not None:
        return _classifier

    api_key = settings.ai_api_key
    base_url = settings.ai_base_url
    model = settings.ai_model

    # 优先从 Manager 获取轻量模型（tool-selection 角色）
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            info = manager.get_model_info(role="tool-selection")
            client = manager.get_sync_client(role="tool-selection")
            api_key = client.api_key
            base_url = client.base_url
            model = info["model"]
    except Exception as e:
        logger.debug("从 Manager 获取 classifier 参数失败 | error=%s", e)

    if api_key:
        with _classifier_lock:
            if _classifier is None:
                _classifier = LLMIntentClassifier(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                )
    return _classifier


def _get_season(current_date: date | None = None) -> str:
    """根据当前月份返回季节。"""
    if current_date is None:
        current_date = date.today()
    month = current_date.month
    if month in (3, 4, 5):
        return "春季"
    elif month in (6, 7, 8):
        return "夏季"
    elif month in (9, 10, 11):
        return "秋季"
    else:
        return "冬季"


def sliding_window_compact(
    messages: list, keep_rounds: int = 5
) -> list:
    """Sliding window 消息压缩：最近 N 轮完整保留，旧 ToolMessage 截断。

    一轮 = 从 HumanMessage 到下一个 HumanMessage 之前的所有消息。
    """
    if not messages:
        return messages

    round_starts = []
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            round_starts.append(i)

    if len(round_starts) <= keep_rounds:
        return messages

    compress_up_to = round_starts[-keep_rounds]

    result = list(messages)
    for i, msg in enumerate(result):
        if i >= compress_up_to:
            break
        if isinstance(msg, ToolMessage):
            content = msg.content or ""
            if len(content) > 50:
                tool_name = getattr(msg, "name", "unknown")
                result[i] = ToolMessage(
                    content=f"[已执行 {tool_name}]",
                    tool_call_id=msg.tool_call_id,
                )

    return result


def _should_continue(state: AgentState) -> str:
    """判断是否需要继续调用工具。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _find_last_human_message(messages: list) -> str:
    """从消息列表中找到最后一条 HumanMessage 的内容。"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content or ""
    return ""


def _extract_tool_calls_from_content(content: str) -> list[dict] | None:
    """从 LLM content 中解析 JSON 格式的伪工具调用，转换为 LangChain tool_calls 格式。

    兼容以下格式：
      {"name": "xxx", "parameters": {...}}
      {"action": "xxx", "args": {...}}
      {"tool": "xxx", "arguments": {...}}
      🌱 {"name": "xxx", "parameters": {...}}  （emoji 前缀）
      工具调用：{"name": "xxx", "parameters": {...}}  （文本前缀）
    """
    if not content:
        return None

    # 匹配 content 中的 JSON 对象（支持 emoji/文本前缀，支持多行）
    # 使用更宽松的匹配：先找到完整的 {...} 块，再验证内部结构
    # 前缀允许：行首、空白、emoji、任意非单词字符（覆盖中文文本前缀如"工具调用："）
    json_pattern = re.compile(
        r'(?:^|\s|\W)'  # 行首、空白或任意非单词字符（覆盖中文前缀）
        r'(\{[ \t\n\r]*"'  # 开始大括号
        r'(?:name|action|tool|function)'  # 工具名键
        r'"[ \t\n\r]*:[ \t\n\r]*"([^"]+)"'  # 工具名值
        r'[ \t\n\r]*,[ \t\n\r]*'
        r'"(?:parameters|params|args|arguments)"'  # 参数键
        r'[ \t\n\r]*:[ \t\n\r]*'  # 冒号
        r'(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})'  # 嵌套参数对象
        r'[ \t\n\r]*\})',  # 结束大括号
        re.DOTALL,
    )

    matches = list(json_pattern.finditer(content))
    if not matches:
        return None

    tool_calls: list[dict] = []
    for idx, m in enumerate(matches):
        tool_name = m.group(2)
        params_json = m.group(3)
        try:
            args = json.loads(params_json)
        except json.JSONDecodeError:
            logger.warning("Content JSON 参数解析失败 | tool=%s | raw=%s", tool_name, params_json[:200])
            continue
        tool_calls.append({
            "id": f"call_content_{idx}_{_time.time_ns()}",
            "name": tool_name,
            "args": args,
        })

    return tool_calls if tool_calls else None


def _detect_missed_tool_call(
    user_msg: str,
    llm_reply: str,
    selected_tools: list,
) -> tuple[bool, list]:
    """检测 LLM 是否应该在调用工具但返回了纯文本。

    启发式规则：
    1. 用户消息包含工具选择器匹配到的关键词
    2. LLM 回复包含"帮你"、"查询"等承诺性词汇但没有实际调用工具
    3. 有 selected_tools 被绑定但 LLM 未调用
    """
    if not selected_tools:
        return False, []

    # 承诺性词汇 = LLM 说要做某事但实际上没做
    promise_words = ["帮你", "为你", "查询", "查看", "获取", "调用", "处理"]
    has_promise = any(w in llm_reply for w in promise_words)

    # 如果 LLM 回复很短（<20字）且没有承诺词，可能是正常闲聊，不重试
    if len(llm_reply) < 20 and not has_promise:
        return False, []

    # 如果用户消息明显匹配某个工具的关键词，且 LLM 没有调用
    from app.agent.tool_selector import WRITE_PATTERNS, QUERY_TRIGGERS

    matched_tools = []
    for tool in selected_tools:
        # 检查 write patterns
        patterns = WRITE_PATTERNS.get(tool.name, [])
        for pat in patterns:
            if pat.search(user_msg):
                matched_tools.append(tool)
                break
        if tool in matched_tools:
            continue
        # 检查 query triggers
        triggers = QUERY_TRIGGERS.get(tool.name, set())
        for trigger in triggers:
            if trigger in user_msg:
                matched_tools.append(tool)
                break

    # 如果用户消息匹配了工具关键词，且 LLM 回复包含承诺词但没有调用工具
    if matched_tools and has_promise:
        return True, matched_tools

    return False, []


def _extract_tokens_used(response: AIMessage) -> int | None:
    """从 LLM 响应中提取 token 用量。"""
    try:
        usage = response.response_metadata.get("token_usage", {})
        total = usage.get("total_tokens")
        if total is not None:
            return int(total)
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _build_circuit_key(llm_instance) -> str:
    """从 LLM 实例构建 cooldown key（provider_name/model_id）。"""
    model_id = getattr(llm_instance, "model_name", "") or getattr(llm_instance, "model", "")
    base_url = ""
    try:
        base_url = getattr(llm_instance, "base_url", "") or llm_instance.openai_api_base
    except Exception:
        pass

    # 从 Manager chain 中匹配 provider name
    try:
        from app.core.llm_client_manager import get_llm_manager
        manager = get_llm_manager()
        if not manager.fallback_mode:
            for provider, model in manager.chain:
                if model.id == model_id and base_url and provider.base_url in base_url:
                    return f"{provider.name}/{model.id}"
    except Exception:
        pass
    return model_id or "unknown"


def _record_llm_failure(circuit_key: str, exc: Exception) -> None:
    """LLM 调用失败，记录到 Manager cooldown。"""
    try:
        from app.core.llm_client_manager import get_llm_manager, classify_error
        manager = get_llm_manager()
        if not manager.fallback_mode:
            level = classify_error(exc)
            manager.record_failure(circuit_key, error_level=level)
            logger.warning(
                "LLM 故障记录 | key=%s | level=%s | error=%s",
                circuit_key, level.value, str(exc)[:120],
            )
    except Exception as e:
        logger.debug("记录 LLM 故障失败 | error=%s", e)


def _record_llm_success(circuit_key: str) -> None:
    """LLM 调用成功，清除 cooldown。"""
    try:
        from app.core.llm_client_manager import get_llm_manager
        manager = get_llm_manager()
        if not manager.fallback_mode:
            manager.record_success(circuit_key)
    except Exception:
        pass


async def _get_farm_context(farm_id: int) -> dict:
    """异步获取农场上下文（位置、坐标、称呼、种植信息），带 5 分钟 TTL 缓存。"""
    cache = get_farm_ctx_cache()
    cached = cache.get(farm_id)
    if cached is not None:
        return cached

    def _query() -> dict:
        db = SessionLocal()
        try:
            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            display_name = "农友"
            user_city = ""
            user_lat = None
            user_lon = None
            active_crops = ""

            if farm and farm.user_id:
                user = db.query(User).filter(User.id == farm.user_id).first()
                if user:
                    display_name = user.nickname or display_name

                user_setting = (
                    db.query(UserSetting)
                    .filter(UserSetting.user_id == farm.user_id)
                    .first()
                )
                if user_setting:
                    user_city = user_setting.default_city or ""
                    user_lat = user_setting.default_lat
                    user_lon = user_setting.default_lon

                # 获取当前活跃的茬口信息
                try:
                    from app.models.cycle import CropCycle, CycleStage

                    cycles = (
                        db.query(CropCycle)
                        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
                        .all()
                    )
                    if cycles:
                        crop_infos = []
                        for cycle in cycles:
                            crop_name = cycle.name or "未知作物"
                            current_stage = (
                                db.query(CycleStage)
                                .filter(CycleStage.cycle_id == cycle.id, CycleStage.is_current == 1)
                                .first()
                            )
                            stage_name = current_stage.name if current_stage else "未知阶段"
                            crop_infos.append(f"{crop_name}({stage_name})")
                        active_crops = "、".join(crop_infos[:3])  # 最多3个
                except Exception:
                    pass  # 种植信息非关键，失败不影响主流程

            farm_location = user_city or (farm.location if farm and farm.location else "")

            farm_coords = ""
            if user_lat is not None and user_lon is not None:
                farm_coords = f"{user_lat:.4f},{user_lon:.4f}"

            return {
                "farm_location": farm_location,
                "farm_coords": farm_coords,
                "display_name": display_name,
                "active_crops": active_crops,
            }
        except Exception:
            logger.warning("获取农场上下文失败，使用默认值", exc_info=True)
            return {
                "farm_location": "",
                "farm_coords": "",
                "display_name": "农友",
                "active_crops": "",
            }
        finally:
            db.close()

    result = await asyncio.to_thread(_query)
    cache.set(farm_id, result)
    return result


_PRELOAD_MAP: dict[str, list[str]] = {
    "get_weather_forecast": ["weather"],
    "get_cost_summary": ["cost_summary"],
    "get_cost_analytics": ["cost_analytics"],
    "get_farm_status": ["farm_status"],
    "get_crop_cycle_info": ["crop_cycle"],
    "get_recent_farm_logs": ["farm_logs"],
}


async def _warm_tool_caches(
    selected_names: list[str], farm_id: int, farm_ctx: dict,
) -> None:
    """并行预热已选 tool 的底层缓存，2s 超时，失败不影响主流程。"""
    tasks = []
    for name in selected_names:
        data_types = _PRELOAD_MAP.get(name, [])
        for dt in data_types:
            if dt == "weather" and farm_ctx.get("farm_location"):
                try:
                    from app.services.weather_service import fetch_weather

                    coords = farm_ctx.get("farm_coords", "")
                    lat = float(coords.split(",")[0]) if coords else None
                    lon = float(coords.split(",")[-1]) if coords else None
                    tasks.append(fetch_weather(
                        location=farm_ctx["farm_location"],
                        lat=lat,
                        lon=lon,
                    ))
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


async def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    messages = state["messages"]

    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    pending_msgs = [m for m in tool_msgs if is_pending_tool_message(m)]
    normal_msgs = [m for m in tool_msgs if not is_pending_tool_message(m)]

    if pending_msgs and normal_msgs:
        summaries = []
        for m in normal_msgs:
            content = str(m.content or "")
            if content:
                summaries.append(content[:200])
        confirm_parts = []
        for m in pending_msgs:
            confirm = m.content.replace(PENDING_MARKER, "").strip()
            confirm_parts.append(confirm)
        combined = "\n\n".join(summaries) + "\n\n" + "\n\n".join(confirm_parts)
        logger.info(
            "混合 ToolMessage | pending=%d normal=%d | 跳过 LLM 合并回复",
            len(pending_msgs),
            len(normal_msgs),
        )
        return {"messages": [AIMessage(content=combined)]}

    if pending_msgs:
        confirm = pending_msgs[-1].content.replace(PENDING_MARKER, "").strip()
        logger.info("检测到 pending ToolMessage，跳过 LLM 直接确认 | text=%s", confirm)
        return {"messages": [AIMessage(content=confirm)]}

    farm_id = state.get("farm_id", 1)

    # 获取农场上下文（位置、坐标、称呼、种植信息）
    farm_ctx = await _get_farm_context(farm_id)
    display_name = farm_ctx["display_name"]
    farm_location = farm_ctx["farm_location"]

    tools = get_langchain_tools(farm_id=farm_id)
    has_tool_results = bool(tool_msgs)

    intent = state.get("intent", "agent")
    model_role = "lightweight" if intent == "query" else "generation"
    raw_llm = get_llm(role=model_role)
    logger.info("模型路由 | intent=%s | role=%s", intent, model_role)
    _circuit_key = _build_circuit_key(raw_llm)
    user_msg = _find_last_human_message(messages)
    selected_names = select_tools(
        user_msg, tools, intent_classifier=_get_classifier(),
        # user_location=farm_location,
    )
    if has_tool_results:
        selected_names_set = expand_by_chain(set(selected_names))
        selected_tools = [t for t in tools if t.name in selected_names_set]
    else:
        selected_tools = [t for t in tools if t.name in selected_names]
    if selected_tools:
        parallel = {"parallel_tool_calls": True} if settings.ai.parallel_tool_calls else {}
        llm = raw_llm.bind_tools(selected_tools, **parallel)
    else:
        llm = raw_llm
        logger.info("无匹配工具，LLM 直接回复（闲聊模式）")
    _round_idx = increment_round()
    collector = get_collector()

    current_date = get_request_date()
    date_str = str(current_date)
    prompt_cache = get_prompt_cache()

    cached_prompt = prompt_cache.get(farm_id=farm_id, date_str=date_str)
    if cached_prompt is not None:
        system_text = cached_prompt
    else:
        current_season = _get_season(current_date)
        system_text = get_composer().compose(
            "system_base",
            variables={
                "display_name": display_name,
                "farm_location": farm_location,
                "farm_coords": farm_ctx["farm_coords"],
                "current_season": current_season,
                "active_crops": farm_ctx["active_crops"],
            },
            current_date=current_date,
        )
        prompt_cache.set(farm_id=farm_id, date_str=date_str, value=system_text)

    # 记录 prompt_render trace
    collector.record(
        node_type="prompt_render",
        node_name="system_prompt",
        input_data={"template": "system_base", "variables_count": 2},
        output_data=system_text[:2000],
    )

    system = SystemMessage(content=system_text)
    messages = sliding_window_compact(state["messages"])
    input_summary = _find_last_human_message(state["messages"])[:200]

    # Token 配额检查
    if not check_quota(farm_id=farm_id):
        action = settings.token_quota.over_quota_action
        if action == "reject":
            logger.warning("Token 配额超限，拒绝调用（reject 模式）")
            return {"messages": [AIMessage(content="今日用量已达上限，明天再来吧。")]}
        elif action == "warn":
            logger.warning("Token 配额超限，继续调用（warn 模式）")

    # 并行缓存预热（与 LLM 调用并行执行）
    selected_names_for_preload = [t.name for t in selected_tools] if selected_tools else []
    preload_task = asyncio.create_task(
        _warm_tool_caches(selected_names_for_preload, farm_id, farm_ctx)
    )

    # LLM 调用 + 计时 + 请求内重试
    start = _time.perf_counter()
    max_retries = settings.ai.failover_max_retries
    response = None

    async with _LLM_SEMAPHORE:
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    raw_llm = get_llm(role=model_role)
                    _circuit_key = _build_circuit_key(raw_llm)
                    if selected_tools:
                        parallel = {"parallel_tool_calls": True} if settings.ai.parallel_tool_calls else {}
                        llm = raw_llm.bind_tools(selected_tools, **parallel)
                    else:
                        llm = raw_llm
                response = await llm.ainvoke([system] + messages)
                _record_llm_success(_circuit_key)
                break
            except Exception as exc:
                duration_ms = int((_time.perf_counter() - start) * 1000)
                model_name = getattr(raw_llm, "model_name", "unknown")
                _record_llm_failure(_circuit_key, exc)

                # 非可恢复错误（400 schema 错误等）不重试，直接抛出
                from app.core.llm_client_manager import classify_error, ErrorLevel
                error_level = classify_error(exc)
                if error_level == ErrorLevel.MODEL:
                    logger.warning(
                        "LLM 不可恢复错误，跳过重试 | key=%s | model=%s | level=%s",
                        _circuit_key, model_name, error_level.value,
                    )
                    collector.record(
                        node_type="llm_call",
                        node_name=model_name,
                        input_data=input_summary,
                        duration_ms=duration_ms,
                        error_message=str(exc),
                    )
                    raise

                logger.warning(
                    "LLM 重试 | attempt=%d/%d | key=%s | model=%s | latency_ms=%d | error=%s",
                    attempt + 1, max_retries, _circuit_key, model_name,
                    duration_ms, str(exc)[:120],
                )
                if attempt == max_retries - 1:
                    collector.record(
                        node_type="llm_call",
                        node_name=model_name,
                        input_data=input_summary,
                        duration_ms=duration_ms,
                        error_message=str(exc),
                    )
                    raise

    duration_ms = int((_time.perf_counter() - start) * 1000)
    model_name = getattr(raw_llm, "model_name", "unknown")

    # 等待预热完成（不阻塞，已并行运行）
    try:
        await asyncio.wait_for(preload_task, timeout=0.1)
    except (asyncio.TimeoutError, Exception):
        pass

    # 兼容层：部分 provider（如 nvidia llama-3.1）不支持 bind_tools，
    # LLM 会把工具调用 JSON 直接写进 content 而不是通过 tool_calls API。
    # 这里检测并手动解析，确保 graph 能正确路由到 tools 节点。
    if not response.tool_calls:
        parsed_tool_calls = _extract_tool_calls_from_content(response.content or "")
        if parsed_tool_calls:
            logger.info(
                "LLM content 中检测到工具调用 JSON，手动构造 tool_calls | tools=%s | model=%s",
                [tc["name"] for tc in parsed_tool_calls],
                model_name,
            )
            # 重建 AIMessage，保留原 metadata，注入 tool_calls
            response = AIMessage(
                content="",
                tool_calls=parsed_tool_calls,
                response_metadata=response.response_metadata,
                id=response.id,
            )

    # 检测"应该调用工具但未调用"的情况：用户消息匹配工具关键词，但 LLM 返回了纯文本
    if not response.tool_calls and response.content:
        should_retry, _ = _detect_missed_tool_call(
            user_msg, response.content, selected_tools
        )
        if should_retry and selected_tools:
            logger.warning(
                "检测到 LLM 应调用工具但未调用 | user_msg=%r | selected=%s | 尝试重试",
                user_msg[:80],
                [t.name for t in selected_tools],
            )
            retry_system = SystemMessage(
                content=system_text + "\n\n【重要提醒】用户的问题需要调用工具获取真实数据，请直接输出工具调用 JSON，不要回复文本。"
            )
            retry_messages = [retry_system] + messages
            try:
                retry_response = await llm.ainvoke(retry_messages)
                retry_parsed = _extract_tool_calls_from_content(retry_response.content or "")
                if retry_parsed:
                    logger.info("重试成功，LLM 输出了工具调用 | tools=%s", [tc["name"] for tc in retry_parsed])
                    response = AIMessage(
                        content="",
                        tool_calls=retry_parsed,
                        response_metadata=retry_response.response_metadata,
                        id=retry_response.id,
                    )
                else:
                    logger.warning("重试后 LLM 仍未输出工具调用，使用原回复")
            except Exception as retry_exc:
                logger.warning("重试调用失败 | error=%s", retry_exc)

    # 提取 token 用量
    tokens = _extract_tokens_used(response)
    token_usage = None
    if tokens is not None:
        usage_meta = response.response_metadata.get("token_usage", {})
        token_usage = {
            "prompt_tokens": usage_meta.get("prompt_tokens", 0),
            "completion_tokens": usage_meta.get("completion_tokens", 0),
            "total_tokens": tokens,
        }

    # LLM 工具选择日志
    if response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        logger.info("LLM 工具选择 | tool_calls=%s | model=%s", tool_names, model_name)
        output_summary = f"tool_calls: {tool_names}"
    else:
        content = response.content or ""
        logger.info("LLM 直接回复 | reply_len=%d | model=%s", len(content), model_name)
        output_summary = content[:200]

    collector.record(
        node_type="llm_call",
        node_name=model_name,
        input_data=input_summary,
        output_data=output_summary,
        duration_ms=duration_ms,
        token_usage=token_usage,
    )

    return {"messages": [response]}


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。写操作 Skill 拦截为 pending action。"""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    farm_id = state.get("farm_id", 1)
    tool_map = {t.name: t for t in get_langchain_tools(farm_id=farm_id)}
    collector = get_collector()

    # 获取用户原始输入（最近一条 HumanMessage）
    original_input = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            original_input = msg.content[:200]
            break

    async def _call_one(tc: dict) -> ToolMessage:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        logger.info("Skill 调用 %s(%s)", name, args)
        start = _time.perf_counter()

        tool = tool_map.get(name)

        # Pydantic 参数校验：在写操作拦截前校验，校验失败反馈 LLM 自纠错
        if tool and hasattr(tool, "args_schema") and tool.args_schema:
            try:
                tool.args_schema.model_validate(args)
            except Exception as e:
                error_msg = f"参数校验失败: {e}"
                logger.warning(
                    "Tool 参数校验失败 | name=%s | error=%s", name, e
                )
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                )

        # 写操作 Skill 拦截：存储 pending action，不直接执行
        if is_write_skill(name):
            action_id = store_pending(
                farm_id, name, args, original_input=original_input
            )
            logger.info(
                "写操作 Skill 已拦截 | farm=%s action_id=%s skill=%s",
                farm_id,
                action_id,
                name,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data="已拦截为 pending action",
                duration_ms=0,
            )
            confirm_text = build_confirm_message(
                name, args, original_input=original_input
            )
            return ToolMessage(
                content=f"{PENDING_MARKER} {confirm_text}",
                tool_call_id=tool_call_id,
            )

        # 读操作执行
        if not tool:
            return ToolMessage(
                content=f"未知工具: {name}", tool_call_id=tool_call_id
            )
        try:
            result = await tool.ainvoke(args)
            duration_ms = int((_time.perf_counter() - start) * 1000)
            summary = str(result)[:120].replace("\n", " ")
            logger.info(
                "Skill 完成 | name=%s | duration_ms=%d | result=%s",
                name,
                duration_ms,
                summary,
            )
            trace_output = getattr(result, "trace_data", None)
            if not trace_output:
                trace_output = {
                    "status": "success",
                    "reply_preview": str(result)[:500],
                }
            else:
                trace_output["reply_preview"] = str(result)[:500]
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data=trace_output,
                duration_ms=duration_ms,
            )
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            duration_ms = int((_time.perf_counter() - start) * 1000)
            logger.error(
                "Skill 失败 | name=%s | error=%s",
                name,
                e,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)

    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("并行执行 %d 个 Skill", len(last.tool_calls))
        batch_start = _time.perf_counter()
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])
        batch_duration = int((_time.perf_counter() - batch_start) * 1000)
        collector.record(
            node_type="parallel_batch",
            node_name=f"parallel_{len(results)}_skills",
            output_data={
                "parallel_count": len(results),
                "skills": [{"name": tc["name"]} for tc in last.tool_calls],
            },
            duration_ms=batch_duration,
        )

    return {"messages": results}


def compile_advisor_graph():
    """编译建议 Agent 的 StateGraph（支持并行 Skill 执行，最大 15 步）。"""
    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", _parallel_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


__all__ = ["compile_advisor_graph"]
