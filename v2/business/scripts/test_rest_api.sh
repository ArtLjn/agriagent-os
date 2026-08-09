#!/usr/bin/env bash
# Business REST + MCP 只读批量验收脚本。
# 用法：BUSINESS_TOKEN=... ./v2/business/scripts/test_rest_api.sh
set -euo pipefail

BASE_URL="${BUSINESS_BASE_URL:-http://127.0.0.1:9876}"
TOKEN="${BUSINESS_TOKEN:-}"
CONNECT_TIMEOUT="${BUSINESS_CONNECT_TIMEOUT:-5}"
MAX_TIME="${BUSINESS_MAX_TIME:-20}"

if ! command -v curl >/dev/null 2>&1; then
  echo "FAIL: curl 未安装" >&2
  exit 1
fi

curl_json() {
  curl --silent --show-error --fail-with-body \
    --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
    -H "accept: application/json" "$@"
}

if [[ -z "$TOKEN" ]]; then
  : "${BUSINESS_PHONE:?请设置 BUSINESS_TOKEN，或同时设置 BUSINESS_PHONE 和 BUSINESS_PASSWORD}"
  : "${BUSINESS_PASSWORD:?请设置 BUSINESS_TOKEN，或同时设置 BUSINESS_PHONE 和 BUSINESS_PASSWORD}"
  login_payload="$(python3 - "$BUSINESS_PHONE" "$BUSINESS_PASSWORD" <<'PY'
import json
import sys

print(json.dumps({"phone": sys.argv[1], "password": sys.argv[2]}))
PY
)"
  login_response="$(curl_json -X POST "$BASE_URL/api/v2/auth/login" \
    -H "content-type: application/json" \
    -d "$login_payload")"
  TOKEN="$(printf '%s' "$login_response" | python3 -c \
    'import json, sys; print(json.load(sys.stdin)["token"])')"
fi

if [[ -z "$TOKEN" ]]; then
  echo "FAIL: 登录响应未返回 token" >&2
  exit 1
fi

get_api() {
  local path="$1"
  curl_json -H "authorization: Bearer $TOKEN" "$BASE_URL$path" >/dev/null
  printf 'PASS GET %s\n' "$path"
}

check_no_auth() {
  local status
  status="$(curl --silent --show-error --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" -o /dev/null -w '%{http_code}' \
    "$BASE_URL/api/v2/users/me")"
  [[ "$status" == "401" ]] || {
    printf 'FAIL GET /api/v2/users/me without auth: HTTP %s\n' "$status" >&2
    return 1
  }
  printf 'PASS GET /api/v2/users/me without auth: HTTP 401\n'
}

check_mcp() {
  local status
  status="$(curl --silent --show-error --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" -o /dev/null -w '%{http_code}' \
    -X POST "$BASE_URL/mcp" \
    -H 'accept: application/json, text/event-stream' \
    -H 'content-type: application/json' \
    -H 'mcp-protocol-version: 2025-06-18' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"business-rest-smoke","version":"1"}}}')"
  [[ "$status" =~ ^2[0-9][0-9]$ ]] || {
    printf 'FAIL POST /mcp: HTTP %s\n' "$status" >&2
    return 1
  }
  printf 'PASS POST /mcp: HTTP %s\n' "$status"
}

check_mcp
get_api /api/v2/health
get_api /api/v2/readiness
check_no_auth
get_api /api/v2/users/me
get_api /api/v2/farms/my
get_api /api/v2/dashboard
get_api /api/v2/crop-templates
get_api /api/v2/crop-cycles
get_api /api/v2/farm-logs
get_api /api/v2/workers
get_api /api/v2/work-orders
get_api /api/v2/planting-units
get_api /api/v2/labor/unsettled-summary
get_api /api/v2/recent-operations
get_api /api/v2/operation-types
get_api /api/v2/cost-categories
get_api /api/v2/cost-records
get_api /api/v2/debts
get_api '/api/v2/locations/search?keyword=%E8%8B%8F%E5%B7%9E'

echo "Business REST + MCP 批量验收通过"
