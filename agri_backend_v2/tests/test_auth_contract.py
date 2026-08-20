"""用户 JWT、Agent 解析和委托凭证的无数据库合同测试。"""

from __future__ import annotations

import unittest

import jwt
from fastapi import HTTPException

from agent.auth import create_delegation_token, parse_identity
from agent.config import settings as agent_settings
from agent.domains.harness.observability.trace.context import clear_trace, init_trace
from business.config import settings as business_settings
from business.services.tokens import create_access_token, decode_access_token


class AuthContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = "auth-contract-test-secret-32-bytes-long"
        self.delegation_secret = "delegation-contract-test-secret-32-bytes"
        self.agent_values = {
            "jwt_secret": agent_settings.auth.jwt_secret,
            "delegation_secret": agent_settings.auth.delegation_secret,
            "agent_service_token": agent_settings.auth.agent_service_token,
        }
        self.business_values = {
            "jwt_secret": business_settings.auth.jwt_secret,
            "delegation_secret": business_settings.auth.delegation_secret,
        }
        agent_settings.auth.jwt_secret = self.secret
        agent_settings.auth.delegation_secret = self.delegation_secret
        agent_settings.auth.agent_service_token = "agent-service-test"
        business_settings.auth.jwt_secret = self.secret
        business_settings.auth.delegation_secret = self.delegation_secret

    def tearDown(self) -> None:
        for key, value in self.agent_values.items():
            setattr(agent_settings.auth, key, value)
        for key, value in self.business_values.items():
            setattr(business_settings.auth, key, value)

    def test_access_token_uses_user_sub_and_farm_uid(self) -> None:
        token = create_access_token(
            user_id="user-uuid",
            farm_uid="farm-uuid",
            farm_id=7,
        )
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-uuid")
        self.assertEqual(payload["farm_uid"], "farm-uuid")
        self.assertEqual(payload["farm_id"], 7)
        self.assertNotIn("user_uid", payload)

    def test_agent_rejects_invalid_token_instead_of_default_identity(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            parse_identity("Bearer invalid")
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.detail["code"], "invalid_token")

    def test_agent_creates_short_lived_delegation_token(self) -> None:
        token = create_delegation_token(
            {
                "user_id": "user-uuid",
                "farm_uid": "farm-uuid",
                "role": "user",
                "token_id": "source-jti",
                "scope": "farm:read",
            },
            conversation_id="conversation-uuid",
            turn_id="turn-uuid",
        )
        payload = jwt.decode(
            token,
            self.delegation_secret,
            algorithms=[agent_settings.auth.jwt_algorithm],
            issuer=agent_settings.auth.delegation_issuer,
            audience=agent_settings.auth.delegation_audience,
        )
        self.assertEqual(payload["sub"], "user-uuid")
        self.assertEqual(payload["farm_uid"], "farm-uuid")
        self.assertEqual(payload["act"], {"sub": "agent", "type": "service"})
        self.assertEqual(payload["turn_id"], "turn-uuid")

    def test_trace_context_keeps_user_and_farm_uid(self) -> None:
        trace = init_trace(
            conversation_id="conversation-uuid",
            turn_id="turn-uuid",
            user_id="user-uuid",
            farm_uid="farm-uuid",
        )
        try:
            self.assertEqual(trace.user_id, "user-uuid")
            self.assertEqual(trace.farm_uid, "farm-uuid")
        finally:
            clear_trace()


if __name__ == "__main__":
    unittest.main()
