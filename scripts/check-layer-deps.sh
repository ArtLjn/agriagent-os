#!/bin/bash
# scripts/check-layer-deps.sh
# 检查分层架构依赖方向，确保不违规

set -e

ERRORS=0
WARNINGS=0

is_size_baseline_file() {
  case "$1" in
    backend/app/infra/pending_actions.py|\
    backend/app/infra/pending_action_presenter.py|\
    backend/app/agent/runtime/nodes.py|\
    backend/app/agent/runtime/tool_executor.py|\
    backend/app/application/smart_fill.py|\
    backend/app/agent/router/classifier.py|\
    backend/app/platforms/data_flywheel/router.py|\
    backend/app/platforms/data_flywheel/review_issue_chain_repository.py|\
    backend/app/platforms/evaluation/discovery/rule_engine.py|\
    backend/app/platforms/data_flywheel/repair_pack_repository.py|\
    backend/app/platforms/data_flywheel/service.py)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

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
    \( -name "__pycache__" -o -name ".venv" -o -name "build" -o -name "vendor" -o -name "_vendor" \) -prune \
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
# 兼容期旧目录只拦截反向依赖；services/ 可依赖 shared/infra 这类底层能力。
BACKEND="backend/app"
if [ -d "$BACKEND" ]; then
  echo "🔍 检查后端分层依赖..."
  if [ -d "$BACKEND/core" ]; then
    echo "❌ ERROR: backend/app/core 已下线，不得重新创建旧 core 入口"
    echo "✅ FIX: 基础设施统一放入 app.shared.*，不要创建旧 core 兼容壳"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  for retired_dir in api models schemas services modules simulation; do
    if [ -d "$BACKEND/$retired_dir" ]; then
      echo "❌ ERROR: backend/app/$retired_dir 已收束下线，不得重新创建旧技术层入口"
      echo "✅ FIX: 业务代码放入 app.domains.*，平台能力放入 app.platforms.*，共享基础设施放入 app.shared.*"
      echo "📖 See: docs/architecture/boundaries.md"
      ERRORS=$((ERRORS + 1))
    fi
  done

  CORE_IMPORT_PATTERN="app\\.co""re\\.|from app\\.co""re|import app\\.co""re"
  CORE_IMPORT_MATCHES=$(rg -n "$CORE_IMPORT_PATTERN" \
    backend/app backend/tests backend/alembic scripts 2>/dev/null || true)
  if [ -n "$CORE_IMPORT_MATCHES" ]; then
    echo "$CORE_IMPORT_MATCHES"
    echo "❌ ERROR: 检测到已下线的旧 core 活动引用"
    echo "✅ FIX: 改用 app.shared.config/database/time/logging/llm/json_repair 等真实入口"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  RETIRED_IMPORT_PATTERN="app\\.(api|models|schemas|services|modules|simulation)\\.|from app\\.(api|models|schemas|services|modules|simulation)([[:space:]]|$)|import app\\.(api|models|schemas|services|modules|simulation)([[:space:]]|$)"
  RETIRED_IMPORT_MATCHES=$(rg -n "$RETIRED_IMPORT_PATTERN" \
    backend/app backend/tests backend/alembic scripts 2>/dev/null || true)
  if [ -n "$RETIRED_IMPORT_MATCHES" ]; then
    echo "$RETIRED_IMPORT_MATCHES"
    echo "❌ ERROR: 检测到已下线旧技术层活动引用"
    echo "✅ FIX: 改用 app.domains.*、app.platforms.*、app.shared.* 或 app.agent.* 真实入口"
    echo "📖 See: docs/architecture/boundaries.md"
    ERRORS=$((ERRORS + 1))
  fi

  # schemas/ 层不能引用 agents, api, models, services
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
    "只允许导入: agents, shared, models, services"

  # api/ 层不能引用 agents
  check_python_imports_recursive_excluding \
    "$BACKEND/api" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.agents(\\.|[[:space:]]|$)" \
    "api/ 层违规引用了其他层" \
    "只允许导入: api, shared, models, schemas, services"

  # models/ 层不能引用 agents, api, schemas, services
  check_python_imports_recursive_excluding \
    "$BACKEND/models" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.(agent|agents|api|schemas|services)(\\.|[[:space:]]|$)" \
    "models/ 层违规引用了其他层" \
    "只允许导入: shared, models"

  # services/ 层不能引用 api
  check_python_imports_recursive_excluding \
    "$BACKEND/services" \
    "^[[:space:]]*(from|import)[[:space:]]+app\\.api(\\.|[[:space:]]|$)" \
    "services/ 层违规引用了其他层" \
    "只允许导入 shared/infra 底层能力、agent 编排、models、schemas、services；不得反向依赖 api"

  echo "🔍 检查 Agent 平台边界..."
  check_python_files \
    "_execute_pending_action|_execute_advisor_pending_action|manager\\.execute\\(pending\\.skill_name|get_langchain_tools\\(farm_id=farm_id" \
    "兼容入口重新引入了 pending action 执行逻辑" \
    "使用 app.agent.executor.pending_actions.handle_pending_action 进行兼容委托" \
    "$BACKEND/services/agent_service.py" \
    "$BACKEND/agent/advisor.py"

  check_python_imports_recursive_excluding \
    "$BACKEND/application" \
    "^[[:space:]]*from[[:space:]]+app\\.services\\.agent_service[[:space:]]+import[[:space:]]+.*\\b(chat_with_agent|stream_chat_with_agent)\\b" \
    "application/ 依赖了旧 service 聊天编排入口" \
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

# Python 文件。生产代码 1000 行以内可接受；500-1000 行只观察职责边界。
for f in $(find backend/app \
  \( -name "__pycache__" -o -name ".venv" -o -name "build" -o -name "vendor" -o -name "_vendor" \) -prune \
  -o -name "*.py" -type f -print 2>/dev/null); do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 1000 ]; then
    echo "❌ ERROR: $f 有 ${lines} 行（生产 Python 文件硬上限 1000）"
    echo "✅ FIX: 按职责收束为领域/平台内聚文件，不要拆出 20-50 行碎片"
    ERRORS=$((ERRORS + 1))
  elif [ "$lines" -gt 500 ]; then
    if is_size_baseline_file "$f"; then
      echo "⚠️  BASELINE: $f 有 ${lines} 行（500-1000 行观察区间，按职责混杂度判断是否收束）"
      WARNINGS=$((WARNINGS + 1))
      continue
    fi
    echo "⚠️  WARN: $f 有 ${lines} 行（500-1000 行观察区间，非硬失败）"
    WARNINGS=$((WARNINGS + 1))
  fi
done

# TypeScript 文件
for frontend_dir in admin-web/src farm-index/app/src frontend/src; do
  if [ ! -d "$frontend_dir" ]; then
    continue
  fi
  while IFS= read -r f; do
    lines=$(wc -l < "$f")
    if [ "$lines" -gt 300 ]; then
      echo "⚠️  BASELINE: $f 有 ${lines} 行（上限 300，历史超限，需专项拆分）"
      WARNINGS=$((WARNINGS + 1))
    fi
  done < <(find "$frontend_dir" \( -name "*.ts" -o -name "*.tsx" \) -type f 2>/dev/null | grep -v node_modules)
done

# Dart 文件
if [ -d "mobile-app/lib" ]; then
  while IFS= read -r f; do
    lines=$(wc -l < "$f")
    if [ "$lines" -gt 500 ]; then
      echo "⚠️  BASELINE: $f 有 ${lines} 行（上限 500，历史超限，需专项拆分）"
      WARNINGS=$((WARNINGS + 1))
    fi
  done < <(find mobile-app/lib -name "*.dart" -type f 2>/dev/null)
fi

# ── TODO/FIXME 检查 ──
echo "🔍 检查 TODO/FIXME 残留..."
TODO_TARGETS=""
if [ -d "backend/app" ]; then
  TODO_TARGETS="$TODO_TARGETS backend/app"
fi
for frontend_dir in admin-web/src farm-index/app/src frontend/src mobile-app/lib; do
  if [ -d "$frontend_dir" ]; then
    TODO_TARGETS="$TODO_TARGETS $frontend_dir"
  fi
done

TODO_MATCHES=""
if [ -n "$TODO_TARGETS" ]; then
  TODO_MATCHES=$(rg -n "TODO|FIXME|NotImplemented|pass  # TODO" $TODO_TARGETS \
    --glob '!**/__pycache__/**' \
    --glob '!**/.venv/**' \
    --glob '!**/build/**' \
    --glob '!**/vendor/**' \
    --glob '!**/_vendor/**' \
    --glob '!**/node_modules/**' 2>/dev/null || true)
fi
TODO_COUNT=$(printf "%s\n" "$TODO_MATCHES" | sed '/^$/d' | wc -l | tr -d ' ')
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
