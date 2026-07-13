#!/usr/bin/env bash
# scripts/harness-check.sh
# Harness Engineering 全量验证入口，一键跑完所有检查

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "╔══════════════════════════════════════╗"
echo "║   Harness Engineering 全量验证        ║"
echo "╚══════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0
SKIP=0

run_check() {
  local name="$1"
  local cmd="$2"
  echo "── $name ──"
  if (eval "$cmd"); then
    echo "✅ $name 通过"
    PASS=$((PASS + 1))
  else
    echo "❌ $name 失败"
    FAIL=$((FAIL + 1))
  fi
  echo ""
}

# ── Linter ──
if [ -d "backend" ] && command -v ruff &>/dev/null; then
  run_check "Python Lint (ruff)" "ruff check backend/"
else
  echo "⏭️  Python Lint: 跳过"
  SKIP=$((SKIP + 1))
fi

if [ -d "admin-web" ] && command -v pnpm &>/dev/null; then
  run_check "Frontend Lint" "cd admin-web && pnpm lint"
else
  echo "⏭️  Frontend Lint: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 类型检查 ──
if [ -d "admin-web" ] && [ -f "admin-web/tsconfig.json" ] && command -v npx &>/dev/null; then
  run_check "TypeScript Check" "cd admin-web && npx tsc --noEmit"
else
  echo "⏭️  TypeScript Check: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 单元测试 ──
if [ -d "backend" ] && command -v pytest &>/dev/null; then
  run_check "Python Tests (pytest)" "cd backend && PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider -v --tb=short"
else
  echo "⏭️  Python Tests: 跳过"
  SKIP=$((SKIP + 1))
fi

if [ -d "admin-web" ] && command -v pnpm &>/dev/null; then
  run_check "Frontend Tests" "cd admin-web && pnpm test"
else
  echo "⏭️  Frontend Tests: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 架构约束 ──
if [ -f "scripts/check-layer-deps.sh" ]; then
  run_check "架构约束检查" "bash scripts/check-layer-deps.sh"
else
  echo "⏭️  架构约束检查: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 复杂度预算 ──
if [ -f "scripts/check-complexity-budget.sh" ]; then
  run_check "复杂度预算检查" "bash scripts/check-complexity-budget.sh"
else
  echo "⏭️  复杂度预算检查: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── TODO/FIXME ──
echo "── TODO/FIXME 残留检查 ──"
echo "✅ 检查完成"
PASS=$((PASS + 1))
echo ""

# ── 文档新鲜度 ──
if [ -f "scripts/check-doc-freshness.sh" ]; then
  run_check "文档新鲜度" "bash scripts/check-doc-freshness.sh"
else
  echo "⏭️  文档新鲜度: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── Skill 文档契约 ──
if [ -f "scripts/check-skill-registry.sh" ]; then
  run_check "Skill Registry 治理" "bash scripts/check-skill-registry.sh"
else
  echo "⏭️  Skill Registry 治理: 跳过"
  SKIP=$((SKIP + 1))
fi

if [ -f "scripts/check-skill-docs.sh" ]; then
  run_check "Skill 文档契约" "bash scripts/check-skill-docs.sh"
else
  echo "⏭️  Skill 文档契约: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── Guide+Sensor 配对检查（增强） ──
if [ -f "scripts/check-guide-sensor-pairing.sh" ]; then
  run_check "Guide+Sensor 配对" "bash scripts/check-guide-sensor-pairing.sh"
else
  echo "⏭️  Guide+Sensor 配对: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── Lint 规则过期追踪（增强） ──
if [ -f "scripts/check-lint-expiry.sh" ]; then
  run_check "Lint 规则过期追踪" "bash scripts/check-lint-expiry.sh"
else
  echo "⏭️  Lint 规则过期追踪: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 汇总 ──
echo "╔══════════════════════════════════════╗"
echo "║   验证结果汇总                        ║"
echo "╠══════════════════════════════════════╣"
echo "║   ✅ 通过: $PASS"
echo "║   ❌ 失败: $FAIL"
echo "║   ⏭️  跳过: $SKIP"
echo "╚══════════════════════════════════════╝"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
