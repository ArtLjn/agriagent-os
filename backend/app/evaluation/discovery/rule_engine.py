"""DataFlywheel 业务规则引擎。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.evaluation.discovery.risk_scorer import calculate_risk
from app.infra.agent_events import read_event_segment
from app.models.trace import TraceRecord

logger = logging.getLogger(__name__)

DEFAULT_RULES_PATH = Path(__file__).with_name("rules.yaml")
REQUIRED_RULE_FIELDS = {"id", "weight", "severity", "description", "when"}
VALID_SEVERITIES = {"P0", "P1"}


class RuleConfigError(ValueError):
    """规则配置格式错误。"""


@dataclass(frozen=True)
class Rule:
    """已校验的业务规则。"""

    id: str
    weight: float
    severity: str
    description: str
    when: dict[str, Any]


@dataclass(frozen=True)
class RuleEvaluationResult:
    """规则命中结果。"""

    hits: list[Rule]
    rule_score: float
    highest_severity: str | None
    risk_score: float
    risk_dominant_signal: str | None

    @property
    def hit_rule_ids(self) -> list[str]:
        return [rule.id for rule in self.hits]


class RuleEngine:
    """加载、校验并执行 rules.yaml 的小型 DSL。"""

    def __init__(self, rules: list[Rule]) -> None:
        self._rules = rules

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> "RuleEngine":
        return cls(load_rules(path or DEFAULT_RULES_PATH))

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)

    def replace_rules(self, rules: list[Rule]) -> None:
        self._rules = rules

    def evaluate(self, context: dict[str, Any]) -> RuleEvaluationResult:
        hits = [rule for rule in self._rules if evaluate_condition(rule.when, context)]
        rule_score = max((rule.weight for rule in hits), default=0.0)
        highest_severity = _highest_severity(hits)
        risk = calculate_risk(
            rule_score=rule_score if hits else None, judge_bad_prob=None
        )
        return RuleEvaluationResult(
            hits=hits,
            rule_score=rule_score,
            highest_severity=highest_severity,
            risk_score=risk.risk_score,
            risk_dominant_signal=risk.risk_dominant_signal,
        )


def evaluate_turn(db, turn) -> RuleEvaluationResult:  # noqa: ANN001
    """评估单个 AgentTurn，并把规则风险信号写回数据库。"""

    engine = RuleEngine.from_file()
    result = engine.evaluate(turn_context(turn, tool_calls=_load_tool_calls(db, turn)))
    turn.rule_score = result.rule_score
    turn.rule_hits = result.hit_rule_ids
    turn.risk_score = result.risk_score
    turn.risk_dominant_signal = result.risk_dominant_signal
    turn.risk_severity = result.highest_severity
    db.commit()
    db.refresh(turn)
    return result


def turn_context(
    turn,  # noqa: ANN001
    *,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """从 SQLAlchemy model 转成规则 DSL 可访问的白名单上下文。"""

    input_preview = turn.input_preview or ""
    reply_preview = turn.reply_preview or ""
    intent = _infer_intent(input_preview, reply_preview)
    return {
        "intent": intent,
        "user_message": input_preview,
        "reply_preview": reply_preview,
        "reply_is_blank": not reply_preview.strip(),
        "tool_calls": tool_calls or [],
        "feedback": {"rating": None, "text": ""},
        "pending_action": {"created": bool(getattr(turn, "pending_plan_id", None))},
        "safety": {"blocked": False},
        "status": turn.status,
        "selected_tools_count": turn.selected_tools_count,
        "tool_calls_count": turn.tool_calls_count,
        "token_total": turn.token_total,
        "latency_ms": turn.latency_ms,
    }


def _load_tool_calls(db, turn) -> list[dict[str, Any]]:  # noqa: ANN001
    """从事件日志和 trace 中提取规则需要的工具调用摘要。"""

    calls = _tool_calls_from_event_log(turn)
    if calls:
        return calls
    return _tool_calls_from_trace(db, turn)


def _tool_calls_from_event_log(turn) -> list[dict[str, Any]]:  # noqa: ANN001
    if (
        not getattr(turn, "event_file", None)
        or getattr(turn, "event_seq_start", None) is None
        or getattr(turn, "event_seq_end", None) is None
    ):
        return []
    events = read_event_segment(
        turn.event_file,
        turn.event_seq_start,
        turn.event_seq_end,
    )
    calls: list[dict[str, Any]] = []
    for event in events:
        call = _tool_call_from_event(event)
        if call is not None:
            calls.append(call)
    return calls


def _tool_call_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = str(event.get("event_type") or "")
    payload = event.get("payload") or {}
    if not isinstance(payload, dict) or not event_type.startswith("tool.call."):
        return None

    name = payload.get("tool_name") or payload.get("name") or payload.get("skill_name")
    if not name:
        return None
    status = payload.get("status")
    if not status:
        status = "error" if event_type.endswith(".failed") else "success"
    return {
        "name": str(name),
        "status": _normalize_tool_status(status),
        "result": payload.get("result") or payload.get("output") or {},
    }


def _tool_calls_from_trace(db, turn) -> list[dict[str, Any]]:  # noqa: ANN001
    request_id = getattr(turn, "request_id", None)
    if not request_id:
        return []
    records = (
        db.query(TraceRecord)
        .filter(
            TraceRecord.request_id == request_id,
            TraceRecord.node_type == "skill_call",
        )
        .order_by(TraceRecord.round_index.asc(), TraceRecord.id.asc())
        .all()
    )
    calls: list[dict[str, Any]] = []
    for record in records:
        output_data = record.output_data or {}
        if not isinstance(output_data, dict):
            output_data = {"reply_preview": str(output_data)}
        calls.append(
            {
                "name": record.node_name,
                "status": _normalize_tool_status(
                    output_data.get("status") or record.status
                ),
                "result": output_data.get("result") or output_data,
            }
        )
    return calls


def _normalize_tool_status(status: Any) -> str:
    normalized = str(status or "").lower()
    if normalized in {"success", "ok", "finished", "pending"}:
        return "success"
    return "error"


def load_rules(path: str | Path = DEFAULT_RULES_PATH) -> list[Rule]:
    """从 yaml 文件加载并校验规则。"""

    rules_path = Path(path)
    try:
        raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuleConfigError(f"rules.yaml parse failed: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("rules"), list):
        raise RuleConfigError("rules.yaml must contain a rules list")

    rules = [_parse_rule(item, index) for index, item in enumerate(raw["rules"])]
    ids = [rule.id for rule in rules]
    if len(set(ids)) != len(ids):
        raise RuleConfigError("rule ids must be unique")
    return rules


def evaluate_condition(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """对 dict/turn 上下文求值条件 DSL。"""

    if not isinstance(condition, dict) or len(condition) != 1:
        raise RuleConfigError("condition must contain exactly one operator")

    operator, payload = next(iter(condition.items()))
    match operator:
        case "all":
            if not isinstance(payload, list):
                raise RuleConfigError("all expects a list")
            return all(evaluate_condition(item, context) for item in payload)
        case "any":
            if not isinstance(payload, list):
                raise RuleConfigError("any expects a list")
            return any(evaluate_condition(item, context) for item in payload)
        case "not":
            return not evaluate_condition(payload, context)
        case "contains":
            return _contains(payload, context, expected=True)
        case "not_contains":
            return _contains(payload, context, expected=False)
        case "equals":
            field, value = _field_value_payload(payload)
            return any(
                candidate == value for candidate in _resolve_values(context, field)
            )
        case "gt" | "gte" | "lt" | "lte":
            return _compare(operator, payload, context)
        case "exists":
            field = _field_payload(payload)
            return bool(_resolve_values(context, field))
        case "count_gte":
            field, value = _field_value_payload(payload)
            return _count_values(payload, context, field) >= int(value)
        case _:
            raise RuleConfigError(f"unsupported operator: {operator}")


class PollingRuleWatcher:
    """可测试的轮询热重载 watcher。"""

    def __init__(
        self,
        engine: RuleEngine,
        path: str | Path,
        *,
        interval_seconds: float = 5.0,
        loader: Callable[[str | Path], list[Rule]] = load_rules,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.interval_seconds = interval_seconds
        self.loader = loader
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_mtime = self._mtime()

    def reload_once(self) -> bool:
        """重载一次；失败保留旧规则。"""

        try:
            rules = self.loader(self.path)
        except Exception as exc:
            logger.error(
                "discovery_rules_reload_failed",
                extra={
                    "event": "discovery_rules_reload_failed",
                    "path": str(self.path),
                    "error": str(exc),
                },
            )
            return False
        self.engine.replace_rules(rules)
        self._last_mtime = self._mtime()
        logger.info(
            "discovery_rules_reloaded",
            extra={
                "event": "discovery_rules_reloaded",
                "path": str(self.path),
                "rule_count": len(rules),
            },
        )
        return True

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.interval_seconds + 1)

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            current_mtime = self._mtime()
            if current_mtime != self._last_mtime:
                self.reload_once()

    def _mtime(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except FileNotFoundError:
            return None


def create_rule_watcher(
    engine: RuleEngine,
    path: str | Path = DEFAULT_RULES_PATH,
    *,
    interval_seconds: float = 5.0,
):
    """优先创建 watchdog watcher，缺依赖时回退轮询。"""

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return PollingRuleWatcher(
            engine,
            path,
            interval_seconds=interval_seconds,
        )

    class _Handler(FileSystemEventHandler):
        def __init__(self, watcher: PollingRuleWatcher) -> None:
            self.watcher = watcher

        def on_modified(self, event) -> None:  # noqa: ANN001
            if Path(event.src_path) == self.watcher.path:
                self.watcher.reload_once()

    class _WatchdogRuleWatcher(PollingRuleWatcher):
        def start(self) -> None:
            if getattr(self, "_observer", None):
                return
            observer = Observer()
            observer.schedule(_Handler(self), str(self.path.parent), recursive=False)
            observer.start()
            self._observer = observer

        def stop(self) -> None:
            observer = getattr(self, "_observer", None)
            if not observer:
                return
            observer.stop()
            observer.join(timeout=interval_seconds + 1)
            self._observer = None

    return _WatchdogRuleWatcher(engine, path, interval_seconds=interval_seconds)


def _parse_rule(raw: Any, index: int) -> Rule:
    if not isinstance(raw, dict):
        raise RuleConfigError(f"rule[{index}] must be an object")
    missing = REQUIRED_RULE_FIELDS - set(raw)
    if missing:
        raise RuleConfigError(f"rule[{index}] missing fields: {sorted(missing)}")

    rule_id = raw["id"]
    weight = raw["weight"]
    severity = raw["severity"]
    description = raw["description"]
    when = raw["when"]

    if not isinstance(rule_id, str) or not rule_id.strip():
        raise RuleConfigError(f"rule[{index}].id must be a non-empty string")
    if not isinstance(weight, int | float) or weight < 0 or weight > 1:
        raise RuleConfigError(f"rule[{index}].weight must be between 0 and 1")
    if severity not in VALID_SEVERITIES:
        raise RuleConfigError(f"rule[{index}].severity must be P0 or P1")
    if not isinstance(description, str) or not description.strip():
        raise RuleConfigError(f"rule[{index}].description must be a non-empty string")
    if not isinstance(when, dict):
        raise RuleConfigError(f"rule[{index}].when must be an object")

    evaluate_condition(when, {})
    return Rule(
        id=rule_id,
        weight=float(weight),
        severity=severity,
        description=description,
        when=when,
    )


def _highest_severity(rules: list[Rule]) -> str | None:
    severities = {rule.severity for rule in rules}
    if "P0" in severities:
        return "P0"
    if "P1" in severities:
        return "P1"
    return None


def _field_value_payload(payload: Any) -> tuple[str, Any]:
    if (
        not isinstance(payload, dict)
        or "field" not in payload
        or "value" not in payload
    ):
        raise RuleConfigError("operator expects field and value")
    field = payload["field"]
    if not isinstance(field, str) or not field:
        raise RuleConfigError("field must be a non-empty string")
    return field, payload["value"]


def _field_payload(payload: Any) -> str:
    field = payload["field"] if isinstance(payload, dict) else payload
    if not isinstance(field, str) or not field:
        raise RuleConfigError("field must be a non-empty string")
    return field


def _contains(payload: Any, context: dict[str, Any], *, expected: bool) -> bool:
    field, value = _field_value_payload(payload)
    candidates = _resolve_values(context, field)
    if isinstance(value, list):
        found = any(
            _value_contains(candidate, item)
            for candidate in candidates
            for item in value
        )
    else:
        found = any(_value_contains(candidate, value) for candidate in candidates)
    return found if expected else not found


def _compare(operator: str, payload: Any, context: dict[str, Any]) -> bool:
    field, value = _field_value_payload(payload)
    for candidate in _resolve_values(context, field):
        try:
            candidate_number = float(candidate)
            target_number = float(value)
        except (TypeError, ValueError):
            continue
        if operator == "gt" and candidate_number > target_number:
            return True
        if operator == "gte" and candidate_number >= target_number:
            return True
        if operator == "lt" and candidate_number < target_number:
            return True
        if operator == "lte" and candidate_number <= target_number:
            return True
    return False


def _count_values(payload: Any, context: dict[str, Any], field: str) -> int:
    values = _resolve_values(context, field)
    if not isinstance(payload, dict) or "contains" not in payload:
        return len(values)

    needle = str(payload["contains"]).lower()
    count = 0
    for value in values:
        if isinstance(value, str):
            count += value.lower().count(needle)
        elif isinstance(value, list):
            count += sum(1 for item in value if _value_contains(item, needle))
        elif _value_contains(value, needle):
            count += 1
    return count


def _value_contains(candidate: Any, needle: Any) -> bool:
    if candidate is None:
        return False
    if isinstance(candidate, list):
        return any(_value_contains(item, needle) for item in candidate)
    if isinstance(candidate, dict):
        return needle in candidate.values() or needle in candidate.keys()
    return str(needle).lower() in str(candidate).lower()


def _resolve_values(context: Any, path: str) -> list[Any]:
    values = [context]
    for segment in path.split("."):
        next_values: list[Any] = []
        for value in values:
            if isinstance(value, list):
                for item in value:
                    next_values.extend(_resolve_segment(item, segment))
            else:
                next_values.extend(_resolve_segment(value, segment))
        values = next_values
        if not values:
            break
    return values


def _resolve_segment(value: Any, segment: str) -> list[Any]:
    if isinstance(value, dict):
        if segment in value:
            return [value[segment]]
        return []
    return []


def _infer_intent(input_preview: str, reply_preview: str) -> str:
    combined = f"{input_preview} {reply_preview}"
    if any(word in combined for word in ("天气", "下雨", "有雨", "气温")):
        return "weather_query"
    if any(word in combined for word in ("工资", "用工", "实发", "基本工资")):
        return "wage_query"
    if any(word in combined for word in ("成本", "支出", "农资")):
        return "create_cost"
    if any(word in combined for word in ("更新", "修改", "改为")):
        return "update_crop_cycle"
    return "unknown"
