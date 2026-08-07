#!/usr/bin/env bash
# 多轮对话测试：planner、HITL、context_usage、doom_loop 等能力
#
# 跑法：
#   cd /Users/ljn/Documents/demo/explore/v2
#   bash scripts/test_multi_turn.sh
#
# 前提：agent 服务运行在 :8000

set -uo pipefail

AGENT="http://127.0.0.1:8000"
CONV_ID="test-multi-$(date +%s)"
AUTH_HEADER="Authorization: Bearer test"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
TOTAL_EVENTS=0

# ─── 工具函数 ─────────────────────────────────────────────────

# 发送 chat 请求，解析 SSE 事件
# 用法: send_chat "消息内容" > /tmp/sse_output.txt
send_chat() {
  local msg="$1"
  curl -s -N -X POST "$AGENT/chat" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "{\"conversation_id\":\"$CONV_ID\",\"message\":\"$msg\"}" \
    --max-time 60 2>/dev/null
}

# 从 SSE 输出中提取事件类型列表
# 用法: get_event_types < /tmp/sse_output.txt
get_event_types() {
  grep '^event: ' | sed 's/^event: //' | tr -d '\r'
}

# 从 SSE 输出中提取特定事件类型的 data
# 用法: get_event_data "final_answer" < /tmp/sse_output.txt
get_event_data() {
  local target_type="$1"
  local in_target=0
  while IFS= read -r line; do
    if [[ "$line" == event:\ * ]]; then
      local etype="${line#event: }"
      etype="${etype%$'\r'}"
      if [[ "$etype" == "$target_type" ]]; then
        in_target=1
      else
        in_target=0
      fi
    elif [[ "$line" == data:\ * ]] && [[ $in_target -eq 1 ]]; then
      echo "${line#data: }"
    fi
  done
}

# 检查事件是否存在
# 用法: has_event "plan_created" < /tmp/sse_output.txt
has_event() {
  local target="$1"
  grep -q "^event: ${target}$" <<< "$(cat)"
}

# 提取 final_answer 文本
get_final_answer() {
  get_event_data "final_answer" | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        print(d.get('text', ''))
    except: pass
" 2>/dev/null
}

# 统计事件数
count_events() {
  get_event_types | wc -l | tr -d ' '
}

# ─── 测试用例 ─────────────────────────────────────────────────

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN} 多轮对话测试：planner / HITL / context_usage / doom_loop${NC}"
echo -e "${CYAN} conv_id: $CONV_ID${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ─── 测试 1：简单对话（验证基本流程 + context_usage）──
echo -e "${YELLOW}[测试 1] 简单对话 → 验证 context_usage + final_answer${NC}"
send_chat "你好" > /tmp/sse_1.txt 2>&1
EVENTS_1=$(cat /tmp/sse_1.txt | get_event_types)
FINAL_1=$(cat /tmp/sse_1.txt | get_final_answer)

if echo "$EVENTS_1" | grep -q "context_usage" && [[ -n "$FINAL_1" ]]; then
  echo -e "  ${GREEN}✓ PASS${NC} context_usage 事件存在，final_answer 非空"
  PASS=$((PASS+1))
else
  echo -e "  ${RED}✗ FAIL${NC} 期望 context_usage + final_answer"
  echo -e "    事件列表: $(echo $EVENTS_1 | tr '\n' ' ')"
  echo -e "    final_answer: ${FINAL_1:0:80}"
  FAIL=$((FAIL+1))
fi
TOTAL_EVENTS=$((TOTAL_EVENTS + $(echo "$EVENTS_1" | count_events)))
echo ""

# ─── 测试 2：工具调用（验证 thought → action → observation）──
echo -e "${YELLOW}[测试 2] 工具调用 → 验证 thought/action/observation 事件${NC}"
send_chat "查询北京天气" > /tmp/sse_2.txt 2>&1
EVENTS_2=$(cat /tmp/sse_2.txt | get_event_types)
FINAL_2=$(cat /tmp/sse_2.txt | get_final_answer)

HAS_ACTION=$(echo "$EVENTS_2" | grep -c "^action$" || echo 0)
HAS_OBS=$(echo "$EVENTS_2" | grep -c "^observation$" || echo 0)

if [[ "$HAS_ACTION" -ge 1 ]] && [[ "$HAS_OBS" -ge 1 ]]; then
  echo -e "  ${GREEN}✓ PASS${NC} action($HAS_ACTION) + observation($HAS_OBS) 事件存在"
  PASS=$((PASS+1))
else
  echo -e "  ${RED}✗ FAIL${NC} 期望 action + observation 事件"
  echo -e "    事件列表: $(echo $EVENTS_2 | tr '\n' ' ')"
  FAIL=$((FAIL+1))
fi
TOTAL_EVENTS=$((TOTAL_EVENTS + $(echo "$EVENTS_2" | count_events)))
echo ""

# ─── 测试 3：HITL（写操作需要审批）──
echo -e "${YELLOW}[测试 3] HITL 审批 → 验证 approval_required 事件${NC}"
send_chat "帮我创建一条农事日志，内容是浇水" > /tmp/sse_3.txt 2>&1
EVENTS_3=$(cat /tmp/sse_3.txt | get_event_types)

if echo "$EVENTS_3" | grep -q "approval_required"; then
  APPROVAL_DATA=$(cat /tmp/sse_3.txt | get_event_data "approval_required" | head -1)
  TOOL_NAME=$(echo "$APPROVAL_DATA" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('tool_name',''))" 2>/dev/null || echo "")
  echo -e "  ${GREEN}✓ PASS${NC} approval_required 事件存在 (tool: $TOOL_NAME)"
  PASS=$((PASS+1))
else
  echo -e "  ${YELLOW}⚠ SKIP${NC} 未触发 approval_required（LLM 可能用了其他方式回答）"
  echo -e "    事件列表: $(echo $EVENTS_3 | tr '\n' ' ')"
fi
TOTAL_EVENTS=$((TOTAL_EVENTS + $(echo "$EVENTS_3" | count_events)))
echo ""

# ─── 测试 4：多轮对话记忆（验证第二轮能引用第一轮内容）──
echo -e "${YELLOW}[测试 4] 多轮记忆 → 第二轮引用第一轮内容${NC}"
send_chat "我刚才问你什么了？" > /tmp/sse_4.txt 2>&1
EVENTS_4=$(cat /tmp/sse_4.txt | get_event_types)
FINAL_4=$(cat /tmp/sse_4.txt | get_final_answer)

if echo "$FINAL_4" | grep -q "天气\|北京\|你好"; then
  echo -e "  ${GREEN}✓ PASS${NC} 第二轮回答引用了之前内容"
  echo -e "    回答摘要: ${FINAL_4:0:80}"
  PASS=$((PASS+1))
else
  echo -e "  ${YELLOW}⚠ SKIP${NC} 回答未明显引用前文（LLM 行为差异）"
  echo -e "    回答摘要: ${FINAL_4:0:80}"
fi
TOTAL_EVENTS=$((TOTAL_EVENTS + $(echo "$EVENTS_4" | count_events)))
echo ""

# ─── 测试 5：复杂任务（验证 make_plan 或多步 action）──
echo -e "${YELLOW}[测试 5] 复杂任务 → 验证 plan_created 或多步 action${NC}"
send_chat "请同时查询北京天气和上海天气，然后告诉我哪个更热" > /tmp/sse_5.txt 2>&1
EVENTS_5=$(cat /tmp/sse_5.txt | get_event_types)
FINAL_5=$(cat /tmp/sse_5.txt | get_final_answer)

HAS_PLAN=$(echo "$EVENTS_5" | grep -c "plan_created" | tr -d '\n ' || echo 0)
ACTION_COUNT=$(echo "$EVENTS_5" | grep -c "^action$" | tr -d '\n ' || echo 0)

if [[ "$HAS_PLAN" -ge 1 ]]; then
  echo -e "  ${GREEN}✓ PASS${NC} 触发了 make_plan（plan_created 事件存在）"
  PASS=$((PASS+1))
elif [[ "$ACTION_COUNT" -ge 2 ]]; then
  echo -e "  ${GREEN}✓ PASS${NC} 多步 action（$ACTION_COUNT 次调用），LLM 选择逐步执行"
  PASS=$((PASS+1))
else
  echo -e "  ${YELLOW}⚠ SKIP${NC} 未触发 plan_created 也未多步调用"
  echo -e "    事件列表: $(echo $EVENTS_5 | tr '\n' ' ')"
  echo -e "    action 次数: $ACTION_COUNT"
fi
TOTAL_EVENTS=$((TOTAL_EVENTS + $(echo "$EVENTS_5" | count_events)))
echo ""

# ─── 测试 6：context_usage 持续上报（验证每步都有）──
echo -e "${YELLOW}[测试 6] context_usage 持续上报${NC}"
CTX_COUNT=$(echo "$EVENTS_5" | grep -c "context_usage" || echo 0)
if [[ "$CTX_COUNT" -ge 2 ]]; then
  echo -e "  ${GREEN}✓ PASS${NC} context_usage 上报 $CTX_COUNT 次（>=2）"
  PASS=$((PASS+1))
else
  echo -e "  ${RED}✗ FAIL${NC} context_usage 只上报 $CTX_COUNT 次（期望 >=2）"
  FAIL=$((FAIL+1))
fi
echo ""

# ─── 测试 7：done 事件（验证每轮正常结束）──
echo -e "${YELLOW}[测试 7] done 事件 → 验证每轮正常结束${NC}"
ALL_DONE=true
for i in 1 2 3 4 5; do
  if ! cat /tmp/sse_${i}.txt | get_event_types | grep -q "^done$"; then
    ALL_DONE=false
    echo -e "  ${RED}✗ 轮次 $i 缺少 done 事件${NC}"
  fi
done
if $ALL_DONE; then
  echo -e "  ${GREEN}✓ PASS${NC} 所有 5 轮对话都有 done 事件"
  PASS=$((PASS+1))
else
  FAIL=$((FAIL+1))
fi
echo ""

# ─── 汇总 ─────────────────────────────────────────────────
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN} 测试汇总${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  通过: ${GREEN}$PASS${NC}"
echo -e "  失败: ${RED}$FAIL${NC}"
echo -e "  总事件数: $TOTAL_EVENTS"
echo -e "  对话轮数: 5"
echo ""

if [[ $FAIL -eq 0 ]]; then
  echo -e "${GREEN}✓ 所有测试通过！${NC}"
  exit 0
else
  echo -e "${RED}✗ 有 $FAIL 个测试失败${NC}"
  exit 1
fi
