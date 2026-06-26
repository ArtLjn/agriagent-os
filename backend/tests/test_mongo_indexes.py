"""MongoDB 索引初始化脚本测试。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


class FakeCollection:
    def __init__(self):
        self.calls = []

    async def create_index(self, keys, **options):
        self.calls.append((tuple(keys), dict(options)))
        return options.get("name")


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, collection_name):
        if collection_name not in self.collections:
            self.collections[collection_name] = FakeCollection()
        return self.collections[collection_name]


@pytest.mark.no_db
def test_mongo_index_plan_contains_document_collections_and_tenant_indexes():
    from scripts.init_mongo_indexes import get_index_plan

    plan = get_index_plan()

    assert set(plan) == {
        "traceRecords",
        "caseDrafts",
        "repairPacks",
        "reviewIssueChains",
        "prelabels",
        "conversationMessages",
        "agentRecords",
        "guardrailsLogs",
    }

    for indexes in plan.values():
        assert any(
            index.keys == (("mysqlId", 1),) and index.options["unique"] is True
            for index in indexes
        )
        assert any(
            "farmId" in [field for field, _direction in index.keys] for index in indexes
        )

    trace_indexes = plan["traceRecords"]
    request_id_indexes = [
        index for index in trace_indexes if index.keys == (("requestId", 1),)
    ]
    assert request_id_indexes
    assert all("unique" not in index.options for index in request_id_indexes)
    assert any(
        index.keys == (("requestId", 1), ("roundIndex", 1), ("mysqlId", 1))
        and "unique" not in index.options
        for index in trace_indexes
    )
    assert any(
        index.keys == (("createdAt", 1),)
        and index.options["expireAfterSeconds"] == 60 * 60 * 24 * 30 * 18
        for index in trace_indexes
    )

    assert any(
        index.keys == (("draftId", 1),) and index.options["unique"] is True
        for index in plan["caseDrafts"]
    )
    assert any(
        index.keys == (("packId", 1),) and index.options["unique"] is True
        for index in plan["repairPacks"]
    )
    assert any(
        index.keys == (("chainId", 1),) and index.options["unique"] is True
        for index in plan["reviewIssueChains"]
    )
    assert any(
        index.keys == (("sampleId", 1), ("source", 1)) for index in plan["prelabels"]
    )

    assert any(
        index.keys
        == (
            ("farmId", 1),
            ("conversationId", 1),
            ("createdAt", 1),
            ("mysqlId", 1),
        )
        for index in plan["conversationMessages"]
    )
    assert any(
        index.keys
        == (("farmId", 1), ("sessionId", 1), ("createdAt", 1), ("mysqlId", 1))
        for index in plan["conversationMessages"]
    )
    assert any(
        index.keys == (("farmId", 1), ("turnId", 1))
        for index in plan["conversationMessages"]
    )

    assert any(
        index.keys == (("farmId", 1), ("recordType", 1), ("createdAt", -1))
        for index in plan["agentRecords"]
    )
    assert any(
        index.keys
        == (
            ("farmId", 1),
            ("cycleId", 1),
            ("recordType", 1),
            ("createdAt", -1),
        )
        for index in plan["agentRecords"]
    )
    assert any(
        index.keys == (("farmId", 1), ("conversationId", 1), ("createdAt", -1))
        for index in plan["agentRecords"]
    )

    guardrails_indexes = plan["guardrailsLogs"]
    assert any(
        index.keys == (("farmId", 1), ("triggerType", 1), ("createdAt", -1))
        for index in guardrails_indexes
    )
    assert any(index.keys == (("sourceTextHash", 1),) for index in guardrails_indexes)
    assert all(
        "expireAfterSeconds" not in index.options for index in guardrails_indexes
    )


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_apply_index_plan_is_idempotent_for_repeated_fake_collection_runs():
    from scripts.init_mongo_indexes import apply_index_plan, get_index_plan

    database = FakeDatabase()
    plan = get_index_plan()

    first_result = await apply_index_plan(database, plan)
    second_result = await apply_index_plan(database, plan)

    assert first_result == second_result
    for collection_name, indexes in plan.items():
        calls = database.collections[collection_name].calls
        assert calls[: len(indexes)] == calls[len(indexes) :]


@pytest.mark.no_db
def test_dry_run_index_plan_is_stable_and_has_named_indexes():
    from scripts.init_mongo_indexes import build_dry_run_plan

    first_plan = build_dry_run_plan()
    second_plan = build_dry_run_plan()

    assert first_plan == second_plan
    assert first_plan["traceRecords"][0] == {
        "keys": [("mysqlId", 1)],
        "options": {"name": "uniq_trace_records_mysql_id", "unique": True},
    }


@pytest.mark.no_db
def test_script_non_dry_run_reports_disabled_mongo_instead_of_import_error():
    env = os.environ.copy()
    env["MONGODB__ENABLED"] = "false"
    result = subprocess.run(
        [sys.executable, "scripts/init_mongo_indexes.py"],
        capture_output=True,
        check=False,
        cwd=BACKEND_DIR,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert "MongoDB 未启用，无法执行索引初始化" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
