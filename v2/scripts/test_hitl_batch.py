"""HITL 批量测试：验证所有 write skill 的风险分类 + 完整审批流程。

跑法：
  cd /Users/ljn/Documents/demo/explore/v2
  uv run --package farm-manager-agent python scripts/test_hitl_batch.py

测试内容：
  1. 单元测试：每个 write skill 的 dynamic_risk_level 分类
     - query 操作 → read（不触发 HITL）
     - create/update/advance/repay/settle → write_confirm（触发 HITL）
     - delete → write_high（触发 HITL）
  2. gate 行为测试：hitl.gate() 正确设置 pending_approval
  3. approve 行为测试：approve(True) 恢复 running，approve(False) 设为 rejected
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from agent.core import hitl  # noqa: E402
from agent.core.turn import Turn  # noqa: E402
from agent.skills import loader as skill_loader  # noqa: E402


def _make_turn() -> Turn:
    """构造一个测试用 Turn。"""
    return Turn(
        conversation_id="test-hitl",
        user_input="test",
        user_id="test-user",
        farm_id=1,
    )


class RiskClassificationTests(unittest.TestCase):
    """测试每个 write skill 的 dynamic_risk_level 分类。"""

    @classmethod
    def setUpClass(cls):
        cls.skills = skill_loader.load_all()
        cls.skill_index = {s.name: s for s in cls.skills}

    def _get_skill(self, name: str):
        s = self.skill_index.get(name)
        self.assertIsNotNone(s, f"skill {name} 未注册")
        return s

    def test_01_manage_farm_logs_risk(self):
        """manage_farm_logs: query→read, create/update→write_confirm, delete→write_high"""
        s = self._get_skill("manage_farm_logs")
        # query → read
        self.assertEqual(s.dynamic_risk_level({"operation": "query"}), "read")
        # create → write_confirm
        self.assertEqual(s.dynamic_risk_level({"operation": "create"}), "write_confirm")
        # update → write_confirm
        self.assertEqual(s.dynamic_risk_level({"operation": "update"}), "write_confirm")
        # delete → write_high
        self.assertEqual(s.dynamic_risk_level({"operation": "delete"}), "write_high")
        print("  ✓ [1/12] manage_farm_logs 风险分类正确")

    def test_02_manage_crop_cycle_risk(self):
        """manage_crop_cycle: query→read, create/advance/update→write_confirm, delete→write_high"""
        s = self._get_skill("manage_crop_cycle")
        self.assertEqual(s.dynamic_risk_level({"operation": "query"}), "read")
        self.assertEqual(s.dynamic_risk_level({"operation": "create"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "advance"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "update"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "delete"}), "write_high")
        print("  ✓ [2/12] manage_crop_cycle 风险分类正确")

    def test_03_manage_cost_risk(self):
        """manage_cost: query→read, create→write_confirm, delete→write_high"""
        s = self._get_skill("manage_cost")
        self.assertEqual(s.dynamic_risk_level({"operation": "query"}), "read")
        self.assertEqual(s.dynamic_risk_level({"operation": "create"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "delete"}), "write_high")
        print("  ✓ [3/12] manage_cost 风险分类正确")

    def test_04_manage_workers_risk(self):
        """manage_workers: query→read, create/update/delete→write_confirm"""
        s = self._get_skill("manage_workers")
        self.assertEqual(s.dynamic_risk_level({"operation": "query"}), "read")
        self.assertEqual(s.dynamic_risk_level({"operation": "create"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "update"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "delete"}), "write_confirm")
        print("  ✓ [4/12] manage_workers 风险分类正确")

    def test_05_manage_debt_risk(self):
        """manage_debt: query→read, create/repay→write_confirm"""
        s = self._get_skill("manage_debt")
        self.assertEqual(s.dynamic_risk_level({"operation": "query"}), "read")
        self.assertEqual(s.dynamic_risk_level({"operation": "create"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "repay"}), "write_confirm")
        print("  ✓ [5/12] manage_debt 风险分类正确")

    def test_06_manage_work_orders_risk(self):
        """manage_work_orders: query→read, create/update/settle→write_confirm"""
        s = self._get_skill("manage_work_orders")
        self.assertEqual(s.dynamic_risk_level({"operation": "query"}), "read")
        self.assertEqual(s.dynamic_risk_level({"operation": "create"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "update"}), "write_confirm")
        self.assertEqual(s.dynamic_risk_level({"operation": "settle"}), "write_confirm")
        print("  ✓ [6/12] manage_work_orders 风险分类正确")

    def test_07_default_risk_is_read(self):
        """所有 manage-* skill 的默认 risk_level（无 operation 参数）应该是 read"""
        for name in ["manage_farm_logs", "manage_crop_cycle", "manage_cost",
                      "manage_workers", "manage_debt", "manage_work_orders"]:
            s = self._get_skill(name)
            self.assertEqual(s.risk_level, "read",
                             f"{name}.risk_level 应为 read（默认），实际为 {s.risk_level}")
        print("  ✓ [7/12] 所有 manage-* skill 默认 risk_level=read")

    def test_08_unknown_operation_is_read(self):
        """未知 operation 应该返回 read（安全默认）"""
        for name in ["manage_farm_logs", "manage_crop_cycle", "manage_cost",
                      "manage_workers", "manage_debt", "manage_work_orders"]:
            s = self._get_skill(name)
            risk = s.dynamic_risk_level({"operation": "unknown_op"})
            self.assertEqual(risk, "read",
                             f"{name} 未知 operation 应返回 read，实际为 {risk}")
        print("  ✓ [8/12] 未知 operation 安全降级为 read")

    def test_09_missing_operation_is_read(self):
        """缺少 operation 参数应该返回 read（安全默认）"""
        for name in ["manage_farm_logs", "manage_crop_cycle", "manage_cost",
                      "manage_workers", "manage_debt", "manage_work_orders"]:
            s = self._get_skill(name)
            risk = s.dynamic_risk_level({})
            self.assertEqual(risk, "read",
                             f"{name} 无 operation 应返回 read，实际为 {risk}")
        print("  ✓ [9/12] 缺少 operation 参数安全降级为 read")


class HitlGateTests(unittest.TestCase):
    """测试 hitl.gate() 和 hitl.approve() 的行为。"""

    def test_10_gate_sets_pending_approval(self):
        """gate(write_confirm) 设置 pending_approval + status=awaiting_approval"""
        turn = _make_turn()
        turn = hitl.gate(
            turn,
            tool_name="manage_farm_logs",
            tool_description="create farm log [RISK: write_confirm]",
            arguments={"operation": "create"},
            tool_call_id="tc_001",
            rationale="用户要求创建日志",
        )
        self.assertEqual(turn.status, "awaiting_approval")
        self.assertIsNotNone(turn.pending_approval)
        self.assertEqual(turn.pending_approval["tool_name"], "manage_farm_logs")
        self.assertEqual(turn.pending_approval["risk_level"], "write_confirm")
        self.assertEqual(turn.pending_approval["tool_call_id"], "tc_001")
        print("  ✓ [10/12] gate() 正确设置 pending_approval + awaiting_approval")

    def test_11_approve_true_resumes_running(self):
        """approve(True) 恢复 status=running，清除 pending_approval"""
        turn = _make_turn()
        turn = hitl.gate(
            turn,
            tool_name="manage_cost",
            tool_description="create cost [RISK: write_confirm]",
            arguments={"operation": "create"},
            tool_call_id="tc_002",
        )
        turn = hitl.approve(turn, decision=True, reason="用户同意")
        self.assertEqual(turn.status, "running")
        self.assertIsNone(turn.pending_approval)
        self.assertTrue(turn.approved)
        print("  ✓ [11/12] approve(True) 恢复 running，清除 pending_approval")

    def test_12_approve_false_sets_rejected(self):
        """approve(False) 设置 status=rejected + rejected_reason"""
        turn = _make_turn()
        turn = hitl.gate(
            turn,
            tool_name="manage_crop_cycle",
            tool_description="delete crop cycle [RISK: write_high]",
            arguments={"operation": "delete"},
            tool_call_id="tc_003",
        )
        turn = hitl.approve(turn, decision=False, reason="用户拒绝删除")
        self.assertEqual(turn.status, "rejected")
        self.assertIsNone(turn.pending_approval)
        self.assertEqual(turn.rejected_reason, "用户拒绝删除")
        print("  ✓ [12/12] approve(False) 设置 rejected + rejected_reason")


class NeedsApprovalTests(unittest.TestCase):
    """测试 hitl.needs_approval() 的判断逻辑。"""

    def test_read_needs_no_approval(self):
        self.assertFalse(hitl.needs_approval("read"))

    def test_write_confirm_needs_approval(self):
        self.assertTrue(hitl.needs_approval("write_confirm"))

    def test_write_high_needs_approval(self):
        self.assertTrue(hitl.needs_approval("write_high"))


def main():
    print("=" * 60)
    print("HITL 批量测试：write skill 风险分类 + 审批流程")
    print("=" * 60)
    print()

    # 先打印 skill 注册情况
    skills = skill_loader.load_all()
    write_skills = [s for s in skills if "manage" in s.name]
    print(f"已加载 {len(skills)} 个 skill，其中 {len(write_skills)} 个 manage-* write skill：")
    for s in write_skills:
        print(f"  - {s.name}: risk_level={s.risk_level}")
    print()

    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(RiskClassificationTests))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(HitlGateTests))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(NeedsApprovalTests))

    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)

    print()
    if result.wasSuccessful():
        print("=" * 60)
        print("✓ 所有测试通过！HITL 风险分类和审批流程正确。")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("✗ 测试失败：")
        for failure in result.failures:
            print(f"  - {failure[0]}")
        for error in result.errors:
            print(f"  - {error[0]}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
