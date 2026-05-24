#!/bin/bash
# scripts/check-lint-expiry.sh
# 追踪 lint 规则和检查脚本的过期状态，发现长期未更新的规则

set -e

# ── 参数解析 ──
THRESHOLD_DAYS=90
CREATE_ISSUE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --threshold)
      THRESHOLD_DAYS="$2"
      shift 2
      ;;
    --create-issue)
      CREATE_ISSUE=true
      shift
      ;;
    --help|-h)
      echo "用法: bash scripts/check-lint-expiry.sh [选项]"
      echo ""
      echo "选项:"
      echo "  --threshold N    过期阈值天数（默认 90）"
      echo "  --create-issue   为过期规则创建 GitHub issue"
      echo "  --help           显示帮助信息"
      exit 0
      ;;
    *)
      echo "❌ 未知参数: $1"
      echo "✅ FIX: 使用 --help 查看可用选项"
      echo "📖 See: .claude/CLAUDE.md"
      exit 1
      ;;
  esac
done

EXPIRED_COUNT=0
ACTIVE_COUNT=0

echo "╔══════════════════════════════════════╗"
echo "║   Lint 规则过期追踪                  ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "🔍 检查阈值: ${THRESHOLD_DAYS} 天"
echo ""

# 获取当前时间戳
NOW=$(date +%s)

# ── 检查 scripts/ 下的 .sh 脚本 ──
if [ -d "scripts" ]; then
  echo "🔍 检查 scripts/ 目录下的脚本..."
  find scripts/ -name "*.sh" -type f | while read script; do
    if git rev-parse --git-dir > /dev/null 2>&1; then
      # 跳过未提交到 git 的新文件
      if ! git ls-files --error-unmatch "$script" >/dev/null 2>&1; then
        echo "ℹ️  $script: 新文件（未提交到 git），跳过过期检查"
        continue
      fi
      # 优先用 git log 获取最后修改时间
      LAST_MOD_TS=$(git log -1 --format=%ct "$script" 2>/dev/null || echo "0")
    else
      # 无 git 仓库时用文件修改时间
      LAST_MOD_TS=$(stat -f %m "$script" 2>/dev/null || stat -c %Y "$script" 2>/dev/null || echo "0")
    fi

    if [ "$LAST_MOD_TS" -eq 0 ]; then
      echo "⚠️  $script: 无法获取修改时间"
      continue
    fi

    DAYS_SINCE=$(( (NOW - LAST_MOD_TS) / 86400 ))

    if [ "$DAYS_SINCE" -gt "$THRESHOLD_DAYS" ]; then
      echo "⚠️  $script 已 ${DAYS_SINCE} 天未更新，请审查是否仍有必要"
      echo "     最后修改: $(date -r "$script" '+%Y-%m-%d' 2>/dev/null || echo '未知')"
      EXPIRED_COUNT=$((EXPIRED_COUNT + 1))

      if [ "$CREATE_ISSUE" = true ]; then
        ISSUE_TITLE="[Harness] 过期检查脚本审查: $script"
        ISSUE_BODY="## 过期检查脚本

脚本 \`$script\` 已 ${DAYS_SINCE} 天未更新。

### 需要确认
- [ ] 此脚本对应的规则是否仍然有效
- [ ] 检查逻辑是否覆盖了最新的代码模式
- [ ] 是否需要更新或废弃

---
*此 issue 由 \`check-lint-expiry.sh --create-issue\` 自动生成*"

        if command -v gh &>/dev/null; then
          gh issue create             --title "$ISSUE_TITLE"             --body "$ISSUE_BODY"             --label "harness,rules-review" 2>/dev/null &&             echo "  📋 已创建 issue: $ISSUE_TITLE" ||             echo "  ⚠️  创建 issue 失败，请手动创建"
        else
          echo "  ⚠️  gh CLI 未安装，无法创建 issue"
          echo "  ✅ FIX: 安装 GitHub CLI (brew install gh) 后重新运行"
          echo "  📖 See: https://cli.github.com/"
        fi
      fi
    else
      ACTIVE_COUNT=$((ACTIVE_COUNT + 1))
    fi
  done
else
  echo "⏭️  无 scripts/ 目录，跳过脚本检查"
fi

echo ""

# ── 检查 .claude/hooks/ 下的 JSON 文件 ──
if [ -d ".claude/hooks" ]; then
  echo "🔍 检查 .claude/hooks/ 目录下的规则..."
  find .claude/hooks/ -name "*.json" -type f | while read hook; do
    if git rev-parse --git-dir > /dev/null 2>&1; then
      # 跳过未提交到 git 的新文件
      if ! git ls-files --error-unmatch "$hook" >/dev/null 2>&1; then
        echo "ℹ️  $hook: 新文件（未提交到 git），跳过过期检查"
        continue
      fi
      LAST_MOD_TS=$(git log -1 --format=%ct "$hook" 2>/dev/null || echo "0")
    else
      LAST_MOD_TS=$(stat -f %m "$hook" 2>/dev/null || stat -c %Y "$hook" 2>/dev/null || echo "0")
    fi

    if [ "$LAST_MOD_TS" -eq 0 ]; then
      echo "⚠️  $hook: 无法获取修改时间"
      continue
    fi

    DAYS_SINCE=$(( (NOW - LAST_MOD_TS) / 86400 ))

    if [ "$DAYS_SINCE" -gt "$THRESHOLD_DAYS" ]; then
      echo "⚠️  $hook 已 ${DAYS_SINCE} 天未更新，请审查 hook 规则是否仍有效"
      echo "     最后修改: $(date -r "$hook" '+%Y-%m-%d' 2>/dev/null || echo '未知')"

      # 统计 hook 中规则数量
      RULE_COUNT=$(python3 -c "
import json
with open('$hook') as f:
    data = json.load(f)
count = 0
for h in data.get('hooks', []):
    count += len(h.get('rules', []))
print(count)
" 2>/dev/null || echo "0")
      echo "     包含 $RULE_COUNT 条规则"

      EXPIRED_COUNT=$((EXPIRED_COUNT + 1))
    else
      ACTIVE_COUNT=$((ACTIVE_COUNT + 1))
    fi
  done
else
  echo "⏭️  无 .claude/hooks/ 目录，跳过 hook 检查"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   过期追踪结果汇总                    ║"
echo "╠══════════════════════════════════════╣"
echo "║   ✅ 活跃: $ACTIVE_COUNT"
echo "║   ⚠️  过期: $EXPIRED_COUNT"
echo "╚══════════════════════════════════════╝"

if [ "$EXPIRED_COUNT" -gt 0 ]; then
  echo ""
  echo "💡 建议："
  echo "  过期的检查脚本和 hook 规则需要人工审查。"
  echo "  确认对应规则是否仍有价值，是否需要更新或移除。"
  echo "  使用 --create-issue 可自动创建审查 issue。"
  # 不以非零退出码退出，因为过期不等于错误
fi

echo ""
echo "✅ Lint 规则过期追踪完成"
