"""calculate-arithmetic skill: 本地 Decimal 安全求值。

参考 archive/backend/app/skills/calculate-arithmetic/scripts/main.py 的安全子集设计。
"""
from __future__ import annotations

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext

# 允许的 AST 节点：数字、二元运算、一元负号、括号。
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Num,  # py<3.8 兼容
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.USub,
    ast.UAdd,
)


class ArithmeticExpressionError(ValueError):
    """表达式不在安全算术子集内。"""


def _validate_ast(node: ast.AST) -> None:
    """递归校验 AST 节点都在白名单内。"""
    if not isinstance(node, _ALLOWED_NODES):
        raise ArithmeticExpressionError(
            f"不支持的语法: {type(node).__name__}"
        )
    for child in ast.iter_child_nodes(node):
        _validate_ast(child)


def _evaluate(node: ast.AST) -> Decimal:
    """递归求值为 Decimal。"""
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Decimal(str(node.value))
    if isinstance(node, ast.Num):  # py<3.8
        return Decimal(str(node.n))
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise DivisionByZero("除数为零")
            return left / right
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate(node.operand)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
    raise ArithmeticExpressionError(f"无法求值: {ast.dump(node)}")


class CalculateArithmeticSkill(Skill):
    """确定性算术运算。"""

    kind = "local"

    @property
    def name(self) -> str:
        return "calculate_arithmetic"

    @property
    def description(self) -> str:
        return (
            "确定性算术运算。涉及总价、单价、面积、数量、比例等数学计算时必须用此工具，"
            "不要心算。expression 只允许数字和 + - * / ( ) 字符。"
        )

    @property
    def risk_level(self) -> str:
        return "read"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "只含数字和 + - * / ( ) 的算术表达式，例 '36 * 1000 * 1.5'",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, params: dict, ctx: SkillContext) -> SkillResult:
        expr = (params.get("expression") or "").strip()
        if not expr:
            return SkillResult(error="expression 不能为空")
        try:
            tree = ast.parse(expr, mode="eval")
            _validate_ast(tree)
            # Decimal 高精度上下：28 位有效数字
            with localcontext() as dec_ctx:
                dec_ctx.prec = 28
                result = _evaluate(tree)
            # 整数结果去掉小数点
            if result == result.to_integral_value():
                return SkillResult(data={"expression": expr, "result": int(result)})
            return SkillResult(data={"expression": expr, "result": float(result)})
        except ArithmeticExpressionError as exc:
            return SkillResult(error=f"表达式不安全: {exc}")
        except DivisionByZero:
            return SkillResult(error="除数为零")
        except (InvalidOperation, SyntaxError, ValueError, TypeError) as exc:
            return SkillResult(error=f"无法求值: {exc}")


skill = CalculateArithmeticSkill()
