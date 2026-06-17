#!/usr/bin/env bash
# 清理服务器 /tmp 下的部署备份残留
#
# 备份来源:
#   farm-backup-*           ← deploy/server-sync.sh
#   farm-admin-web-backup-* ← deploy/admin-web-deploy.sh
#   farm-index-backup-*     ← deploy/farm-index-deploy.sh
#
# 用法:
#   bash deploy/clean-tmp-backups.sh                    # 预览（dry-run）
#   bash deploy/clean-tmp-backups.sh -y                 # 真正删除全部
#   bash deploy/clean-tmp-backups.sh -y --keep 2        # 每类保留最近 2 个
#   bash deploy/clean-tmp-backups.sh -y --older-than 3  # 只删 3 天前的
#   bash deploy/clean-tmp-backups.sh -p 'farm-backup-*' # 自定义 pattern
set -euo pipefail

SERVER="root@43.155.217.74"
KEEP=0
OLDER_THAN_DAYS=0
APPLY="false"
DEFAULT_PATTERNS=(
    'farm-backup-*'
    'farm-admin-web-backup-*'
    'farm-index-backup-*'
)
PATTERNS=()

usage() {
    cat <<'EOF'
用法: bash deploy/clean-tmp-backups.sh [选项]

选项:
  -y, --apply              真正执行删除（默认仅预览）
  -k, --keep N             每类 pattern 保留最近 N 个备份（默认 0）
  -o, --older-than DAYS    只清理修改时间超过 N 天的（默认 0=不限）
  -p, --patterns 'A B C'   自定义匹配 pattern（空格分隔，默认三类 farm 备份）
  -s, --server USER@HOST   指定服务器（默认 root@43.155.217.74）
  -h, --help               显示帮助

示例:
  预览:                bash deploy/clean-tmp-backups.sh
  保留最近 1 个并真删:  bash deploy/clean-tmp-backups.sh -y --keep 1
  只清 7 天前的:        bash deploy/clean-tmp-backups.sh -y --older-than 7
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--apply) APPLY="true"; shift ;;
        -k|--keep) KEEP="${2:?--keep 需要参数}"; shift 2 ;;
        -o|--older-than) OLDER_THAN_DAYS="${2:?--older-than 需要参数}"; shift 2 ;;
        -p|--patterns) read -r -a PATTERNS <<< "${2:?--patterns 需要参数}"; shift 2 ;;
        -s|--server) SERVER="${2:?--server 需要参数}"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "未知参数: $1" >&2; usage ;;
    esac
done

[[ ${#PATTERNS[@]} -eq 0 ]] && PATTERNS=( "${DEFAULT_PATTERNS[@]}" )

# 远程脚本通过位置参数接收: KEEP OLDER_THAN_DAYS APPLY pattern1 pattern2 ...
ssh -o ConnectTimeout=5 "${SERVER}" "bash -s" -- \
    "$KEEP" "$OLDER_THAN_DAYS" "$APPLY" "${PATTERNS[@]}" <<'REMOTE'
set -euo pipefail

KEEP="$1"
OLDER_THAN_DAYS="$2"
APPLY="$3"
shift 3
PATTERNS=( "$@" )

TMP_DIR="/tmp"
OLDER_THAN_MIN=$((OLDER_THAN_DAYS * 24 * 60))
total_count=0
total_size_bytes=0

human_size() {
    local bytes=${1:-0}
    if   (( bytes >= 1073741824 )); then awk -v b="$bytes" 'BEGIN{printf "%.2f GB", b/1073741824}'
    elif (( bytes >= 1048576     )); then awk -v b="$bytes" 'BEGIN{printf "%.2f MB", b/1048576}'
    elif (( bytes >= 1024        )); then awk -v b="$bytes" 'BEGIN{printf "%.2f KB", b/1024}'
    else                                  echo "${bytes} B"
    fi
}

mode_label="👁️  预览（dry-run）"
[[ "$APPLY" == "true" ]] && mode_label="🗑️  实际删除"

echo "============================================================"
echo " 服务器: $(hostname)    目标: ${TMP_DIR}"
echo " 模式:   ${mode_label}"
echo " 保留:   每类最近 ${KEEP} 个    超过: ${OLDER_THAN_DAYS} 天"
echo " Patterns: ${PATTERNS[*]}"
echo "============================================================"
echo

for pattern in "${PATTERNS[@]}"; do
    # 收集匹配项（按 mtime 倒序，最新在前）
    mapfile -t matches < <(
        find "${TMP_DIR}" -maxdepth 1 -name "${pattern}" \
            \( -type d -o -type f \) -print0 2>/dev/null \
        | xargs -0 -I{} stat -c '%Y %n' {} 2>/dev/null \
        | sort -rn \
        | cut -d' ' -f2-
    )

    if [[ ${#matches[@]} -eq 0 ]]; then
        echo "  [${pattern}] 无匹配"
        continue
    fi

    echo "  [${pattern}] 共 ${#matches[@]} 个:"

    idx=0
    for item in "${matches[@]}"; do
        idx=$((idx + 1))
        [[ -z "$item" ]] && continue

        # 保留最近 N 个
        if (( KEEP > 0 && idx <= KEEP )); then
            size=$(du -sb "$item" 2>/dev/null | awk '{print $1}')
            printf "    ✅ 保留  [%s] %s\n" "$(human_size "${size:-0}")" "$item"
            continue
        fi

        # 按天数过滤
        if (( OLDER_THAN_MIN > 0 )); then
            age_match=$(find "$item" -maxdepth 0 -mmin +"${OLDER_THAN_MIN}" 2>/dev/null | wc -l)
            [[ "$age_match" -eq 0 ]] && continue
        fi

        size=$(du -sb "$item" 2>/dev/null | awk '{print $1}' || echo 0)
        total_count=$((total_count + 1))
        total_size_bytes=$((total_size_bytes + ${size:-0}))

        if [[ "$APPLY" == "true" ]]; then
            if rm -rf "$item"; then
                printf "    🗑️  已删  [%s] %s\n" "$(human_size "${size:-0}")" "$item"
            else
                printf "    ❌ 失败  %s\n" "$item"
            fi
        else
            printf "    🔍 将删  [%s] %s\n" "$(human_size "${size:-0}")" "$item"
        fi
    done
    echo
done

echo "------------------------------------------------------------"
printf " 合计: %d 项,  %s\n" "$total_count" "$(human_size "$total_size_bytes")"
if [[ "$APPLY" != "true" && $total_count -gt 0 ]]; then
    echo
    echo "💡 这是预览。确认后加 -y 真正执行:"
    echo "    bash deploy/clean-tmp-backups.sh -y"
fi
echo
REMOTE
