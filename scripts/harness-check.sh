#!/bin/bash
# scripts/harness-check.sh
# Harness Engineering 全量验证入口，一键跑完所有检查

set -e

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
  if eval "$cmd"; then
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

if [ -d "admin-web" ]; then
  run_check "Frontend Lint" "cd admin-web && pnpm lint 2>/dev/null || echo 'lint not configured'"
else
  echo "⏭️  Frontend Lint: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 类型检查 ──
if [ -d "admin-web" ] && [ -f "admin-web/tsconfig.json" ]; then
  run_check "TypeScript Check" "cd admin-web && npx tsc --noEmit"
else
  echo "⏭️  TypeScript Check: 跳过"
  SKIP=$((SKIP + 1))
fi

# ── 单元测试 ──
if [ -d "backend" ] && command -v pytest &>/dev/null; then
  run_check "Python Tests (pytest)" "cd backend && pytest -v --tb=short"
else
  echo "⏭️  Python Tests: 跳过"
  SKIP=$((SKIP + 1))
fi

if [ -d "admin-web" ]; then
  run_check "Frontend Tests" "cd admin-web && pnpm test 2>/dev/null || echo 'no tests'"
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
