"""外部记忆语义模型的测试替身，默认测试不发送真实模型请求。"""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def memory_assessment_stub(monkeypatch):
    from agent.domains.harness.memory import tools

    assess = AsyncMock(return_value=tools.MemoryAssessment(authorized=True))
    monkeypatch.setattr(tools, "assess", assess)
    return assess
