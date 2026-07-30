#!/usr/bin/env python3
"""只读分析 farm-manager Agent 请求链路。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

PREVIEW_LIMIT = 220
DEFAULT_LIMIT = 5
MAX_LIMIT = 50
SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}


@dataclass
class EvidenceStatus:
    mysql: str
    mongo: str
    events: str


@dataclass
class TraceNode:
    source: str
    storage_id: str | None
    request_id: str
    session_id: str | None
    farm_id: int | None
    conversation_message_id: int | None
    round_index: int | None
    node_type: str
    node_name: str
    status: str | None
    duration_ms: int | None
    token_total: int | None
    error_message: str | None
    input_data: Any
    output_data: Any
    started_at: str | None
    sort_key: str


@dataclass
class TurnItem:
    source: str
    id: int | None
    request_id: str | None
    session_id: str | None
    status: str | None
    latency_ms: int | None
    tool_calls_count: int | None
    token_total: int | None
    input_preview: str | None
    reply_preview: str | None
    event_file: str | None
    event_seq_start: int | None
    event_seq_end: int | None


@dataclass
class MessageItem:
    source: str
    storage_id: str | None
    role: str | None
    content: str | None
    created_at: str | None
    turn_id: int | None
    session_id: str | None
    farm_id: int | None
    meta: dict[str, Any] | None
    event_file: str | None
    event_seq_range: list[int | None] | None


@dataclass
class EventItem:
    seq: int | None
    event_type: str | None
    request_id: str | None
    turn_id: int | None
    payload: Any


@dataclass
class ChainReport:
    target: dict[str, Any]
    status: EvidenceStatus
    resolved: dict[str, Any]
    turns: list[TurnItem]
    trace_nodes: list[TraceNode]
    messages: list[MessageItem]
    events: list[EventItem]
    errors: list[str]
    suggestions: list[str]


def main() -> int:
    args = parse_args()
    project = Path(args.project).expanduser().resolve()
    report = asyncio.run(build_report(project, args))
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str))
    else:
        print(format_markdown(report, include_payload=args.include_payload))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读分析 farm-manager Agent 链路")
    parser.add_argument("--project", default=".", help="项目根目录，默认当前目录")
    parser.add_argument("--request-id", help="完整 request_id 或前缀")
    parser.add_argument("--session-id", help="session_id")
    parser.add_argument("--turn-id", type=int, help="agent_turns.id")
    parser.add_argument("--farm-id", type=int, help="可选 farm_id 过滤")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="会话最近轮数")
    parser.add_argument(
        "--include-payload", action="store_true", help="展示输入输出摘要"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


async def build_report(project: Path, args: argparse.Namespace) -> ChainReport:
    if not args.request_id and not args.session_id and args.turn_id is None:
        return ChainReport(
            target=target_dict(args),
            status=EvidenceStatus("skipped", "skipped", "skipped"),
            resolved={},
            turns=[],
            trace_nodes=[],
            messages=[],
            events=[],
            errors=["缺少定位参数：请提供 --request-id、--session-id 或 --turn-id"],
            suggestions=[
                "先从日志或前端请求中复制 request_id；只有短 ID 时也可以按前缀查询。"
            ],
        )

    backend = project / "backend"
    sys.path.insert(0, str(backend if backend.exists() else project))
    mysql_data, mysql_status = query_mysql(args)
    mongo_data, mongo_status = await query_mongo(args)

    turns = mysql_data.get("turns", [])
    trace_nodes = merge_nodes(
        mysql_data.get("trace_nodes", []), mongo_data.get("trace_nodes", [])
    )
    messages = [*mysql_data.get("messages", []), *mongo_data.get("messages", [])]
    request_ids = collect_request_ids(turns, trace_nodes, messages, args.request_id)
    resolved = build_resolved_scope(turns, trace_nodes, messages, request_ids)
    events, events_status = read_events(project, turns, messages, args, request_ids)

    errors = collect_errors(trace_nodes, events)
    suggestions = build_suggestions(
        turns=turns,
        mysql_nodes=mysql_data.get("trace_nodes", []),
        mongo_nodes=mongo_data.get("trace_nodes", []),
        all_nodes=trace_nodes,
        mysql_status=mysql_status,
        mongo_status=mongo_status,
        events_status=events_status,
    )
    return ChainReport(
        target=target_dict(args),
        status=EvidenceStatus(
            mysql=mysql_status, mongo=mongo_status, events=events_status
        ),
        resolved=resolved,
        turns=turns,
        trace_nodes=trace_nodes,
        messages=messages,
        events=events,
        errors=errors,
        suggestions=suggestions,
    )


def query_mysql(args: argparse.Namespace) -> tuple[dict[str, list[Any]], str]:
    try:
        from sqlalchemy import inspect as sa_inspect
        from sqlalchemy import or_

        from app.agent.turn_models import AgentTurn
        from app.domains.conversation.models import Conversation, ConversationMessage
        from app.platforms.evaluation.trace_models import TraceRecord
        from app.shared.database import SessionLocal
    except Exception as exc:
        return (
            empty_data(),
            f"unavailable(code=mysql_import_failed,error={preview(str(exc))})",
        )

    db = SessionLocal()
    try:
        missing: list[str] = []
        errors: list[str] = []
        inspector = sa_inspect(db.get_bind())

        turn_rows: list[Any] = []
        if table_exists(inspector, "agent_turns"):
            try:
                turn_rows = query_turn_rows(db, AgentTurn, args, or_)
            except Exception as exc:
                errors.append(f"agent_turns={preview(str(exc))}")
        else:
            missing.append("agent_turns")

        request_ids = collect_request_ids_from_rows(turn_rows, args.request_id)

        trace_rows: list[Any] = []
        if table_exists(inspector, "trace_records"):
            try:
                trace_rows = query_trace_rows(db, TraceRecord, args, request_ids, or_)
            except Exception as exc:
                errors.append(f"trace_records={preview(str(exc))}")
        else:
            missing.append("trace_records")

        message_rows: list[Any] = []
        if table_exists(inspector, "conversations") and table_exists(
            inspector, "conversation_messages"
        ):
            try:
                message_rows = query_message_rows(
                    db, Conversation, ConversationMessage, turn_rows, args
                )
            except Exception as exc:
                errors.append(f"conversation_messages={preview(str(exc))}")
        else:
            missing.append("conversation_messages")

        status = mysql_status(missing=missing, errors=errors)
        return {
            "turns": [turn_from_row(row) for row in turn_rows],
            "trace_nodes": [node_from_mysql(row) for row in trace_rows],
            "messages": [message_from_mysql(row) for row in message_rows],
        }, status
    except Exception as exc:
        return empty_data(), f"error(code=mysql_query_failed,error={preview(str(exc))})"
    finally:
        db.close()


def query_turn_rows(
    db: Any, AgentTurn: Any, args: argparse.Namespace, or_: Any
) -> list[Any]:
    query = db.query(AgentTurn)
    if args.farm_id is not None:
        query = query.filter(AgentTurn.farm_id == args.farm_id)
    if args.turn_id is not None:
        return query.filter(AgentTurn.id == args.turn_id).all()
    if args.request_id:
        return (
            query.filter(
                or_(
                    AgentTurn.request_id == args.request_id,
                    AgentTurn.request_id.like(f"{args.request_id}%"),
                )
            )
            .order_by(AgentTurn.created_at.desc(), AgentTurn.id.desc())
            .limit(clamp(args.limit, 1, MAX_LIMIT))
            .all()
        )
    if args.session_id:
        return (
            query.filter(AgentTurn.session_id == args.session_id)
            .order_by(AgentTurn.created_at.desc(), AgentTurn.id.desc())
            .limit(clamp(args.limit, 1, MAX_LIMIT))
            .all()
        )
    return []


def query_trace_rows(
    db: Any,
    TraceRecord: Any,
    args: argparse.Namespace,
    request_ids: list[str],
    or_: Any,
) -> list[Any]:
    query = db.query(TraceRecord)
    if args.farm_id is not None:
        query = query.filter(TraceRecord.farm_id == args.farm_id)
    if request_ids:
        query = query.filter(TraceRecord.request_id.in_(request_ids))
    elif args.request_id:
        query = query.filter(
            or_(
                TraceRecord.request_id == args.request_id,
                TraceRecord.request_id.like(f"{args.request_id}%"),
            )
        )
    elif args.session_id:
        query = query.filter(TraceRecord.session_id == args.session_id)
    else:
        return []
    return (
        query.order_by(
            TraceRecord.request_id.asc(),
            TraceRecord.round_index.asc(),
            TraceRecord.start_time.asc(),
            TraceRecord.id.asc(),
        )
        .limit(300)
        .all()
    )


def query_message_rows(
    db: Any,
    Conversation: Any,
    ConversationMessage: Any,
    turns: list[Any],
    args: argparse.Namespace,
) -> list[Any]:
    message_ids = {
        value
        for turn in turns
        for value in (
            getattr(turn, "user_message_id", None),
            getattr(turn, "assistant_message_id", None),
        )
        if value
    }
    query = db.query(ConversationMessage).join(
        Conversation, Conversation.id == ConversationMessage.conversation_id
    )
    if args.farm_id is not None:
        query = query.filter(Conversation.farm_id == args.farm_id)
    if message_ids:
        return (
            query.filter(ConversationMessage.id.in_(message_ids))
            .order_by(
                ConversationMessage.created_at.asc(), ConversationMessage.id.asc()
            )
            .all()
        )
    if args.session_id:
        return (
            query.filter(Conversation.session_id == args.session_id)
            .order_by(
                ConversationMessage.created_at.desc(), ConversationMessage.id.desc()
            )
            .limit(40)
            .all()
        )
    return []


async def query_mongo(args: argparse.Namespace) -> tuple[dict[str, list[Any]], str]:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        from app.shared.config import settings
    except Exception as exc:
        return (
            empty_data(),
            f"unavailable(code=mongo_import_failed,error={preview(str(exc))})",
        )

    config = getattr(settings, "mongodb", None)
    if (
        not config
        or not getattr(config, "enabled", False)
        or not getattr(config, "uri", "")
    ):
        return empty_data(), "disabled(code=mongo_not_configured)"

    client = AsyncIOMotorClient(
        config.uri,
        tls=getattr(config, "tls", False),
        connectTimeoutMS=getattr(config, "connect_timeout_ms", 2000),
        serverSelectionTimeoutMS=getattr(config, "server_selection_timeout_ms", 2000),
        maxPoolSize=getattr(config, "max_pool_size", 20),
    )
    try:
        db = client[getattr(config, "database", "farm_manager")]
        await client.admin.command("ping")
        trace_docs = await mongo_trace_docs(db, args)
        message_docs = await mongo_message_docs(db, args, trace_docs)
        return {
            "trace_nodes": [node_from_mongo(doc) for doc in trace_docs],
            "messages": [message_from_mongo(doc) for doc in message_docs],
        }, "ok"
    except Exception as exc:
        return empty_data(), f"error(code=mongo_query_failed,error={preview(str(exc))})"
    finally:
        client.close()


async def mongo_trace_docs(db: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    filter_doc: dict[str, Any] = {}
    if args.farm_id is not None:
        filter_doc["farmId"] = args.farm_id
    if args.request_id:
        filter_doc["requestId"] = {"$regex": f"^{escape_regex(args.request_id)}"}
    elif args.session_id:
        filter_doc["sessionId"] = args.session_id
    else:
        return []
    cursor = (
        db["traceRecords"]
        .find(filter_doc)
        .sort([("requestId", 1), ("roundIndex", 1), ("startTime", 1)])
        .limit(300)
    )
    return await cursor.to_list(None)


async def mongo_message_docs(
    db: Any, args: argparse.Namespace, trace_docs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    base_filter: dict[str, Any] = {}
    if args.farm_id is not None:
        base_filter["farmId"] = args.farm_id

    if args.request_id and not args.session_id and args.turn_id is None:
        primary_filter = {
            **base_filter,
            "meta.trace_request_id": {"$regex": f"^{escape_regex(args.request_id)}"},
        }
        primary_docs = await (
            db["conversationMessages"]
            .find(primary_filter)
            .sort([("createdAt", 1), ("mysqlId", 1)])
            .limit(20)
            .to_list(None)
        )
        turn_ids = sorted(
            {
                int(doc.get("turnId"))
                for doc in primary_docs
                if doc.get("turnId") is not None
            }
        )
        session_ids = sorted(
            {
                str(doc.get("sessionId"))
                for doc in primary_docs
                if doc.get("sessionId") is not None
            }
        )
        farm_ids = sorted(
            {
                int(doc.get("farmId"))
                for doc in primary_docs
                if doc.get("farmId") is not None
            }
        )
        if not turn_ids:
            return primary_docs
        companion_filter: dict[str, Any] = {**base_filter, "turnId": {"$in": turn_ids}}
        if session_ids:
            companion_filter["sessionId"] = {"$in": session_ids}
        if "farmId" not in companion_filter and farm_ids:
            companion_filter["farmId"] = {"$in": farm_ids}
        companion_docs = await (
            db["conversationMessages"]
            .find(companion_filter)
            .sort([("createdAt", 1), ("mysqlId", 1)])
            .limit(40)
            .to_list(None)
        )
        return unique_mongo_docs([*primary_docs, *companion_docs])

    filters: list[dict[str, Any]] = []
    request_ids = sorted(
        {
            str(doc.get("requestId"))
            for doc in trace_docs
            if doc.get("requestId") is not None
        }
    )
    session_ids = sorted(
        {
            str(doc.get("sessionId"))
            for doc in trace_docs
            if doc.get("sessionId") is not None
        }
    )
    farm_ids = sorted(
        {int(doc.get("farmId")) for doc in trace_docs if doc.get("farmId") is not None}
    )

    if args.request_id:
        filters.append(
            {"meta.trace_request_id": {"$regex": f"^{escape_regex(args.request_id)}"}}
        )
    if request_ids:
        filters.append({"meta.trace_request_id": {"$in": request_ids}})
    if args.session_id:
        filters.append({"sessionId": args.session_id})
    if session_ids:
        filters.append({"sessionId": {"$in": session_ids}})
    if args.turn_id is not None:
        filters.append({"turnId": args.turn_id})
    if not filters:
        return []
    filter_doc: dict[str, Any] = {"$or": filters}
    filter_doc.update(base_filter)
    if "farmId" not in filter_doc and farm_ids:
        filter_doc["farmId"] = {"$in": farm_ids}
    cursor = (
        db["conversationMessages"]
        .find(filter_doc)
        .sort([("createdAt", 1), ("mysqlId", 1)])
        .limit(40)
    )
    return await cursor.to_list(None)


def read_events(
    project: Path,
    turns: list[TurnItem],
    messages: list[MessageItem],
    args: argparse.Namespace,
    request_ids: list[str],
) -> tuple[list[EventItem], str]:
    event_files = list(
        dict.fromkeys(
            [
                Path(item.event_file)
                for item in [*turns, *messages]
                if getattr(item, "event_file", None)
            ]
        )
    )
    if not event_files and args.session_id:
        event_files = sorted(
            (project / "data" / "agent-events").glob(
                f"dt=*/farm_id=*/session_id={args.session_id}/events.jsonl"
            )
        )[-5:]
    if not event_files:
        return [], "missing(code=event_file_not_found)"

    items: list[EventItem] = []
    errors: list[str] = []
    for file_path in event_files:
        path = file_path if file_path.is_absolute() else project / file_path
        try:
            items.extend(read_event_file(path, request_ids, turns, messages))
        except Exception as exc:
            errors.append(f"{path}: {preview(str(exc))}")
    if errors and not items:
        return [], f"error(code=event_read_failed,error={'; '.join(errors[:2])})"
    return items[:120], "ok" if items else "missing(code=event_not_matched)"


def read_event_file(
    path: Path,
    request_ids: list[str],
    turns: list[TurnItem],
    messages: list[MessageItem],
) -> list[EventItem]:
    seq_ranges = {
        item.id: (item.event_seq_start, item.event_seq_end)
        for item in turns
        if item.id is not None and item.event_seq_start is not None
    }
    for message in messages:
        if message.turn_id is None or not message.event_seq_range:
            continue
        seq_ranges.setdefault(
            message.turn_id,
            (
                message.event_seq_range[0],
                message.event_seq_range[1]
                if len(message.event_seq_range) > 1
                else None,
            ),
        )
    request_set = set(request_ids)
    items: list[EventItem] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            doc = json.loads(line)
            seq = doc.get("seq")
            request_id = doc.get("request_id")
            turn_id = doc.get("turn_id")
            if request_set and request_id not in request_set:
                continue
            if (
                not request_set
                and seq_ranges
                and not in_any_seq_range(turn_id, seq, seq_ranges)
            ):
                continue
            items.append(
                EventItem(
                    seq=seq,
                    event_type=doc.get("event_type"),
                    request_id=request_id,
                    turn_id=turn_id,
                    payload=redact(doc.get("payload")),
                )
            )
    return items


def in_any_seq_range(
    turn_id: int | None,
    seq: int | None,
    seq_ranges: dict[int | None, tuple[int | None, int | None]],
) -> bool:
    if turn_id not in seq_ranges or seq is None:
        return False
    start, end = seq_ranges[turn_id]
    return start is not None and seq >= start and (end is None or seq <= end)


def format_markdown(report: ChainReport, *, include_payload: bool) -> str:
    lines = ["链路追踪分析", ""]
    lines.append("目标:")
    for key, value in report.target.items():
        if value not in (None, False):
            lines.append(f"- {key}: {value}")
    if report.resolved:
        lines.extend(["", "解析范围:"])
        for key, value in report.resolved.items():
            if value:
                lines.append(f"- {key}: {value}")
    lines.extend(["", "证据状态:"])
    lines.append(f"- MySQL: {report.status.mysql}")
    lines.append(f"- Mongo: {report.status.mongo}")
    lines.append(f"- JSONL events: {report.status.events}")
    lines.append(
        f"- trace_nodes: mysql={count_source(report.trace_nodes, 'mysql')} mongo={count_source(report.trace_nodes, 'mongo')}"
    )
    lines.append(
        f"- messages: mysql={count_source(report.messages, 'mysql')} mongo={count_source(report.messages, 'mongo')}"
    )
    lines.extend(format_turns(report.turns))
    lines.extend(format_nodes(report.trace_nodes, include_payload=include_payload))
    lines.extend(format_audit_block(report))
    lines.extend(format_messages(report.messages))
    lines.extend(format_events(report.events))
    lines.extend(["", "错误节点:"])
    lines.extend([f"- {item}" for item in report.errors] or ["- 未发现显式错误"])
    lines.extend(["", "排查建议:"])
    lines.extend([f"- {item}" for item in report.suggestions])
    return "\n".join(lines)


def format_turns(turns: list[TurnItem]) -> list[str]:
    if not turns:
        return ["", "Turn: 未命中 agent_turns"]
    lines = ["", "Turn:"]
    for item in sorted(turns, key=lambda row: row.id or 0):
        lines.append(
            f"- turn_id={item.id} request_id={item.request_id} session_id={item.session_id} "
            f"status={item.status} latency={item.latency_ms or '-'}ms "
            f"tools={item.tool_calls_count or 0} tokens={item.token_total or '-'}"
        )
        if item.input_preview:
            lines.append(f"  input: {preview(item.input_preview)}")
        if item.reply_preview:
            lines.append(f"  reply: {preview(item.reply_preview)}")
    return lines


def format_nodes(nodes: list[TraceNode], *, include_payload: bool) -> list[str]:
    if not nodes:
        return ["", "Trace 时间线: 未命中 trace 节点"]
    lines = ["", "Trace 时间线:"]
    for index, node in enumerate(nodes, 1):
        lines.append(
            f"{index}. [{node.source}] r{node.round_index} {node.node_type}.{node.node_name} "
            f"status={node.status} duration={node.duration_ms or 0}ms tokens={node.token_total or '-'}"
        )
        if node.error_message:
            lines.append(f"   error={preview(node.error_message)}")
        if include_payload:
            lines.append(f"   input={json_preview(node.input_data)}")
            lines.append(f"   output={json_preview(node.output_data)}")
    lines.extend(format_hotspots(nodes))
    return lines


def format_hotspots(nodes: list[TraceNode]) -> list[str]:
    slow = sorted(nodes, key=lambda item: item.duration_ms or 0, reverse=True)[:3]
    counts = Counter(f"{item.node_type}.{item.node_name}" for item in nodes)
    skills = [item.node_name for item in nodes if item.node_type == "skill_call"]
    return [
        "",
        "耗时热点:",
        "- 最慢节点: "
        + ", ".join(
            f"{item.node_type}.{item.node_name}={item.duration_ms or 0}ms"
            for item in slow
        ),
        "- 节点分布: "
        + ", ".join(f"{name}x{count}" for name, count in counts.most_common(8)),
        f"- 工具调用: {', '.join(skills) if skills else '无'}",
    ]


def format_audit_block(report: ChainReport) -> list[str]:
    final_context = find_node(report.trace_nodes, "final_context", "build")
    output_guard = find_node(
        report.trace_nodes, "output_guard", "final_json_leak_check"
    )
    data_source = find_node(report.trace_nodes, "response", "final_reply_data_source")
    if final_context is None and output_guard is None and data_source is None:
        return ["", "审计追踪: 未记录 final_response 审计节点"]

    turn = report.turns[0] if report.turns else None
    request_id = (
        (final_context or output_guard or data_source).request_id
        if (final_context or output_guard or data_source)
        else None
    )
    final_output = output_dict(final_context)
    guard_output = output_dict(output_guard)
    source_output = output_dict(data_source)
    tool_results = (
        final_output.get("tool_results") if isinstance(final_output, dict) else None
    )
    lines = ["", "审计追踪:"]
    lines.append(f"[审计追踪] {value_or_unknown(request_id)} final_response")
    lines.append(f"工单 ID: {value_or_unknown(getattr(turn, 'id', None))}")
    lines.append(f"Run ID: {value_or_unknown(request_id)}")
    lines.append(f"Trace ID: {value_or_unknown(request_id)}")
    lines.append(
        "边界: "
        + ("AI 可接 / Final Agent 隔离" if final_context or output_guard else "未记录")
    )
    lines.append(
        "SOP: "
        + (
            "final_context_valid -> tool_choice_none -> output_guard_check"
            if output_guard
            else "未记录"
        )
    )
    lines.append(f"工具: {tool_result_names(tool_results)}")
    lines.append(
        "工具结果: "
        f"count={value_or_unknown(final_output.get('tool_result_count'))} "
        f"source={value_or_unknown(source_output.get('data_source'))}"
    )
    lines.append(
        "最终动作: "
        + value_or_unknown(guard_output.get("action") or getattr(turn, "status", None))
    )
    lines.append(
        "结果: "
        + value_or_unknown(
            getattr(turn, "reply_preview", None) or guard_output.get("leak_type")
        )
    )
    lines.append(
        "耗时: "
        + value_or_unknown(
            getattr(turn, "latency_ms", None)
            or getattr(
                output_guard or final_context or data_source, "duration_ms", None
            )
        )
        + "ms"
    )
    return lines


def find_node(
    nodes: list[TraceNode], node_type: str, node_name: str
) -> TraceNode | None:
    for node in nodes:
        if node.node_type == node_type and node.node_name == node_name:
            return node
    return None


def output_dict(node: TraceNode | None) -> dict[str, Any]:
    if node is None:
        return {}
    return node.output_data if isinstance(node.output_data, dict) else {}


def tool_result_names(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "未记录"
    names: list[str] = []
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        names.append(
            f"{value_or_unknown(item.get('tool_name'))}"
            f"({value_or_unknown(item.get('status'))})"
        )
    return ", ".join(names) if names else "未记录"


def value_or_unknown(value: Any) -> str:
    if value in (None, ""):
        return "未记录"
    return preview(value, limit=120)


def format_messages(messages: list[MessageItem]) -> list[str]:
    if not messages:
        return ["", "消息证据: 未命中 conversation_messages"]
    lines = ["", "消息证据:"]
    for item in messages[:10]:
        meta_bits = []
        trace_request_id = (item.meta or {}).get("trace_request_id")
        if trace_request_id:
            meta_bits.append(f"trace_request_id={trace_request_id}")
        if item.event_file:
            meta_bits.append(f"event_file={item.event_file}")
        suffix = f" ({', '.join(meta_bits)})" if meta_bits else ""
        lines.append(
            f"- [{item.source}] {item.role} turn_id={item.turn_id} "
            f"session_id={item.session_id}{suffix}: {preview(item.content)}"
        )
    return lines


def format_events(events: list[EventItem]) -> list[str]:
    if not events:
        return ["", "事件证据: 未命中 JSONL event"]
    lines = ["", "事件证据:"]
    for item in events[:12]:
        lines.append(
            f"- seq={item.seq} type={item.event_type} request_id={item.request_id} payload={json_preview(item.payload)}"
        )
    return lines


def collect_errors(nodes: list[TraceNode], events: list[EventItem]) -> list[str]:
    errors = [
        f"{node.request_id} r{node.round_index} {node.node_type}.{node.node_name}: {preview(node.error_message or json_preview(node.output_data))}"
        for node in nodes
        if node.status not in (None, "success") or node.error_message
    ]
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        status = payload.get("status")
        if status and status != "success":
            errors.append(
                f"event seq={event.seq} {event.event_type}: status={status} payload={json_preview(payload)}"
            )
    return errors[:12]


def build_suggestions(
    *,
    turns: list[TurnItem],
    mysql_nodes: list[TraceNode],
    mongo_nodes: list[TraceNode],
    all_nodes: list[TraceNode],
    mysql_status: str,
    mongo_status: str,
    events_status: str,
) -> list[str]:
    suggestions: list[str] = []
    if turns and not all_nodes:
        suggestions.append(
            "turn 存在但 trace 为空，检查 TraceDAO flush、trace_context 或 storage.trace。"
        )
    if mysql_nodes and not mongo_nodes and mongo_status == "ok":
        suggestions.append(
            "MySQL 有 trace 但 Mongo 为空，检查 dual-write、补偿记录和 traceRecords collection。"
        )
    if mongo_nodes and not mysql_nodes and mysql_status == "ok":
        suggestions.append(
            "Mongo 有 trace 但 MySQL 为空，检查 storage.trace 是否为 mongo 或 MySQL trace_records 是否被清理。"
        )
    if any(node.status not in (None, "success") for node in all_nodes):
        suggestions.append(
            "先从时间线中的第一个 error 节点向前追输入、上下文和上游工具结果。"
        )
    if any((node.duration_ms or 0) > 5000 for node in all_nodes):
        suggestions.append(
            "存在超过 5s 的慢节点，优先排查外部网络、LLM provider、Mongo server selection 或 MySQL 慢查询。"
        )
    if events_status.startswith("missing"):
        suggestions.append(
            "JSONL 事件缺失时，确认 agent_turns.event_file 是否写入，以及 data/agent-events 是否在当前工作区。"
        )
    if not suggestions:
        suggestions.append(
            "链路证据未显示明显系统错误，可继续检查工具选择、prompt 上下文和业务语义。"
        )
    return suggestions


def turn_from_row(row: Any) -> TurnItem:
    return TurnItem(
        source="mysql",
        id=getattr(row, "id", None),
        request_id=getattr(row, "request_id", None),
        session_id=getattr(row, "session_id", None),
        status=getattr(row, "status", None),
        latency_ms=getattr(row, "latency_ms", None),
        tool_calls_count=getattr(row, "tool_calls_count", None),
        token_total=getattr(row, "token_total", None),
        input_preview=getattr(row, "input_preview", None),
        reply_preview=getattr(row, "reply_preview", None),
        event_file=getattr(row, "event_file", None),
        event_seq_start=getattr(row, "event_seq_start", None),
        event_seq_end=getattr(row, "event_seq_end", None),
    )


def node_from_mysql(row: Any) -> TraceNode:
    return TraceNode(
        source="mysql",
        storage_id=str(getattr(row, "id", "")) if getattr(row, "id", None) else None,
        request_id=str(getattr(row, "request_id", "") or ""),
        session_id=getattr(row, "session_id", None),
        farm_id=getattr(row, "farm_id", None),
        conversation_message_id=getattr(row, "conversation_message_id", None),
        round_index=getattr(row, "round_index", None),
        node_type=str(getattr(row, "node_type", "") or ""),
        node_name=str(getattr(row, "node_name", "") or ""),
        status=getattr(row, "status", None),
        duration_ms=getattr(row, "duration_ms", None),
        token_total=token_total(getattr(row, "token_usage", None)),
        error_message=getattr(row, "error_message", None),
        input_data=getattr(row, "input_data", None),
        output_data=getattr(row, "output_data", None),
        started_at=iso(
            getattr(row, "start_time", None) or getattr(row, "created_at", None)
        ),
        sort_key=sort_key(
            getattr(row, "request_id", None),
            getattr(row, "round_index", None),
            getattr(row, "start_time", None),
            getattr(row, "id", None),
        ),
    )


def node_from_mongo(doc: dict[str, Any]) -> TraceNode:
    return TraceNode(
        source="mongo",
        storage_id=str(doc.get("mysqlId") or doc.get("_id") or ""),
        request_id=str(doc.get("requestId") or ""),
        session_id=doc.get("sessionId"),
        farm_id=doc.get("farmId"),
        conversation_message_id=doc.get("conversationMessageId"),
        round_index=doc.get("roundIndex"),
        node_type=str(doc.get("nodeType") or ""),
        node_name=str(doc.get("nodeName") or ""),
        status=doc.get("status"),
        duration_ms=doc.get("durationMs"),
        token_total=token_total(doc.get("tokenUsage")),
        error_message=doc.get("errorMessage"),
        input_data=doc.get("input"),
        output_data=doc.get("output"),
        started_at=iso(doc.get("startTime") or doc.get("createdAt")),
        sort_key=sort_key(
            doc.get("requestId"),
            doc.get("roundIndex"),
            doc.get("startTime"),
            doc.get("mysqlId"),
        ),
    )


def message_from_mysql(row: Any) -> MessageItem:
    meta = coerce_meta(getattr(row, "meta_json", None) or getattr(row, "meta", None))
    return MessageItem(
        source="mysql",
        storage_id=str(getattr(row, "id", "")) if getattr(row, "id", None) else None,
        role=getattr(row, "role", None),
        content=getattr(row, "content", None),
        created_at=iso(getattr(row, "created_at", None)),
        turn_id=getattr(row, "turn_id", None),
        session_id=None,
        farm_id=None,
        meta=meta,
        event_file=meta.get("event_file") if meta else None,
        event_seq_range=meta.get("event_seq_range") if meta else None,
    )


def message_from_mongo(doc: dict[str, Any]) -> MessageItem:
    meta = coerce_meta(doc.get("meta") or doc.get("legacyMetaText"))
    return MessageItem(
        source="mongo",
        storage_id=str(doc.get("mysqlId") or doc.get("_id") or ""),
        role=doc.get("role"),
        content=doc.get("content"),
        created_at=iso(doc.get("createdAt")),
        turn_id=doc.get("turnId"),
        session_id=doc.get("sessionId"),
        farm_id=doc.get("farmId"),
        meta=meta,
        event_file=meta.get("event_file") if meta else None,
        event_seq_range=meta.get("event_seq_range") if meta else None,
    )


def merge_nodes(
    mysql_nodes: list[TraceNode], mongo_nodes: list[TraceNode]
) -> list[TraceNode]:
    result: list[TraceNode] = []
    seen: set[tuple[Any, ...]] = set()
    for node in [*mysql_nodes, *mongo_nodes]:
        key = (
            node.request_id,
            node.round_index,
            node.node_type,
            node.node_name,
            node.started_at,
            node.duration_ms,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(node)
    return sorted(result, key=lambda item: item.sort_key)


def collect_request_ids(
    turns: list[TurnItem],
    nodes: list[TraceNode],
    messages: list[MessageItem],
    request_id: str | None,
) -> list[str]:
    ids = [item.request_id for item in turns if item.request_id]
    ids.extend(node.request_id for node in nodes if node.request_id)
    ids.extend(
        str((message.meta or {}).get("trace_request_id"))
        for message in messages
        if (message.meta or {}).get("trace_request_id")
    )
    if request_id:
        ids.append(request_id)
    return list(dict.fromkeys(ids))


def build_resolved_scope(
    turns: list[TurnItem],
    nodes: list[TraceNode],
    messages: list[MessageItem],
    request_ids: list[str],
) -> dict[str, Any]:
    session_ids = sorted(
        {
            value
            for value in [
                *(turn.session_id for turn in turns),
                *(node.session_id for node in nodes),
                *(message.session_id for message in messages),
            ]
            if value
        }
    )
    farm_ids = sorted(
        {
            int(value)
            for value in [
                *(node.farm_id for node in nodes),
                *(message.farm_id for message in messages),
            ]
            if value is not None
        }
    )
    turn_ids = sorted(
        {
            int(value)
            for value in [
                *(turn.id for turn in turns),
                *(message.turn_id for message in messages),
            ]
            if value is not None
        }
    )
    return {
        "request_ids": request_ids,
        "session_ids": session_ids,
        "farm_ids": farm_ids,
        "turn_ids": turn_ids,
    }


def collect_request_ids_from_rows(rows: list[Any], request_id: str | None) -> list[str]:
    ids = [
        getattr(row, "request_id", None)
        for row in rows
        if getattr(row, "request_id", None)
    ]
    if request_id:
        ids.append(request_id)
    return list(dict.fromkeys(ids))


def target_dict(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "request_id": args.request_id,
        "session_id": args.session_id,
        "turn_id": args.turn_id,
        "farm_id": args.farm_id,
        "limit": clamp(args.limit, 1, MAX_LIMIT),
    }


def empty_data() -> dict[str, list[Any]]:
    return {"turns": [], "trace_nodes": [], "messages": []}


def unique_mongo_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in docs:
        key = str(doc.get("_id") or doc.get("mysqlId") or id(doc))
        if key in seen:
            continue
        seen.add(key)
        result.append(doc)
    return result


def table_exists(inspector: Any, table_name: str) -> bool:
    try:
        return bool(inspector.has_table(table_name))
    except Exception:
        return True


def mysql_status(*, missing: list[str], errors: list[str]) -> str:
    if not missing and not errors:
        return "ok"
    parts = []
    if missing:
        parts.append(f"missing={','.join(missing)}")
    if errors:
        parts.append(f"errors={'; '.join(errors[:3])}")
    return f"partial(code=mysql_partial,{','.join(parts)})"


def count_source(items: list[Any], source: str) -> int:
    return sum(1 for item in items if getattr(item, "source", None) == source)


def coerce_meta(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"legacy_meta_text": value}
        return parsed if isinstance(parsed, dict) else {"meta": parsed}
    return {"meta": value}


def token_total(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    total = value.get("total_tokens")
    if isinstance(total, int):
        return total
    prompt = value.get("prompt_tokens")
    completion = value.get("completion_tokens")
    if isinstance(prompt, int) and isinstance(completion, int):
        return prompt + completion
    return None


def json_preview(value: Any) -> str:
    try:
        return preview(
            json.dumps(redact(value), ensure_ascii=False, default=str, sort_keys=True)
        )
    except TypeError:
        return preview(str(value))


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            result[key_text] = (
                "***" if key_text.lower() in SENSITIVE_KEYS else redact(item)
            )
        return result
    if isinstance(value, list):
        return [redact(item) for item in value[:30]]
    return value


def preview(value: Any, limit: int = PREVIEW_LIMIT) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[:limit]}..."


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def sort_key(request_id: Any, round_index: Any, started_at: Any, row_id: Any) -> str:
    return f"{request_id or ''}|{int(round_index or 0):04d}|{iso(started_at) or ''}|{int(row_id or 0):010d}"


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def escape_regex(value: str) -> str:
    import re

    return re.escape(value)


if __name__ == "__main__":
    raise SystemExit(main())
