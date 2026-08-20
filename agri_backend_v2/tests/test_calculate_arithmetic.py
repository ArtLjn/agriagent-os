"""calculate_arithmetic Skill 的 Python AST 兼容性测试。"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "agent"
    / "tools"
    / "calculate-arithmetic"
    / "scripts"
    / "main.py"
)


def _load_skill_module():
    spec = importlib.util.spec_from_file_location(
        "calculate_arithmetic_skill", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 Skill 模块: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CalculateArithmeticTests(unittest.IsolatedAsyncioTestCase):
    async def test_python_314_numeric_ast_is_supported(self) -> None:
        module = _load_skill_module()
        result = await module.skill.execute({"expression": "36 * 1000 * 1.5"}, None)
        self.assertIsNone(result.error)
        self.assertEqual(result.data["result"], 54000)

    async def test_unsupported_ast_is_rejected(self) -> None:
        module = _load_skill_module()
        result = await module.skill.execute({"expression": "__import__('os')"}, None)
        self.assertIsNotNone(result.error)
        self.assertIn("表达式不安全", result.error)


if __name__ == "__main__":
    unittest.main()
