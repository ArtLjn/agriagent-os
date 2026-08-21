#!/usr/bin/env bash
#
# Business REST + MCP 完整链路验收脚本。
#
# 默认行为：
#   1. 检查健康、就绪、未认证拒绝和 MCP initialize；
#   2. 自动注册一个隔离测试用户，获取 JWT；
#   3. 通过 curl 串联用户、农场、模板、茬口、种植单元、工人、日志、工单、工资、成本、赊账；
#   4. 对创建的数据执行查询、详情、更新、结算和汇总验证；
#   5. 默认保留测试数据，便于服务端排查。设置 BUSINESS_TEST_CLEANUP=1 执行可用的删除接口。
#
# 用法：
#   ./agri_backend_v2/business/scripts/test_rest_api.sh
#   BUSINESS_BASE_URL=http://127.0.0.1:9876 ./agri_backend_v2/business/scripts/test_rest_api.sh
#   BUSINESS_TOKEN=... BUSINESS_TEST_CLEANUP=1 ./agri_backend_v2/business/scripts/test_rest_api.sh
#   BUSINESS_PHONE=... BUSINESS_PASSWORD=... ./agri_backend_v2/business/scripts/test_rest_api.sh
#
# 说明：当前 Business 没有删除工单/工资的 REST 接口，因此即使开启 cleanup，
#       这两类测试记录也会明确报告为残留，不会通过未授权 SQL 静默删除。

set -Eeuo pipefail

BASE_URL="${BUSINESS_BASE_URL:-http://127.0.0.1:9876}"
TOKEN="${BUSINESS_TOKEN:-}"
PHONE="${BUSINESS_PHONE:-}"
PASSWORD="${BUSINESS_PASSWORD:-}"
REGISTER_NEW="${BUSINESS_TEST_REGISTER:-1}"
CLEANUP="${BUSINESS_TEST_CLEANUP:-0}"
INCLUDE_LABOR="${BUSINESS_TEST_INCLUDE_LABOR:-1}"
CONNECT_TIMEOUT="${BUSINESS_CONNECT_TIMEOUT:-5}"
MAX_TIME="${BUSINESS_MAX_TIME:-30}"

if ! command -v curl >/dev/null 2>&1; then
  echo "FAIL: curl 未安装" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 未安装，脚本需要它解析 JSON" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/farm-manager-business-test.XXXXXX")"
RESPONSE_FILE="$TMP_DIR/response.json"
MCP_RESPONSE_FILE="$TMP_DIR/mcp-response.txt"
LAST_STATUS=""
LAST_BODY=""
TOKEN="${TOKEN#Bearer }"

cleanup_tmp() {
  rm -rf "$TMP_DIR"
}
trap cleanup_tmp EXIT

fail() {
  echo "FAIL: $*" >&2
  if [[ -s "$RESPONSE_FILE" ]]; then
    echo "响应: $(cat "$RESPONSE_FILE")" >&2
  fi
  exit 1
}

on_error() {
  local line="$1"
  echo "FAIL: 脚本在第 ${line} 行中断" >&2
  if [[ -s "$RESPONSE_FILE" ]]; then
    echo "最近响应: $(cat "$RESPONSE_FILE")" >&2
  fi
}
trap 'on_error "$LINENO"' ERR

json_value() {
  local path="$1"
  python3 - "$RESPONSE_FILE" "$path" <<'PY'
import json
import sys

filename, path = sys.argv[1:]
with open(filename, encoding="utf-8") as stream:
    value = json.load(stream)
for part in path.split("."):
    if isinstance(value, dict) and part in value:
        value = value[part]
    else:
        raise SystemExit(f"JSON 字段不存在: {path}")
if isinstance(value, (dict, list)):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
elif value is None:
    print("")
else:
    print(value)
PY
}

require_json_field() {
  local path="$1"
  if ! json_value "$path" >/dev/null; then
    fail "响应缺少字段 ${path}"
  fi
}

assert_json_value() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(json_value "$path")" || fail "响应缺少字段 ${path}"
  [[ "$actual" == "$expected" ]] || fail "字段 ${path} 期望 ${expected}，实际 ${actual}"
}

status_allowed() {
  local actual="$1"
  local expected
  shift
  for expected in "$@"; do
    [[ "$actual" == "$expected" ]] && return 0
  done
  return 1
}

request() {
  local method="$1"
  local path="$2"
  local expected_statuses="$3"
  local payload="${4:-}"
  local -a curl_args
  local status_ok=1

  curl_args=(
    --silent --show-error
    --connect-timeout "$CONNECT_TIMEOUT"
    --max-time "$MAX_TIME"
    -X "$method"
    "$BASE_URL$path"
    -H "accept: application/json"
  )
  if [[ -n "$TOKEN" ]]; then
    curl_args+=( -H "authorization: Bearer $TOKEN" )
  fi
  if [[ -n "$payload" ]]; then
    curl_args+=( -H "content-type: application/json" -d "$payload" )
  fi

  LAST_STATUS="$(curl "${curl_args[@]}" -o "$RESPONSE_FILE" -w '%{http_code}')" || {
    LAST_STATUS="000"
    LAST_BODY="$(cat "$RESPONSE_FILE" 2>/dev/null || true)"
    fail "$method $path 网络请求失败，HTTP ${LAST_STATUS}"
  }
  LAST_BODY="$(cat "$RESPONSE_FILE")"

  local expected
  for expected in $expected_statuses; do
    if [[ "$LAST_STATUS" == "$expected" ]]; then
      status_ok=0
      break
    fi
  done
  if (( status_ok != 0 )); then
    echo "FAIL ${method} ${path}: HTTP ${LAST_STATUS}" >&2
    echo "响应: ${LAST_BODY}" >&2
    exit 1
  fi
  echo "PASS ${method} ${path}: HTTP ${LAST_STATUS}"
}

request_without_auth() {
  local method="$1"
  local path="$2"
  local expected_statuses="$3"
  local old_token="$TOKEN"
  TOKEN=""
  request "$method" "$path" "$expected_statuses" "${4:-}"
  TOKEN="$old_token"
}

new_phone() {
  printf '139%s%s' "$(date +%s)" "${RANDOM}"
}

login_or_register() {
  if [[ -n "$TOKEN" ]]; then
    echo "使用 BUSINESS_TOKEN 进行测试"
    return
  fi

  if [[ "$REGISTER_NEW" == "1" ]]; then
    PHONE="${PHONE:-$(new_phone)}"
    PASSWORD="${PASSWORD:-FarmTest_2026!}"
    local payload
    payload="$(python3 - "$PHONE" "$PASSWORD" <<'PY'
import json
import sys
print(json.dumps({"phone": sys.argv[1], "password": sys.argv[2], "nickname": "DDL链路测试"}, ensure_ascii=False))
PY
)"
    request_without_auth POST /api/v2/auth/register "201" "$payload"
    TOKEN="$(json_value token)"
    [[ -n "$TOKEN" ]] || fail "注册响应没有 token"
    echo "已注册隔离测试用户: ${PHONE}"
  else
    : "${PHONE:?未设置 BUSINESS_TOKEN 时，请设置 BUSINESS_PHONE}"
    : "${PASSWORD:?未设置 BUSINESS_TOKEN 时，请设置 BUSINESS_PASSWORD}"
    local payload
    payload="$(python3 - "$PHONE" "$PASSWORD" <<'PY'
import json
import sys
print(json.dumps({"phone": sys.argv[1], "password": sys.argv[2]}))
PY
)"
    request_without_auth POST /api/v2/auth/login "200" "$payload"
    TOKEN="$(json_value token)"
    [[ -n "$TOKEN" ]] || fail "登录响应没有 token"
  fi
}

check_mcp() {
  local status
  status="$(curl --silent --show-error \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$MCP_RESPONSE_FILE" \
    -w '%{http_code}' \
    -X POST "$BASE_URL/mcp" \
    -H 'accept: application/json, text/event-stream' \
    -H 'content-type: application/json' \
    -H 'mcp-protocol-version: 2025-06-18' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"business-full-chain","version":"1"}}}')" || true
  if [[ "$status" =~ ^2[0-9][0-9]$ ]]; then
    echo "PASS POST /mcp initialize: HTTP ${status}"
  else
    echo "FAIL POST /mcp initialize: HTTP ${status}" >&2
    cat "$MCP_RESPONSE_FILE" >&2
    exit 1
  fi
}

echo "== Business REST + MCP 完整链路测试 =="
echo "BASE_URL=${BASE_URL} REGISTER_NEW=${REGISTER_NEW} CLEANUP=${CLEANUP} INCLUDE_LABOR=${INCLUDE_LABOR}"

request GET /api/v2/health "200"
request GET /api/v2/readiness "200"
request_without_auth GET /api/v2/users/me "401"
check_mcp

login_or_register

request GET /api/v2/users/me "200"
require_json_field id
request GET /api/v2/users/me/settings "200"
request PATCH /api/v2/users/me/settings "200" '{"default_city":"苏州","default_lat":31.2989,"default_lon":120.5853,"assistant_role":"professional"}'
assert_json_value default_city 苏州
request PATCH /api/v2/users/me "200" '{"nickname":"DDL链路测试用户"}'
assert_json_value nickname DDL链路测试用户

request GET /api/v2/farms/my "200"
FARM_ID="$(json_value farm_id)"
[[ "$FARM_ID" =~ ^[0-9]+$ ]] || fail "农场 ID 无效: ${FARM_ID}"
request GET "/api/v2/farms/${FARM_ID}" "200"
request GET "/api/v2/farms/${FARM_ID}/overview" "200"
request PATCH "/api/v2/farms/${FARM_ID}" "200" '{"name":"DDL链路测试农场"}'
request PATCH "/api/v2/farms/${FARM_ID}/location" "200" '{"location":"苏州","lat":31.2989,"lon":120.5853}'

request GET '/api/v2/locations/search?keyword=%E8%8B%8F%E5%B7%9E' "200"
request GET '/api/v2/locations/coords?city=%E8%8B%8F%E5%B7%9E' "200"
request GET '/api/v2/weather?location=%E8%8B%8F%E5%B7%9E&days=1&lat=31.2989&lon=120.5853' "200 502 503"
request GET '/api/v2/weather/now?location=%E8%8B%8F%E5%B7%9E&lat=31.2989&lon=120.5853' "200 502 503"

request GET /api/v2/crop-templates/system/list "200"
TEMPLATE_PAYLOAD='{"name":"DDL链路测试番茄","variety":"agri_backend_v2-test","category":"蔬菜","stages":[{"name":"育苗期","duration_days":10,"order_index":0,"key_tasks":"育苗"},{"name":"结果期","duration_days":20,"order_index":1,"key_tasks":"管理结果"}]}'
request POST /api/v2/crop-templates "201" "$TEMPLATE_PAYLOAD"
TEMPLATE_ID="$(json_value id)"
[[ "$TEMPLATE_ID" =~ ^[0-9]+$ ]] || fail "模板 ID 无效: ${TEMPLATE_ID}"
request GET "/api/v2/crop-templates/${TEMPLATE_ID}" "200"
request GET /api/v2/crop-templates "200"
request PATCH "/api/v2/crop-templates/${TEMPLATE_ID}" "200" "$TEMPLATE_PAYLOAD"

CYCLE_PAYLOAD="$(python3 - "$TEMPLATE_ID" <<'PY'
import json
import sys
print(json.dumps({
    "name": "DDL链路测试番茄茬口",
    "crop_template_id": int(sys.argv[1]),
    "start_date": "2026-08-13",
    "field_name": "DDL测试一号棚",
    "total_area_mu": 2.5,
    "season": "夏秋",
    "batch_note": "REST完整链路测试",
}, ensure_ascii=False))
PY
)"
request POST /api/v2/crop-cycles "201" "$CYCLE_PAYLOAD"
CYCLE_ID="$(json_value id)"
[[ "$CYCLE_ID" =~ ^[0-9]+$ ]] || fail "茬口 ID 无效: ${CYCLE_ID}"
request GET "/api/v2/crop-cycles/${CYCLE_ID}" "200"
request GET /api/v2/crop-cycles "200"
request PATCH "/api/v2/crop-cycles/${CYCLE_ID}" "200" '{"batch_note":"REST链路已更新"}'
request POST "/api/v2/crop-cycles/${CYCLE_ID}/advance-stage" "200 400"

UNIT_PAYLOAD="$(python3 - "$CYCLE_ID" <<'PY'
import json
import sys
print(json.dumps({
    "cycle_id": int(sys.argv[1]),
    "name": "DDL测试一号棚",
    "area_mu": 2.5,
    "planted_date": "2026-08-13",
    "status": "active",
    "note": "REST完整链路测试",
}, ensure_ascii=False))
PY
)"
request POST /api/v2/planting-units "201" "$UNIT_PAYLOAD"
UNIT_ID="$(json_value id)"
[[ "$UNIT_ID" =~ ^[0-9]+$ ]] || fail "种植单元 ID 无效: ${UNIT_ID}"
request GET "/api/v2/planting-units?cycle_id=${CYCLE_ID}" "200"
request PATCH "/api/v2/planting-units/${UNIT_ID}" "200" '{"note":"REST链路已更新"}'

WORKER_PAYLOAD='{"name":"DDL测试工人","phone":"13800009999","default_pay_type":"daily","default_unit_price":180,"note":"REST完整链路测试"}'
request POST /api/v2/workers "201" "$WORKER_PAYLOAD"
WORKER_ID="$(json_value id)"
[[ "$WORKER_ID" =~ ^[0-9]+$ ]] || fail "工人 ID 无效: ${WORKER_ID}"
request GET "/api/v2/workers/${WORKER_ID}" "200"
request GET /api/v2/workers "200"
request PATCH "/api/v2/workers/${WORKER_ID}" "200" '{"note":"REST链路已更新"}'
request GET /api/v2/workers/summary "200"

LOG_PAYLOAD="$(python3 - "$CYCLE_ID" <<'PY'
import json
import sys
print(json.dumps({
    "cycle_id": int(sys.argv[1]),
    "operation_type": "浇水",
    "operation_date": "2026-08-13",
    "note": "REST完整链路测试",
    "worker_names": ["DDL测试工人"],
}, ensure_ascii=False))
PY
)"
request POST /api/v2/farm-logs "201" "$LOG_PAYLOAD"
LOG_ID="$(json_value id)"
[[ "$LOG_ID" =~ ^[0-9]+$ ]] || fail "农事日志 ID 无效: ${LOG_ID}"
request GET "/api/v2/farm-logs/${LOG_ID}" "200"
request GET "/api/v2/farm-logs?cycle_id=${CYCLE_ID}" "200"
request PATCH "/api/v2/farm-logs/${LOG_ID}" "200" '{"note":"REST日志已更新"}'
request GET /api/v2/farm-logs/operations/types "200"

WORK_ORDER_PAYLOAD="$(python3 - "$CYCLE_ID" "$UNIT_ID" <<'PY'
import json
import sys
print(json.dumps({
    "operation_type": "施肥",
    "operation_date": "2026-08-13",
    "cycle_id": int(sys.argv[1]),
    "scope_type": "unit",
    "unit_ids": [int(sys.argv[2])],
    "labor_entries": [],
    "note": "REST完整链路测试",
}, ensure_ascii=False))
PY
)"
request POST /api/v2/work-orders "201" "$WORK_ORDER_PAYLOAD"
WORK_ORDER_ID="$(json_value id)"
[[ "$WORK_ORDER_ID" =~ ^[0-9]+$ ]] || fail "工单 ID 无效: ${WORK_ORDER_ID}"
request GET "/api/v2/work-orders/${WORK_ORDER_ID}" "200"
request GET "/api/v2/work-orders?cycle_id=${CYCLE_ID}" "200"
request PATCH "/api/v2/work-orders/${WORK_ORDER_ID}" "200" '{"note":"REST工单已更新"}'
request GET /api/v2/operation-types "200"

if [[ "$INCLUDE_LABOR" == "1" ]]; then
  WAGE_PAYLOAD="$(python3 - "$CYCLE_ID" "$WORK_ORDER_ID" <<'PY'
import json
import sys
print(json.dumps({
    "worker_name": "DDL测试工人",
    "cycle_id": int(sys.argv[1]),
    "operation_type": "施肥",
    "work_date": "2026-08-13",
    "pay_type": "daily",
    "quantity": 1,
    "unit_price": 180,
    "payable_amount": 180,
    "paid_amount": 0,
    "client_request_id": f"ddl-chain-wage-{sys.argv[1]}-{sys.argv[2]}",
    "note": "REST工资链路测试",
}, ensure_ascii=False))
PY
)"
  request POST /api/v2/labor/wages "201" "$WAGE_PAYLOAD"
  LABOR_ENTRY_ID="$(json_value id)"
  [[ "$LABOR_ENTRY_ID" =~ ^[0-9]+$ ]] || fail "工资记录 ID 无效: ${LABOR_ENTRY_ID}"
  request GET '/api/v2/labor/wages?mode=unpaid' "200"
  request GET '/api/v2/labor/unsettled-summary' "200"
  request POST "/api/v2/work-orders/${WORK_ORDER_ID}/settle" "200 400"
fi

CATEGORY_PAYLOAD='{"name":"DDL测试材料","type":"cost","icon":"tag","sort_order":99}'
request POST /api/v2/cost-categories "201" "$CATEGORY_PAYLOAD"
CATEGORY_ID="$(json_value id)"
[[ "$CATEGORY_ID" =~ ^[0-9]+$ ]] || fail "成本分类 ID 无效: ${CATEGORY_ID}"
request GET /api/v2/cost-categories "200"
request PATCH "/api/v2/cost-categories/${CATEGORY_ID}" "200" '{"sort_order":100}'

COST_PAYLOAD="$(python3 - "$CYCLE_ID" <<'PY'
import json
import sys
print(json.dumps({
    "record_type": "cost",
    "category": "DDL测试材料",
    "amount": 88.50,
    "record_date": "2026-08-13",
    "cycle_id": int(sys.argv[1]),
    "note": "REST成本链路测试",
}, ensure_ascii=False))
PY
)"
request POST /api/v2/cost-records "201" "$COST_PAYLOAD"
COST_ID="$(json_value id)"
[[ "$COST_ID" =~ ^[0-9]+$ ]] || fail "成本记录 ID 无效: ${COST_ID}"
request GET "/api/v2/cost-records?cycle_id=${CYCLE_ID}" "200"
request PATCH "/api/v2/cost-records/${COST_ID}" "200" '{"note":"REST成本已更新"}'
request GET '/api/v2/cost-records/summary/yearly?year=2026' "200"
request GET "/api/v2/cost-records/cycles/${CYCLE_ID}/profit" "200"

DEBT_PAYLOAD="$(python3 - "$CYCLE_ID" <<'PY'
import json
import sys
print(json.dumps({
    "counterparty": "DDL测试供应商",
    "amount": 120,
    "record_date": "2026-08-13",
    "due_date": "2026-09-13",
    "note": "REST赊账链路测试",
    "cycle_id": int(sys.argv[1]),
    "record_type": "cost",
    "category": "赊账",
}, ensure_ascii=False))
PY
)"
request POST /api/v2/debts "201" "$DEBT_PAYLOAD"
request GET /api/v2/debts "200"
request GET /api/v2/debts/summary "200"
request POST /api/v2/debts/settle "200" '{"counterparty":"DDL测试供应商","amount":120,"note":"REST赊账已结算"}'

request GET /api/v2/dashboard "200"
request GET "/api/v2/dashboard/recent-operations?cycle_id=${CYCLE_ID}&days=365&limit=50" "200"
request GET '/api/v2/dashboard/cost-summary?year=2026' "200"
request GET /api/v2/dashboard/active-cycles "200"
request GET /api/v2/dashboard/unsettled-labor "200"
request GET "/api/v2/recent-operations?cycle_id=${CYCLE_ID}&days=365&limit=50" "200"

if [[ "$CLEANUP" == "1" ]]; then
  echo "== 开始清理 API 支持删除的测试数据 =="
  request DELETE "/api/v2/farm-logs/${LOG_ID}" "200"
  request DELETE "/api/v2/cost-records/${COST_ID}" "200"
  request DELETE "/api/v2/cost-categories/${CATEGORY_ID}" "200 400"
  request DELETE "/api/v2/planting-units/${UNIT_ID}" "200"
  request DELETE "/api/v2/crop-cycles/${CYCLE_ID}" "200"
  request DELETE "/api/v2/crop-templates/${TEMPLATE_ID}" "200"
  request DELETE "/api/v2/workers/${WORKER_ID}" "200 400"
  echo "WARN: 用户、农场以及当前没有删除接口的工单/工资记录不会被清理"
else
  echo "INFO: 测试数据已保留，FARM_ID=${FARM_ID} CYCLE_ID=${CYCLE_ID} WORK_ORDER_ID=${WORK_ORDER_ID}"
  echo "INFO: 如需清理可重跑 BUSINESS_TEST_CLEANUP=1，但工单/工资仍需人工处理"
fi

echo "Business REST + MCP 完整链路验收通过"
