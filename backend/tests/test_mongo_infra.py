"""MongoDB client provider 与健康检查测试。"""

import pytest


class FakeAdmin:
    def __init__(self, error: Exception | None = None):
        self.error = error

    async def command(self, command_name: str):
        assert command_name == "ping"
        if self.error:
            raise self.error
        return {"ok": 1}


class FakeDatabase:
    def __init__(self, name: str, error: Exception | None = None):
        self.name = name
        self.client = type("FakeClient", (), {"admin": FakeAdmin(error)})()


@pytest.mark.no_db
def test_redact_mongo_uri_masks_password_and_preserves_host():
    from app.infra.mongo import redact_mongo_uri

    redacted = redact_mongo_uri(
        "mongodb://farm_user:plain-secret@mongo.internal:27017/farm_manager"
        "?authSource=admin"
    )

    assert redacted == (
        "mongodb://farm_user:***@mongo.internal:27017/farm_manager?authSource=admin"
    )
    assert "plain-secret" not in redacted


@pytest.mark.no_db
def test_redact_mongo_uri_masks_srv_connection_password():
    from app.infra.mongo import redact_mongo_uri

    redacted = redact_mongo_uri(
        "mongodb+srv://farm_user:plain-secret@cluster.example/farm_manager"
    )

    assert redacted == "mongodb+srv://farm_user:***@cluster.example/farm_manager"
    assert "plain-secret" not in redacted


@pytest.mark.no_db
def test_redact_mongo_uri_preserves_replica_set_hosts():
    from app.infra.mongo import redact_mongo_uri

    redacted = redact_mongo_uri(
        "mongodb://farm_user:plain-secret@host1:27017,host2:27017/farm_manager"
        "?replicaSet=rs0"
    )

    assert redacted == (
        "mongodb://farm_user:***@host1:27017,host2:27017/farm_manager?replicaSet=rs0"
    )
    assert "plain-secret" not in redacted


@pytest.mark.no_db
def test_redact_mongo_uri_preserves_ipv6_brackets():
    from app.infra.mongo import redact_mongo_uri

    redacted = redact_mongo_uri(
        "mongodb://farm_user:plain-secret@[::1]:27017/farm_manager"
    )

    assert redacted == "mongodb://farm_user:***@[::1]:27017/farm_manager"
    assert "plain-secret" not in redacted


@pytest.mark.no_db
def test_create_mongo_client_uses_configured_timeouts_and_pool(monkeypatch):
    from app.core.config import MongoConfig
    from app.infra import mongo

    calls = []

    class FakeMotorClient:
        def __init__(self, uri: str, **kwargs):
            calls.append((uri, kwargs))

    monkeypatch.setattr(mongo, "AsyncIOMotorClient", FakeMotorClient)

    client = mongo.create_mongo_client(
        MongoConfig(
            uri="mongodb://user:secret@localhost:27017/farm_manager",
            tls=True,
            connect_timeout_ms=1234,
            server_selection_timeout_ms=2345,
            max_pool_size=17,
        )
    )

    assert isinstance(client, FakeMotorClient)
    assert calls == [
        (
            "mongodb://user:secret@localhost:27017/farm_manager",
            {
                "tls": True,
                "connectTimeoutMS": 1234,
                "serverSelectionTimeoutMS": 2345,
                "maxPoolSize": 17,
            },
        )
    ]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_check_mongo_health_returns_ok_for_ping_success():
    from app.infra.mongo import check_mongo_health

    result = await check_mongo_health(FakeDatabase("farm_manager_docs"))

    assert result == {
        "status": "ok",
        "database": "farm_manager_docs",
        "code": "mongo_ping_ok",
    }


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_check_mongo_health_accepts_real_motor_database_without_bool_check(
    monkeypatch,
):
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.infra.mongo import check_mongo_health

    client = AsyncIOMotorClient("mongodb://localhost:27017", connect=False)
    database = client["farm_manager_docs"]

    async def fake_command(_admin, command_name: str):
        assert command_name == "ping"
        return {"ok": 1}

    monkeypatch.setattr(
        "motor.motor_asyncio.AsyncIOMotorDatabase.command",
        fake_command,
    )

    try:
        result = await check_mongo_health(database)
    finally:
        client.close()

    assert result == {
        "status": "ok",
        "database": "farm_manager_docs",
        "code": "mongo_ping_ok",
    }


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_check_mongo_health_returns_redacted_error_context():
    from app.infra.mongo import check_mongo_health

    result = await check_mongo_health(
        FakeDatabase(
            "farm_manager_docs",
            RuntimeError(
                "cannot connect mongodb://user:plain-secret@mongo.internal:27017/db"
            ),
        )
    )

    assert result["status"] == "error"
    assert result["database"] == "farm_manager_docs"
    assert result["code"] == "mongo_ping_failed"
    assert "plain-secret" not in result["context"]["error"]
    assert "***@mongo.internal" in result["context"]["error"]
