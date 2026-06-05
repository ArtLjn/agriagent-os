#!/usr/bin/env bash
# Skill 文档契约检查：验证所有 backend/app/agent/skills/*/skill.md 符合项目规范。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR/backend"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python"
fi

"$PYTHON" -m pytest tests/skills/test_skill_docs.py -q
