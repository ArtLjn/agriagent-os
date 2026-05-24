#!/bin/bash
# scripts/check-layer-deps.sh
# 检查分层架构依赖方向，确保不违规

set -e

ERRORS=0
WARNINGS=0

# ── 后端检查 ──
# 层级（从低到高）: schemas → agents → api → core → models → services
BACKEND="backend/app"
if [ -d "$BACKEND" ]; then
  echo "🔍 检查后端分层依赖..."
  # schemas/ 层不能引用 agents, api, core, models, services
  if grep -rn "from.*(agents\|api\|core\|models\|services)\|import.*(agents\|api\|core\|models\|services)" "$BACKEND/schemas/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: schemas/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: schemas"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # agents/ 层不能引用 api, schemas
  if grep -rn "from.*(api\|schemas)\|import.*(api\|schemas)" "$BACKEND/agents/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: agents/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: agents, core, models, services"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # api/ 层不能引用 agents
  if grep -rn "from.*(agents)\|import.*(agents)" "$BACKEND/api/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: api/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: api, core, models, schemas, services"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # core/ 层不能引用 agents, api, schemas, services
  if grep -rn "from.*(agents\|api\|schemas\|services)\|import.*(agents\|api\|schemas\|services)" "$BACKEND/core/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: core/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: core, models"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # models/ 层不能引用 agents, api, schemas, services
  if grep -rn "from.*(agents\|api\|schemas\|services)\|import.*(agents\|api\|schemas\|services)" "$BACKEND/models/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: models/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: core, models"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # services/ 层不能引用 api, core
  if grep -rn "from.*(api\|core)\|import.*(api\|core)" "$BACKEND/services/" 2>/dev/null | grep -v "__pycache__" | grep -v "# harness-exempt:"; then
    echo "❌ ERROR: services/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: agents, models, schemas, services"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

fi


# ── 前端检查 ──
# 层级（从低到高）: api → components → layouts → pages
FRONTEND="admin-web/src"
if [ -d "$FRONTEND" ]; then
  echo "🔍 检查前端分层依赖..."
  # api/ 层不能引用 components, layouts, pages
  if grep -rn "from.*(components\|layouts\|pages)\|import.*(components\|layouts\|pages)" "$FRONTEND/api/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: api/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: api"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # components/ 层不能引用 layouts, pages
  if grep -rn "from.*(layouts\|pages)\|import.*(layouts\|pages)" "$FRONTEND/components/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: components/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: api, components"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # layouts/ 层不能引用 api, components, pages
  if grep -rn "from.*(api\|components\|pages)\|import.*(api\|components\|pages)" "$FRONTEND/layouts/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: layouts/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: layouts"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # pages/ 层不能引用 layouts
  if grep -rn "from.*(layouts)\|import.*(layouts)" "$FRONTEND/pages/" 2>/dev/null | grep -v "__pycache__" | grep -v "// harness-exempt:"; then
    echo "❌ ERROR: pages/ 层违规引用了其他层"
    echo "✅ FIX: 只允许导入: api, components, pages"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

fi

# ── 文件大小检查 ──
echo "🔍 检查文件大小..."

# Python 文件
for f in $(find backend/ -name "*.py" 2>/dev/null | grep -v __pycache__ | grep -v ".venv"); do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 500 ]; then
    echo "❌ ERROR: $f 有 ${lines} 行（上限 500）"
    echo "✅ FIX: 拆分为更小的模块，将辅助函数移至 utils/"
    ERRORS=$((ERRORS + 1))
  fi
done

# TypeScript 文件
for f in $(find frontend/src/ -name "*.ts" -o -name "*.tsx" 2>/dev/null | grep -v node_modules); do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 300 ]; then
    echo "❌ ERROR: $f 有 ${lines} 行（上限 300）"
    echo "✅ FIX: 拆分为更小的组件或模块"
    ERRORS=$((ERRORS + 1))
  fi
done

# ── TODO/FIXME 检查 ──
echo "🔍 检查 TODO/FIXME 残留..."
TODO_COUNT=$(grep -rn "TODO\|FIXME\|NotImplemented\|pass  # TODO" backend/ frontend/src/ 2>/dev/null | grep -v __pycache__ | grep -v node_modules | wc -l | tr -d ' ')
if [ "$TODO_COUNT" -gt 0 ]; then
  echo "⚠️  发现 $TODO_COUNT 处 TODO/FIXME 残留："
  grep -rn "TODO\|FIXME\|NotImplemented\|pass  # TODO" backend/ frontend/src/ 2>/dev/null | grep -v __pycache__ | grep -v node_modules | head -20
  WARNINGS=$((WARNINGS + 1))
fi

# ── 结果 ──
echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "❌ 架构检查失败：${ERRORS} 个错误，${WARNINGS} 个警告"
  exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
  echo "⚠️  架构检查通过但有 ${WARNINGS} 个警告"
  exit 0
fi

echo "✅ 架构依赖检查全部通过"
