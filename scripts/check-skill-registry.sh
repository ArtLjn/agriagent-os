#!/usr/bin/env bash
# Skill Capability Registry 治理检查：验证 YAML、alias 覆盖和关键安全 guardrail。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR/backend"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python"
fi

PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m app.skills.registry.governance
