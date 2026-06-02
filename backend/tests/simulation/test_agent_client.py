"""测试 Agent HTTP API 客户端。"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.simulation.agent_client import AgentClient


class TestAgentClientInit:
    def test_default_init(self):
        client = AgentClient()
        assert client._base_url == "http://localhost:8000"
        assert client._token == ""

    def test_custom_init(self):
        client = AgentClient(base_url="http://api.test/", token="test-token")
        assert client._base_url == "http://api.test"
        assert client._token == "test-token"


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        client = AgentClient(base_url="http://localhost:8000", token="tk")
        mock_response = MagicMock()
        mock_response.json.return_value = {"reply": "已记账", "pending_action": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.send_message("买化肥200块")

        assert result["reply"] == "已记账"
        assert result["pending_action"] is None
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:8000/agent/chat"

    @pytest.mark.asyncio
    async def test_send_message_with_session_and_cycle(self):
        client = AgentClient(base_url="http://localhost:8000", token="tk")
        mock_response = MagicMock()
        mock_response.json.return_value = {"reply": "已记账", "pending_action": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.send_message(
                "买化肥200块", session_id="sess-1", cycle_id=42
            )

        assert result["reply"] == "已记账"
        call_kwargs = mock_client.post.call_args[1]
        json_body = call_kwargs["json"]
        assert json_body["message"] == "买化肥200块"
        assert json_body["session_id"] == "sess-1"
        assert json_body["cycle_id"] == 42

    @pytest.mark.asyncio
    async def test_send_message_with_pending_action(self):
        client = AgentClient(base_url="http://localhost:8000", token="tk")
        pending = {"action_id": "a1", "skill_name": "create_cost_record", "params": {}}
        mock_response = MagicMock()
        mock_response.json.return_value = {"reply": "请确认", "pending_action": pending}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.send_message("买化肥200块")

        assert result["pending_action"] == pending

    @pytest.mark.asyncio
    async def test_send_message_http_error(self):
        client = AgentClient(base_url="http://localhost:8000", token="tk")

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection failed"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPError):
                await client.send_message("买化肥200块")


class TestSendConfirm:
    @pytest.mark.asyncio
    async def test_send_confirm(self):
        client = AgentClient(base_url="http://localhost:8000", token="tk")
        mock_response = MagicMock()
        mock_response.json.return_value = {"reply": "已确认执行", "pending_action": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.send_confirm("sess-1", "a1")

        assert result["reply"] == "已确认执行"
        call_kwargs = mock_client.post.call_args[1]
        json_body = call_kwargs["json"]
        assert json_body["message"] == "确认"
        assert json_body["session_id"] == "sess-1"


class TestSendCancel:
    @pytest.mark.asyncio
    async def test_send_cancel(self):
        client = AgentClient(base_url="http://localhost:8000", token="tk")
        mock_response = MagicMock()
        mock_response.json.return_value = {"reply": "已取消", "pending_action": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.send_cancel("sess-1", "a1")

        assert result["reply"] == "已取消"
        call_kwargs = mock_client.post.call_args[1]
        json_body = call_kwargs["json"]
        assert json_body["message"] == "取消"
        assert json_body["session_id"] == "sess-1"
