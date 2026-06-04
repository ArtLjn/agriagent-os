#!/bin/bash
# scripts/check-layer-deps.sh
# 检查分层架构依赖方向，确保不违规

set -e

ERRORS=0
WARNINGS=0

if ! command -v rg >/dev/null 2>&1; then
  echo "❌ ERROR: 缺少 rg（ripgrep），架构检查无法可靠执行"
  echo "✅ FIX: 请先安装 ripgrep，例如 macOS 执行: brew install ripgrep"
  echo "📖 See: docs/architecture/boundaries.md"
  exit 1
fi

check_python_imports() {
  DIR="$1"
  PATTERN="$2"
  MESSAGE="$3"
  FIX="$4"

  if [ ! -d "$DIR" ]; then
    return 0
  fi

  MATCHES=$(find "$DIR" -maxdepth 1 -name "*.py" -type f 2>/dev/null \
    | while IFS= read -r file; do
        rg -n --with-filename "$PATTERN" "$file" 2>/dev/null | grep -v "# harness-exempt:" || true
      done)

  if [ -n "$MATCHES" ]; then
    echo "$MATCHES"
    echo "❌ ERROR: $MESSAGE"
    echo "✅ FIX: $FIX"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
}

check_python_imports_recursive() {
  DIR="$1"
  PATTERN="$2"
  MESSAGE="$3"
  FIX="$4"

  if [ ! -d "$DIR" ]; then
    return 0
  fi

  MATCHES=$(find "$DIR" -name "*.py" -type f 2>/dev/null \
    | while IFS= read -r file; do
        rg -n --with-filename "$PATTERN" "$file" 2>/dev/null | grep -v "# harness-exempt:" || true
      done)

  if [ -n "$MATCHES" ]; then
    echo "$MATCHES"
    echo "❌ ERROR: $MESSAGE"
    echo "✅ FIX: $FIX"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
}

check_python_imports_recursive_excluding() {
  DIR="$1"
  PATTERN="$2"
  MESSAGE="$3"
  FIX="$4"

  if [ ! -d "$DIR" ]; then
    return 0
  fi

  MATCHES=$(find "$DIR" \
    \( -name "__pycache__" -o -name ".venv" -o -name "skillify-sdk" -o -name "build" -o -name "vendor" -o -name "_vendor" \) -prune \
    -o -name "*.py" -type f -print 2>/dev/null \
    | while IFS= read -r file; do
        rg -n --with-filename "$PATTERN" "$file" 2>/dev/null | grep -v "# harness-exempt:" || true
      done)

  if [ -n "$MATCHES" ]; then
    echo "$MATCHES"
    echo "❌ ERROR: $MESSAGE"
    echo "✅ FIX: $FIX"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
}

check_python_files() {
  PATTERN="$1"
  MESSAGE="$2"
  FIX="$3"
  shift 3

  MATCHES=$(for file in "$@"; do
    if [ -f "$file" ]; then
      rg -n --with-filename "$PATTERN" "$file" 2>/dev/null | grep -v "# harness-exempt:" || true
    fi
  done)

  if [ -n "$MATCHES" ]; then
    echo "$MATCHES"
    echo "❌ ERROR: $MESSAGE"
    echo "✅ FIX: $FIX"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi
}

# ── 后端检查 ──
# 层级（从低到高）: schemas → agents → api → core → models → services
BACKEND="backend/app"
if [ -d "$BACKEND" ]; then
  echo "🔍 检查后端分层依赖..."
  # schemas/ 层不能引用 agents, api, core, models, services
  check_python_imports_recursive_excluding \
    "$BACKEND/schemas" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.(agent|agents|api|core|models|services)(\\.|[[:space:]]|$)" \
    "schemas/ 层违规引用了其他层" \
    "只允许导入: schemas"

  # agents/ 层不能引用 api, schemas
  check_python_imports_recursive_excluding \
    "$BACKEND/agents" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.(api|schemas)(\\.|[[:space:]]|$)" \
    "agents/ 层违规引用了其他层" \
    "只允许导入: agents, core, models, services"

  # api/ 层不能引用 agents
  check_python_imports_recursive_excluding \
    "$BACKEND/api" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.agents(\\.|[[:space:]]|$)" \
    "api/ 层违规引用了其他层" \
    "只允许导入: api, core, models, schemas, services"

  # core/ 层不能引用 agents, api, schemas, services
  check_python_imports_recursive_excluding \
    "$BACKEND/core" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.(agent|agents|api|schemas|services)(\\.|[[:space:]]|$)" \
    "core/ 层违规引用了其他层" \
    "只允许导入: core, models"

  # models/ 层不能引用 agents, api, schemas, services
  check_python_imports_recursive_excluding \
    "$BACKEND/models" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.(agent|agents|api|schemas|services)(\\.|[[:space:]]|$)" \
    "models/ 层违规引用了其他层" \
    "只允许导入: core, models"

  # services/ 层不能引用 api, core
  check_python_imports_recursive_excluding \
    "$BACKEND/services" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.(api|core)(\\.|[[:space:]]|$)" \
    "services/ 层违规引用了其他层" \
    "只允许导入: agents, models, schemas, services"

  echo "🔍 检查 Agent 平台边界..."
  check_python_files \
    "_execute_pending_action|_execute_advisor_pending_action|manager\\.execute\\(pending\\.skill_name|get_langchain_tools\\(farm_id=farm_id" \
    "兼容入口重新引入了 pending action 执行逻辑" \
    "使用 app.agent.executor.pending_actions.handle_pending_action 进行兼容委托" \
    "$BACKEND/services/agent_service.py" \
    "$BACKEND/agent/advisor.py"

  check_python_imports_recursive_excluding \
    "$BACKEND/agent/application" \
    "^[[:space:]]*from[[:space:]]+app\\.services\\.agent_service[[:space:]]+import[[:space:]]+.*\\b(chat_with_agent|stream_chat_with_agent)\\b" \
    "agent/application/ 依赖了旧 service 聊天编排入口" \
    "Agent Application 应拥有聊天生命周期编排，不能导入 services.agent_service 的 chat_with_agent/stream_chat_with_agent"

  check_python_imports \
    "$BACKEND/api" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.(memory|prompt|context)(\\.|[[:space:]]|$)" \
    "api/ 层直接引用了 Memory、Prompt 或 Context 平台模块" \
    "API 只做请求校验、依赖注入和调用 application use case"

  check_python_imports_recursive_excluding \
    "$BACKEND/agent/runtime" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.memory(\\.|[[:space:]]|$)" \
    "agent/runtime/ 直接引用了 Memory 模块" \
    "通过 application 注入端口或 Memory Service 接口，不在 Runtime 访问记忆实现"

  check_python_imports_recursive_excluding \
    "$BACKEND/agent/runtime" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.context\\.(selectors|retrieval|compressors|preload|cache)(\\.|[[:space:]]|$)" \
    "agent/runtime/ 直接引用了 Context 平台实现细节" \
    "由 Context Builder 在进入 Runtime 前产出 ContextBundle"

  check_python_imports_recursive_excluding \
    "$BACKEND/agent/runtime" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.prompt\\.(registry|versions|snippets|snapshots|renderer|composer)(\\.|[[:space:]]|$)" \
    "agent/runtime/ 直接引用了 Prompt 平台治理实现细节" \
    "由 Prompt Composer 在进入 Runtime 前产出已渲染 Prompt"

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
for f in $(find backend/app \
  \( -name "__pycache__" -o -name ".venv" -o -name "skillify-sdk" -o -name "build" -o -name "vendor" -o -name "_vendor" \) -prune \
  -o -name "*.py" -type f -print 2>/dev/null); do
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
TODO_TARGETS=""
if [ -d "backend/app" ]; then
  TODO_TARGETS="$TODO_TARGETS backend/app"
fi
if [ -d "frontend/src" ]; then
  TODO_TARGETS="$TODO_TARGETS frontend/src"
fi

TODO_MATCHES=""
if [ -n "$TODO_TARGETS" ]; then
  TODO_MATCHES=$(rg -n "TODO|FIXME|NotImplemented|pass  # TODO" $TODO_TARGETS \
    --glob '!**/__pycache__/**' \
    --glob '!**/.venv/**' \
    --glob '!**/skillify-sdk/**' \
    --glob '!**/build/**' \
    --glob '!**/vendor/**' \
    --glob '!**/_vendor/**' \
    --glob '!**/node_modules/**' 2>/dev/null || true)
fi
TODO_COUNT=$(printf "%s" "$TODO_MATCHES" | sed '/^$/d' | wc -l | tr -d ' ')
if [ "$TODO_COUNT" -gt 0 ]; then
  echo "⚠️  发现 $TODO_COUNT 处 TODO/FIXME 残留："
  printf "%s\n" "$TODO_MATCHES" | head -20
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
