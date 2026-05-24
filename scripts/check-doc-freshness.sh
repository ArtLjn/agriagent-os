#!/bin/bash
# scripts/check-doc-freshness.sh
# 检查 docs/ 下文档的新鲜度，标记过期文档

set -e

MAX_DAYS=${1:-60}
DOCS_DIR="docs"
ERRORS=0

if [ ! -d "$DOCS_DIR" ]; then
  echo "⏭️  无 docs/ 目录，跳过文档新鲜度检查"
  exit 0
fi

echo "🔍 检查文档新鲜度（阈值 ${MAX_DAYS} 天）..."

if git rev-parse --git-dir > /dev/null 2>&1; then
  find "$DOCS_DIR" -name "*.md" | while read f; do
    # 跳过未提交到 git 的新文件
    if ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      echo "ℹ️  $f: 新文件（未提交到 git），跳过新鲜度检查"
      continue
    fi
    last_mod=$(git log -1 --format=%ct "$f" 2>/dev/null || echo "0")
    now=$(date +%s)
    if [ "$last_mod" -eq 0 ]; then
      echo "⚠️  $f: 无法获取修改时间"
      continue
    fi
    days_old=$(( (now - last_mod) / 86400 ))
    if [ "$days_old" -gt "$MAX_DAYS" ]; then
      echo "❌ $f 已 ${days_old} 天未更新（超过 ${MAX_DAYS} 天阈值）"
      echo "✅ FIX: 审查内容是否仍准确，如已过时标记 status: deprecated"
      echo "📖 See: .claude/rules/docs-sync.md"
    fi
  done
fi

echo "🔍 检查文档状态标记..."
find "$DOCS_DIR" -name "*.md" | while read f; do
  # 跳过未提交到 git 的新文件
  if git rev-parse --git-dir > /dev/null 2>&1; then
    if ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      continue
    fi
  fi
  if ! head -5 "$f" | grep -q "^---"; then
    echo "⚠️  $f: 缺少 front-matter（需添加 last_updated/status 字段）"
    continue
  fi
  status=$(grep "^status:" "$f" 2>/dev/null | head -1 | sed 's/status: *//')
  if [ "$status" = "draft" ]; then
    last_mod=$(git log -1 --format=%ct "$f" 2>/dev/null || echo "0")
    now=$(date +%s)
    if [ "$last_mod" -gt 0 ]; then
      days_old=$(( (now - last_mod) / 86400 ))
      if [ "$days_old" -gt 30 ]; then
        echo "⚠️  $f: 状态为 draft 已 ${days_old} 天，请审批或删除"
      fi
    fi
  fi
done

echo "✅ 文档新鲜度检查完成"
