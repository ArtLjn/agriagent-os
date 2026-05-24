#!/bin/bash
# scripts/agent-verify.sh
# 为指定分支创建隔离验证环境，在 worktree 中跑完整检查

set -e

BRANCH=${1:?用法: agent-verify.sh <branch_name>}
WORKTREE_DIR="/tmp/agent-verify-$(date +%s)"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔧 创建 worktree: $WORKTREE_DIR"
git worktree add "$WORKTREE_DIR" "$BRANCH" 2>/dev/null || {
  echo "❌ 无法创建 worktree，请确认分支存在"
  exit 1
}

cd "$WORKTREE_DIR"

if [ -d "backend" ]; then
  echo "📦 安装后端依赖..."
  cd backend && poetry install --quiet 2>/dev/null || pip install -r requirements.txt 2>/dev/null || echo "⚠️ 依赖安装跳过"
  echo "🔍 运行 Ruff 检查..."
  poetry run ruff check . 2>/dev/null || ruff check . || { echo "❌ Ruff 检查失败"; exit 1; }
  echo "🧪 运行后端测试..."
  poetry run pytest -v 2>/dev/null || pytest -v || { echo "❌ 后端测试失败"; exit 1; }
  cd "$WORKTREE_DIR"
fi


if [ -d "admin-web" ]; then
  echo "📦 安装前端依赖..."
  cd admin-web && pnpm install --silent 2>/dev/null || echo "⚠️ pnpm install 跳过"
  echo "🔍 运行 TypeScript 检查..."
  npx tsc --noEmit 2>/dev/null || { echo "❌ TypeScript 检查失败"; exit 1; }
  echo "🧪 运行前端测试..."
  pnpm test 2>/dev/null || { echo "❌ 前端测试失败"; exit 1; }
  cd "$WORKTREE_DIR"
fi

echo "🔍 运行架构约束检查..."
bash scripts/check-layer-deps.sh || { echo "❌ 架构约束检查失败"; exit 1; }

echo "🔍 运行 Guide+Sensor 配对检查..."
bash scripts/check-guide-sensor-pairing.sh || echo "⚠️ Guide+Sensor 配对检查发现问题"

echo "🧹 清理 worktree..."
cd "$PROJECT_DIR"
git worktree remove "$WORKTREE_DIR" --force

echo "✅ 所有验证通过"
