"""备忘录的持久化、权限、幂等与 Agent 接入回归。"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastmcp import Client, FastMCP
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent.domains.harness.runtime.turn import Turn
from agent.domains.harness.tools import loader as skill_loader
from agent.domains.harness.tools.context import SkillContext
from agent.platforms.mcp.client import BusinessClient
from farm_business.api import memos
from farm_business.api.deps import get_current_user
from farm_business.db import get_db
from farm_business.models import Memo
from farm_business.services import memo_service as service
from farm_business.tools import _headers, farm_review
from farm_business.tools import memos as memo_tools
from shared.api_response import install_api_exception_handlers
from shared.roles import Permission


@pytest.fixture
def sessions():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Memo.__table__.create(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def request(key="one", **changes):
    return service.MemoCreate(
        **{
            "title": "采购清单",
            "content": "滴灌接头 20 个",
            "client_request_id": key,
            **changes,
        }
    )


@pytest.fixture
def skill_registry():
    return skill_loader.load_registry()


@pytest_asyncio.fixture
async def skill_context(sessions, monkeypatch):
    """保留真实 MCP 编解码与业务落库，仅替换传输、数据库和已验证主体。"""
    monkeypatch.setattr(
        _headers, "get_principal", lambda permission: {"farm_id": 1, "user_id": "u1"}
    )
    monkeypatch.setattr(memo_tools, "session_scope", sessions.begin)
    monkeypatch.setattr(farm_review, "session_scope", sessions.begin)
    server = FastMCP("备忘录接入测试")
    for tool in (
        memo_tools.manage_memos,
        farm_review.get_farm_review,
        farm_review.get_payment_overview,
    ):
        server.tool(tool)
    async with Client(server) as transport:
        client = BusinessClient(url="http://localhost/mcp")
        client._client = transport
        yield SkillContext(business_client=client, turn=Turn(), user_id="u1", farm_id=1)


@pytest.mark.asyncio
async def test_agent_memo_tools_execute_through_mcp_to_persistence(
    skill_registry, skill_context, sessions
):
    create = skill_registry.require("create_memo")
    params = request().model_dump()
    created = await create.execute(params, skill_context)
    assert created.ok
    memo_id = created.data["id"]
    replay = await create.execute(params, skill_context)
    assert replay.ok and replay.data == created.data
    with sessions.begin() as db:
        assert db.query(Memo).count() == 1

    for pinned in [True, False]:
        updated = await skill_registry.require("update_memo").execute(
            {"memo_id": memo_id, "pinned": pinned}, skill_context
        )
        assert updated.ok and updated.data["pinned"] is pinned
    for archived in [True, False]:
        changed = await skill_registry.require("archive_memo").execute(
            {"memo_id": memo_id, "archived": archived}, skill_context
        )
        assert changed.ok and changed.data["archived"] is archived
        found = await skill_registry.require("query_memos").execute(
            {"keyword": "接头", "archived": archived}, skill_context
        )
        assert found.ok and found.data["total"] == 1
        assert found.data["items"][0]["id"] == memo_id
        hidden = await skill_registry.require("query_memos").execute(
            {"archived": not archived}, skill_context
        )
        assert hidden.ok and hidden.data["total"] == 0


@pytest.mark.asyncio
async def test_agent_memo_failure_does_not_report_success(
    skill_registry, skill_context, sessions
):
    create = skill_registry.require("create_memo")
    assert (await create.execute(request().model_dump(), skill_context)).ok
    conflict = await create.execute(
        request(content="另一份采购内容").model_dump(), skill_context
    )
    assert not conflict.ok and conflict.data["code"] == "idempotency_conflict"
    invalid = await create.execute(
        request().model_dump() | {"title": " "}, skill_context
    )
    assert not invalid.ok and invalid.data["code"] == "validation_error"
    missing = await skill_registry.require("update_memo").execute(
        {"memo_id": 999, "content": "不存在"}, skill_context
    )
    assert not missing.ok and missing.data["code"] == "not_found"
    with sessions.begin() as db:
        assert db.query(Memo).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,params",
    [
        ("create_memo", {"title": "标题", "content": "内容"}),
        ("update_memo", {"memo_id": 1}),
        ("archive_memo", {"memo_id": 1}),
    ],
)
async def test_agent_rejects_missing_memo_arguments_before_mcp(
    skill_registry, name, params
):
    from unittest.mock import AsyncMock

    ctx = AsyncMock(spec=SkillContext)
    result = await skill_registry.require(name).execute(params, ctx)
    assert not result.ok
    ctx.call_mcp_tool.assert_not_awaited()


def test_router_exposes_memo_actions_and_review_tools(skill_registry):
    names = {item["name"] for item in skill_registry.router_catalog()}
    assert {"manage_memos", "get_farm_review", "get_payment_overview"} <= names
    selected = skill_registry.tools_for_router_skills(("manage_memos",))
    assert {tool["function"]["name"] for tool in selected} == {
        "create_memo",
        "query_memos",
        "update_memo",
        "archive_memo",
    }
    for tool in selected:
        properties = tool["function"]["parameters"]["properties"]
        assert not {"operation", "farm_id", "user_id"} & properties.keys()


def test_persistence_idempotency_and_conflict(sessions):
    with sessions.begin() as db:
        first = service.create_memo(db, farm_id=1, user_id="u1", request=request())
    with sessions.begin() as db:
        again = service.create_memo(db, farm_id=1, user_id="u1", request=request())
        assert again == first
        assert db.query(Memo).count() == 1
        with pytest.raises(service.MemoError, match="不同备忘录") as error:
            service.create_memo(
                db, farm_id=1, user_id="u1", request=request(content="新内容")
            )
        assert error.value.code == "idempotency_conflict"


def test_isolation_search_pin_archive_restore(sessions):
    with sessions.begin() as db:
        mine = service.create_memo(db, farm_id=1, user_id="u1", request=request())
        service.create_memo(db, farm_id=2, user_id="u1", request=request())
        service.create_memo(db, farm_id=1, user_id="u2", request=request())
        literal = service.create_memo(
            db,
            farm_id=1,
            user_id="u1",
            request=request("two", title="浓度 10%", pinned=True),
        )
        assert (
            service.list_memos(db, farm_id=1, user_id="u1")["items"][0]["id"]
            == literal["id"]
        )
        assert (
            service.list_memos(db, farm_id=1, user_id="u1", keyword="%")["total"] == 1
        )
        assert (
            service.list_memos(db, farm_id=1, user_id="u1", keyword="接头")["total"]
            == 2
        )
        for farm_id, user_id in [(2, "u1"), (1, "u2")]:
            with pytest.raises(service.MemoError) as error:
                service.update_memo(
                    db,
                    farm_id=farm_id,
                    user_id=user_id,
                    memo_id=mine["id"],
                    request=service.MemoUpdate(title="越权"),
                )
            assert error.value.code == "not_found"
        for archived in [True, False]:
            updated = service.update_memo(
                db,
                farm_id=1,
                user_id="u1",
                memo_id=mine["id"],
                request=service.MemoUpdate(archived=archived),
            )
            assert updated["archived"] is archived
            assert updated["content"] == "滴灌接头 20 个"
        with pytest.raises(service.MemoError):
            service.update_memo(
                db,
                farm_id=1,
                user_id="u1",
                memo_id=mine["id"],
                request=service.MemoUpdate(content=None),
            )


@pytest.mark.parametrize(
    "changes",
    [{"content": "   "}, {"title": ""}, {"content": "字" * 10001}, {"farm_id": 2}],
)
def test_invalid_content_rejected(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_rest_permissions_validation_and_isolation(sessions):
    principal = {
        "farm_id": 1,
        "user_id": "u1",
        "role": "user",
        "scope": "farm:read farm:write",
    }
    app = FastAPI()
    install_api_exception_handlers(app)
    app.include_router(memos.router, prefix="/api/v2")
    app.dependency_overrides[get_current_user] = lambda: principal

    def db_dependency():
        with sessions.begin() as db:
            yield db

    app.dependency_overrides[get_db] = db_dependency
    with TestClient(app) as client:
        response = client.post("/api/v2/memos", json=request().model_dump())
        assert response.status_code == 201
        memo_id = response.json()["id"]
        assert client.get("/api/v2/memos").json()["total"] == 1
        assert client.patch(f"/api/v2/memos/{memo_id}", json={"pinned": True}).json()[
            "pinned"
        ]
        assert client.patch(f"/api/v2/memos/{memo_id}", json={}).status_code == 422
        assert (
            client.post(
                "/api/v2/memos", json={**request().model_dump(), "farm_id": 9}
            ).status_code
            == 422
        )
        principal["user_id"] = "u2"
        assert client.get("/api/v2/memos").json()["total"] == 0
        assert (
            client.patch(
                f"/api/v2/memos/{memo_id}", json={"archived": True}
            ).status_code
            == 404
        )
        principal["scope"] = "farm:read"
        assert (
            client.post("/api/v2/memos", json=request().model_dump()).status_code == 403
        )
    app.dependency_overrides.pop(get_current_user)
    with TestClient(app) as client:
        assert client.get("/api/v2/memos").status_code == 401


def test_mcp_and_skill_operation_contract(sessions, monkeypatch):
    permissions = []

    def principal(permission):
        permissions.append(permission)
        return {"farm_id": 1, "user_id": "u1"}

    monkeypatch.setattr(_headers, "get_principal", principal)
    monkeypatch.setattr(memo_tools, "session_scope", sessions.begin)
    created = memo_tools.manage_memos(operation="create", **request().model_dump())
    assert memo_tools.manage_memos(operation="query")["total"] == 1
    assert memo_tools.manage_memos(
        operation="archive", memo_id=created["id"], archived=True
    )["archived"]
    assert permissions == [
        Permission.FARM_WRITE,
        Permission.FARM_READ,
        Permission.FARM_WRITE,
    ]
    registry = skill_loader.load_registry()
    assert registry.require("create_memo").risk_level == "write_confirm"
    assert registry.require("query_memos").risk_level == "read"
    assert registry.require("get_farm_review").risk_level == "read"
    assert registry.require("get_payment_overview").risk_level == "read"


@pytest.mark.asyncio
async def test_farm_review_uses_complete_counts_and_bounded_preview(
    sessions, monkeypatch, skill_registry, skill_context
):
    from datetime import datetime, timedelta

    from farm_business.models import FarmLog
    from farm_business.tools import farm_review

    with sessions.begin() as db:
        FarmLog.__table__.create(db.get_bind())
        today = datetime(2026, 10, 23)
        db.add_all(
            [
                FarmLog(
                    farm_id=1,
                    cycle_id=1,
                    operation_type="浇水",
                    operation_date=today.date(),
                )
                for _ in range(25)
            ]
        )
        db.add_all(
            [
                FarmLog(
                    farm_id=2,
                    cycle_id=1,
                    operation_type="施肥",
                    operation_date=today.date(),
                ),
                FarmLog(
                    farm_id=1,
                    cycle_id=1,
                    operation_type="旧记录",
                    operation_date=(today - timedelta(days=7)).date(),
                ),
                FarmLog(
                    farm_id=1,
                    cycle_id=1,
                    operation_type="未来记录",
                    operation_date=(today + timedelta(days=1)).date(),
                ),
            ]
        )
    monkeypatch.setattr(farm_review, "session_scope", sessions.begin)
    monkeypatch.setattr(farm_review, "get_farm_id_from_headers", lambda: 1)
    monkeypatch.setattr(farm_review, "beijing_now", lambda: today)
    execution = await skill_registry.require("get_farm_review").execute(
        {}, skill_context
    )
    assert execution.ok
    result = execution.data
    assert result["total"] == 25
    assert len(result["recent_logs"]) == 20
    assert result["by_operation"] == [{"operation_type": "浇水", "count": 25}]
    assert result["start_date"] == "2026-10-17"
    assert farm_review.get_farm_review(0)["code"] == "validation_error"


@pytest.mark.asyncio
async def test_payment_overview_separates_directions_and_excludes_deleted(
    sessions, monkeypatch, skill_registry, skill_context
):
    from datetime import datetime

    from farm_business.models import CostRecord, LaborEntry, Worker
    from farm_business.tools import farm_review

    with sessions.begin() as db:
        for model in [CostRecord, Worker, LaborEntry]:
            model.__table__.create(db.get_bind())
        for kind, amount, settled, farm, deleted in [
            ("cost", 100, 30, 1, None),
            ("income", 200, 0, 1, None),
            ("cost", 999, 0, 2, None),
            ("cost", 555, 0, 1, datetime.now()),
            ("cost", 100, 100, 1, None),
        ]:
            db.add(
                CostRecord(
                    farm_id=farm,
                    record_type=kind,
                    category="赊账",
                    record_subtype="赊账",
                    counterparty="农资店",
                    amount=amount,
                    settled_amount=settled,
                    record_date=datetime.now().date(),
                    deleted_at=deleted,
                )
            )
        db.add(Worker(id=1, farm_id=1, name="张师傅"))
        db.add(
            LaborEntry(
                farm_id=1,
                work_order_id=1,
                worker_id=1,
                unit_price=300,
                payable_amount=300,
                unpaid_amount=300,
            )
        )
    monkeypatch.setattr(farm_review, "session_scope", sessions.begin)
    monkeypatch.setattr(farm_review, "get_farm_id_from_headers", lambda: 1)
    execution = await skill_registry.require("get_payment_overview").execute(
        {}, skill_context
    )
    assert execution.ok
    result = execution.data
    assert result["debts"] == [
        {"record_type": "cost", "counterparty": "农资店", "remaining": 70.0},
        {"record_type": "income", "counterparty": "农资店", "remaining": 200.0},
    ]
    assert result["unpaid_labor"]["total_unpaid"] == 300


@pytest.mark.asyncio
async def test_server_registers_new_mcp_tools_and_rest_routes():
    from farm_business import server
    from farm_business.mcp_app import mcp

    names = {tool.name for tool in await mcp.list_tools()}
    assert {"manage_memos", "get_farm_review", "get_payment_overview"} <= names
    paths = server.create_app().openapi()["paths"]
    assert set(paths["/api/v2/memos"]) == {"get", "post"}
    assert "patch" in paths["/api/v2/memos/{memo_id}"]


def test_mcp_denies_write_before_opening_database(monkeypatch):
    def deny(permission):
        raise _headers.McpToolAuthorizationError(permission)

    def unexpected_database():
        pytest.fail("未授权请求不应访问数据库")

    monkeypatch.setattr(_headers, "get_principal", deny)
    monkeypatch.setattr(memo_tools, "session_scope", unexpected_database)
    with pytest.raises(_headers.McpToolAuthorizationError) as error:
        memo_tools.manage_memos(operation="create", **request().model_dump())
    assert error.value.permission == Permission.FARM_WRITE


@pytest.mark.parametrize("operation", ["query", "create", "update", "archive"])
def test_missing_table_is_safe_in_mcp(sessions, monkeypatch, operation):
    monkeypatch.setattr(
        _headers, "get_principal", lambda permission: {"farm_id": 1, "user_id": "u1"}
    )
    monkeypatch.setattr(memo_tools, "session_scope", sessions.begin)
    with sessions.begin() as db:
        Memo.__table__.drop(db.connection())
    result = memo_tools.manage_memos(
        operation=operation, memo_id=1, archived=True, **request().model_dump()
    )
    assert result["code"] == "memo_schema_not_ready"
    assert result["error"] == result["code"]
    assert result["meta"] == {"operation": operation}
    assert "SELECT" not in str(result) and "接头" not in str(result)


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/api/v2/memos", None),
        ("post", "/api/v2/memos", request().model_dump()),
        ("patch", "/api/v2/memos/1", {"title": "秘密笔记"}),
    ],
)
def test_rest_missing_table_returns_actionable_503(sessions, method, path, body):
    with sessions.begin() as db:
        Memo.__table__.drop(db.connection())
    app = FastAPI()
    install_api_exception_handlers(app)
    app.include_router(memos.router, prefix="/api/v2")
    app.dependency_overrides[get_current_user] = lambda: {
        "farm_id": 1,
        "user_id": "u1",
        "role": "user",
        "scope": "farm:read farm:write",
    }

    def db_dependency():
        with sessions.begin() as db:
            yield db

    app.dependency_overrides[get_db] = db_dependency
    with TestClient(app) as client:
        response = client.request(method, path, json=body)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "memo_schema_not_ready"
    assert "SQL" not in response.text and "秘密笔记" not in response.text


@pytest.mark.parametrize(
    "number,code", [(1146, "memo_schema_not_ready"), (2006, "memo_storage_unavailable")]
)
def test_mysql_storage_errors_do_not_expose_parameters(number, code):
    from pymysql.err import ProgrammingError
    from sqlalchemy.exc import DBAPIError

    error = service.storage_error(
        DBAPIError(
            "SELECT secret FROM memos",
            {"content": "秘密"},
            ProgrammingError(number, "秘密 SQL"),
        ),
        operation="create",
    )
    assert error.code == code
    assert "秘密" not in str(error)
