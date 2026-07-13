#!/usr/bin/env bash
# Skill 文档契约检查：验证 skill.md 结构和 Registry alias 一致性。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR/backend"

cleanup_generated_python_artifacts() {
  find app tests -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  find app tests -type f -name '*.pyc' -delete 2>/dev/null || true
}

trap cleanup_generated_python_artifacts EXIT

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python"
fi

PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m pytest tests/skills/test_skill_docs.py -q
