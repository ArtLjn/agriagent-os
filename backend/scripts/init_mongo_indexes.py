"""初始化第 1 期 MongoDB 集合索引。"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TRACE_TTL_SECONDS = 60 * 60 * 24 * 30 * 18


@dataclass(frozen=True)
class MongoIndex:
    keys: tuple[tuple[str, int], ...]
    options: dict[str, Any]

    def as_dry_run(self) -> dict[str, Any]:
        return {
            "keys": list(self.keys),
            "options": dict(self.options),
        }


IndexPlan = dict[str, tuple[MongoIndex, ...]]


def _index(
    keys: tuple[tuple[str, int], ...],
    name: str,
    *,
    unique: bool = False,
    expire_after_seconds: int | None = None,
) -> MongoIndex:
    options: dict[str, Any] = {"name": name}
    if unique:
        options["unique"] = True
    if expire_after_seconds is not None:
        options["expireAfterSeconds"] = expire_after_seconds
    return MongoIndex(keys=keys, options=options)


def get_index_plan() -> IndexPlan:
    """返回五个集合的稳定索引计划。"""
    return {
        "traceRecords": (
            _index((("mysqlId", 1),), "uniq_trace_records_mysql_id", unique=True),
            _index((("requestId", 1),), "idx_trace_records_request_id"),
            _index(
                (("requestId", 1), ("roundIndex", 1), ("mysqlId", 1)),
                "idx_trace_records_request_timeline",
            ),
            _index(
                (("farmId", 1), ("sessionId", 1), ("createdAt", -1)),
                "idx_trace_records_farm_session_created_at",
            ),
            _index(
                (("farmId", 1), ("nodeType", 1), ("status", 1)),
                "idx_trace_records_farm_node_status",
            ),
            _index(
                (("conversationMessageId", 1),),
                "idx_trace_records_conversation_message_id",
            ),
            _index(
                (("createdAt", 1),),
                "ttl_trace_records_created_at",
                expire_after_seconds=TRACE_TTL_SECONDS,
            ),
        ),
        "caseDrafts": (
            _index((("mysqlId", 1),), "uniq_case_drafts_mysql_id", unique=True),
            _index((("draftId", 1),), "uniq_case_drafts_draft_id", unique=True),
            _index(
                (("farmId", 1), ("status", 1), ("updatedAt", -1)),
                "idx_case_drafts_farm_status_updated_at",
            ),
            _index(
                (("farmId", 1), ("sourceSampleId", 1)),
                "idx_case_drafts_farm_source_sample_id",
            ),
            _index(
                (("status", 1), ("updatedAt", -1)), "idx_case_drafts_status_updated_at"
            ),
            _index((("sourceSampleId", 1),), "idx_case_drafts_source_sample_id"),
        ),
        "repairPacks": (
            _index((("mysqlId", 1),), "uniq_repair_packs_mysql_id", unique=True),
            _index((("packId", 1),), "uniq_repair_packs_pack_id", unique=True),
            _index(
                (("farmId", 1), ("status", 1), ("fixTarget", 1)),
                "idx_repair_packs_farm_status_fix_target",
            ),
            _index(
                (("status", 1), ("fixTarget", 1)), "idx_repair_packs_status_fix_target"
            ),
        ),
        "reviewIssueChains": (
            _index(
                (("mysqlId", 1),),
                "uniq_review_issue_chains_mysql_id",
                unique=True,
            ),
            _index((("chainId", 1),), "uniq_review_issue_chains_chain_id", unique=True),
            _index(
                (("farmId", 1), ("sessionId", 1), ("status", 1)),
                "idx_review_issue_chains_farm_session_status",
            ),
            _index(
                (("farmId", 1), ("severity", 1), ("createdAt", -1)),
                "idx_review_issue_chains_farm_severity_created_at",
            ),
            _index(
                (("sessionId", 1), ("status", 1)),
                "idx_review_issue_chains_session_status",
            ),
            _index(
                (("severity", 1), ("createdAt", -1)),
                "idx_review_issue_chains_severity_created_at",
            ),
        ),
        "prelabels": (
            _index((("mysqlId", 1),), "uniq_prelabels_mysql_id", unique=True),
            _index(
                (("farmId", 1), ("sampleId", 1), ("source", 1)),
                "idx_prelabels_farm_sample_source",
            ),
            _index(
                (("farmId", 1), ("status", 1), ("confidence", -1)),
                "idx_prelabels_farm_status_confidence",
            ),
            _index(
                (("farmId", 1), ("judgeModel", 1), ("promptVersion", 1)),
                "idx_prelabels_farm_judge_model_prompt_version",
            ),
            _index((("sampleId", 1), ("source", 1)), "idx_prelabels_sample_source"),
            _index(
                (("status", 1), ("confidence", -1)), "idx_prelabels_status_confidence"
            ),
            _index(
                (("judgeModel", 1), ("promptVersion", 1)),
                "idx_prelabels_judge_model_prompt_version",
            ),
        ),
    }


def build_dry_run_plan(
    plan: IndexPlan | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """返回可打印、可测试的索引计划。"""
    selected_plan = plan or get_index_plan()
    return {
        collection_name: [index.as_dry_run() for index in indexes]
        for collection_name, indexes in selected_plan.items()
    }


def _mongodb_enabled_by_static_config() -> bool:
    env_value = os.getenv("MONGODB__ENABLED")
    if env_value is not None:
        return env_value.lower() in {"1", "true", "yes", "on"}

    config_path = BACKEND_ROOT / "config.yaml"
    if not config_path.exists():
        return False

    in_mongodb_section = False
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            in_mongodb_section = line.strip() == "mongodb:"
            continue
        if in_mongodb_section and line.lstrip().startswith("enabled:"):
            _, value = line.split(":", 1)
            return value.strip().strip("\"'").lower() in {"1", "true", "yes", "on"}
    return False


async def apply_index_plan(
    database: Any, plan: IndexPlan | None = None
) -> dict[str, list[str]]:
    """对传入 database 执行索引计划，重复执行依赖 Mongo createIndex 幂等语义。"""
    selected_plan = plan or get_index_plan()
    result: dict[str, list[str]] = {}
    for collection_name, indexes in selected_plan.items():
        collection = database[collection_name]
        result[collection_name] = []
        for index in indexes:
            index_name = await collection.create_index(
                list(index.keys), **index.options
            )
            result[collection_name].append(index_name)
    return result


async def _run(dry_run: bool) -> dict[str, Any]:
    plan = get_index_plan()
    if dry_run:
        return build_dry_run_plan(plan)

    if not _mongodb_enabled_by_static_config():
        raise RuntimeError("MongoDB 未启用，无法执行索引初始化")

    from app.core.config import settings
    from app.infra.mongo import create_mongo_client

    if not settings.mongodb.enabled:
        raise RuntimeError("MongoDB 未启用，无法执行索引初始化")

    client = create_mongo_client(settings.mongodb)
    try:
        return await apply_index_plan(client[settings.mongodb.database], plan)
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化第 1 期 MongoDB 集合索引")
    parser.add_argument(
        "--dry-run", action="store_true", help="仅输出索引计划，不连接 MongoDB"
    )
    args = parser.parse_args()

    result = asyncio.run(_run(dry_run=args.dry_run))
    for collection_name, indexes in result.items():
        print(f"{collection_name}: {indexes}")


if __name__ == "__main__":
    main()
