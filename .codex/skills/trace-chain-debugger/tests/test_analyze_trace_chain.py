"""trace-chain-debugger agri_backend_v2 召回协议测试，不连接真实服务。"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_trace_chain.py"
SPEC = importlib.util.spec_from_file_location("analyze_trace_chain", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def args_for(**overrides):
    values = {
        "project": ".",
        "request_id": None,
        "session_id": None,
        "turn_id": None,
        "trace_id": None,
        "conversation_id": None,
        "farm_id": None,
        "agri_backend_v2": True,
        "v2_base_url": "http://agent.test",
        "limit": 2,
        "include_payload": False,
        "include_events": True,
        "json": True,
    }
    values.update(overrides)
    return MODULE.argparse.Namespace(**values)


class V2RecallTest(unittest.TestCase):
    def tearDown(self):
        MODULE._AUTO_AUTH_CACHE.clear()

    def test_auto_auth_logs_in_with_environment_credentials(self):
        calls = []

        def fake_request(url, **kwargs):
            calls.append((url, kwargs))
            return {"access_token": "jwt-from-login"}

        with (
            patch.dict(
                os.environ,
                {
                    "V2_AGENT_PHONE": "13800138000",
                    "V2_AGENT_PASSWORD": "secret123",
                },
                clear=True,
            ),
            patch.object(MODULE, "_v2_request_json", side_effect=fake_request),
        ):
            authorization, automatic = MODULE._resolve_v2_authorization(
                "http://agent.test/api/v2"
            )

        self.assertEqual(authorization, "Bearer jwt-from-login")
        self.assertTrue(automatic)
        self.assertEqual(calls[0][1]["method"], "POST")
        self.assertEqual(
            calls[0][1]["payload"],
            {"phone": "13800138000", "password": "secret123"},
        )

    def test_loopback_auto_auth_selects_unique_dev_user(self):
        def fake_request(url, **kwargs):
            self.assertTrue(url.endswith("/dev-users"))
            return {"users": [{"phone": "13800138000", "token": "dev-jwt"}]}

        with (
            patch.dict(os.environ, {"V2_AGENT_AUTO_AUTH": "1"}, clear=True),
            patch.object(MODULE, "_v2_request_json", side_effect=fake_request),
        ):
            authorization, automatic = MODULE._resolve_v2_authorization(
                "http://127.0.0.1:8000/api/v2"
            )

        self.assertEqual(authorization, "Bearer dev-jwt")
        self.assertTrue(automatic)

    def test_explicit_authorization_has_priority_over_auto_auth(self):
        with (
            patch.dict(
                os.environ,
                {
                    "V2_AGENT_AUTHORIZATION": "Bearer explicit-jwt",
                    "V2_AGENT_PHONE": "13800138000",
                    "V2_AGENT_PASSWORD": "secret123",
                },
                clear=True,
            ),
            patch.object(MODULE, "_fetch_auto_authorization") as fetch,
        ):
            authorization, automatic = MODULE._resolve_v2_authorization(
                "http://127.0.0.1:8000/api/v2"
            )

        self.assertEqual(authorization, "Bearer explicit-jwt")
        self.assertFalse(automatic)
        fetch.assert_not_called()

    def test_conversation_recall_paginates_and_fetches_each_timeline(self):
        def fake_get_json(url: str):
            parsed = urlparse(url)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/api/agri_backend_v2/traces":
                if query.get("cursor") == ["c1"]:
                    return {
                        "items": [
                            {
                                "request_id": "trace-2",
                                "turn_id": "turn-2",
                                "conversation_id": "conv-1",
                            }
                        ],
                        "has_more": False,
                    }
                return {
                    "items": [
                        {
                            "request_id": "trace-1",
                            "turn_id": "turn-1",
                            "conversation_id": "conv-1",
                        }
                    ],
                    "next_cursor": "c1",
                    "has_more": True,
                }
            if path.endswith("/summary"):
                trace_id = path.split("/")[-2]
                return {
                    "request_id": trace_id,
                    "turn_id": trace_id.replace("trace", "turn"),
                    "conversation_id": "conv-1",
                    "status": "success",
                    "metrics": {},
                }
            if path.endswith("/nodes"):
                return {"nodes": []}
            if path.endswith("/timeline"):
                trace_id = path.split("/")[-2]
                return {
                    "events": [
                        {
                            "seq": 1,
                            "event_id": f"{trace_id}-event",
                            "event_type": "done",
                            "turn_id": trace_id.replace("trace", "turn"),
                            "terminal": True,
                        }
                    ]
                }
            if path.endswith("/conversations/conv-1"):
                if query.get("before") == ["2"]:
                    return {
                        "items": [
                            {"role": "user", "content": "第一轮", "created_at": "1"}
                        ],
                        "has_more": False,
                    }
                return {
                    "items": [
                        {"role": "user", "content": "第二轮", "created_at": "3"},
                        {"role": "assistant", "content": "答复", "created_at": "2"},
                    ],
                    "has_more": True,
                }
            raise AssertionError(f"unexpected URL: {url}")

        original = MODULE.v2_get_json
        MODULE.v2_get_json = fake_get_json
        try:
            report = asyncio.run(
                MODULE.build_v2_report(args_for(conversation_id="conv-1"))
            )
        finally:
            MODULE.v2_get_json = original

        self.assertEqual(report.resolved["trace_ids"], ["trace-1", "trace-2"])
        self.assertEqual(len(report.turns), 2)
        self.assertEqual(report.conversation_overview["message_count"], 3)
        self.assertEqual(report.status.events, "ok(v2_api)")
        self.assertEqual(len(report.sse_timeline), 2)

    def test_v2_trace_prefers_formal_nodes_then_marks_event_api_unavailable(self):
        calls: list[str] = []

        def fake_get_json(url: str):
            calls.append(url)
            path = urlparse(url).path
            if path.endswith("/summary"):
                return {
                    "request_id": "trace-1",
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "status": "success",
                    "total_duration_ms": 42,
                    "metrics": {"tool_calls": 1, "total_tokens": 12},
                    "business_committed": True,
                    "reply_generated": True,
                }
            if path.endswith("/nodes"):
                raise MODULE.V2ApiError(url, 404, "not_found")
            if path.endswith("/timeline") or path.endswith("/events"):
                raise MODULE.V2ApiError(url, 404, "not_found")
            if path.endswith("/traces/trace-1"):
                return {
                    "request_id": "trace-1",
                    "turn_id": "turn-1",
                    "conversation_id": "conv-1",
                    "nodes": [
                        {
                            "step_index": 1,
                            "node_type": "tool_call",
                            "node_name": "weather",
                            "status": "success",
                            "input_data": {"token": "hidden"},
                            "duration_ms": 7,
                        }
                    ],
                }
            if path.endswith("/conversations/conv-1"):
                return {
                    "items": [
                        {"role": "user", "content": "今天天气", "created_at": "1"},
                        {"role": "assistant", "content": "晴", "created_at": "2"},
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"unexpected URL: {url}")

        original = MODULE.v2_get_json
        MODULE.v2_get_json = fake_get_json
        try:
            report = asyncio.run(MODULE.build_v2_report(args_for(trace_id="trace-1")))
            report = MODULE.finalize_report(report)
        finally:
            MODULE.v2_get_json = original

        self.assertTrue(any("/api/agri_backend_v2/traces/trace-1/nodes" in call for call in calls))
        self.assertTrue(any("/api/agri_backend_v2/traces/trace-1?" in call for call in calls))
        self.assertEqual(report.status.events, "not_available(v2_api)")
        self.assertTrue(
            any(
                "trace_events=not_available(v2_api)" in gap
                for gap in report.evidence_gaps
            )
        )
        self.assertEqual(report.business_outcome["business_committed"], True)
        self.assertEqual(report.trace_nodes[0].input_data["token"], "***")
        output = MODULE.report_dict(report)
        for key in (
            "target",
            "resolved_scope",
            "evidence_status",
            "conversation_overview",
            "turn_overview",
            "sse_timeline",
            "trace_timeline",
            "business_outcome",
            "errors",
            "evidence_gaps",
            "suggestions",
        ):
            self.assertIn(key, output)

    def test_v2_pagination_uses_cursor_and_deduplicates(self):
        calls: list[str] = []

        def fake_get_json(url: str):
            calls.append(url)
            query = parse_qs(urlparse(url).query)
            if query.get("cursor") == ["c1"]:
                return {"items": [{"request_id": "trace-2"}], "has_more": False}
            return {
                "items": [{"request_id": "trace-1"}],
                "next_cursor": "c1",
                "has_more": True,
            }

        original = MODULE.v2_get_json
        MODULE.v2_get_json = fake_get_json
        try:
            items, status = asyncio.run(
                MODULE.v2_paginate("http://agent.test/api/v2", "/traces", {}, 2)
            )
        finally:
            MODULE.v2_get_json = original

        self.assertIsNone(status)
        self.assertEqual([item["request_id"] for item in items], ["trace-1", "trace-2"])
        self.assertEqual(len(calls), 2)
        self.assertIn("cursor=c1", calls[1])

    def test_sse_diagnostics_detects_sequence_and_event_id_duplicates(self):
        events = [
            MODULE.EventItem(1, "started", "trace", "turn", None, event_id="e1"),
            MODULE.EventItem(
                3, "done", "trace", "turn", None, event_id="e1", terminal=True
            ),
        ]
        diagnostics = MODULE.sse_diagnostics(events)
        self.assertEqual(diagnostics["seq_gaps"], [2])
        self.assertEqual(diagnostics["duplicate_event_id"], ["e1"])
        self.assertEqual(diagnostics["done_count"], 1)


if __name__ == "__main__":
    unittest.main()
