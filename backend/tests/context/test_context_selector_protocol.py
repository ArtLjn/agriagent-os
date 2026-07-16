"""ContextSelector Protocol single-source tests."""

import pytest

import app.context.builder as builder_module
from app.context.builder import ContextBuilder
from app.context.policy import ContextBuildRequest, ContextPolicy, ContextSelector

pytestmark = pytest.mark.no_db


def test_context_builder_uses_policy_context_selector_protocol() -> None:
    builder_annotations = ContextBuilder.__init__.__annotations__

    assert "selectors" in builder_annotations
    assert "ContextSelector" in str(builder_annotations["selectors"])
    assert ContextSelector.__module__ == "app.context.policy"
    assert "ContextSelector" not in vars(builder_module)


def test_context_policy_still_resolves_default_selectors() -> None:
    result = ContextPolicy().resolve(ContextBuildRequest(farm_id=1))

    assert result.selectors
    assert result.max_tokens >= 512
