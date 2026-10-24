"""真实记忆服务验收：独立 Mongo/Redis、实际模型；空 MCP 隔离农场业务。"""

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import jwt
import pytest
from pymongo import MongoClient
from redis import Redis

from agent.config import settings
from shared.roles import UserRole, scope_for_role

pytestmark = pytest.mark.skipif(
    os.getenv("AGENT_MEMORY_E2E") != "1", reason="仅显式开启真实服务和模型验收"
)
_ROOT = Path(__file__).resolve().parents[1]
_SERVICE_PYTHON = os.getenv("AGENT_MEMORY_E2E_PYTHON", sys.executable)


@pytest.fixture
def service(tmp_path):
    """测试资源使用随机专属命名，退出时停止进程并精确清理。"""
    identifier = "memory_qa_" + uuid.uuid4().hex
    mongo = MongoClient(
        settings.mongodb.uri, tls=settings.mongodb.tls, serverSelectionTimeoutMS=3000
    )
    redis = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.database,
        username=settings.redis.username or None,
        password=settings.redis.password or None,
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        mcp_port = sock.getsockname()[1]
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "MONGODB__DATABASE": identifier,
        "REDIS__KEY_PREFIX": identifier,
        "MEMORY_POLL_SECONDS": "0.2",
        "MEMORY_RAG_URL": "",
        "MEMORY_RAG_API_KEY": "",
        "BUSINESS_MCP__URL": f"http://127.0.0.1:{mcp_port}/mcp",
    }
    user_id, farm_uid = str(uuid.uuid4()), str(uuid.uuid4())
    timestamp = int(time.time())
    token = jwt.encode(
        {
            "iss": settings.auth.jwt_issuer,
            "aud": settings.auth.jwt_audience,
            "sub": user_id,
            "farm_uid": farm_uid,
            "farm_id": 1,
            "role": UserRole.USER.value,
            "scope": scope_for_role(UserRole.USER),
            "type": "access",
            "iat": timestamp,
            "exp": timestamp + 3600,
            "jti": identifier,
        },
        settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
    )
    with (
        (tmp_path / "agent.log").open("w") as log,
        httpx.Client(
            base_url=f"http://127.0.0.1:{port}/api/v2",
            headers={"Authorization": "Bearer " + token},
            timeout=120,
        ) as http,
    ):

        def start():
            process = subprocess.Popen(
                [
                    _SERVICE_PYTHON,
                    "-B",
                    "-m",
                    "uvicorn",
                    "agent.bootstrap.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=_ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            for _ in range(100):
                if process.poll() is not None:
                    pytest.fail("测试服务启动失败，请查看 agent.log")
                try:
                    if http.get("/health").status_code == 200:
                        return process
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            process.terminate()
            process.wait(timeout=15)
            pytest.fail("测试服务启动超时")

        # Runtime 会主动连接业务 MCP；空协议服务只完成握手，不提供任何业务工具。
        business = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                (
                    "from fastmcp import FastMCP; import sys; "
                    "FastMCP('memory-qa').run(transport='http', host='127.0.0.1', port=int(sys.argv[1]))"
                ),
                str(mcp_port),
            ],
            cwd=_ROOT,
            env=env,
            stdout=log,
            stderr=log,
        )
        process = None

        def restart():
            nonlocal process
            process.terminate()
            process.wait(timeout=20)
            process = start()

        try:
            for _ in range(100):
                assert business.poll() is None, (
                    "空 MCP 测试服务启动失败，请查看 agent.log"
                )
                try:
                    http.get(f"http://127.0.0.1:{mcp_port}/mcp")
                    break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                pytest.fail("空 MCP 测试服务启动超时")
            process = start()
            yield http, mongo[identifier], user_id, farm_uid, restart
        finally:
            if process is not None:
                process.terminate()
                process.wait(timeout=20)
            business.terminate()
            business.wait(timeout=20)
            # 只有本 fixture 创建的随机专属命名可被销毁。
            assert identifier.startswith("memory_qa_") and len(identifier) == 42
            mongo.drop_database(identifier)
            keys = list(redis.scan_iter(match=identifier + ":*"))
            if keys:
                redis.delete(*keys)
            mongo.close()
            redis.close()


def chat(http, message, conversation):
    """通过真正的 SSE/Redis/Worker 路径收集公开事件，不直接调用领域函数。"""
    response = http.post(
        "/chat", json={"message": message, "conversation_id": conversation}
    )
    assert response.status_code == 200, response.text[:300]
    events = []
    for block in response.text.split("\n\n"):
        kind, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if kind and data is not None:
            events.append({"type": kind, "data": data})
    assert any(event["type"] == "done" for event in events), events
    return events


def learned(db, turn_id):
    """实际任务必须完成，不能将无候选、入队成功或主对话完成当作记忆生效。"""
    for _ in range(240):
        job = db.agentMemoryLearningTasksV2.find_one({"turn_id": turn_id})
        if job and job["status"] in {"done", "failed"}:
            assert job["status"] == "done", {
                k: job.get(k) for k in ("status", "error_code", "attempts")
            }
            return job
        time.sleep(0.5)
    pytest.fail("后台学习在 120 秒内未完成")


def turn_id(events):
    return next(e["data"]["turn_id"] for e in events if e["type"] == "done")


def test_real_legacy_correction_restart_and_cross_session_recall(service):
    http, db, user_id, _farm_uid, restart = service
    source = _ROOT / "agent/domains/harness/memory"
    expected = hashlib.sha256(
        b"".join(p.read_bytes() for p in sorted(source.glob("*.py")))
    ).hexdigest()[:16]
    assert http.get("/health").json()["runtime"]["memory_build"] == expected
    response = http.post(
        "/me/memories",
        json={
            "memory_id": "legacy-fruit",
            "key": "food_preference",
            "text": "偏好食用西瓜、芒果、葡萄和草莓",
            "scope": "user_farm",
            "category": "preference",
        },
    )
    assert response.status_code == 200, response.text
    prior = chat(http, "上次系统说保存失败了，请先回复收到。", "correction")
    learned(db, turn_id(prior))
    events = chat(http, "我不喜欢吃葡萄了", "correction")
    assert (
        next(e["data"]["status"] for e in events if e["type"] == "done") == "completed"
    ), json.dumps(events, ensure_ascii=False)
    job = learned(db, turn_id(events))
    assert job["applied_count"] >= 1, job
    records = http.get("/me/memories").json()["items"]
    assert len(records) == 1, records
    atoms = records[0]["atoms"]
    assert len(atoms) == 4, atoms
    grape = next(a for a in atoms if "葡萄" in a["text"])
    assert "不" in grape["text"] and grape["evidence_count"] == 1
    assert all(
        any(
            fruit in a["text"]
            and ("喜欢" in a["text"] or "偏好" in a["text"])
            and "不" not in a["text"]
            and a["source_type"] == "explicit"
            for a in atoms
        )
        for fruit in ("西瓜", "芒果", "草莓")
    ), atoms
    restart()
    events = chat(http, "我对葡萄的偏好是什么？只依据已有记忆回答。", "new-session")
    answer = "".join(
        e["data"].get("text", "") for e in events if e["type"] == "final_answer"
    )
    assert "葡萄" in answer and "不" in answer, answer
    assert "memory_explicit_intent_required" not in json.dumps(events)
    assert http.delete("/me/memories/legacy-fruit").status_code == 200
    document = db.agentUserPreferences.find_one(
        {"_id": f"{settings.auth.jwt_issuer}:{user_id}"}
    )
    assert "葡萄" not in json.dumps(document, default=str, ensure_ascii=False)
    assert not http.get("/me/memories").json()["items"]


def test_real_message_outbox_survives_assistant_failure_and_restart(service):
    http, db, user_id, farm_uid, restart = service
    identifier = "failed-assistant-turn"
    # 构造消息已提交、助手失败且尚未投递的崩溃边界，随后只通过启动后的后台恢复。
    db.conversationMessages.insert_one(
        {
            "userId": user_id,
            "farmId": 1,
            "conversationId": "failed",
            "turnId": identifier,
            "role": "user",
            "messageKind": "prompt",
            "content": "我一直偏好简洁的回答",
            "createdAt": "2026-10-24 10:00:00",
            "memoryLearningV2": {
                "status": "pending",
                "farm_uid": farm_uid,
                "observed_at": time.time(),
            },
        }
    )
    restart()
    result = learned(db, identifier)
    assert result["applied_count"] == 1
    assert "简洁" in str(http.get("/me/memories").json()["items"])


def test_real_explicit_save_and_background_share_facts(service):
    http, db, _user_id, _farm_uid, _restart = service
    events = chat(http, "请长期记住：我喜欢西瓜、芒果、葡萄和草莓。", "explicit")
    assert (
        next(e["data"]["status"] for e in events if e["type"] == "done") == "completed"
    ), events
    learned(db, turn_id(events))
    records = http.get("/me/memories").json()["items"]
    assert len(records) == 1, records
    atoms = records[0]["atoms"]
    assert len(atoms) == 4 and all(a["source_type"] == "explicit" for a in atoms), atoms
    assert all(a["evidence_count"] == 1 for a in atoms), atoms
