#!/usr/bin/env python3
"""只读分析 farm-manager Agent 请求链路。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PREVIEW_LIMIT = 220
DEFAULT_LIMIT = 5
MAX_LIMIT = 50
MAX_V2_PAGES = 100
_AUTO_AUTH_CACHE: dict[str, str] = {}
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
    trace_id: str | None = None
    turn_id: str | None = None
    conversation_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    phase: str | None = None
    attempt: int | None = None


@dataclass
class TurnItem:
    source: str
    id: int | str | None
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
    trace_id: str | None = None
    conversation_id: str | None = None


@dataclass
class MessageItem:
    source: str
    storage_id: str | None
    role: str | None
    content: str | None
    created_at: str | None
    turn_id: int | str | None
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
    turn_id: int | str | None
    payload: Any
    event_id: str | None = None
    trace_id: str | None = None
    conversation_id: str | None = None
    phase: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    terminal: bool | None = None
    occurred_at: str | None = None
    span_id: str | None = None


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
    conversation_overview: dict[str, Any] = field(default_factory=dict)
    turn_overview: list[dict[str, Any]] = field(default_factory=list)
    sse_timeline: list[dict[str, Any]] = field(default_factory=list)
    trace_timeline: list[dict[str, Any]] = field(default_factory=list)
    business_outcome: dict[str, Any] = field(default_factory=dict)
    evidence_gaps: list[str] = field(default_factory=list)
    evidence_details: dict[str, str] = field(default_factory=dict)


def main() -> int:
    args = parse_args()
    project = Path(args.project).expanduser().resolve()
    report = finalize_report(asyncio.run(build_report(project, args)))
    if args.json:
        print(
            json.dumps(report_dict(report), ensure_ascii=False, indent=2, default=str)
        )
    else:
        print(format_markdown(report, include_payload=args.include_payload))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读分析 farm-manager Agent 链路")
    parser.add_argument("--project", default=".", help="项目根目录，默认当前目录")
    parser.add_argument("--request-id", help="完整 request_id 或前缀")
    parser.add_argument("--session-id", help="session_id")
    parser.add_argument(
        "--turn-id", help="旧版 agent_turns.id 或 agri_backend_v2 Agent 的字符串 turn_id"
    )
    parser.add_argument("--trace-id", help="agri_backend_v2 Trace 的正式 trace_id，精确召回一轮")
    parser.add_argument("--conversation-id", help="agri_backend_v2 conversation_id，召回整段会话")
    parser.add_argument("--farm-id", type=int, help="可选 farm_id 过滤")
    parser.add_argument(
        "--agri_backend_v2",
        action="store_true",
        help="按 agri_backend_v2 Agent 的 HTTP/Mongo trace 接口查询",
    )
    parser.add_argument(
        "--agri_backend_v2-base-url",
        default=os.getenv("V2_AGENT_BASE_URL", "http://127.0.0.1:8000"),
        help="agri_backend_v2 Agent 地址，默认 http://127.0.0.1:8000",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="会话最近轮数")
    parser.add_argument(
        "--include-payload", action="store_true", help="展示输入输出摘要"
    )
    parser.add_argument(
        "--include-events", action="store_true", help="召回并展示 agri_backend_v2 SSE 事件时间线"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


async def build_report(project: Path, args: argparse.Namespace) -> ChainReport:
    if (
        not args.request_id
        and not args.session_id
        and args.turn_id is None
        and args.trace_id is None
        and args.conversation_id is None
    ):
        return ChainReport(
            target=target_dict(args),
            status=EvidenceStatus("skipped", "skipped", "skipped"),
            resolved={},
            turns=[],
            trace_nodes=[],
            messages=[],
            events=[],
            errors=[
                "缺少定位参数：请提供 --request-id、--session-id、--turn-id、"
                "--trace-id 或 --conversation-id"
            ],
            suggestions=[
                "先从日志或前端请求中复制 request_id；只有短 ID 时也可以按前缀查询。"
            ],
        )

    if should_use_v2(project, args):
        return await build_v2_report(args)

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


def should_use_v2(project: Path, args: argparse.Namespace) -> bool:
    """识别 agri_backend_v2 请求，避免用 archive/backend 的旧表模型误查。"""
    if args.v2:
        return True
    if args.trace_id is not None or args.conversation_id is not None:
        return True
    return (project / "agri_backend_v2" / "agent" / "main.py").exists() and (
        args.turn_id is not None and not str(args.turn_id).isdigit()
    )


class V2ApiError(RuntimeError):
    """保留 agri_backend_v2 HTTP 错误类别，避免把接口不可用伪装成空数据。"""

    def __init__(self, path: str, status_code: int | None, kind: str) -> None:
        super().__init__(f"agri_backend_v2 API {kind}: {path}")
        self.path = path
        self.status_code = status_code
        self.kind = kind


def _is_loopback_url(url: str) -> bool:
    return urlparse(url).hostname in {"127.0.0.1", "localhost", "::1"}


def _bearer_value(value: str) -> str:
    value = value.strip()
    return value if value.lower().startswith("bearer ") else f"Bearer {value}"


def _configured_authorization() -> str | None:
    authorization = os.getenv("V2_AGENT_AUTHORIZATION") or os.getenv(
        "AGENT_AUTHORIZATION"
    )
    if authorization:
        return _bearer_value(authorization)
    token = os.getenv("V2_AGENT_TOKEN") or os.getenv("AGENT_TOKEN")
    return _bearer_value(token) if token else None


def _auto_auth_enabled() -> bool:
    value = os.getenv("V2_AGENT_AUTO_AUTH", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _auth_error(url: str, kind: str, status_code: int | None = None) -> V2ApiError:
    return V2ApiError(url, status_code, f"auth_{kind}")


def _extract_access_token(payload: dict[str, Any]) -> str | None:
    token = payload.get("access_token") or payload.get("token")
    return token if isinstance(token, str) and token.strip() else None


def _v2_request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    authorization: str | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        kind = "not_found" if exc.code == 404 else "http_error"
        raise V2ApiError(url, exc.code, kind) from exc
    except (URLError, TimeoutError) as exc:
        raise V2ApiError(url, None, "unavailable") from exc
    if not isinstance(result, dict):
        raise V2ApiError(url, None, "invalid_response")
    return result


def _fetch_auto_authorization(base_url: str) -> str:
    login_url = v2_api_url(base_url, "/auth/login", {})
    phone = os.getenv("V2_AGENT_PHONE") or os.getenv("V2_AGENT_LOGIN_PHONE")
    password = os.getenv("V2_AGENT_PASSWORD") or os.getenv("V2_AGENT_LOGIN_PASSWORD")
    if bool(phone) != bool(password):
        raise _auth_error(login_url, "credentials_incomplete")
    if phone and password:
        try:
            payload = _v2_request_json(
                login_url,
                method="POST",
                payload={"phone": phone, "password": password},
            )
        except V2ApiError as exc:
            raise _auth_error(login_url, "login_failed", exc.status_code) from exc
        token = _extract_access_token(payload)
        if token is None:
            raise _auth_error(login_url, "token_missing")
        return _bearer_value(token)

    if not _is_loopback_url(base_url):
        raise _auth_error(login_url, "credentials_required")

    dev_users_url = v2_api_url(base_url, "/dev-users", {})
    try:
        payload = _v2_request_json(dev_users_url)
    except V2ApiError as exc:
        raise _auth_error(
            dev_users_url, "dev_users_unavailable", exc.status_code
        ) from exc
    users = payload.get("users")
    if not isinstance(users, list):
        raise _auth_error(dev_users_url, "dev_users_invalid")
    selector = os.getenv("V2_AGENT_USER_PHONE")
    candidates = [
        user
        for user in users
        if isinstance(user, dict)
        and (not selector or str(user.get("phone") or "") == selector)
    ]
    if len(candidates) != 1:
        raise _auth_error(dev_users_url, "dev_user_ambiguous")
    token = _extract_access_token(candidates[0]) or candidates[0].get("token")
    if not isinstance(token, str) or not token.strip():
        raise _auth_error(dev_users_url, "dev_user_token_missing")
    return _bearer_value(token)


def _resolve_v2_authorization(
    base_url: str, *, force_refresh: bool = False
) -> tuple[str | None, bool]:
    explicit = _configured_authorization()
    if explicit:
        return explicit, False
    if not _auto_auth_enabled():
        return None, False
    phone = os.getenv("V2_AGENT_PHONE") or os.getenv("V2_AGENT_LOGIN_PHONE")
    password = os.getenv("V2_AGENT_PASSWORD") or os.getenv("V2_AGENT_LOGIN_PASSWORD")
    if not (phone or password) and not _is_loopback_url(base_url):
        return None, False
    if not force_refresh and base_url in _AUTO_AUTH_CACHE:
        return _AUTO_AUTH_CACHE[base_url], True
    authorization = _fetch_auto_authorization(base_url)
    _AUTO_AUTH_CACHE[base_url] = authorization
    return authorization, True


def _clear_auto_authorization(base_url: str) -> None:
    _AUTO_AUTH_CACHE.pop(base_url, None)


async def build_v2_report(args: argparse.Namespace) -> ChainReport:
    """按 trace_id、turn_id 或 conversation_id 只读召回 agri_backend_v2 证据。"""
    base_url = v2_api_base_url(args.v2_base_url)
    evidence = {
        "trace_summary": "not_requested",
        "trace_nodes": "not_requested",
        "trace_events": "not_requested",
        "conversation_messages": "not_requested",
        "runtime_turn": "not_available(v2_api)",
    }
    try:
        targets, resolution, list_status = await resolve_v2_targets(base_url, args)
        if not targets:
            evidence["trace_summary"] = "missing(agri_backend_v2)"
            evidence["trace_nodes"] = "missing(agri_backend_v2)"
            if args.include_events:
                evidence["trace_events"] = "missing(agri_backend_v2)"
            errors = [
                "agri_backend_v2 未找到匹配的 trace_id、turn_id、request_id 或 conversation_id"
            ]
            if list_status:
                errors.append(list_status)
            return v2_empty_report(args, base_url, evidence, errors, resolution)

        conversation_ids = sorted(
            {
                str(item.get("conversation_id"))
                for item in targets
                if item.get("conversation_id")
            }
        )
        if args.conversation_id:
            conversation_ids = [args.conversation_id]
        messages: list[MessageItem] = []
        message_status = "missing(agri_backend_v2)"
        if conversation_ids:
            messages, message_status = await fetch_v2_messages(
                base_url, conversation_ids[0], args.limit
            )
            evidence["conversation_messages"] = message_status

        all_nodes: list[TraceNode] = []
        all_events: list[EventItem] = []
        turns: list[TurnItem] = []
        trace_statuses: list[str] = []
        event_statuses: list[str] = []
        trace_errors: list[str] = []
        trace_gaps: list[str] = []
        for target in targets:
            result = await fetch_v2_trace(base_url, target, args)
            all_nodes.extend(result["nodes"])
            all_events.extend(result["events"])
            turns.append(
                v2_turn_from_summary(
                    result["summary"],
                    result["trace_id"],
                    messages,
                    result["events"],
                )
            )
            trace_statuses.append(result["nodes_status"])
            event_statuses.append(result["events_status"])
            trace_errors.extend(result["errors"])
            trace_gaps.extend(result["gaps"])

        evidence["trace_summary"] = "ok(v2_api)"
        evidence["trace_nodes"] = combine_v2_statuses(trace_statuses, "trace_nodes")
        evidence["trace_events"] = combine_v2_statuses(event_statuses, "trace_events")
        if args.conversation_id and not targets:
            evidence["trace_summary"] = "missing(agri_backend_v2)"

        errors = collect_errors(all_nodes, all_events)
        errors = list(dict.fromkeys([*trace_errors, *errors]))[:20]
        gaps = list(dict.fromkeys([*trace_gaps, *v2_message_gaps(messages, turns)]))
        suggestions = build_v2_recall_suggestions(
            turns, all_nodes, all_events, evidence, gaps
        )
        resolved = {
            "conversation_ids": conversation_ids,
            "trace_ids": sorted(
                {str(item.get("trace_id")) for item in targets if item.get("trace_id")}
            ),
            "turn_ids": sorted(
                {str(item.get("turn_id")) for item in targets if item.get("turn_id")}
            ),
            "request_ids": sorted(
                {
                    str(item.get("request_id"))
                    for item in targets
                    if item.get("request_id")
                }
            ),
            "resolution": resolution,
        }
        overview = build_conversation_overview(
            conversation_ids, messages, turns, targets
        )
        return ChainReport(
            target={**target_dict(args), "v2_base_url": base_url},
            status=EvidenceStatus(
                "not_applicable(agri_backend_v2)",
                evidence["trace_nodes"],
                evidence["trace_events"],
            ),
            resolved=resolved,
            turns=turns,
            trace_nodes=sorted(all_nodes, key=lambda item: item.sort_key),
            messages=messages,
            events=sorted(
                all_events, key=lambda item: (item.trace_id or "", item.seq or 0)
            ),
            errors=errors,
            suggestions=suggestions,
            conversation_overview=overview,
            turn_overview=[turn_overview(item, turns, all_events) for item in turns],
            sse_timeline=[event_dict(item) for item in all_events],
            trace_timeline=[node_dict(item) for item in all_nodes],
            business_outcome=build_business_outcome(
                targets, turns, all_nodes, all_events, messages
            ),
            evidence_gaps=gaps,
            evidence_details=evidence,
        )
    except V2ApiError as exc:
        evidence["trace_summary"] = v2_error_status(exc)
        return v2_empty_report(
            args,
            base_url,
            evidence,
            [f"agri_backend_v2 trace 查询失败: {preview(str(exc))}"],
            {"resolution": "error"},
        )
    except Exception as exc:  # noqa: BLE001
        evidence["trace_summary"] = "unavailable(code=v2_api_error)"
        return v2_empty_report(
            args,
            base_url,
            evidence,
            [f"agri_backend_v2 trace 查询失败: {preview(str(exc))}"],
            {"resolution": "error"},
        )


async def resolve_v2_targets(
    base_url: str, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], str, str | None]:
    """先解析正式 ID，再把旧 request_id 仅作为兼容别名处理。"""
    if args.trace_id:
        try:
            summary = await v2_call(
                base_url, f"/traces/{quote(args.trace_id, safe='')}/summary"
            )
            return [normalize_v2_summary(summary, args.trace_id)], "trace_id", None
        except V2ApiError as exc:
            if exc.status_code != 404:
                raise
            return [], "trace_id:not_found", v2_error_status(exc)
    if args.conversation_id:
        items, error = await v2_paginate(
            base_url,
            "/traces",
            {"conversation_id": args.conversation_id},
            args.limit,
        )
        return [normalize_v2_summary(item) for item in items], "conversation_id", error

    items, error = await v2_paginate(base_url, "/traces", {}, args.limit)
    if args.turn_id is not None:
        matches = [
            item for item in items if str(item.get("turn_id")) == str(args.turn_id)
        ]
        return [normalize_v2_summary(item) for item in matches], "turn_id", error
    if args.request_id:
        exact = [
            item for item in items if str(item.get("request_id")) == args.request_id
        ]
        if exact:
            return (
                [normalize_v2_summary(item) for item in exact],
                "request_id:exact",
                error,
            )
        prefix = [
            item
            for item in items
            if str(item.get("request_id") or "").startswith(args.request_id)
        ]
        return (
            [normalize_v2_summary(item) for item in prefix],
            "request_id:prefix",
            error,
        )
    return [], "unsupported_v2_scope", error


async def fetch_v2_trace(
    base_url: str, target: dict[str, Any], args: argparse.Namespace
) -> dict[str, Any]:
    trace_id = str(target.get("trace_id") or target.get("request_id") or "")
    summary = target
    errors: list[str] = []
    gaps: list[str] = []
    try:
        summary = normalize_v2_summary(
            await v2_call(base_url, f"/traces/{quote(trace_id, safe='')}/summary"),
            trace_id,
        )
    except V2ApiError as exc:
        if exc.status_code == 404:
            gaps.append("trace_summary=missing(agri_backend_v2)")
        else:
            errors.append(f"summary: {preview(str(exc))}")

    nodes_data: dict[str, Any] = {}
    nodes_status = "missing(agri_backend_v2)"
    try:
        nodes_data = await v2_call(
            base_url,
            f"/traces/{quote(trace_id, safe='')}/nodes",
            {
                "limit": 1000,
                **({"include_payload": "true"} if args.include_payload else {}),
            },
        )
        nodes_status = "ok(v2_api)"
    except V2ApiError as exc:
        if exc.status_code == 404:
            try:
                nodes_data = await v2_call(
                    base_url, f"/traces/{quote(trace_id, safe='')}", {"limit": 1000}
                )
                nodes_status = "ok(v2_api_compat)"
                gaps.append(
                    "trace_nodes=formal_endpoint_not_implemented(v2_api); used_compat_detail"
                )
            except V2ApiError as compat_exc:
                nodes_status = v2_error_status(compat_exc, missing=True)
                gaps.append(f"trace_nodes={nodes_status}")
        else:
            nodes_status = v2_error_status(exc)
            errors.append(f"nodes: {preview(str(exc))}")
    nodes = [
        node_from_v2(args, trace_id, summary, item)
        for item in (nodes_data.get("nodes") or [])
        if isinstance(item, dict)
    ]

    events: list[EventItem] = []
    events_status = "not_requested"
    if args.include_events:
        events, events_status, event_gaps, event_errors = await fetch_v2_events(
            base_url, trace_id, args
        )
        gaps.extend(event_gaps)
        errors.extend(event_errors)
    return {
        "trace_id": trace_id,
        "summary": summary,
        "nodes": nodes,
        "events": events,
        "nodes_status": nodes_status,
        "events_status": events_status,
        "errors": errors,
        "gaps": gaps,
    }


async def fetch_v2_events(
    base_url: str, trace_id: str, args: argparse.Namespace
) -> tuple[list[EventItem], str, list[str], list[str]]:
    """timeline 优先，events 次之；两个正式端点都不可用时明确标记。"""
    gaps: list[str] = []
    errors: list[str] = []
    params = {"limit": 1000}
    if args.include_payload:
        params["include_payload"] = "true"
    try:
        document = await v2_call(
            base_url, f"/traces/{quote(trace_id, safe='')}/timeline", params
        )
        nodes, events = split_v2_timeline(document, trace_id)
        return events, "ok(v2_api)", gaps, errors
    except V2ApiError as timeline_exc:
        if timeline_exc.status_code != 404:
            return (
                [],
                v2_error_status(timeline_exc),
                [],
                [f"timeline: {preview(str(timeline_exc))}"],
            )
        gaps.append("trace_timeline=not_available(v2_api)")
    try:
        document = await v2_call(
            base_url, f"/traces/{quote(trace_id, safe='')}/events", params
        )
        _, events = split_v2_timeline(document, trace_id)
        gaps.append("trace_timeline=not_available(v2_api); used_events_endpoint")
        return events, "ok(v2_api_events)", gaps, errors
    except V2ApiError as events_exc:
        if events_exc.status_code == 404:
            gaps.append("trace_events=not_available(v2_api)")
            return [], "not_available(v2_api)", gaps, errors
        return (
            [],
            v2_error_status(events_exc),
            gaps,
            [f"events: {preview(str(events_exc))}"],
        )


async def fetch_v2_messages(
    base_url: str, conversation_id: str, page_size: int
) -> tuple[list[MessageItem], str]:
    items, error = await v2_paginate(
        base_url,
        f"/conversations/{quote(conversation_id, safe='')}",
        {},
        page_size,
        cursor_param="before",
    )
    if error:
        return [], error
    return [
        message_from_v2({"conversation_id": conversation_id}, item) for item in items
    ], "ok(v2_api)"


async def v2_paginate(
    base_url: str,
    path: str,
    params: dict[str, Any],
    page_size: int,
    *,
    cursor_param: str = "cursor",
) -> tuple[list[dict[str, Any]], str | None]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for _ in range(MAX_V2_PAGES):
        query = {**params, "limit": clamp(page_size, 1, MAX_LIMIT)}
        if cursor:
            query[cursor_param] = cursor
        try:
            document = await v2_call(base_url, path, query)
        except V2ApiError as exc:
            if exc.status_code == 404:
                return items, "missing(agri_backend_v2)"
            return items, v2_error_status(exc)
        page_items = document.get("items") or []
        items.extend(item for item in page_items if isinstance(item, dict))
        has_more = bool(document.get("has_more"))
        next_cursor = document.get("next_cursor")
        if cursor_param == "before" and not next_cursor and page_items:
            next_cursor = page_items[-1].get("created_at")
        if not has_more or not next_cursor or str(next_cursor) in seen_cursors:
            return unique_v2_items(items), None
        cursor = str(next_cursor)
        seen_cursors.add(cursor)
    return unique_v2_items(items), "partial(code=v2_pagination_limit)"


async def v2_call(
    base_url: str, path: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    url = v2_api_url(base_url, path, params or {})
    authorization, automatic = _resolve_v2_authorization(base_url)
    try:
        if authorization:
            return await asyncio.to_thread(v2_get_json, url, authorization)
        return await asyncio.to_thread(v2_get_json, url)
    except V2ApiError as exc:
        if not (automatic and exc.status_code == 401):
            raise
        _clear_auto_authorization(base_url)
        refreshed, _ = _resolve_v2_authorization(base_url, force_refresh=True)
        if not refreshed:
            raise
        return await asyncio.to_thread(v2_get_json, url, refreshed)


def v2_get_json(url: str, authorization: str | None = None) -> dict[str, Any]:
    return _v2_request_json(url, authorization=authorization)


def v2_api_base_url(value: str) -> str:
    base = value.rstrip("/")
    return base if base.endswith("/api/v2") else f"{base}/api/v2"


def v2_api_url(base_url: str, path: str, params: dict[str, Any]) -> str:
    query = urlencode(
        {key: value for key, value in params.items() if value is not None}
    )
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}" + (f"?{query}" if query else "")


def normalize_v2_summary(
    doc: dict[str, Any], trace_id: str | None = None
) -> dict[str, Any]:
    result = dict(doc)
    resolved_trace_id = str(
        doc.get("trace_id") or doc.get("request_id") or trace_id or ""
    )
    result["trace_id"] = resolved_trace_id
    result["request_id"] = str(doc.get("request_id") or resolved_trace_id)
    result["turn_id"] = doc.get("turn_id")
    result["conversation_id"] = doc.get("conversation_id")
    return result


def unique_v2_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        # Trace/turn/conversation 是消息的关联键，不能作为消息唯一键：
        # 同一轮天然同时包含 user 和 assistant 两条消息。优先使用消息
        # 存储 ID，再用角色+时间+内容兜底，避免把整轮对话折叠成一条。
        key = str(
            item.get("message_id")
            or item.get("id")
            or item.get("_id")
            or item.get("mysqlId")
            or (
                item.get("trace_id") or item.get("request_id") or item.get("turn_id"),
                item.get("created_at") or item.get("createdAt"),
                item.get("role"),
                item.get("content"),
            )
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def v2_error_status(exc: V2ApiError, *, missing: bool = False) -> str:
    if exc.status_code == 404:
        return "missing(agri_backend_v2)" if missing else "not_available(v2_api)"
    if exc.status_code in {401, 403}:
        return f"unavailable(code=v2_auth_{exc.status_code})"
    if exc.status_code is None:
        return "unavailable(code=v2_api_unavailable)"
    return f"error(code=v2_api_http_{exc.status_code})"


def combine_v2_statuses(statuses: list[str], evidence_name: str) -> str:
    if not statuses:
        return "missing(agri_backend_v2)"
    if any(
        status.startswith("error") or status.startswith("unavailable")
        for status in statuses
    ):
        return next(
            status
            for status in statuses
            if status.startswith("error") or status.startswith("unavailable")
        )
    if any(status == "not_available(v2_api)" for status in statuses):
        return "not_available(v2_api)"
    if any(status.startswith("ok") for status in statuses):
        return "ok(v2_api)"
    if any(status.startswith("partial") for status in statuses):
        return next(status for status in statuses if status.startswith("partial"))
    return f"missing(agri_backend_v2,source={evidence_name})"


def split_v2_timeline(
    document: dict[str, Any], trace_id: str
) -> tuple[list[dict[str, Any]], list[EventItem]]:
    raw_nodes = document.get("nodes") or document.get("trace_nodes") or []
    raw_events = document.get("events") or document.get("sse_events") or []
    timeline = document.get("timeline") or document.get("items") or []
    if timeline:
        for item in timeline:
            if not isinstance(item, dict):
                continue
            if item.get("event_type") or item.get("event_id") or "seq" in item:
                raw_events.append(item)
            elif item.get("node_type") or item.get("node_name"):
                raw_nodes.append(item)
    events = [
        event_from_v2(trace_id, item) for item in raw_events if isinstance(item, dict)
    ]
    return [item for item in raw_nodes if isinstance(item, dict)], events


def event_from_v2(trace_id: str, doc: dict[str, Any]) -> EventItem:
    data = doc.get("data") if "data" in doc else doc.get("payload")
    return EventItem(
        seq=as_int(doc.get("seq")),
        event_type=doc.get("event_type") or doc.get("type"),
        request_id=doc.get("request_id") or trace_id,
        turn_id=doc.get("turn_id"),
        payload=redact(data),
        event_id=doc.get("event_id") or doc.get("id"),
        trace_id=doc.get("trace_id") or trace_id,
        conversation_id=doc.get("conversation_id"),
        phase=doc.get("phase"),
        status_before=doc.get("status_before"),
        status_after=doc.get("status_after"),
        terminal=doc.get("terminal"),
        occurred_at=doc.get("occurred_at") or doc.get("created_at"),
        span_id=doc.get("span_id"),
    )


def as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def v2_turn_from_summary(
    summary: dict[str, Any],
    trace_id: str,
    messages: list[MessageItem],
    events: list[EventItem],
) -> TurnItem:
    turn_id = summary.get("turn_id")
    related = [
        item
        for item in messages
        if item.turn_id is not None and str(item.turn_id) == str(turn_id)
    ]
    source_messages = related or messages
    user_message = next(
        (item for item in reversed(source_messages) if item.role == "user"), None
    )
    assistant_message = next(
        (item for item in reversed(source_messages) if item.role == "assistant"), None
    )
    seqs = [item.seq for item in events if item.seq is not None]
    metrics = summary.get("metrics") or {}
    return TurnItem(
        source="agri_backend_v2",
        id=turn_id,
        request_id=summary.get("request_id") or trace_id,
        session_id=summary.get("conversation_id"),
        status=summary.get("status"),
        latency_ms=summary.get("total_duration_ms"),
        tool_calls_count=metrics.get("tool_calls"),
        token_total=metrics.get("total_tokens"),
        input_preview=user_message.content if user_message else None,
        reply_preview=assistant_message.content if assistant_message else None,
        event_file=None,
        event_seq_start=min(seqs) if seqs else None,
        event_seq_end=max(seqs) if seqs else None,
        trace_id=trace_id,
        conversation_id=summary.get("conversation_id"),
    )


def event_dict(event: EventItem) -> dict[str, Any]:
    return asdict(event)


def node_dict(node: TraceNode) -> dict[str, Any]:
    return asdict(node)


def turn_overview(
    turn: TurnItem, turns: list[TurnItem], events: list[EventItem]
) -> dict[str, Any]:
    turn_events = [item for item in events if str(item.turn_id) == str(turn.id)]
    diagnostics = sse_diagnostics(turn_events)
    return {
        "trace_id": turn.trace_id or turn.request_id,
        "turn_id": turn.id,
        "conversation_id": turn.conversation_id or turn.session_id,
        "status": turn.status,
        "latency_ms": turn.latency_ms,
        "tool_calls_count": turn.tool_calls_count,
        "token_total": turn.token_total,
        "input_preview": preview(turn.input_preview) if turn.input_preview else None,
        "reply_preview": preview(turn.reply_preview) if turn.reply_preview else None,
        "sse": diagnostics,
    }


def sse_diagnostics(events: list[EventItem]) -> dict[str, Any]:
    seqs = sorted(item.seq for item in events if item.seq is not None)
    gaps: list[int] = []
    duplicates: list[int] = []
    if seqs:
        counts = Counter(seqs)
        duplicates = sorted(seq for seq, count in counts.items() if count > 1)
        expected = set(range(seqs[0], seqs[-1] + 1))
        gaps = sorted(expected - set(seqs))
    event_ids = [item.event_id for item in events if item.event_id]
    done_events = [
        item for item in events if item.event_type == "done" or item.terminal
    ]
    return {
        "count": len(events),
        "first_seq": seqs[0] if seqs else None,
        "last_seq": seqs[-1] if seqs else None,
        "seq_gaps": gaps,
        "duplicate_seq": duplicates,
        "duplicate_event_id": sorted(
            event_id for event_id, count in Counter(event_ids).items() if count > 1
        ),
        "done_count": len([item for item in done_events if item.event_type == "done"]),
        "terminal_count": len(done_events),
    }


def v2_message_gaps(messages: list[MessageItem], turns: list[TurnItem]) -> list[str]:
    gaps: list[str] = []
    if turns and not messages:
        gaps.append("conversation_messages=missing(agri_backend_v2)")
    if messages and any(item.turn_id is None for item in messages) and len(turns) > 1:
        gaps.append(
            "conversation_messages.turn_id=not_available(v2_api); cannot_exactly_bind_messages_to_turns"
        )
    if turns and any(item.reply_preview is None for item in turns):
        gaps.append("assistant_message=missing(agri_backend_v2)")
    return gaps


def build_conversation_overview(
    conversation_ids: list[str],
    messages: list[MessageItem],
    turns: list[TurnItem],
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "conversation_ids": conversation_ids,
        "message_count": len(messages),
        "user_message_count": sum(item.role == "user" for item in messages),
        "assistant_message_count": sum(item.role == "assistant" for item in messages),
        "turn_count": len(turns),
        "trace_count": len(targets),
        "trace_ids": [item.get("trace_id") for item in targets],
    }


def build_business_outcome(
    targets: list[dict[str, Any]],
    turns: list[TurnItem],
    nodes: list[TraceNode],
    events: list[EventItem],
    messages: list[MessageItem] | None = None,
) -> dict[str, Any]:
    messages = messages or []
    summaries = [
        key
        for target in targets
        for key in ("business_committed", "reply_generated", "reply_persisted")
        if key in target
    ]
    commit_events = [
        item for item in events if item.event_type == "operation_committed"
    ]
    commit_nodes = [item for item in nodes if item.node_type == "business_commit"]
    final_events = [
        item for item in events if item.event_type in {"final_answer", "done"}
    ]
    explicit_commit = [
        target.get("business_committed")
        for target in targets
        if "business_committed" in target
    ]
    explicit_reply = [
        target.get("reply_generated")
        for target in targets
        if "reply_generated" in target
    ]
    assistant_messages = [item for item in messages if item.role == "assistant"]
    explicit_persisted = [
        target.get("reply_persisted")
        for target in targets
        if "reply_persisted" in target
    ]
    return {
        "business_committed": True
        if any(explicit_commit) or commit_events or commit_nodes
        else (False if explicit_commit and not any(explicit_commit) else None),
        "reply_generated": True
        if any(explicit_reply)
        or final_events
        or any(turn.reply_preview for turn in turns)
        else (False if explicit_reply and not any(explicit_reply) else None),
        "reply_persisted": next(
            iter(explicit_persisted),
            True if assistant_messages else None,
        ),
        "commit_evidence": "confirmed"
        if explicit_commit or commit_events or commit_nodes
        else "missing",
        "reply_evidence": "confirmed"
        if explicit_reply or final_events or any(turn.reply_preview for turn in turns)
        else "missing",
        "reply_persistence_evidence": "confirmed"
        if explicit_persisted or assistant_messages
        else "missing",
        "commit_event_count": len(commit_events),
        "commit_node_count": len(commit_nodes),
        "terminal_event_count": len(
            [item for item in events if item.event_type == "done"]
        ),
        "source_fields": summaries,
    }


def build_v2_recall_suggestions(
    turns: list[TurnItem],
    nodes: list[TraceNode],
    events: list[EventItem],
    evidence: dict[str, str],
    gaps: list[str],
) -> list[str]:
    suggestions: list[str] = []
    if any(
        status.startswith("unavailable") or status.startswith("error")
        for status in evidence.values()
    ):
        suggestions.append(
            "先确认 agri_backend_v2 Agent、Mongo 和鉴权环境一致，再重新召回缺失的数据源。"
        )
    if any(
        node.status not in (None, "success") or node.error_message for node in nodes
    ):
        suggestions.append(
            "从 Trace 时间线第一个错误节点向前追输入、上下文和上游工具结果。"
        )
    diagnostics = sse_diagnostics(events)
    if (
        diagnostics["seq_gaps"]
        or diagnostics["duplicate_seq"]
        or diagnostics["duplicate_event_id"]
    ):
        suggestions.append(
            "SSE seq 或 event_id 存在不连续/重复，检查 Redis 重放、发布入口和断线恢复。"
        )
    if events and diagnostics["done_count"] != 1:
        suggestions.append("本轮 done 事件不是唯一终态，检查取消、超时和错误收敛逻辑。")
    if any((node.duration_ms or 0) > 5000 for node in nodes):
        suggestions.append(
            "存在超过 5s 的慢节点，分别检查排队、LLM、MCP 和审批等待耗时。"
        )
    if gaps:
        suggestions.append(
            "报告中的证据缺口不能用自然语言最终答复补全；需补齐对应 Trace/SSE/消息接口。"
        )
    if not suggestions:
        suggestions.append(
            "当前召回证据未显示明显系统错误，可继续核对工具结果与业务语义。"
        )
    return suggestions


def v2_empty_report(
    args: argparse.Namespace,
    base_url: str,
    evidence: dict[str, str],
    errors: list[str],
    resolution: dict[str, Any] | str,
) -> ChainReport:
    gaps = [
        f"{key}={value}"
        for key, value in evidence.items()
        if value in {"missing(agri_backend_v2)", "not_available(v2_api)"}
    ]
    return ChainReport(
        target={**target_dict(args), "v2_base_url": base_url},
        status=EvidenceStatus(
            "not_applicable(agri_backend_v2)",
            evidence.get("trace_nodes", "missing(agri_backend_v2)"),
            evidence.get("trace_events", "not_requested"),
        ),
        resolved={"resolution": resolution},
        turns=[],
        trace_nodes=[],
        messages=[],
        events=[],
        errors=errors,
        suggestions=[
            "确认目标 ID、agri_backend_v2 Agent 地址和鉴权后重试；不可用接口不能当作空数据。"
        ],
        conversation_overview={},
        turn_overview=[],
        sse_timeline=[],
        trace_timeline=[],
        business_outcome={
            "business_committed": None,
            "reply_generated": None,
            "reply_persisted": None,
        },
        evidence_gaps=gaps,
        evidence_details=evidence,
    )


def node_from_v2(
    args: argparse.Namespace,
    request_id: str,
    target: dict[str, Any],
    doc: dict[str, Any],
) -> TraceNode:
    token_usage = doc.get("token_usage")
    return TraceNode(
        source="agri_backend_v2-mongo",
        storage_id=None,
        request_id=request_id,
        session_id=target.get("conversation_id"),
        farm_id=None,
        conversation_message_id=None,
        round_index=doc.get("step_index"),
        node_type=str(doc.get("node_type") or ""),
        node_name=str(doc.get("node_name") or ""),
        status=doc.get("status"),
        duration_ms=doc.get("duration_ms"),
        token_total=token_total(token_usage),
        error_message=doc.get("error_message"),
        input_data=redact(doc.get("input_data")),
        output_data=redact(doc.get("output_data")),
        started_at=doc.get("start_time"),
        sort_key=sort_key(
            request_id, doc.get("step_index"), doc.get("start_time"), None
        ),
        trace_id=doc.get("trace_id") or request_id,
        turn_id=str(doc.get("turn_id") or target.get("turn_id") or "") or None,
        conversation_id=doc.get("conversation_id") or target.get("conversation_id"),
        span_id=doc.get("span_id"),
        parent_span_id=doc.get("parent_span_id"),
        phase=doc.get("phase"),
        attempt=as_int(doc.get("attempt")),
    )


def message_from_v2(target: dict[str, Any], doc: dict[str, Any]) -> MessageItem:
    meta = coerce_meta(doc.get("meta"))
    return MessageItem(
        source="agri_backend_v2-mongo",
        storage_id=str(doc.get("id") or doc.get("_id") or doc.get("mysql_id") or "")
        or None,
        role=doc.get("role"),
        content=doc.get("content"),
        created_at=doc.get("created_at") or doc.get("createdAt"),
        turn_id=doc.get("turn_id") or doc.get("turnId"),
        session_id=target.get("conversation_id"),
        farm_id=doc.get("farm_id") or doc.get("farmId"),
        meta=redact(meta) if meta else None,
        event_file=None,
        event_seq_range=None,
    )


def build_v2_suggestions(
    target: dict[str, Any], nodes: list[TraceNode], messages: list[MessageItem]
) -> list[str]:
    suggestions: list[str] = []
    llm_nodes = [node for node in nodes if node.node_type == "llm_call"]
    tool_nodes = [node for node in nodes if node.node_type == "tool_call"]
    last_llm = max(llm_nodes, key=lambda node: node.round_index or 0, default=None)
    last_tool_step = max((node.round_index or 0 for node in tool_nodes), default=0)
    if last_llm and isinstance(last_llm.output_data, dict):
        if (
            last_llm.output_data.get("tool_calls_count", 0)
            and (last_llm.round_index or 0) > last_tool_step
        ):
            suggestions.append(
                "最后一次 LLM 声明仍有 tool_call，但没有对应 tool_call trace；优先检查缺参分支、max_steps 截断或 make_plan 未记录。"
            )
    if messages and messages[-1].role == "user":
        suggestions.append(
            "会话以当前 user 消息结束，没有对应 assistant 最终消息；当前 agri_backend_v2 trace 状态把未完成链路误判为 success。"
        )
    if any((node.duration_ms or 0) > 5000 for node in nodes):
        suggestions.append(
            "存在超过 5s 的慢节点：本轮主要耗时集中在 LLM，需检查 provider 响应和重复工具规划。"
        )
    if not suggestions:
        suggestions.append("agri_backend_v2 trace 未显示明显错误，可继续核对最终回复与用户意图。")
    return suggestions


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


def finalize_report(report: ChainReport) -> ChainReport:
    """为旧版查询补齐统一报告字段，确保 Markdown/JSON 结构稳定。"""
    if not report.conversation_overview:
        conversation_ids = sorted(
            {
                str(item.session_id)
                for item in report.messages + report.turns
                if item.session_id
            }
        )
        report.conversation_overview = build_conversation_overview(
            conversation_ids, report.messages, report.turns, []
        )
    if not report.turn_overview:
        report.turn_overview = [
            {
                "trace_id": item.request_id,
                "turn_id": item.id,
                "conversation_id": item.session_id,
                "status": item.status,
                "latency_ms": item.latency_ms,
                "tool_calls_count": item.tool_calls_count,
                "token_total": item.token_total,
                "input_preview": preview(item.input_preview)
                if item.input_preview
                else None,
                "reply_preview": preview(item.reply_preview)
                if item.reply_preview
                else None,
                "sse": {},
            }
            for item in report.turns
        ]
    if not report.sse_timeline:
        report.sse_timeline = [event_dict(item) for item in report.events]
    if not report.trace_timeline:
        report.trace_timeline = [node_dict(item) for item in report.trace_nodes]
    if not report.business_outcome:
        report.business_outcome = build_business_outcome(
            [], report.turns, report.trace_nodes, report.events
        )
    if not report.evidence_gaps:
        report.evidence_gaps = build_evidence_gaps(report)
    if not report.evidence_details:
        report.evidence_details = {
            "trace_nodes": report.status.mongo,
            "trace_events": report.status.events,
            "conversation_messages": "ok" if report.messages else "missing",
        }
    return report


def build_evidence_gaps(report: ChainReport) -> list[str]:
    gaps: list[str] = []
    if not report.trace_nodes:
        gaps.append(f"trace_nodes={report.status.mongo}")
    if not report.messages:
        gaps.append("conversation_messages=missing")
    if not report.events:
        gaps.append(f"events={report.status.events}")
    return list(dict.fromkeys(gaps))


def report_dict(report: ChainReport) -> dict[str, Any]:
    """固定 JSON 字段；保留旧数组别名以兼容现有调试调用方。"""
    details = report.evidence_details
    evidence_status = {
        "mysql": report.status.mysql,
        "mongo": report.status.mongo,
        "events": report.status.events,
        "trace_summary": details.get(
            "trace_summary", "ok" if report.turns else "missing"
        ),
        "trace_nodes": details.get("trace_nodes", report.status.mongo),
        "trace_events": details.get("trace_events", report.status.events),
        "conversation_messages": details.get(
            "conversation_messages", "ok" if report.messages else "missing"
        ),
        "runtime_turn": "not_available(v2_api)"
        if report.target.get("v2_base_url")
        else "not_requested",
    }
    return {
        "target": report.target,
        "resolved_scope": report.resolved,
        "evidence_status": evidence_status,
        "conversation_overview": report.conversation_overview,
        "turn_overview": report.turn_overview,
        "sse_timeline": redact(report.sse_timeline),
        "trace_timeline": redact(report.trace_timeline),
        "business_outcome": report.business_outcome,
        "errors": report.errors,
        "evidence_gaps": report.evidence_gaps,
        "suggestions": report.suggestions,
        "turns": [redact(asdict(item)) for item in report.turns],
        "trace_nodes": [redact(asdict(item)) for item in report.trace_nodes],
        "messages": [redact(asdict(item)) for item in report.messages],
        "events": [redact(asdict(item)) for item in report.events],
    }


def format_markdown(report: ChainReport, *, include_payload: bool) -> str:
    lines = ["链路追踪分析", "", "目标:"]
    lines.extend(
        f"- {key}: {value}"
        for key, value in report.target.items()
        if value not in (None, False)
    )
    lines.extend(["", "解析范围:"])
    lines.extend(f"- {key}: {value}" for key, value in report.resolved.items() if value)
    lines.extend(["", "证据状态:"])
    lines.extend(
        [
            f"- MySQL: {report.status.mysql}",
            f"- Mongo/Trace nodes: {report.status.mongo}",
            f"- SSE events: {report.status.events}",
            f"- messages: {len(report.messages)}",
        ]
    )
    lines.extend(["", "会话/Turn 概览:"])
    if report.turn_overview:
        for item in report.turn_overview:
            lines.append(
                f"- trace_id={item.get('trace_id')} turn_id={item.get('turn_id')} "
                f"status={item.get('status')} latency={item.get('latency_ms') or '-'}ms"
            )
            if item.get("input_preview"):
                lines.append(f"  input: {item['input_preview']}")
            if item.get("reply_preview"):
                lines.append(f"  reply: {item['reply_preview']}")
    else:
        lines.append("- 未命中 Turn")
    lines.extend(["", "SSE 时间线:"])
    if report.events:
        for event in report.events:
            state = (
                f" {event.status_before}->{event.status_after}"
                if event.status_before or event.status_after
                else ""
            )
            lines.append(
                f"- seq={event.seq} event_id={event.event_id or '-'} "
                f"type={event.event_type}{state} terminal={event.terminal}"
            )
            if include_payload:
                lines.append(f"  data={json_preview(event.payload)}")
    else:
        lines.append(f"- 无事件证据，状态={report.status.events}")
    lines.extend(["", "Trace 时间线:"])
    if report.trace_nodes:
        for node in report.trace_nodes:
            lines.append(
                f"- [{node.source}] trace_id={node.trace_id or node.request_id} "
                f"span_id={node.span_id or '-'} {node.node_type}.{node.node_name} "
                f"status={node.status} duration={node.duration_ms or 0}ms"
            )
            if node.error_message:
                lines.append(f"  error={preview(node.error_message)}")
            if include_payload:
                lines.append(f"  input={json_preview(node.input_data)}")
                lines.append(f"  output={json_preview(node.output_data)}")
    else:
        lines.append("- 未命中 Trace 节点")
    lines.extend(["", "业务结果:"])
    for key, value in report.business_outcome.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "错误节点:"])
    lines.extend([f"- {item}" for item in report.errors] or ["- 未发现显式错误"])
    lines.extend(["", "证据缺口:"])
    lines.extend([f"- {item}" for item in report.evidence_gaps] or ["- 未发现"])
    lines.extend(["", "排查建议:"])
    lines.extend([f"- {item}" for item in report.suggestions] or ["- 未提供"])
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
    skills = [
        item.node_name
        for item in nodes
        if item.node_type in {"skill_call", "tool_call"}
    ]
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
            str(value)
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
        "trace_id": args.trace_id,
        "conversation_id": args.conversation_id,
        "farm_id": args.farm_id,
        "limit": clamp(args.limit, 1, MAX_LIMIT),
        "include_events": args.include_events,
        "include_payload": args.include_payload,
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
