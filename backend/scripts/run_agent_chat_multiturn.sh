#!/usr/bin/env bash
# 真实打 farm-manager /agent/chat 的多轮脚本。
# 与 run_local_multiturn_ai_smoke.sh 区别：那个绕过后端打 LLM，这个走完整 Agent 链路
# （skill_router → task_state → pending_plan → reflection），可用于 A/B 对比方案效果。
#
# 用法:
#   BASE_URL=http://127.0.0.1:8099 TOKEN=xxx ./run_agent_chat_multiturn.sh
#   BASE_URL=http://127.0.0.1:8099 PHONE=15xxx PASSWORD=xxx ./run_agent_chat_multiturn.sh
#   CASE=planting_plan SESSION_ID=playground-xxx ./run_agent_chat_multiturn.sh
#
# 环境变量:
#   BASE_URL       后端地址，默认 http://127.0.0.1:8099
#   TOKEN          直接给 Bearer token（优先）
#   PHONE/PASSWORD 不给 TOKEN 时自动调 /login 获取
#   CASE           测试场景名，默认 planting_plan
#   SESSION_ID     复用已有 session；不填则新建（playground-<ts>-<rand>）
#   SIMULATE_USER_ID  admin 模拟其他用户（切换 farm_id 等场景）
#   CYCLE_ID       可选
#   SHOW_TRACE     =1 时打印 session_id，便于 trace-chain-debugger 续查（默认就打印）

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8099}"
CASE="${CASE:-planting_plan}"
SESSION_ID="${SESSION_ID:-}"
SIMULATE_USER_ID="${SIMULATE_USER_ID:-}"
CYCLE_ID="${CYCLE_ID:-}"

if ! command -v jq >/dev/null 2>&1; then
  echo "需要 jq，请先安装: brew install jq / apt install jq" >&2
  exit 1
fi

now_ms() {
  python3 -c 'import time; print(int(time.time() * 1000))'
}

# ---------- 鉴权 ----------
resolve_token() {
  if [[ -n "${TOKEN:-}" ]]; then
    echo "$TOKEN"
    return
  fi
  if [[ -z "${PHONE:-}" || -z "${PASSWORD:-}" ]]; then
    echo "必须设置 TOKEN 或 PHONE+PASSWORD 环境变量" >&2
    exit 1
  fi
  local body
  body=$(curl -sS -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"phone\":\"$PHONE\",\"password\":\"$PASSWORD\"}") || {
      echo "登录请求失败" >&2; exit 1;
    }
  local token
  token=$(echo "$body" | jq -er '.access_token // .token // empty') || {
    echo "登录响应解析失败: $body" >&2; exit 1;
  }
  echo "$token"
}

TOKEN_RESOLVED=$(resolve_token)

# ---------- Session ----------
if [[ -z "$SESSION_ID" ]]; then
  SESSION_ID="playground-$(date +%s%N | cut -c1-13)-$(openssl rand -hex 3 2>/dev/null || echo $RANDOM)"
fi

# ---------- 测试场景 ----------
# 每行一句 user message；planting_plan 复刻 trace 失败链路
case "$CASE" in
  planting_plan)
    TURNS=(
      "我在太仓新租了30亩地 每块地 1.5亩 帮我规划下茬口 ，秋季草莓"
      "你帮我自行规划"
      "重试"
      "ok"
      "确认"
      "种植单元创建了吗"
      "随便"
    )
    ;;
  cost_query)
    TURNS=(
      "查一下这个月成本趋势"
      "随便看看"
      "继续"
    )
    ;;
  unit_handoff)
    TURNS=(
      "查一下我有哪些种植单元"
      "第一个地块最近怎么样"
      "随便说说"
    )
    ;;
  *)
    echo "未知 CASE=$CASE，可选: planting_plan / cost_query / unit_handoff" >&2
    exit 1
    ;;
esac

# ---------- 跑轮次 ----------
echo "============================================================"
echo " BASE_URL  : $BASE_URL"
echo " CASE      : $CASE"
echo " SESSION   : $SESSION_ID"
echo " TURNS     : ${#TURNS[@]}"
[[ -n "$SIMULATE_USER_ID" ]] && echo " SIMULATE  : $SIMULATE_USER_ID"
[[ -n "$CYCLE_ID" ]]  && echo " CYCLE_ID  : $CYCLE_ID"
echo "============================================================"

for i in "${!TURNS[@]}"; do
  turn_idx=$((i + 1))
  msg="${TURNS[$i]}"

  # 构造 body，仅写非空字段
  body=$(jq -n --arg msg "$msg" --arg sid "$SESSION_ID" \
    '{message: $msg, session_id: $sid}')
  [[ -n "$CYCLE_ID" ]] && body=$(echo "$body" | jq --arg v "$CYCLE_ID" '. + {cycle_id: ($v|tonumber)}')

  echo
  echo "--- Turn $turn_idx user ---"
  echo "$msg"

  start_ts=$(now_ms)
  tmp_file=$(mktemp)
  http_code=$(curl -sS -o "$tmp_file" -w "%{http_code}" \
    -X POST "$BASE_URL/agent/chat" \
    -H "Authorization: Bearer $TOKEN_RESOLVED" \
    -H "Content-Type: application/json" \
    ${SIMULATE_USER_ID:+-H "X-Simulate-User-Id: $SIMULATE_USER_ID"} \
    -d "$body") || {
      echo "  curl 失败" >&2; rm -f "$tmp_file"; exit 1;
    }
  end_ts=$(now_ms)
  latency=$((end_ts - start_ts))

  echo "--- Turn $turn_idx assistant (HTTP $http_code, ${latency}ms) ---"
  if [[ "$http_code" != "200" ]]; then
    echo "  非 200 响应:" >&2
    cat "$tmp_file" >&2
    echo
    rm -f "$tmp_file"
    exit 1
  fi

  reply=$(jq -r '.reply // empty' "$tmp_file")
  pending=$(jq -r '.pending_action // .pending_plan // empty' "$tmp_file")

  echo "reply      : ${reply:0:240}$( [ ${#reply} -gt 240 ] && echo ' ...' )"
  [[ "$pending" != "" && "$pending" != "null" ]] && echo "pending    : $(echo "$pending" | jq -c '.' 2>/dev/null | head -c 200)"

  rm -f "$tmp_file"
done

echo
echo "============================================================"
echo " 完成。SESSION_ID=$SESSION_ID"
echo " 续查链路: cd backend && FARM_MANAGER_ENV=dev .venv/bin/python \\"
echo "   ../.claude/skills/trace-chain-debugger/scripts/analyze_trace_chain.py \\"
echo "   --project .. --session-id $SESSION_ID --limit ${#TURNS[@]} --include-payload"
echo "============================================================"
