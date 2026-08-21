#!/usr/bin/env python3
"""生成或执行 conversationMessages -> conversationStates 迁移计划。

默认 dry-run。真实写入必须同时提供 ``--allow-write``，且只会创建缺失的
conversationStates，不覆盖已有 state、不删除 conversationMessages。
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from agent.platforms.persistence.mongo import chat_store
from agent.platforms.persistence.mongo.migration import build_migration_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="离线 JSON/JSONL 消息快照")
    parser.add_argument(
        "--from-mongo", action="store_true", help="读取 Mongo 当前事实源"
    )
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--output", type=Path, help="报告输出路径")
    parser.add_argument("--allow-write", action="store_true")
    return parser


def _load_messages(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        raise ValueError("--input is required for offline migration report")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, dict):
        payload = payload.get("messages", [])
    if not isinstance(payload, list):
        raise ValueError("input must be a JSON list or {messages: [...]} object")
    return payload


async def _load_mongo_snapshot(
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """读取 Mongo 投影用于校验；不读取或输出 message content。"""
    messages_collection = chat_store.get_collection()
    states_collection = chat_store.get_state_collection()
    if messages_collection is None or states_collection is None:
        raise RuntimeError("mongo conversation source unavailable")
    projection = {
        "userId": 1,
        "farmId": 1,
        "conversationId": 1,
        "turnId": 1,
        "role": 1,
    }
    messages = (
        await messages_collection.find({}, projection=projection)
        .limit(max(1, limit))
        .to_list(length=max(1, limit))
    )
    states = await states_collection.find(
        {},
        projection={
            "userId": 1,
            "farmId": 1,
            "conversationId": 1,
            "conversationRevision": 1,
            "summarySourceConversationRevision": 1,
        },
    ).to_list(length=max(1, limit))
    return messages, states


async def _write_candidates(report: dict[str, Any]) -> list[str]:
    written: list[str] = []
    for entry in report["entries"]:
        candidate = entry.get("candidate")
        if not candidate or entry.get("issue_codes"):
            continue
        existing = await chat_store.get_conversation_state(
            candidate["conversationId"],
            user_id=candidate["userId"],
            farm_id=candidate["farmId"],
        )
        if existing is not None:
            continue
        result = await chat_store.save_conversation_state(
            candidate["conversationId"],
            user_id=candidate["userId"],
            farm_id=candidate["farmId"],
            expected_revision=0,
            summary_status=candidate["summaryStatus"],
            idempotency_key=f"migration:conversation-state:{candidate['conversationId']}",
        )
        if result.get("status") in {"ready", "idempotent"}:
            written.append(
                f"{candidate['userId']}:{candidate['farmId']}:{candidate['conversationId']}"
            )
    return written


async def _run(args: argparse.Namespace) -> int:
    if args.from_mongo:
        messages, states = await _load_mongo_snapshot(args.limit)
        report = build_migration_report(messages, states)
    else:
        messages = _load_messages(args.input)
        report = build_migration_report(messages)
    if args.allow_write:
        report["write_mode"] = "allow_write"
        created_state_keys = await _write_candidates(report)
        report["written_count"] = len(created_state_keys)
        report["rollback"]["created_state_keys"] = created_state_keys
    else:
        report["write_mode"] = "dry_run"
        report["written_count"] = 0
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["divergence_count"] == 0 else 2


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
