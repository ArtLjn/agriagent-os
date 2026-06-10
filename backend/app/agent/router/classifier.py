"""Skill Router 规则意图分类器。"""

from app.agent.router.models import IntentFrame


class RuleIntentClassifier:
    """基于中文触发词生成轻量意图帧。"""

    _query_hints = ("哪些", "有哪些", "看看", "查询", "查一下", "最近", "怎么样")
    _farm_hints = ("作物", "栽种", "农场", "茬口", "种植")
    _crop_hints = ("作物", "栽种", "茬口", "种植")
    _write_action_hints = ("处理", "弄一下", "搞一下")
    _write_entity_hints = ("工人", "作业", "账")
    _worker_create_hints = ("新来", "招了", "新增", "创建")
    _worker_pay_hints = ("工资", "日薪", "每天")
    _work_order_hints = ("作业", "采收", "授粉", "安排")
    _read_prefixes = ("最近", "查询", "看看", "有哪些")

    def classify(self, message: str) -> list[IntentFrame]:
        """按固定规则抽取意图帧。"""
        normalized = message.strip()
        frames: list[IntentFrame] = []

        if self._looks_like_ambiguous_write(normalized):
            return [
                IntentFrame(
                    domain="general",
                    intent="ambiguous_write",
                    risk="write_confirm",
                    candidate_tools=[],
                    confidence=0.7,
                    requires_confirmation=True,
                )
            ]

        if self._looks_like_active_crop_query(normalized):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_active_crops",
                    risk="read",
                    entities=["farm", "crop_cycle"],
                    candidate_tools=["get_farm_status", "get_crop_cycle_info"],
                    confidence=0.85,
                )
            )
        elif self._looks_like_farm_read(normalized):
            frames.append(
                IntentFrame(
                    domain="farm",
                    intent="unknown_farm_read",
                    risk="read",
                    entities=["farm"],
                    candidate_tools=[],
                    confidence=0.6,
                )
            )

        if self._looks_like_create_worker(normalized):
            frames.append(
                IntentFrame(
                    domain="labor",
                    intent="create_worker",
                    risk="write_confirm",
                    entities=["worker"],
                    candidate_tools=["manage_workers"],
                    confidence=0.78,
                    requires_confirmation=True,
                )
            )

        if self._looks_like_create_work_order(normalized):
            frames.append(
                IntentFrame(
                    domain="operation",
                    intent="create_work_order",
                    risk="write_confirm",
                    entities=["operation_work_order"],
                    candidate_tools=["create_operation_work_order"],
                    confidence=0.76,
                    requires_confirmation=True,
                )
            )

        return frames

    def _looks_like_active_crop_query(self, message: str) -> bool:
        return self._has_any(message, self._query_hints) and self._has_any(
            message, self._crop_hints
        )

    def _looks_like_farm_read(self, message: str) -> bool:
        return self._has_any(message, self._query_hints) and self._has_any(
            message, self._farm_hints
        )

    def _looks_like_create_worker(self, message: str) -> bool:
        if "工人" not in message:
            return False
        has_create_action = self._has_any(message, self._worker_create_hints)
        has_pay_hint = self._has_any(message, self._worker_pay_hints)
        return has_create_action or has_pay_hint

    def _looks_like_create_work_order(self, message: str) -> bool:
        if message.startswith(self._read_prefixes):
            return False
        return self._has_any(message, self._work_order_hints)

    def _looks_like_ambiguous_write(self, message: str) -> bool:
        return self._has_any(message, self._write_action_hints) and self._has_any(
            message, self._write_entity_hints
        )

    @staticmethod
    def _has_any(message: str, hints: tuple[str, ...]) -> bool:
        return any(hint in message for hint in hints)
