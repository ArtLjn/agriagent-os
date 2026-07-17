from __future__ import annotations

import re
from typing import Any


REDACTED_SECRET = "[REDACTED_SECRET]"

# 按 issue_type 统一管理的元数据：fix_target / priority / suggested_action / expected_behavior
# 这里 key 既是 issue_type（来自 issue_detector），也覆盖可直接作为 label 的同名项。
_ISSUE_TYPE_META: dict[str, dict[str, Any]] = {
    "sensitive_info_leak": {
        "fix_target": "guardrail",
        "priority": 100,
        "suggested_action": "修复敏感信息输出拦截、回复审查和安全边界测试。",
        "expected_behavior": "回复不应包含模型参数、系统提示、密钥、token 等内部信息。",
    },
    "pending_missed": {
        "fix_target": "pending_plan",
        "priority": 90,
        "suggested_action": "修复写操作确认计划和多步骤 pending lifecycle。",
        "expected_behavior": "router 选择写操作工具时，应同步生成 pending plan，等待用户确认后再执行。",
    },
    "disabled_worker_used": {
        "fix_target": "tool_guardrail",
        "priority": 85,
        "suggested_action": "修复工具执行前后的停用工人校验和阻断规则。",
        "expected_behavior": "应跳过已停用工人，或主动提示用户「该工人已停用，是否继续」。",
    },
    "missing_wage": {
        "fix_target": "domain_policy",
        "priority": 80,
        "suggested_action": "补齐农事用工工资、已付、不计薪或欠款策略。",
        "expected_behavior": "安排作业时应同时确认工资策略（计薪金额/已付/不计薪/欠款），不应留下空白工资字段。",
    },
    "tool_error_ignored": {
        "fix_target": "tool_result_state",
        "priority": 78,
        "suggested_action": "修复工具失败状态传播，禁止失败后伪装成功。",
        "expected_behavior": "工具调用失败时，回复应明确反映失败状态，并给出后续建议，不应伪装为成功。",
    },
    "hallucinated_execution": {
        "fix_target": "tool_result_state",
        "priority": 78,
        "suggested_action": "修复未成功执行工具时的回复状态和完成声明。",
        "expected_behavior": "回复应基于工具实际返回结果，未调用成功写工具前不得声称已执行/已创建/已安排。",
    },
    "wrong_tool_selection": {
        "fix_target": "router",
        "priority": 75,
        "suggested_action": "修复意图识别、工具路由和候选 skill 选择规则。",
        "expected_behavior": "router 应正确识别用户意图，并选择匹配的查询/计算类工具（如 weather.query、worker.search、wage.list）。",
    },
    "tool_parameter_mismatch": {
        "fix_target": "router",
        "priority": 75,
        "suggested_action": "修复参数抽取、批量作用域保持和 pending 确认策略。",
        "expected_behavior": "router 应保留用户表达的对象、数量和批量作用域，确认流程不得把多对象意图收窄为单个实体。",
    },
    "bulk_intent_narrowed_to_single_entity": {
        "fix_target": "router",
        "priority": 75,
        "suggested_action": "修复参数抽取、批量作用域保持和 pending 确认策略。",
        "expected_behavior": "router 应保留批量操作范围，pending 确认与执行参数必须覆盖用户要求的全部对象。",
    },
    "unsafe_write_on_question": {
        "fix_target": "pending_plan",
        "priority": 88,
        "suggested_action": "修复查询/确认类问题下的写工具选择，应走 pending plan。",
        "expected_behavior": "查询/确认类问题应走查询链路，不应直接调用写操作工具；若需写入应先生成 pending plan 由用户确认。",
    },
    "bad_reply": {
        "fix_target": "prompt_or_sft",
        "priority": 50,
        "suggested_action": "修复回复提示词、拒答边界或后续 SFT 候选，不直接入训。",
        "expected_behavior": "回复应符合用户意图、信息准确、表述清晰，无幻觉、无拒答失衡。",
    },
    "off_topic": {
        "fix_target": "prompt_or_sft",
        "priority": 50,
        "suggested_action": "修复回复聚焦度、提示词约束或后续 SFT 候选，不直接入训。",
        "expected_behavior": "回复应聚焦于农场业务相关话题，对超范围请求应礼貌拒答或引导。",
    },
    "unclear_intent": {
        "fix_target": "prompt_or_sft",
        "priority": 40,
        "suggested_action": "优化意图澄清话术或补充 slot 追问逻辑。",
        "expected_behavior": "意图不明时应主动追问关键信息（人物/时间/对象/数量），不应直接执行或拒答。",
    },
    "needs_regression": {
        "fix_target": "manual_triage",
        "priority": 30,
        "suggested_action": "补齐回归用例并锁定预期行为。",
        "expected_behavior": "应有可复现的回归用例覆盖该路径，防止后续回归。",
    },
    "not_actionable": {
        "fix_target": "manual_triage",
        "priority": 20,
        "suggested_action": "人工确认是否需要进一步处理或归档。",
        "expected_behavior": "由人工确认归类，无自动修复预期。",
    },
}
_DEFAULT_ROUTE = {
    "fix_target": "manual_triage",
    "priority": 10,
    "suggested_action": "人工分诊该标签，导出前确认或覆盖修复目标。",
    "expected_behavior": "回复应符合业务规则、用户意图，且不暴露内部信息。",
}

# label → issue_type 路由：同名直接复用 meta；非 detector 产出的 label 也映射到合适的 issue_type。
# 留空（不在字典里）的 label 走 _DEFAULT_ROUTE。
_LABEL_TO_ISSUE_TYPE: dict[str, str] = {label: label for label in _ISSUE_TYPE_META}

_VERIFY_BY_TARGET = {
    "guardrail": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "pending_plan": [
        "pytest tests/services/test_pending_plan_service.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "tool_guardrail": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "domain_policy": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "tool_result_state": [
        "pytest tests/services/test_data_flywheel_issue_detector.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "router": [
        "pytest tests/services/test_data_flywheel_service.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "prompt_or_sft": [
        "pytest tests/services/test_data_flywheel_judge_service.py -q",
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q",
    ],
    "manual_triage": [
        "pytest tests/services/test_data_flywheel_repair_pack_service.py -q"
    ],
}

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|access[_-]?key|token|secret|password|passwd|credential|"
    r"authorization|auth[_-]?token)",
    re.IGNORECASE,
)
_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?P<key>(?:[A-Z0-9_]*API[_-]?KEY|[A-Z0-9_]*TOKEN|SECRET|PASSWORD|"
    r"AUTHORIZATION|ACCESS[_-]?KEY))\s*=\s*(?P<value>[A-Za-z0-9._~:/+=-]+)",
    re.IGNORECASE,
)
_INLINE_SECRET_RE = re.compile(
    r"(?P<key>(?:api[_-]?key|token|secret|password|passwd|credential))"
    r"\s*[:=]\s*(?P<value>[A-Za-z0-9._~:/+=-]+)",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ADDRESS_RE = re.compile(
    r"[\u4e00-\u9fa5]{2,}(?:省|市|区|县|镇|乡|村|路|街|巷)"
    r"[\u4e00-\u9fa5A-Za-z0-9\-]{0,24}(?:号|栋|单元|室)?"
)
