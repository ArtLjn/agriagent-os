#!/usr/bin/env bash
# agri_backend_v2 Agent 单一动作 skill 批量路由与写参数测试。
#
# 前提：agent 服务运行在 :8000，且本机安装 curl、jq。
# 用法：
#   cd /Users/ljn/Documents/demo/explore/agri_backend_v2
#   bash scripts/test_skill_batch.sh
#
# 可覆盖环境变量：
#   AGENT=http://127.0.0.1:8000 AUTH_TOKEN=test bash scripts/test_skill_batch.sh
#   CYCLE_ID=12 bash scripts/test_skill_batch.sh

set -uo pipefail

AGENT="${AGENT:-http://127.0.0.1:8000}"
AUTH_TOKEN="${AUTH_TOKEN:-test}"
TIMEOUT="${TIMEOUT:-60}"
CYCLE_ID="${CYCLE_ID:-}"
CONVERSATION_PREFIX="skill-batch-$(date +%s)"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/farm-manager-skill-batch.XXXXXX")"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
CASE_INDEX=0

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if ! command -v curl >/dev/null 2>&1; then
  echo "${RED}缺少 curl${NC}"
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "${RED}缺少 jq：请先安装 jq${NC}"
  exit 1
fi

if ! curl -fsS --max-time 5 "$AGENT/health" >/dev/null; then
  echo "${RED}agent 服务不可用：$AGENT${NC}"
  exit 1
fi

# 从 SSE 文件中提取某类事件的 data JSON。
sse_data() {
  local event_name="$1"
  local output_file="$2"
  awk -v target="$event_name" '
    /^event: / { current = substr($0, 8) }
    /^data: / && current == target { print substr($0, 7) }
  ' "$output_file"
}

# 后台读取 SSE，发现 HITL approval_required 后立即自动批准。
approve_pending_turn() {
  local output_file="$1"
  local approval_sent=0
  local deadline=$((SECONDS + TIMEOUT))

  while (( SECONDS < deadline )); do
    if [[ "$approval_sent" -eq 0 ]]; then
      local approval_data
      approval_data="$(sse_data approval_required "$output_file" | tail -n 1)"
      if [[ -n "$approval_data" ]]; then
        local turn_id
        turn_id="$(jq -r '.turn_id // empty' <<<"$approval_data")"
        if [[ -n "$turn_id" ]]; then
          curl -fsS -X POST "$AGENT/approve" \
            -H "Content-Type: application/json" \
            -d "$(jq -nc --arg id "$turn_id" \
              '{turn_id:$id, decision:true, reason:"skill 批量测试自动批准"}')" \
            >/dev/null || return 1
          approval_sent=1
        fi
      fi
    fi

    if ! kill -0 "$CHAT_PID" 2>/dev/null; then
      break
    fi
    sleep 0.2
  done
  return 0
}

run_case() {
  local label="$1"
  local message="$2"
  local expected_tool="$3"
  local expected_field="${4:-}"
  local expected_value="${5:-}"
  CASE_INDEX=$((CASE_INDEX + 1))

  local output_file="$TMP_DIR/case-${CASE_INDEX}.sse"
  local conversation_id="${CONVERSATION_PREFIX}-${CASE_INDEX}"

  echo -e "${CYAN}[${CASE_INDEX}] ${label}${NC}：${message}"
  : >"$output_file"
  curl -sS -N -X POST "$AGENT/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -d "$(jq -nc --arg id "$conversation_id" --arg message "$message" \
      '{conversation_id:$id, message:$message}')" \
    --max-time "$TIMEOUT" >"$output_file" 2>&1 &
  CHAT_PID=$!

  approve_pending_turn "$output_file" || true
  wait "$CHAT_PID" 2>/dev/null || true

  local action_data
  action_data="$(sse_data action "$output_file" | tail -n 20)"
  local matched_action=""
  if [[ -n "$action_data" ]]; then
    matched_action="$(jq -r \
      -c \
      --arg tools "$expected_tool" \
      '.tool_name as $name | select(($tools | split("|") | index($name)) != null)' \
      <<<"$action_data" 2>/dev/null | tail -n 1)"
  fi

  if [[ -z "$matched_action" ]]; then
    echo -e "  ${RED}✗ FAIL${NC} 未找到 ${expected_tool} action"
    echo "    action: $(tr '\n' ' ' <<<"$action_data" | cut -c 1-300)"
    echo "    error: $(sse_data observation "$output_file" | jq -r '.error // empty' 2>/dev/null | tail -n 1)"
    FAIL=$((FAIL + 1))
    return
  fi

  local matched_observation
  matched_observation="$(sse_data observation "$output_file" | jq -r \
    -c \
    --arg tools "$expected_tool" \
    '.tool_name as $name | select(($tools | split("|") | index($name)) != null)' \
    2>/dev/null | tail -n 1)"
  if [[ -z "$matched_observation" ]]; then
    echo -e "  ${RED}✗ FAIL${NC} ${expected_tool} 没有返回 observation"
    FAIL=$((FAIL + 1))
    return
  fi

  local observation_error
  observation_error="$(jq -r '.error // empty' <<<"$matched_observation")"
  if [[ -n "$observation_error" ]]; then
    echo -e "  ${RED}✗ FAIL${NC} ${expected_tool} 执行失败：${observation_error}"
    FAIL=$((FAIL + 1))
    return
  fi

  if [[ -n "$expected_field" ]]; then
    local actual_value
    actual_value="$(jq -r --arg field "$expected_field" '.arguments[$field] // empty' \
      <<<"$matched_action")"
    if [[ "$actual_value" != "$expected_value" ]]; then
      echo -e "  ${RED}✗ FAIL${NC} ${expected_field}=${actual_value:-<empty>}，期望 ${expected_value}"
      FAIL=$((FAIL + 1))
      return
    fi
  fi

  echo -e "  ${GREEN}✓ PASS${NC} ${expected_tool}"
  PASS=$((PASS + 1))
}

skip_case() {
  local label="$1"
  local reason="$2"
  echo -e "  ${YELLOW}⚠ SKIP${NC} ${label}：${reason}"
  SKIP=$((SKIP + 1))
}

echo -e "${CYAN}farm-manager v2 skill 批量测试${NC}"
echo "agent: $AGENT"
echo ""

run_case "最近农事查询" "我最近在干啥" \
  "query_farm_logs"
run_case "查询茬口" "有哪些茬口" \
  "query_crop_cycles"
run_case "新建茬口前查询模板" "我想新建一茬番茄" \
  "list_crop_templates|list_system_crop_templates"
run_case "查询作业单" "有哪些作业单" \
  "query_work_orders"
run_case "新增工人" "请新增一名工人，姓名张三，按日计酬，日薪200元" \
  "create_worker" "name" "张三"
run_case "新增收入" "请记录今天一笔收入：卖菜，金额500元，分类销售" \
  "create_cost_record" "record_type" "income"
run_case "新增赊账" "请记录今天赊购化肥500元，欠张三，分类农资" \
  "create_debt_record" "record_type" "debt_payable"
if [[ -n "$CYCLE_ID" ]]; then
  run_case "新增农事日志" "记录农事：${CYCLE_ID}号茬口今天施肥" \
    "create_farm_log" "operation_type" "施肥"
  run_case "新增作业单" "创建一条浇水作业单，关联${CYCLE_ID}号茬口" \
    "create_work_order" "operation_type" "浇水"
else
  skip_case "新增农事日志/作业单" "请设置 CYCLE_ID 为当前农场有效茬口 ID"
fi

echo ""
echo -e "${CYAN}结果：通过 ${GREEN}${PASS}${NC}，失败 ${RED}${FAIL}${NC}，跳过 ${YELLOW}${SKIP}${NC}"

if [[ "$FAIL" -eq 0 ]]; then
  exit 0
fi
exit 1
