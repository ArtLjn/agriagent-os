"""确定性算术 Skill。"""

from __future__ import annotations

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.skills.metadata import SkillPermissionLevel, SkillRiskLevel


class ArithmeticExpressionError(ValueError):
    """表达式不在安全算术子集内。"""


class CalculateArithmeticSkill(Skill):
    """用 Decimal 执行只读算术，避免模型心算。"""

    def name(self) -> str:
        return "calculate_arithmetic"

    def description(self) -> str:
        return (
            "确定性数学运算工具。凡是涉及总价、单价、面积、数量、比例、公里到米"
            "换算等算术，必须先把用户数字整理成 expression 后调用本工具，不要让"
            "AI 自己心算。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "只包含数字、+、-、*、/ 和括号的算术表达式。"
                        "例：36 * 1000 * 1.5。"
                    ),
                },
                "unit": {
                    "type": "string",
                    "description": "可选结果单位，例如 元、亩、米、个。",
                },
                "precision": {
                    "type": "integer",
                    "description": "小数位数，默认 2，允许 0-8。",
                    "default": 2,
                },
            },
            "required": ["expression"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "domain": "farm",
            "capability": "calculate_arithmetic",
            "operation": "calculate",
            "context_dependencies": ["calculation_expression"],
            "evaluation_tags": ["read", "math", "calculation"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        expression = str(params.get("expression") or "").strip()
        unit = str(params.get("unit") or "").strip()
        precision = _coerce_precision(params.get("precision"))

        if not expression:
            return _failed("INVALID_ARGUMENT", "请提供要计算的 expression。")
        if len(expression) > 200:
            return _failed("EXPRESSION_TOO_LONG", "表达式过长，请拆成更小的步骤。")

        try:
            raw_result = calculate_expression(expression)
            rounded = _quantize(raw_result, precision)
        except DivisionByZero:
            return _failed("DIVISION_BY_ZERO", "除数不能为 0。")
        except (ArithmeticExpressionError, SyntaxError, InvalidOperation):
            return _failed(
                "UNSUPPORTED_EXPRESSION",
                "仅支持数字、+、-、*、/ 和括号组成的算术表达式。",
            )

        formatted = _format_decimal(rounded, precision)
        unit_suffix = f" {unit}" if unit else ""
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=(
                f"计算结果：{formatted}{unit_suffix}\n"
                f"校验：{expression} = {_format_plain_decimal(rounded, precision)}"
            ),
        )


def calculate_expression(expression: str) -> Decimal:
    """安全计算算术表达式。"""
    tree = ast.parse(expression, mode="eval")
    with localcontext() as ctx:
        ctx.prec = 28
        return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant):
        return _decimal_from_constant(node.value)
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ArithmeticExpressionError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        raise ArithmeticExpressionError("unsupported binary operator")
    raise ArithmeticExpressionError("unsupported expression node")


def _decimal_from_constant(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArithmeticExpressionError("unsupported constant")
    return Decimal(str(value))


def _coerce_precision(value: object) -> int:
    try:
        precision = int(value) if value is not None else 2
    except (TypeError, ValueError):
        return 2
    return min(max(precision, 0), 8)


def _quantize(value: Decimal, precision: int) -> Decimal:
    exponent = Decimal("1") if precision == 0 else Decimal(f"1e-{precision}")
    return value.quantize(exponent)


def _format_decimal(value: Decimal, precision: int) -> str:
    return format(value, f",.{precision}f")


def _format_plain_decimal(value: Decimal, precision: int) -> str:
    return format(value, f".{precision}f")


def _failed(code: str, message: str) -> SkillResult:
    return SkillResult(status=ResultStatus.FAILED, reply=f"code={code}；{message}")
