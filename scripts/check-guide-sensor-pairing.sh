#!/bin/bash
# scripts/check-guide-sensor-pairing.sh
# 验证 CLAUDE.md 中每条硬性规则是否在 scripts/ 中有对应的检查脚本（Guide+Sensor 配对）

set -e

CLAUDE_MD=".claude/CLAUDE.md"
SCRIPTS_DIR="scripts"
PAIRED=0
UNPAIRED=0

echo "╔══════════════════════════════════════╗"
echo "║   Guide+Sensor 配对检查              ║"
echo "╚══════════════════════════════════════╝"
echo ""

if [ ! -f "$CLAUDE_MD" ]; then
  echo "❌ 找不到 $CLAUDE_MD，无法检查配对"
  echo "✅ FIX: 先运行 init_harness.py 初始化项目"
  echo "📖 See: .claude/CLAUDE.md"
  exit 1
fi

if [ ! -d "$SCRIPTS_DIR" ]; then
  echo "❌ 找不到 $SCRIPTS_DIR/ 目录"
  echo "✅ FIX: 先运行 init_harness.py 初始化项目"
  echo "📖 See: .claude/CLAUDE.md"
  exit 1
fi

echo "🔍 从 $CLAUDE_MD 解析硬性规则..."
echo ""

# 使用函数映射规则关键词到脚本文件（兼容 bash 3.2，不使用 declare -A）
get_paired_script() {
  case "$1" in
    *依赖方向*)        echo "check-layer-deps.sh" ;;
    *横切关注点*)      echo "check-layer-deps.sh" ;;
    *单文件*|*单方法*) echo "check-layer-deps.sh" ;;
    *新增代码*|*测试*) echo "check-layer-deps.sh" ;;
    *结构化日志*)      echo "check-lint-expiry.sh" ;;
    *console.log*)     echo "check-lint-expiry.sh" ;;
    *print*)           echo "check-lint-expiry.sh" ;;
    *错误信息*)        echo "check-lint-expiry.sh" ;;
    *code*字段*)       echo "check-lint-expiry.sh" ;;
    *复杂度*|*冗余*|*抽象*|*生成物*|*工作区污染*|*大文件*) echo "check-complexity-budget.sh" ;;
    *)                 echo "" ;;
  esac
}

# 从 CLAUDE.md 提取硬性规则段
IN_RULES_SECTION=false
RULE_NUM=0

while IFS= read -r line; do
  # 检测是否进入硬性规则段
  if echo "$line" | grep -q "硬性规则"; then
    IN_RULES_SECTION=true
    continue
  fi

  # 检测是否离开硬性规则段（遇到新的 ## 标题）
  if $IN_RULES_SECTION && echo "$line" | grep -q "^## "; then
    break
  fi

  # 提取编号规则
  if $IN_RULES_SECTION && echo "$line" | grep -qE "^[0-9]+\."; then
    RULE_NUM=$((RULE_NUM + 1))
    RULE_TEXT=$(echo "$line" | sed 's/^[0-9]*\.\s*//')

    # 通过函数匹配对应的脚本
    FOUND_SCRIPT=$(get_paired_script "$RULE_TEXT")

    if [ -n "$FOUND_SCRIPT" ] && [ -f "$SCRIPTS_DIR/$FOUND_SCRIPT" ]; then
      echo "✅ 已配对: $(echo "$RULE_TEXT" | cut -c1-40)... → $FOUND_SCRIPT"
      PAIRED=$((PAIRED + 1))
    elif [ -n "$FOUND_SCRIPT" ]; then
      echo "❌ 已映射但脚本不存在: $(echo "$RULE_TEXT" | cut -c1-40)... → $FOUND_SCRIPT"
      UNPAIRED=$((UNPAIRED + 1))
    else
      echo "❌ 未配对: $(echo "$RULE_TEXT" | cut -c1-60)... 规则没有对应检查脚本"
      UNPAIRED=$((UNPAIRED + 1))
    fi
  fi
done < "$CLAUDE_MD"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   配对结果汇总                        ║"
echo "╠══════════════════════════════════════╣"
echo "║   ✅ 已配对: $PAIRED"
echo "║   ❌ 未配对: $UNPAIRED"
echo "╚══════════════════════════════════════╝"

if [ "$UNPAIRED" -gt 0 ]; then
  echo ""
  echo "💡 建议："
  echo "  未配对的规则需要在 scripts/ 中添加对应的检查脚本。"
  echo "  每条硬性规则都应有自动化的验证手段（Guide+Sensor 闭环）。"
  echo "  参考 docs/architecture/boundaries.md 了解已有的约束检查。"
  exit 1
fi

echo ""
echo "✅ 所有硬性规则均有对应检查脚本，Guide+Sensor 配对完整"
