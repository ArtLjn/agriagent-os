"""DataFlywheel discovery rule engine 测试。"""

from pathlib import Path

import pytest
import yaml

from app.evaluation.discovery.rule_engine import (
    PollingRuleWatcher,
    RuleConfigError,
    RuleEngine,
    evaluate_condition,
)


def _turn(**overrides):
    reply_preview = overrides.get("reply_preview", "你好，我可以帮你查看农场信息。")
    data = {
        "intent": "greeting",
        "reply_preview": reply_preview,
        "reply_is_blank": not str(reply_preview).strip(),
        "user_message": "你好",
        "tool_calls": [],
        "feedback": {"rating": "positive", "text": ""},
        "pending_action": {"created": False},
        "safety": {"blocked": False},
    }
    data.update(overrides)
    return data


def _write_rules(path: Path, rules: list[dict]) -> None:
    path.write_text(
        yaml.safe_dump({"rules": rules}, allow_unicode=True), encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("rule_id", "positive_context", "negative_context"),
    [
        (
            "tool_error_ignored",
            _turn(
                tool_calls=[{"name": "create_cost", "status": "error"}],
                reply_preview="已帮你记录好了。",
            ),
            _turn(
                tool_calls=[{"name": "create_cost", "status": "error"}],
                reply_preview="工具调用失败，请稍后重试。",
            ),
        ),
        (
            "missing_wage",
            _turn(intent="wage_query", reply_preview="张三本月工资 3200 元。"),
            _turn(
                intent="wage_query",
                reply_preview="张三本月基本工资 3000，实发工资 2800。",
            ),
        ),
        (
            "hallucinated_execution",
            _turn(
                intent="create_cost",
                tool_calls=[],
                reply_preview="已创建这笔农资支出。",
            ),
            _turn(
                intent="create_cost",
                tool_calls=[{"name": "create_cost", "status": "success"}],
                reply_preview="已创建这笔农资支出。",
            ),
        ),
        (
            "negative_feedback",
            _turn(feedback={"rating": "negative", "text": "答非所问"}),
            _turn(feedback={"rating": "positive", "text": "很好"}),
        ),
        (
            "weather_without_search",
            _turn(intent="weather_query", tool_calls=[], reply_preview="今天有雨。"),
            _turn(
                intent="weather_query",
                tool_calls=[{"name": "weather_search", "status": "success"}],
                reply_preview="今天有雨。",
            ),
        ),
        (
            "empty_reply",
            _turn(reply_preview="   "),
            _turn(reply_preview="这是正常回复。"),
        ),
        (
            "apology_loop",
            _turn(reply_preview="抱歉抱歉，真的抱歉，这次没处理好。"),
            _turn(reply_preview="抱歉，这次没处理好。"),
        ),
        (
            "missing_pending_confirmation",
            _turn(
                intent="update_crop_cycle",
                pending_action={"created": True},
                reply_preview="已经改好了。",
            ),
            _turn(
                intent="update_crop_cycle",
                pending_action={"created": True},
                reply_preview="请确认是否把播种日期改为明天。",
            ),
        ),
        (
            "unsafe_advice",
            _turn(reply_preview="可以随意混用农药并加大剂量。"),
            _turn(reply_preview="请按标签和农技人员建议用药。"),
        ),
        (
            "context_missing",
            _turn(
                intent="farm_status", reply_preview="未找到地块信息，无法判断当前状态。"
            ),
            _turn(intent="farm_status", reply_preview="A 地块长势良好。"),
        ),
        (
            "tool_result_contradiction",
            _turn(
                tool_calls=[
                    {"name": "get_cost", "status": "success", "result": {"total": 0}}
                ],
                reply_preview="总成本是 1200 元。",
            ),
            _turn(
                tool_calls=[
                    {"name": "get_cost", "status": "success", "result": {"total": 0}}
                ],
                reply_preview="总成本是 0 元。",
            ),
        ),
        (
            "low_confidence_answer",
            _turn(reply_preview="我猜可能是已经完成了。"),
            _turn(reply_preview="根据记录，这项任务已经完成。"),
        ),
    ],
)
def test_default_rules_hit_and_miss_key_scenarios(
    rule_id: str, positive_context: dict, negative_context: dict
) -> None:
    engine = RuleEngine.from_file()

    positive = engine.evaluate(positive_context)
    negative = engine.evaluate(negative_context)

    assert rule_id in positive.hit_rule_ids
    assert rule_id not in negative.hit_rule_ids


def test_rule_score_uses_max_weight_and_highest_severity() -> None:
    result = RuleEngine.from_file().evaluate(
        _turn(
            intent="wage_query",
            reply_preview="已帮你记录好了。",
            tool_calls=[{"name": "settle_labor", "status": "error"}],
        )
    )

    assert result.rule_score == 0.95
    assert result.highest_severity == "P0"
    assert result.risk_score == 0.95
    assert result.risk_dominant_signal == "rule"


def test_condition_dsl_supports_numeric_comparison_and_exists() -> None:
    context = {"metrics": {"latency_ms": 120, "retry_count": 2}}

    assert evaluate_condition(
        {"gt": {"field": "metrics.latency_ms", "value": 100}}, context
    )
    assert evaluate_condition(
        {"gte": {"field": "metrics.retry_count", "value": 2}}, context
    )
    assert evaluate_condition(
        {"lt": {"field": "metrics.retry_count", "value": 3}}, context
    )
    assert evaluate_condition(
        {"lte": {"field": "metrics.latency_ms", "value": 120}}, context
    )
    assert evaluate_condition({"exists": "metrics.latency_ms"}, context)
    assert not evaluate_condition({"exists": "metrics.missing"}, context)


def test_condition_dsl_does_not_read_object_attributes() -> None:
    class Secret:
        hidden = "leak"

    assert not evaluate_condition({"exists": "secret.hidden"}, {"secret": Secret()})


def test_invalid_yaml_is_rejected_on_startup(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yaml"
    _write_rules(
        rules_path,
        [
            {
                "id": "bad_rule",
                "weight": 1.5,
                "severity": "P2",
                "description": "bad",
                "when": {"equals": {"field": "intent", "value": "x"}},
            }
        ],
    )

    with pytest.raises(RuleConfigError):
        RuleEngine.from_file(rules_path)


def test_hot_reload_failure_keeps_old_rules_and_logs(tmp_path: Path, caplog) -> None:
    rules_path = tmp_path / "rules.yaml"
    _write_rules(
        rules_path,
        [
            {
                "id": "first",
                "weight": 0.4,
                "severity": "P1",
                "description": "first",
                "when": {"equals": {"field": "intent", "value": "first"}},
            }
        ],
    )
    engine = RuleEngine.from_file(rules_path)
    watcher = PollingRuleWatcher(engine, rules_path, interval_seconds=0.01)

    rules_path.write_text("rules:\n  - id: broken\n", encoding="utf-8")
    reloaded = watcher.reload_once()

    assert reloaded is False
    assert engine.evaluate(_turn(intent="first")).hit_rule_ids == ["first"]
    assert any(
        record.__dict__.get("event") == "discovery_rules_reload_failed"
        for record in caplog.records
    )


def test_hot_reload_success_replaces_rules(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yaml"
    _write_rules(
        rules_path,
        [
            {
                "id": "first",
                "weight": 0.4,
                "severity": "P1",
                "description": "first",
                "when": {"equals": {"field": "intent", "value": "first"}},
            }
        ],
    )
    engine = RuleEngine.from_file(rules_path)
    watcher = PollingRuleWatcher(engine, rules_path, interval_seconds=0.01)

    _write_rules(
        rules_path,
        [
            {
                "id": "second",
                "weight": 0.7,
                "severity": "P0",
                "description": "second",
                "when": {"equals": {"field": "intent", "value": "second"}},
            }
        ],
    )
    reloaded = watcher.reload_once()

    assert reloaded is True
    assert engine.evaluate(_turn(intent="first")).hit_rule_ids == []
    assert engine.evaluate(_turn(intent="second")).hit_rule_ids == ["second"]
