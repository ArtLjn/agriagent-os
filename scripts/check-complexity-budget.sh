#!/usr/bin/env bash
# scripts/check-complexity-budget.sh
# Vibe Coding 复杂度预算检查：先发现可删噪音、历史债务和过度抽象风险。

set -euo pipefail

STRICT="${HARNESS_COMPLEXITY_STRICT:-0}"
ERRORS=0
WARNINGS=0

warn() {
  echo "WARN: $1"
  WARNINGS=$((WARNINGS + 1))
}

fail() {
  echo "ERROR: $1"
  ERRORS=$((ERRORS + 1))
}

maybe_fail() {
  if [ "$STRICT" = "1" ]; then
    fail "$1"
  else
    warn "$1"
  fi
}

echo "复杂度预算检查"
echo ""

if ! command -v rg >/dev/null 2>&1; then
  fail "缺少 rg，无法执行复杂度预算检查。请安装 ripgrep。"
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  fail "当前目录不是 Git 仓库，无法区分源码与生成物。"
fi

echo "检查工作区污染文件..."
POLLUTION_MATCHES=$(find . \
  \( -path "./.git" \
    -o -path "./.worktrees" \
    -o -path "./admin-web/node_modules" \
    -o -path "./farm-index/app/node_modules" \
    -o -path "./archive/FarmManagerMobile/node_modules" \
    -o -path "./backend/.venv" \
    -o -path "./mobile-app/.dart_tool" \
    -o -path "./mobile-app/android/.gradle" \) -prune \
  -o \( -type d -name "__pycache__" \
    -o -type f -name "*.pyc" \
    -o -type f -name ".DS_Store" \
    -o -type d -name "*.egg-info" \) -print 2>/dev/null || true)

if [ -n "$POLLUTION_MATCHES" ]; then
  echo "$POLLUTION_MATCHES" | sed -n '1,80p'
  fail "发现 Python/系统生成物。请清理 __pycache__、*.pyc、.DS_Store、*.egg-info。"
else
  echo "OK: 未发现工作区污染文件。"
fi

echo ""
echo "检查被 Git 跟踪的生成物/归档噪音..."
TRACKED_NOISE=$(git ls-files | rg '^(archive/|output/)' || true)
if [ -n "$TRACKED_NOISE" ]; then
  noise_count=$(printf "%s\n" "$TRACKED_NOISE" | sed '/^$/d' | wc -l | tr -d ' ')
  maybe_fail "archive/ 或 output/ 中有 ${noise_count} 个文件被 Git 跟踪；应迁到归档仓库、对象存储或仅保留少量 golden/reference。"
fi

NESTED_REPOS=$(git ls-files -s | awk '$1 == "160000" {print $4}' || true)
if [ -n "$NESTED_REPOS" ]; then
  echo "$NESTED_REPOS" | sed -n '1,40p'
  maybe_fail "发现 Git 子模块/嵌套仓库入口。若不是有意维护，应迁出或补充子模块说明。"
fi

echo ""
echo "检查包管理器锁文件混用..."
for dir in admin-web farm-index/app; do
  if [ -f "$dir/package-lock.json" ] && [ -f "$dir/pnpm-lock.yaml" ]; then
    maybe_fail "$dir 同时存在 package-lock.json 和 pnpm-lock.yaml；项目脚本使用 pnpm 时应移除 npm lock。"
  fi
done

echo ""
echo "检查源码文件大小预算..."
python3 - <<'PY' > /tmp/harness_complexity_files.txt
from pathlib import Path
import subprocess

limits = [
    ("backend/app", (".py",), 1000, 500, True),
    ("backend/tests", (".py",), 500, None, False),
    ("admin-web/src", (".ts", ".tsx"), 300, None, False),
    ("farm-index/app/src", (".ts", ".tsx"), 300, None, False),
    ("mobile-app/lib", (".dart",), 500, None, False),
    ("mobile-app/test", (".dart",), 500, None, False),
]

tracked = set(subprocess.check_output(["git", "ls-files"], text=True).splitlines())
for item in limits:
    root, suffixes, limit, observe_from, hard_fail = item
    for path in sorted(Path(root).rglob("*")):
        rel = path.as_posix()
        if rel not in tracked or not path.is_file() or not rel.endswith(suffixes):
            continue
        lines = sum(1 for _ in path.open("rb"))
        if lines > limit:
            status = "ERROR" if hard_fail else "WARN"
            print(f"{status}\t{lines}\t{limit}\t{rel}")
        elif observe_from is not None and lines > observe_from:
            print(f"WARN\t{lines}\t{observe_from}-{limit}\t{rel}")
PY

if [ -s /tmp/harness_complexity_files.txt ]; then
  sed -n '1,80p' /tmp/harness_complexity_files.txt
  if rg -q '^ERROR' /tmp/harness_complexity_files.txt; then
    fail "存在源码文件超过硬性复杂度预算；生产 Python 文件超过 1000 行必须收束。"
  fi
  if rg -q '^WARN' /tmp/harness_complexity_files.txt; then
    warn "存在生产 Python 文件超过 500 行；500-1000 行仅作观察，按职责混杂度判断是否收束。"
  fi
else
  echo "OK: 源码文件大小在预算内。"
fi
rm -f /tmp/harness_complexity_files.txt

echo ""
echo "检查 Python 方法长度预算..."
python3 - <<'PY' > /tmp/harness_complexity_functions.txt
from pathlib import Path
import ast
import subprocess

tracked = subprocess.check_output(["git", "ls-files", "backend/app"], text=True).splitlines()
for rel in tracked:
    if not rel.endswith(".py"):
        continue
    path = Path(rel)
    if not path.is_file():
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and getattr(node, "end_lineno", None):
            lines = node.end_lineno - node.lineno + 1
            if lines > 50:
                print(f"{lines}\t50\t{rel}:{node.lineno}\t{node.name}")
PY

if [ -s /tmp/harness_complexity_functions.txt ]; then
  sed -n '1,80p' /tmp/harness_complexity_functions.txt
  maybe_fail "存在 Python 方法超过 50 行；应拆成明确步骤并用测试锁住行为。"
else
  echo "OK: Python 方法长度在预算内。"
fi
rm -f /tmp/harness_complexity_functions.txt

echo ""
echo "检查过度抽象关键词密度..."
ABSTRACT_MATCHES=$(rg -n \
  '\b(Protocol|ABC|abstractmethod|Factory|Strategy|Adapter|Provider|Manager|Registry|Plugin|Hook|Extension|Facade)\b' \
  backend/app admin-web/src farm-index/app/src mobile-app/lib \
  --glob '*.py' --glob '*.ts' --glob '*.tsx' --glob '*.dart' \
  --glob '!**/__pycache__/**' 2>/dev/null || true)
ABSTRACT_COUNT=$(printf "%s" "$ABSTRACT_MATCHES" | sed '/^$/d' | wc -l | tr -d ' ')
if [ "$ABSTRACT_COUNT" -gt 120 ]; then
  printf "%s\n" "$ABSTRACT_MATCHES" | sed -n '1,80p'
  maybe_fail "抽象关键词命中 ${ABSTRACT_COUNT} 处；新增抽象必须证明存在第二个实现或明确变化需求。"
else
  echo "OK: 抽象关键词数量未超过预算。"
fi

echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "复杂度预算检查失败：${ERRORS} 个错误，${WARNINGS} 个警告。"
  exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
  echo "复杂度预算检查通过但有 ${WARNINGS} 个警告。设置 HARNESS_COMPLEXITY_STRICT=1 可升级为硬门禁。"
  exit 0
fi

echo "复杂度预算检查通过。"
