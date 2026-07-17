from __future__ import annotations

from typing import Any


def build_repair_pack_readme(manifest: dict[str, Any]) -> str:
    commands = "\n".join(
        f"- `{command}`" for command in manifest["verification_commands"]
    )
    return f"""# Repair Pack {manifest["pack_id"]}

面向 vibecoding 的读取顺序：
1. 先读 `manifest.json`，确认 fix_target={manifest["fix_target"]} 和样本范围。
2. 再读 `cases.jsonl`，理解 observed_failure、expected_behavior 和回归准备状态。
3. 按需读取 `debug/` 中脱敏证据和 `regression-drafts/` 中草稿断言。

修复步骤：
1. 先复现或补回归测试，优先使用 regression draft 中的断言。
2. 只围绕当前 fix_target 做最小范围修复，不修改无关 API、模型、迁移或前端。
3. 禁止把 bad reply 直接作为训练数据使用；如需 SFT，只能作为候选并经人工审核。
4. 运行 manifest 中的验证命令。

验证命令：
{commands}

完成回报格式：
- 修复目标
- 改动文件
- 新增或更新的回归测试
- 验证命令和结果
- 剩余风险或需要人工确认的样本
"""
