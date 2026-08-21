#!/usr/bin/env python3
"""评估脱敏 Skill Router 回放集。

输入 JSONL 每行格式：
``case_id, expected_skills, candidate_skills, expected_tools, called_tools,
candidate_tokens, all_tools_tokens``，其中四个集合字段是字符串数组。
该脚本只评估，不自动切换生产配置。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.domains.harness.router.evaluation import ReplayCase, evaluate_replay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    cases = []
    for line in args.replay.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cases.append(
            ReplayCase(
                case_id=str(item["case_id"]),
                expected_skills=frozenset(item.get("expected_skills", [])),
                candidate_skills=frozenset(item.get("candidate_skills", [])),
                expected_tools=frozenset(item.get("expected_tools", [])),
                called_tools=frozenset(item.get("called_tools", [])),
                candidate_tokens=int(item.get("candidate_tokens", 0)),
                all_tools_tokens=int(item.get("all_tools_tokens", 0)),
            )
        )
    result = evaluate_replay(cases)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
