"""每日建议 v2 生成结果校验测试。"""

from datetime import date

from pytest import MonkeyPatch

from app.agent.reflector.daily_advice import check_daily_advice_generation
from app.agent.reflector.models import ReflectionDecision, ReflectionSeverity
from app.services.daily_advice_models import DailyAdviceCandidate
from app.services.daily_advice_validation import validate_daily_advice_payload


def _candidate(
    *,
    candidate_id: str = "weather-1",
    category: str = "weather",
    priority: int = 2,
    source_type: str = "weather_service",
    source_id: int | None = 12,
) -> DailyAdviceCandidate:
    return DailyAdviceCandidate(
        id=candidate_id,
        category=category,
        title_hint="高温错峰采收",
        detail_hint="今天最高温 36 度，建议避开中午高温时段安排采收。",
        priority=priority,
        due_date=date(2026, 6, 13),
        source_type=source_type,
        source_id=source_id,
        dedupe_key=f"{category}:{candidate_id}",
        reason="天气服务命中高温规则",
    )


def _valid_item(candidate: DailyAdviceCandidate) -> dict:
    return {
        "id": candidate.id,
        "category": candidate.category,
        "source_type": candidate.source_type,
        "source_id": candidate.source_id,
        "priority": candidate.priority,
        "compact": {
            "title": "高温错峰采收",
            "subtitle": "今天最高温较高，建议避开中午高温时段安排采收。",
        },
        "detail_view": {
            "title": "高温错峰采收",
            "description": "今天最高温较高，需要避开中午高温时段安排采收并关注人员状态。",
            "evidence": [
                {
                    "title": "天气依据",
                    "description": "天气服务命中高温规则",
                    "source_type": candidate.source_type,
                    "source_id": candidate.source_id,
                }
            ],
            "steps": [
                {
                    "order": 1,
                    "title": "查看天气窗口",
                    "description": "确认上午和傍晚适合作业的时间。",
                },
                {
                    "order": 2,
                    "title": "调整采收安排",
                    "description": "将人员和车辆集中安排到较凉爽时段。",
                },
            ],
            "actions": [
                {
                    "type": "ask_agent",
                    "label": "问问芽芽",
                    "payload": {"candidate_id": candidate.id},
                }
            ],
        },
    }


def _valid_payload(candidate: DailyAdviceCandidate | None = None) -> dict:
    item_candidate = candidate or _candidate()
    return {
        "preview": "今日建议",
        "overview": {
            "score": 82,
            "subtitle": "今日天气偏热，请优先安排关键作业。",
            "metrics": [
                {
                    "key": "weather",
                    "label": "天气",
                    "value": "高温",
                    "level": "important",
                    "icon": "CloudSun",
                },
                {
                    "key": "work_order",
                    "label": "作业",
                    "value": "1项",
                    "level": "normal",
                    "icon": "ClipboardList",
                },
                {
                    "key": "pending",
                    "label": "待处理",
                    "value": "0项",
                    "level": "normal",
                    "icon": "Bell",
                },
            ],
        },
        "items": [_valid_item(item_candidate)],
        "generation": {
            "schema_version": "daily_advice_v2",
            "mode": "llm",
            "retry_count": 0,
        },
        "created_at": "2026-06-13T08:00:00",
    }


def _issue_codes(payload: dict, candidates: list[DailyAdviceCandidate]) -> set[str]:
    result = validate_daily_advice_payload(payload, candidates)
    return {issue.code for issue in result.issues}


def test_valid_payload_passes() -> None:
    candidate = _candidate()

    result = validate_daily_advice_payload(_valid_payload(candidate), [candidate])

    assert result.valid is True
    assert result.issues == []
    assert result.repair_instruction == ""


def test_empty_items_fail() -> None:
    payload = _valid_payload()
    payload["items"] = []

    result = validate_daily_advice_payload(payload, [_candidate()])

    assert result.valid is False
    assert result.issues[0].code == "empty_daily_advice_items"


def test_missing_top_level_v2_fields_fail() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    for field in ("preview", "overview", "generation", "created_at"):
        del payload[field]

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "invalid_payload_shape"
    assert result.issues[0].evidence["missing_fields"] == [
        "preview",
        "overview",
        "generation",
        "created_at",
    ]


def test_invalid_overview_and_generation_shape_fail() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["overview"] = {"metrics": [{"key": "weather"}]}
    payload["generation"] = {"schema_version": "daily_advice_v1"}

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    codes = [issue.code for issue in result.issues]
    assert codes.count("invalid_payload_shape") == 2
    assert any(issue.path == "overview.metrics" for issue in result.issues)
    assert any(issue.path == "generation.schema_version" for issue in result.issues)


def test_short_content_fails() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["compact"]["subtitle"] = "太短"
    payload["items"][0]["detail_view"]["description"] = "也短"
    payload["items"][0]["detail_view"]["steps"] = [{"order": 1, "title": "一步"}]
    payload["items"][0]["detail_view"]["actions"] = [
        {"type": "create_work_order", "label": "生成作业单"}
    ]
    payload["items"][0]["detail_view"]["evidence"] = []

    assert _issue_codes(payload, [candidate]) == {"daily_advice_content_too_thin"}


def test_forbidden_topic_fails() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["detail_view"]["description"] = (
        "今天需要处理诸葛四郎相关事项，避免影响农场现场经营安排。"
    )

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "forbidden_daily_advice_topic"
    assert result.issues[0].evidence["term"] == "诸葛四郎"


def test_unknown_candidate_id_fails() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["id"] = "unknown-1"

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "candidate_id_not_allowed"


def test_priority_escalation_fails() -> None:
    candidate = _candidate(priority=2)
    payload = _valid_payload(candidate)
    payload["items"][0]["priority"] = 1

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "priority_escalation_not_allowed"


def test_priority_missing_or_invalid_fails() -> None:
    candidate = _candidate(priority=2)
    payloads = []
    missing_payload = _valid_payload(candidate)
    del missing_payload["items"][0]["priority"]
    payloads.append(missing_payload)
    for priority in ("1", 0, 4):
        payload = _valid_payload(candidate)
        payload["items"][0]["priority"] = priority
        payloads.append(payload)

    for payload in payloads:
        result = validate_daily_advice_payload(payload, [candidate])

        assert result.valid is False
        assert result.issues[0].code == "priority_escalation_not_allowed"
        assert "invalid_reason" in result.issues[0].evidence


def test_category_source_mismatch_fails() -> None:
    candidate = _candidate(category="weather", source_type="weather_service")
    payload = _valid_payload(candidate)
    payload["items"][0]["category"] = "operation"
    payload["items"][0]["source_type"] = "work_order"
    payload["items"][0]["source_id"] = 99

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "candidate_source_mismatch"
    assert result.issues[0].evidence["fields"] == [
        "category",
        "source_type",
        "source_id",
    ]


def test_missing_category_source_fields_fail() -> None:
    candidate = _candidate(category="weather", source_type="weather_service")
    payload = _valid_payload(candidate)
    del payload["items"][0]["category"]
    del payload["items"][0]["source_type"]
    del payload["items"][0]["source_id"]

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "candidate_source_mismatch"
    assert result.issues[0].evidence["missing_fields"] == [
        "category",
        "source_type",
        "source_id",
    ]


def test_incomplete_step_entries_fail() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["detail_view"]["steps"] = [{}, {}]

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "daily_advice_content_too_thin"
    assert "detail_view.steps[0]" in str(result.issues[0].evidence)
    assert "detail_view.steps[1]" in str(result.issues[0].evidence)


def test_incomplete_evidence_entries_fail() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["detail_view"]["evidence"] = [{}]

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "daily_advice_content_too_thin"
    assert "detail_view.evidence[0]" in str(result.issues[0].evidence)


def test_payload_generation_mode_cannot_skip_evidence_requirement() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["generation"]["mode"] = "fallback"
    payload["items"][0]["detail_view"]["evidence"] = []

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "daily_advice_content_too_thin"


def test_external_fallback_generation_mode_skips_evidence_requirement() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["detail_view"]["evidence"] = []

    result = validate_daily_advice_payload(
        payload,
        [candidate],
        generation_mode="fallback",
    )

    assert result.valid is True


def test_repair_instruction_contains_issue_information() -> None:
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["id"] = "unknown-1"
    payload["items"][0]["compact"]["subtitle"] = "太短"

    result = validate_daily_advice_payload(payload, [candidate])

    assert "candidate_id_not_allowed" in result.repair_instruction
    assert "daily_advice_content_too_thin" in result.repair_instruction
    assert candidate.id in result.repair_instruction


def test_reflector_valid_payload_passes() -> None:
    class FakeCollector:
        def __init__(self) -> None:
            self.records = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

    candidate = _candidate()
    collector = FakeCollector()

    result = _check_daily_advice_generation(
        _valid_payload(candidate), [candidate], collector=collector
    )

    assert result.decision == ReflectionDecision.PASS
    assert result.issues == []
    assert result.metadata["valid"] is True
    assert result.metadata["farm_id"] == 7
    assert result.metadata["candidate_fingerprint"] == "abc123"
    assert result.metadata["retry_index"] == 0
    assert result.metadata["generation_mode"] == "llm"
    assert collector.records[0]["node_type"] == "reflection_check"
    assert collector.records[0]["output_data"]["decision"] == "pass"


def test_reflector_trace_metadata_does_not_override_core_fields(
    monkeypatch: MonkeyPatch,
) -> None:
    class FakeCollector:
        def __init__(self) -> None:
            self.records = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

    collector = FakeCollector()
    monkeypatch.setattr(
        "app.agent.reflector.daily_advice.get_collector",
        lambda: collector,
    )
    candidate = _candidate()

    result = check_daily_advice_generation(
        _valid_payload(candidate),
        [candidate],
        farm_id=7,
        candidate_fingerprint="abc123",
        retry_index=0,
        generation_mode="llm",
        trace_metadata={"farm_id": 999, "note": "kept"},
    )

    assert result.metadata["farm_id"] == 7
    assert result.metadata["extra"] == {"farm_id": 999, "note": "kept"}
    assert collector.records[0]["input_data"]["farm_id"] == 7
    assert collector.records[0]["input_data"]["extra"]["farm_id"] == 999


def test_reflector_trace_error_does_not_break_return(
    monkeypatch: MonkeyPatch,
) -> None:
    class BrokenCollector:
        def record(self, **_kwargs) -> None:
            raise RuntimeError("trace down")

    monkeypatch.setattr(
        "app.agent.reflector.daily_advice.get_collector",
        lambda: BrokenCollector(),
    )
    candidate = _candidate()

    result = check_daily_advice_generation(
        _valid_payload(candidate),
        [candidate],
        farm_id=7,
        candidate_fingerprint="abc123",
        retry_index=0,
        generation_mode="llm",
    )

    assert result.decision == ReflectionDecision.PASS
    assert result.metadata["farm_id"] == 7


def test_reflector_invalid_payload_retries_and_converts_issues(
    monkeypatch: MonkeyPatch,
) -> None:
    class FakeCollector:
        def __init__(self) -> None:
            self.records = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

    collector = FakeCollector()
    monkeypatch.setattr(
        "app.agent.reflector.daily_advice.get_collector",
        lambda: collector,
    )
    candidate = _candidate()
    payload = _valid_payload(candidate)
    payload["items"][0]["id"] = "unknown-1"

    result = check_daily_advice_generation(
        payload,
        [candidate],
        farm_id=7,
        candidate_fingerprint="abc123",
        retry_index=1,
        generation_mode="llm",
    )

    assert result.decision == ReflectionDecision.RETRY_GENERATION
    assert result.issues[0].code == "candidate_id_not_allowed"
    assert result.issues[0].severity == ReflectionSeverity.BLOCKER
    assert (
        result.issues[0].suggested_decision
        == ReflectionDecision.RETRY_GENERATION
    )
    assert "candidate_id_not_allowed" in result.metadata["repair_instruction"]
    assert collector.records[0]["node_type"] == "reflection_check"
    assert collector.records[0]["node_name"] == "daily_advice_generation"
    assert collector.records[0]["input_data"]["farm_id"] == 7
    assert collector.records[0]["input_data"]["candidate_fingerprint"] == "abc123"
    assert collector.records[0]["input_data"]["retry_index"] == 1
    assert collector.records[0]["input_data"]["generation_mode"] == "llm"


def _check_daily_advice_generation(
    payload: dict,
    candidates: list[DailyAdviceCandidate],
    *,
    collector,
):
    from pytest import MonkeyPatch as _MonkeyPatch

    monkeypatch = _MonkeyPatch()
    monkeypatch.setattr(
        "app.agent.reflector.daily_advice.get_collector",
        lambda: collector,
    )
    try:
        return check_daily_advice_generation(
            payload,
            candidates,
            farm_id=7,
            candidate_fingerprint="abc123",
            retry_index=0,
            generation_mode="llm",
        )
    finally:
        monkeypatch.undo()
