#!/usr/bin/env bash
# agri_backend_v2 Agent Trace/SSE 多轮对话冒烟测试。
#
# 用法：
#   AGENT_TOKEN=... ./agri_backend_v2/scripts/test_trace_sse_rounds.sh
#   AGENT_PHONE=... AGENT_PASSWORD=... ./agri_backend_v2/scripts/test_trace_sse_rounds.sh
#   ROUNDS=3 AGENT_BASE_URL=http://127.0.0.1:8000 ./agri_backend_v2/scripts/test_trace_sse_rounds.sh
#
# 脚本只发送只读问题，不调用写业务工具。每轮检查：
#   1. SSE envelope 的 trace_id/turn_id/event_id/seq/done；
#   2. 相同 client_request_id + after_seq 的 SSE 重放；
#   3. Turn 状态、Trace timeline 和 conversationMessages 回链。

set -Eeuo pipefail

AGENT_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:8000}"
AGENT_TOKEN="${AGENT_TOKEN:-${V2_AGENT_TOKEN:-}}"
AGENT_PHONE="${AGENT_PHONE:-}"
AGENT_PASSWORD="${AGENT_PASSWORD:-}"
ROUNDS="${ROUNDS:-3}"
MAX_TIME="${AGENT_MAX_TIME:-180}"
CONNECT_TIMEOUT="${AGENT_CONNECT_TIMEOUT:-5}"
REPLAY_AFTER_SEQ="${REPLAY_AFTER_SEQ:-1}"

if ! command -v curl >/dev/null 2>&1; then
  echo "FAIL: curl 未安装" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 未安装，脚本需要解析 JSON 和 SSE" >&2
  exit 1
fi
if ! [[ "$ROUNDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "FAIL: ROUNDS 必须是正整数" >&2
  exit 1
fi

case "$AGENT_BASE_URL" in
  */api/agri_backend_v2) API_BASE="$AGENT_BASE_URL" ;;
  *) API_BASE="${AGENT_BASE_URL%/}/api/v2" ;;
esac

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/farm-manager-trace-sse.XXXXXX")"
RESPONSE_FILE="$TMP_DIR/response"
SUMMARY_FILE="$TMP_DIR/summary.json"
CONVERSATION_ID="trace-smoke-$(date +%s)-$RANDOM"
LAST_STATUS=""

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  if [[ -s "$RESPONSE_FILE" ]]; then
    echo "响应摘要: $(head -c 800 "$RESPONSE_FILE")" >&2
  fi
  exit 1
}

json_value() {
  local file="$1"
  local path="$2"
  python3 - "$file" "$path" <<'PY'
import json
import sys

filename, path = sys.argv[1:]
with open(filename, encoding="utf-8") as stream:
    value = json.load(stream)
for part in path.split("."):
    if not isinstance(value, dict) or part not in value:
        raise SystemExit(f"字段不存在: {path}")
    value = value[part]
if isinstance(value, (dict, list)):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
elif value is None:
    print("")
else:
    print(value)
PY
}

request() {
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local -a args
  args=(
    --silent --show-error
    --connect-timeout "$CONNECT_TIMEOUT"
    --max-time "$MAX_TIME"
    -X "$method"
    "$API_BASE$path"
    -H "accept: application/json"
    -H "authorization: Bearer $AGENT_TOKEN"
  )
  if [[ -n "$payload" ]]; then
    args+=( -H "content-type: application/json" -d "$payload" )
  fi
  LAST_STATUS="$(curl "${args[@]}" -o "$RESPONSE_FILE" -w '%{http_code}')" || {
    LAST_STATUS="000"
    return 1
  }
  return 0
}

login() {
  AGENT_TOKEN="${AGENT_TOKEN#Bearer }"
  if [[ -n "$AGENT_TOKEN" ]]; then
    echo "使用环境变量中的 Agent token（不输出 token）"
    return 0
  fi
  if [[ -z "$AGENT_PHONE" || -z "$AGENT_PASSWORD" ]]; then
    fail "请设置 AGENT_TOKEN，或同时设置 AGENT_PHONE 和 AGENT_PASSWORD"
  fi
  local payload
  payload="$(python3 - "$AGENT_PHONE" "$AGENT_PASSWORD" <<'PY'
import json
import sys
print(json.dumps({"phone": sys.argv[1], "password": sys.argv[2]}))
PY
)"
  request POST /auth/login "$payload" || fail "登录请求失败"
  [[ "$LAST_STATUS" == "200" ]] || fail "登录失败，HTTP $LAST_STATUS"
  AGENT_TOKEN="$(json_value "$RESPONSE_FILE" access_token)" || fail "登录响应缺少 access_token"
  [[ -n "$AGENT_TOKEN" ]] || fail "登录响应返回空 access_token"
  echo "登录成功（不输出 token）"
}

parse_sse() {
  local input_file="$1"
  local output_file="$2"
  python3 - "$input_file" "$output_file" <<'PY'
import json
import sys

input_file, output_file = sys.argv[1:]
events = []
current = {"event": None, "id": None, "data": []}

def flush() -> None:
    if not current["data"]:
        current["event"] = None
        current["id"] = None
        return
    raw = "\n".join(current["data"])
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"_invalid_json": raw[:500]}
    events.append({
        "event": current["event"] or "message",
        "id": current["id"],
        "data": payload,
    })
    current["event"] = None
    current["id"] = None
    current["data"] = []

with open(input_file, encoding="utf-8", errors="replace") as stream:
    for line in stream:
        line = line.rstrip("\r\n")
        if not line:
            flush()
        elif line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("id: "):
            current["id"] = line[4:]
        elif line.startswith("data: "):
            current["data"].append(line[6:])
flush()

errors = []
if not events:
    errors.append("没有解析到 SSE 事件")

seqs = []
event_ids = []
trace_ids = []
turn_ids = []
for index, item in enumerate(events, start=1):
    payload = item["data"]
    if not isinstance(payload, dict) or "_invalid_json" in payload:
        errors.append(f"第 {index} 个事件 data 不是有效 JSON")
        continue
    required = ("event_id", "trace_id", "turn_id", "seq", "event_type", "terminal")
    missing = [key for key in required if key not in payload]
    if missing:
        errors.append(f"第 {index} 个事件缺少字段: {','.join(missing)}")
    if item["id"] and payload.get("event_id") != item["id"]:
        errors.append(f"第 {index} 个事件 SSE id 与 data.event_id 不一致")
    try:
        seqs.append(int(payload.get("seq")))
    except (TypeError, ValueError):
        errors.append(f"第 {index} 个事件 seq 无效")
    if payload.get("event_id"):
        event_ids.append(str(payload["event_id"]))
    if payload.get("trace_id"):
        trace_ids.append(str(payload["trace_id"]))
    if payload.get("turn_id"):
        turn_ids.append(str(payload["turn_id"]))

done = [item for item in events if item.get("event") == "done" or item.get("data", {}).get("event_type") == "done"]
if len(done) != 1:
    errors.append(f"done 事件数量为 {len(done)}，期望 1")
if seqs:
    expected = list(range(min(seqs), max(seqs) + 1))
    if seqs != sorted(seqs):
        errors.append("seq 不是单调递增")
    if seqs != expected:
        errors.append(f"seq 存在跳号: 实际={seqs} 期望={expected}")
if len(event_ids) != len(set(event_ids)):
    errors.append("event_id 存在重复")
if len(set(trace_ids)) != 1:
    errors.append(f"trace_id 不唯一: {sorted(set(trace_ids))}")
if len(set(turn_ids)) != 1:
    errors.append(f"turn_id 不唯一: {sorted(set(turn_ids))}")

summary = {
    "event_count": len(events),
    "done_count": len(done),
    "first_seq": min(seqs) if seqs else None,
    "last_seq": max(seqs) if seqs else None,
    "trace_id": trace_ids[0] if trace_ids else None,
    "turn_id": turn_ids[0] if turn_ids else None,
    "event_ids": event_ids,
    "events": [item["event"] for item in events],
    "errors": errors,
}
with open(output_file, "w", encoding="utf-8") as stream:
    json.dump(summary, stream, ensure_ascii=False, indent=2)
if errors:
    print("；".join(errors), file=sys.stderr)
    raise SystemExit(1)
PY
}

send_chat() {
  local conversation_id="$1"
  local client_request_id="$2"
  local message="$3"
  local after_seq="${4:-0}"
  local payload
  payload="$(python3 - "$conversation_id" "$client_request_id" "$message" <<'PY'
import json
import sys
print(json.dumps({
    "conversation_id": sys.argv[1],
    "client_request_id": sys.argv[2],
    "message": sys.argv[3],
}, ensure_ascii=False))
PY
)"
  curl --silent --show-error --no-buffer \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -X POST "$API_BASE/chat?after_seq=$after_seq" \
    -H "accept: text/event-stream" \
    -H "content-type: application/json" \
    -H "authorization: Bearer $AGENT_TOKEN" \
    -d "$payload" \
    -o "$RESPONSE_FILE" \
    -w '%{http_code}'
}

check_round_trace() {
  local trace_id="$1"
  local turn_id="$2"
  local conversation_id="$3"
  request GET "/turns/$turn_id" || fail "Turn 查询网络失败: $turn_id"
  [[ "$LAST_STATUS" == "200" ]] || fail "Turn 查询失败: HTTP $LAST_STATUS"
  local status
  status="$(json_value "$RESPONSE_FILE" status)"
  echo "    Turn status=$status"

  request GET "/traces/$trace_id/timeline?include_payload=false" || fail "Trace timeline 网络失败: $trace_id"
  [[ "$LAST_STATUS" == "200" ]] || fail "Trace timeline 查询失败: HTTP $LAST_STATUS"
  local evidence count
  evidence="$(json_value "$RESPONSE_FILE" evidence_status)"
  count="$(json_value "$RESPONSE_FILE" count)"
  case "$evidence" in
    ok|partial) ;;
    *) fail "Trace timeline 证据不可用: evidence_status=$evidence" ;;
  esac
  echo "    Trace timeline evidence_status=$evidence count=$count"
  [[ "$count" =~ ^[1-9][0-9]*$ ]] || fail "Trace timeline 没有返回节点或事件"

  request GET "/traces/$trace_id/events?include_payload=false" || fail "Trace events 网络失败: $trace_id"
  [[ "$LAST_STATUS" == "200" ]] || fail "Trace events 查询失败: HTTP $LAST_STATUS"
  local event_evidence event_count
  event_evidence="$(json_value "$RESPONSE_FILE" evidence_status)"
  event_count="$(json_value "$RESPONSE_FILE" count)"
  [[ "$event_evidence" == "ok" ]] || fail "traceEvents 证据不可用: evidence_status=$event_evidence"
  [[ "$event_count" =~ ^[1-9][0-9]*$ ]] || fail "traceEvents 没有持久化事件"
  echo "    Trace events evidence_status=$event_evidence count=$event_count"

  if [[ "$conversation_id" != "" ]]; then
    request GET "/conversations/$conversation_id?limit=100" || fail "会话历史网络失败: $conversation_id"
    [[ "$LAST_STATUS" == "200" ]] || fail "会话历史查询失败: HTTP $LAST_STATUS"
    python3 - "$RESPONSE_FILE" "$trace_id" "$turn_id" <<'PY' || fail "会话消息没有回链到当前 Trace/Turn"
import json
import sys

filename, trace_id, turn_id = sys.argv[1:]
with open(filename, encoding="utf-8") as stream:
    document = json.load(stream)
items = document.get("items") or []
if not any(
    str(item.get("trace_id")) == trace_id and str(item.get("turn_id")) == turn_id
    for item in items
):
    raise SystemExit(1)
PY
    echo "    conversationMessages 已回链当前 Trace/Turn"
  fi
}

login
echo "== v2 Agent Trace/SSE 多轮冒烟测试 =="
echo "API_BASE=$API_BASE"
echo "conversation_id=$CONVERSATION_ID"
echo "rounds=$ROUNDS"

FAILURES=0
for round in $(seq 1 "$ROUNDS"); do
  client_request_id="trace-smoke-${CONVERSATION_ID}-${round}"
  case "$round" in
    1) message="请确认本轮 Trace 测试已开始，只读回答一句话。" ;;
    2) message="请回顾上一轮我说了什么，只读回答一句话。" ;;
    *) message="请总结当前会话上下文，只读回答一句话。" ;;
  esac

  echo "[轮次 $round/$ROUNDS] 发送对话"
  status="$(send_chat "$CONVERSATION_ID" "$client_request_id" "$message" 0)" || status="000"
  [[ "$status" == "200" ]] || {
    echo "  FAIL: chat HTTP $status" >&2
    FAILURES=$((FAILURES + 1))
    continue
  }
  parse_sse "$RESPONSE_FILE" "$SUMMARY_FILE" || {
    echo "  FAIL: 初始 SSE envelope 校验失败" >&2
    FAILURES=$((FAILURES + 1))
    continue
  }
  trace_id="$(json_value "$SUMMARY_FILE" trace_id)"
  turn_id="$(json_value "$SUMMARY_FILE" turn_id)"
  first_seq="$(json_value "$SUMMARY_FILE" first_seq)"
  echo "  PASS: events=$(json_value "$SUMMARY_FILE" event_count) seq=${first_seq}-$(json_value "$SUMMARY_FILE" last_seq)"
  echo "    trace_id=$trace_id turn_id=$turn_id"

  echo "  [重放] after_seq=$REPLAY_AFTER_SEQ"
  status="$(send_chat "$CONVERSATION_ID" "$client_request_id" "$message" "$REPLAY_AFTER_SEQ")" || status="000"
  [[ "$status" == "200" ]] || {
    echo "  FAIL: 重放 chat HTTP $status" >&2
    FAILURES=$((FAILURES + 1))
    continue
  }
  parse_sse "$RESPONSE_FILE" "$SUMMARY_FILE" || {
    echo "  FAIL: 重放 SSE envelope 校验失败" >&2
    FAILURES=$((FAILURES + 1))
    continue
  }
  replay_trace_id="$(json_value "$SUMMARY_FILE" trace_id)"
  replay_turn_id="$(json_value "$SUMMARY_FILE" turn_id)"
  replay_first_seq="$(json_value "$SUMMARY_FILE" first_seq)"
  [[ "$replay_trace_id" == "$trace_id" && "$replay_turn_id" == "$turn_id" ]] || {
    echo "  FAIL: 重放的 trace_id/turn_id 发生变化" >&2
    FAILURES=$((FAILURES + 1))
    continue
  }
  [[ "$replay_first_seq" -gt "$REPLAY_AFTER_SEQ" ]] || {
    echo "  FAIL: 重放返回了 after_seq 之前的事件" >&2
    FAILURES=$((FAILURES + 1))
    continue
  }
  echo "  PASS: replay events=$(json_value "$SUMMARY_FILE" event_count) first_seq=$replay_first_seq"

  if ! check_round_trace "$trace_id" "$turn_id" "$CONVERSATION_ID"; then
    FAILURES=$((FAILURES + 1))
  fi
done

echo "== 测试完成 =="
echo "conversation_id=$CONVERSATION_ID"
echo "failures=$FAILURES"
if [[ "$FAILURES" -ne 0 ]]; then
  exit 1
fi
echo "PASS: $ROUNDS 轮对话及 Trace/SSE 回链校验通过"
