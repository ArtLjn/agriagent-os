#!/usr/bin/env bash
# Farm Manager API 全接口测试脚本
# 用法: ./scripts/test_api.sh [BASE_URL]
# 示例: ./scripts/test_api.sh http://localhost:8000

set -euo pipefail

BASE_URL="${1:-http://localhost:8099}"
ERROR_LOG="backend/app/logs/error.log"
PASS=0
FAIL=0
ERRORS=()

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

> "$ERROR_LOG"

log_pass() { PASS=$((PASS + 1)); echo -e "  ${GREEN}[PASS]${NC} $1"; }
log_fail() {
  FAIL=$((FAIL + 1))
  echo -e "  ${RED}[FAIL]${NC} $1"
  ERRORS+=("$1")
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAIL: $1" >> "$ERROR_LOG"
  if [ -n "${2:-}" ]; then
    echo "  Response: $2" >> "$ERROR_LOG"
  fi
}
log_section() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

request() {
  local method="$1" url="$2" desc="$3"
  shift 3
  local body="" headers=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --body) body="$2"; shift 2 ;;
      --header) headers+=("-H" "$2"); shift 2 ;;
      *) shift ;;
    esac
  done

  local curl_args=(-s -w "\n%{http_code}" -X "$method")
  if [ ${#headers[@]} -gt 0 ]; then
    curl_args+=("${headers[@]}")
  fi
  if [ -n "$body" ]; then
    curl_args+=(-H "Content-Type: application/json" -d "$body")
  fi
  curl_args+=("${BASE_URL}${url}")

  local resp
  resp=$(curl "${curl_args[@]}" 2>&1) || true
  local http_code
  http_code=$(echo "$resp" | tail -1)
  local body_resp
  body_resp=$(echo "$resp" | sed '$d')

  if echo "$http_code" | grep -qE '^[2-3][0-9]{2}$'; then
    log_pass "$desc (HTTP $http_code)"
    echo "$body_resp"
  else
    log_fail "$desc (HTTP $http_code)" "$body_resp"
    echo ""
  fi
}

echo -e "${YELLOW}Farm Manager API 全接口测试${NC}"
echo "目标: $BASE_URL"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"

# ============================================================
log_section "1. 健康检查"
# ============================================================
request GET "/health" "健康检查"

# ============================================================
log_section "2. 认证 - 注册/登录/用户信息"
# ============================================================
PHONE="13800000001"
PASSWORD="test12345678"

request POST "/auth/register" "用户注册" \
  --body "{\"phone\":\"$PHONE\",\"password\":\"$PASSWORD\",\"nickname\":\"测试用户\"}"

LOGIN_RESP=$(request POST "/auth/login" "用户登录" \
  --body "{\"phone\":\"$PHONE\",\"password\":\"$PASSWORD\"}")

TOKEN=""
if [ -n "$LOGIN_RESP" ]; then
  TOKEN=$(echo "$LOGIN_RESP" | grep -o '"access_token":"[^"]*"' | head -1 | cut -d'"' -f4)
fi

if [ -z "$TOKEN" ]; then
  echo -e "  ${RED}无法获取 TOKEN，后续认证接口将跳过${NC}"
  TOKEN="invalid-token"
fi

AUTH_HEADER="Authorization: Bearer $TOKEN"

request GET "/auth/me" "获取当前用户" --header "$AUTH_HEADER"

request PUT "/auth/me" "更新用户信息" \
  --header "$AUTH_HEADER" \
  --body '{"nickname":"测试农友"}'

# ============================================================
log_section "3. 作物模板 CRUD"
# ============================================================
TEMPLATE_RESP=$(request POST "/crops/templates" "创建作物模板" \
  --header "$AUTH_HEADER" \
  --body '{"name":"番茄","variety":"大红番茄","stages":[{"name":"育苗期","duration_days":30,"order_index":1,"key_tasks":"播种育苗"},{"name":"生长期","duration_days":60,"order_index":2,"key_tasks":"施肥浇水"},{"name":"采收期","duration_days":30,"order_index":3,"key_tasks":"采摘"}]}')

TEMPLATE_ID=$(echo "$TEMPLATE_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

request GET "/crops/templates" "获取作物模板列表" --header "$AUTH_HEADER"

if [ -n "$TEMPLATE_ID" ]; then
  request GET "/crops/templates/$TEMPLATE_ID" "获取作物模板详情" --header "$AUTH_HEADER"

  request PUT "/crops/templates/$TEMPLATE_ID" "更新作物模板" \
    --header "$AUTH_HEADER" \
    --body '{"name":"小番茄","variety":"圣女果","stages":[{"name":"育苗期","duration_days":25,"order_index":1,"key_tasks":"播种"},{"name":"生长期","duration_days":55,"order_index":2,"key_tasks":"浇水"}]}'
fi

# ============================================================
log_section "4. 茬口 CRUD + 推进阶段"
# ============================================================
CYCLE_RESP=$(request POST "/cycles" "创建茬口" \
  --header "$AUTH_HEADER" \
  --body "{\"name\":\"春季番茄\",\"crop_template_id\":${TEMPLATE_ID:-1},\"start_date\":\"2026-03-01\",\"field_name\":\"1号地\"}")

CYCLE_ID=$(echo "$CYCLE_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

request GET "/cycles" "获取茬口列表" --header "$AUTH_HEADER"

if [ -n "$CYCLE_ID" ]; then
  request GET "/cycles/$CYCLE_ID" "获取茬口详情" --header "$AUTH_HEADER"

  request PUT "/cycles/$CYCLE_ID" "更新茬口" \
    --header "$AUTH_HEADER" \
    --body "{\"name\":\"春季番茄v2\",\"crop_template_id\":${TEMPLATE_ID:-1},\"start_date\":\"2026-03-01\",\"field_name\":\"2号地\"}"

  request POST "/cycles/$CYCLE_ID/advance-stage" "推进茬口阶段" --header "$AUTH_HEADER"
fi

# ============================================================
log_section "5. 农事日志 CRUD"
# ============================================================
LOG_RESP=$(request POST "/logs" "创建农事日志" \
  --header "$AUTH_HEADER" \
  --body "{\"cycle_id\":${CYCLE_ID:-1},\"operation_type\":\"施肥\",\"operation_date\":\"2026-05-27\",\"note\":\"追施氮肥\"}")

LOG_ID=$(echo "$LOG_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

request GET "/logs" "获取农事日志列表" --header "$AUTH_HEADER"
request GET "/logs?cycle_id=${CYCLE_ID:-1}" "按周期筛选日志" --header "$AUTH_HEADER"

if [ -n "$LOG_ID" ]; then
  request PUT "/logs/$LOG_ID" "更新农事日志" \
    --header "$AUTH_HEADER" \
    --body "{\"cycle_id\":${CYCLE_ID:-1},\"operation_type\":\"浇水\",\"operation_date\":\"2026-05-27\",\"note\":\"滴灌浇水\"}"

  request DELETE "/logs/$LOG_ID" "删除农事日志" --header "$AUTH_HEADER"
fi

# ============================================================
log_section "6. 成本记账 CRUD"
# ============================================================
COST_RESP=$(request POST "/costs" "创建成本记录" \
  --header "$AUTH_HEADER" \
  --body "{\"cycle_id\":${CYCLE_ID:-1},\"record_type\":\"cost\",\"category\":\"化肥\",\"amount\":120.50,\"record_date\":\"2026-05-27\",\"note\":\"买尿素\"}")

COST_ID=$(echo "$COST_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

request GET "/costs" "获取成本记录列表" --header "$AUTH_HEADER"
request GET "/costs?category=化肥" "按分类筛选成本" --header "$AUTH_HEADER"

if [ -n "$CYCLE_ID" ]; then
  request GET "/costs/cycles/$CYCLE_ID/profit" "获取周期利润" --header "$AUTH_HEADER"
fi

request GET "/costs/summary/2026" "获取年度汇总" --header "$AUTH_HEADER"

# ============================================================
log_section "7. AI 解析记账"
# ============================================================
request POST "/costs/parse" "AI解析记账描述" \
  --header "$AUTH_HEADER" \
  --header "X-Idempotency-Key: test-idem-001" \
  --body '{"description":"买了50斤化肥花了120块"}'

# ============================================================
log_section "8. 成本分类"
# ============================================================
request GET "/cost-categories?farm_id=1" "获取成本分类列表"

CAT_RESP=$(request POST "/cost-categories?farm_id=1" "创建自定义分类" \
  --body '{"name":"测试分类","type":"cost","icon":"test","sort_order":99}')

CAT_ID=$(echo "$CAT_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

if [ -n "$CAT_ID" ]; then
  request DELETE "/cost-categories/$CAT_ID?farm_id=1" "删除自定义分类"
fi

# ============================================================
log_section "9. Agent 对话"
# ============================================================
request POST "/agent/chat" "Agent对话" \
  --header "$AUTH_HEADER" \
  --body '{"message":"今天天气怎么样"}'

echo -e "  ${CYAN}[INFO]${NC} 测试 Agent 流式对话 (SSE)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}' \
  "${BASE_URL}/agent/chat/stream" 2>&1 || true)
if echo "$HTTP_CODE" | grep -qE '^[2-3][0-9]{2}$'; then
  log_pass "Agent流式对话 (HTTP $HTTP_CODE)"
else
  log_fail "Agent流式对话 (HTTP $HTTP_CODE)"
fi

# ============================================================
log_section "10. Agent 每日建议"
# ============================================================
request GET "/agent/daily" "获取每日建议" --header "$AUTH_HEADER"

if [ -n "$CYCLE_ID" ]; then
  request GET "/agent/daily?cycle_id=$CYCLE_ID" "获取指定周期每日建议" --header "$AUTH_HEADER"
fi

request POST "/agent/daily/refresh" "强制刷新每日建议" --header "$AUTH_HEADER"

if [ -n "$CYCLE_ID" ]; then
  request POST "/agent/daily/refresh?cycle_id=$CYCLE_ID" "强制刷新指定周期建议" --header "$AUTH_HEADER"
fi

# ============================================================
log_section "11. Agent 报告"
# ============================================================
if [ -n "$CYCLE_ID" ]; then
  request POST "/agent/report" "生成种植报告" \
    --header "$AUTH_HEADER" \
    --body "{\"cycle_id\":$CYCLE_ID,\"report_type\":\"weekly\"}"
fi

request GET "/agent/advice-history" "获取建议历史" --header "$AUTH_HEADER"
request GET "/agent/report-history" "获取报告历史" --header "$AUTH_HEADER"
request GET "/agent/reports" "获取报告列表(分页)" --header "$AUTH_HEADER"

# ============================================================
log_section "12. Agent 会话"
# ============================================================
request GET "/agent/conversations" "获取会话列表" --header "$AUTH_HEADER"

request GET "/agent/conversations/test-session/messages" "获取会话消息" --header "$AUTH_HEADER"

# ============================================================
log_section "13. Agent 反馈"
# ============================================================
request POST "/agent/feedback" "提交AI反馈" \
  --header "$AUTH_HEADER" \
  --body '{"message_id":1,"rating":"good"}'

request GET "/agent/feedback/stats" "获取反馈统计" --header "$AUTH_HEADER"

# ============================================================
log_section "14. 天气预报"
# ============================================================
request GET "/weather/forecast" "获取天气预报(默认)"
request GET "/weather/forecast?days=3" "获取3天天气预报"
request GET "/weather/forecast?lat=31.23&lon=121.47" "获取指定位置天气"

# ============================================================
log_section "15. 用户设置"
# ============================================================
request GET "/settings" "获取用户设置" --header "$AUTH_HEADER"

request PUT "/settings" "更新用户设置" \
  --header "$AUTH_HEADER" \
  --body '{"display_name":"测试农场"}'

# ============================================================
log_section "16. 债务管理"
# ============================================================
request POST "/debts" "创建赊账记录" \
  --header "$AUTH_HEADER" \
  --body "{\"cycle_id\":${CYCLE_ID:-1},\"record_type\":\"cost\",\"category\":\"农资\",\"amount\":500,\"record_date\":\"2026-05-27\",\"note\":\"赊账\",\"record_subtype\":\"debt\",\"counterparty\":\"老王\"}"

request GET "/debts" "获取赊账列表" --header "$AUTH_HEADER"
request GET "/debts?counterparty=老王" "按债权人筛选" --header "$AUTH_HEADER"

request POST "/debts/settle" "结清赊账" \
  --header "$AUTH_HEADER" \
  --body '{"counterparty":"老王","amount":100,"note":"部分还款"}'

# ============================================================
log_section "17. Admin - 运维接口"
# ============================================================
request GET "/admin/guardrails-logs" "获取Guardrails日志"

# ============================================================
log_section "18. Admin - 统计"
# ============================================================
request GET "/admin/stats/tokens?farm_id=1&days=7" "Token用量汇总"
request GET "/admin/stats/tokens/daily?farm_id=1" "Token日明细"

# ============================================================
log_section "19. Admin - Trace"
# ============================================================
request GET "/admin/traces" "获取Trace列表"
request GET "/admin/traces?farm_id=1&limit=5" "按农场筛选Trace"

# ============================================================
log_section "20. Admin - 配置管理"
# ============================================================
request GET "/admin/skills" "列出所有Skill"
request GET "/admin/prompts" "列出Prompt模板"
request GET "/admin/config" "运行时配置查看"

request POST "/admin/cache/clear" "清空所有缓存"
request POST "/admin/prompts/reload" "热加载Prompt"

# ============================================================
log_section "21. 清理测试数据"
# ============================================================
if [ -n "$CYCLE_ID" ]; then
  request DELETE "/cycles/$CYCLE_ID" "删除茬口" --header "$AUTH_HEADER"
fi
if [ -n "$TEMPLATE_ID" ]; then
  request DELETE "/crops/templates/$TEMPLATE_ID" "删除作物模板" --header "$AUTH_HEADER"
fi
if [ -n "$COST_ID" ]; then
  request DELETE "/costs/$COST_ID" "删除成本记录" --header "$AUTH_HEADER" 2>/dev/null || true
fi

# ============================================================
# 汇总报告
# ============================================================
echo ""
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo -e "${CYAN}  测试结果汇总${NC}"
echo -e "${CYAN}════════════════════════════════════════${NC}"
TOTAL=$((PASS + FAIL))
echo -e "  总计: ${TOTAL}  通过: ${GREEN}${PASS}${NC}  失败: ${RED}${FAIL}${NC}"

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo -e "\n  ${RED}失败列表:${NC}"
  for err in "${ERRORS[@]}"; do
    echo -e "    ${RED}✗${NC} $err"
  done
  echo -e "\n  详细错误日志: ${ERROR_LOG}"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}所有接口测试通过!${NC}"
else
  echo -e "${RED}存在 $FAIL 个失败接口，请检查 error.log${NC}"
fi

exit $FAIL
