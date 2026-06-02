import logging
import re

from app.simulation.models import Claim

logger = logging.getLogger(__name__)

CLAIM_PATTERNS: dict[str, list[str]] = {
    "create_cost": ["已记账", "已记录", "记好了", "记账成功", "💰 已记账"],
    "create_template": ["已创建", "模板已创建", "创建成功", "✅ .*模板已创建"],
    "create_cycle": ["已创建茬口", "茬口已创建", "创建.*茬口"],
    "update_stage": ["已更新", "阶段已更新", "更新.*阶段"],
    "log_activity": ["已记录", "农事已记录", "记录.*农事"],
    "settle_debt": ["已结算", "结算完成", "结算.*债务"],
}

OP_TYPE_TO_TABLE: dict[str, str] = {
    "create_cost": "cost_records",
    "create_template": "crop_templates",
    "create_cycle": "crop_cycles",
    "update_stage": "cycle_stages",
    "log_activity": "farm_logs",
    "settle_debt": "cost_records",
}


def extract_claims(agent_reply: str) -> list[Claim]:
    """
    从 LLM 回复中提取声称的操作列表。
    使用关键词匹配，不用 NLP 模型。
    """
    claims: list[Claim] = []
    if not agent_reply:
        return claims

    for op_type, keywords in CLAIM_PATTERNS.items():
        matched_keywords = []
        for kw in keywords:
            if kw.startswith("✅ ") or ".*" in kw:
                if re.search(kw, agent_reply):
                    matched_keywords.append(kw)
            elif kw in agent_reply:
                matched_keywords.append(kw)

        if matched_keywords:
            # 提取匹配关键词附近的上下文作为描述
            description = _extract_context(agent_reply, matched_keywords[0])
            claims.append(
                Claim(
                    op_type=op_type,
                    description=description,
                    keywords_matched=matched_keywords,
                )
            )

    return claims


def _extract_context(text: str, keyword: str, window: int = 20) -> str:
    """提取关键词在文本中的上下文片段。"""
    idx = text.find(keyword)
    if idx == -1:
        # 尝试正则匹配
        match = re.search(keyword, text)
        if match:
            idx = match.start()
            keyword = match.group(0)
        else:
            return text[:60] if len(text) > 60 else text

    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    return text[start:end]


def get_table_for_op(op_type: str) -> str | None:
    """获取操作类型对应的数据库表名。"""
    return OP_TYPE_TO_TABLE.get(op_type)
