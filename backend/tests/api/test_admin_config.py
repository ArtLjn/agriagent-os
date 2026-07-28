"""Tests for Admin Config API。"""

from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import admin_headers, auth_override_scope, ensure_admin_user


class TestListSkills:
    def test_returns_skill_list(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/skills", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["items"]
        metadata = data["items"][0]["metadata"]
        assert "permission_level" in metadata
        assert "risk_level" in metadata
        assert "metadata_incomplete" in metadata
        assert "context_dependencies" in metadata
        assert "cache_invalidation" in metadata
        assert "enabled" in metadata
        assert "disabled_reason" in metadata

    def test_returns_skill_status_summary(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/skills", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == data["total"]
        assert data["summary"]["enabled"] > 0
        assert data["summary"]["disabled"] >= 1
        assert data["summary"]["admin_only"] >= 0
        disabled = [item for item in data["items"] if item["status"] == "disabled"]
        assert disabled
        assert disabled[0]["metadata"]["enabled"] is False

    def test_update_skill_enabled_state(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            disabled_resp = TestClient(app).put(
                "/admin/skills/manage_cost/enabled",
                headers=admin_headers(),
                json={"enabled": False, "disabled_reason": "测试禁用"},
            )
            list_resp = TestClient(app).get("/admin/skills", headers=admin_headers())
            enabled_resp = TestClient(app).put(
                "/admin/skills/manage_cost/enabled",
                headers=admin_headers(),
                json={"enabled": True},
            )

        assert disabled_resp.status_code == 200
        assert disabled_resp.json()["metadata"]["enabled"] is False
        assert disabled_resp.json()["metadata"]["disabled_reason"] == "测试禁用"
        items = {item["name"]: item for item in list_resp.json()["items"]}
        assert items["manage_cost"]["status"] == "disabled"
        assert items["manage_cost"]["metadata"]["disabled_reason"] == "测试禁用"
        assert enabled_resp.status_code == 200
        assert enabled_resp.json()["metadata"]["enabled"] is True
        assert enabled_resp.json()["metadata"]["disabled_reason"] is None


class TestSkillRouteRecall:
    def test_preview_returns_ranked_skill_candidates(self, db_session, monkeypatch) -> None:
        ensure_admin_user(db_session)
        vector_calls: list[str] = []

        def fake_vector_search(query: str, candidates) -> dict[str, float]:
            vector_calls.append(query)
            return {
                f"{candidate.name}.{candidate.operation}": (
                    0.99
                    if candidate.name == "manage_farm_logs"
                    and candidate.operation == "query_logs"
                    else 0.01
                )
                for candidate in candidates
            }

        monkeypatch.setattr(
            "app.ops.skill_route_eval.build_skill_vector_search_fn",
            lambda: fake_vector_search,
        )
        monkeypatch.setattr(
            "app.agent.router.service.build_skill_vector_search_fn",
            lambda: fake_vector_search,
        )
        with auth_override_scope(app):
            resp = TestClient(app).post(
                "/admin/skills/route-recall",
                headers=admin_headers(),
                json={"message": "我的农事", "top_k": 3},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "我的农事"
        assert data["top_k"] == 3
        assert data["recall_mode"] == "hybrid_vector"
        assert data["vector_index_enabled"] is True
        assert data["recall"]["path"] == "bm25_vector_hybrid"
        assert data["recall"]["candidate_scope"] == "read"
        assert data["recall"]["vector_search_used"] is True
        assert data["recall"]["quillrag_retrieve_used"] is True
        assert data["top_candidates"][0]["route"] == "manage_farm_logs.query_logs"
        assert vector_calls == ["我的农事", "我的农事"]
        assert data["candidates"][0]["skill"] == "manage_farm_logs"
        assert data["candidates"][0]["operation"] == "query_logs"
        assert data["candidates"][0]["score"] > 0
        assert "vector" in data["candidates"][0]["evidence"]["sources"]
        assert data["candidates"][0]["evidence"]["score"] == data["candidates"][0]["score"]
        assert data["skill_router"]["selected"]["operations"] == {
            "manage_farm_logs": ["query_logs"]
        }
        assert data["skill_router"]["summary"].get("fallback") != (
            "model_choice_read_default"
        )
        assert data["skill_router"]["recall"]["path"] == (
            "bm25_vector_hybrid"
        )
        assert data["skill_router"]["recall"]["vector_search_used"] is True

    def test_dataset_eval_uses_json_cases(self, db_session, monkeypatch) -> None:
        ensure_admin_user(db_session)

        def fake_vector_search(_query: str, candidates) -> dict[str, float]:
            return {
                f"{candidate.name}.{candidate.operation}": 0.1
                for candidate in candidates
            }

        monkeypatch.setattr(
            "app.ops.skill_route_eval.build_skill_vector_search_fn",
            lambda: fake_vector_search,
        )
        with auth_override_scope(app):
            resp = TestClient(app).post(
                "/admin/skills/route-recall/evaluate",
                headers=admin_headers(),
                json={"top_k": 5},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset"]["format"] == "json"
        assert data["report"]["total"] >= 1
        assert data["report"]["recall_at_k"] >= data["report"]["recall_at_1"]
        assert "failures" in data["report"]

    def test_dataset_contains_debt_query_regression_case(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get(
                "/admin/skills/route-recall/dataset",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        items = {item["id"]: item for item in resp.json()["items"]}
        assert items["debt_query_001"]["message"] == "我有哪些欠款"
        assert items["debt_query_001"]["expected"] == {
            "skill": "manage_cost",
            "operation": "query_debt",
        }


class TestListPrompts:
    def test_returns_prompt_list(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/prompts", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetConfig:
    def test_config_masks_api_key(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        key = data["ai"]["api_key"]
        assert "***" in key

    def test_config_returns_monthly_and_weekly_quota(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["token_quota"]["monthly_limit"] == 200000
        assert data["token_quota"]["weekly_limit"] == 50000
        assert data["token_quota"]["over_quota_action"] == "reject"
        assert "daily_limit" not in data["token_quota"]

    def test_config_returns_session_summary_flag(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["ai"]["enable_session_summary"] is True


class TestClearCache:
    def test_clear_cache(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).post("/admin/cache/clear", headers=admin_headers())

        assert resp.status_code == 200
        assert "cleared" in resp.json()


class TestReloadPrompts:
    def test_reload(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).post(
                "/admin/prompts/reload",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
