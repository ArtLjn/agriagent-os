#!/usr/bin/env bash
# farm-index 部署脚本 — 构建 dist，打包上传并同步到腾讯云静态目录。
#
# 用法:
#   bash deploy/farm-index-deploy.sh
#   bash deploy/farm-index-deploy.sh --no-build
#   bash deploy/farm-index-deploy.sh --api-url=https://api.farm.lllcnm.cn
#
# 环境变量(可选):
#   SERVER_HOST=43.155.217.74
#   SERVER_USER=root
#   REMOTE_DIR=/root/workspace/static/farm-index
#   API_URL=https://api.farm.lllcnm.cn

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FARM_INDEX_DIR="$PROJECT_ROOT/farm-index/app"

SERVER_HOST="${SERVER_HOST:-43.155.217.74}"
SERVER_USER="${SERVER_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/root/workspace/static/farm-index}"
API_URL="${API_URL:-https://api.farm.lllcnm.cn}"

SKIP_BUILD=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-build) SKIP_BUILD=1 ;;
    --api-url=*) API_URL="${1#--api-url=}" ;;
    -h|--help)
      sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) printf '未知参数: %s\n' "$1" >&2; exit 1 ;;
  esac
  shift
done

log() { printf '\n\033[1m>>> %s\033[0m\n' "$*"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
die() { printf '  \033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$FARM_INDEX_DIR" ] || die "找不到 farm-index 前端目录: $FARM_INDEX_DIR"

printf '\n=========================================\n'
printf ' farm-index 部署\n'
printf '=========================================\n'
printf ' 服务器:  %s@%s\n' "$SERVER_USER" "$SERVER_HOST"
printf ' 远程目录: %s\n' "$REMOTE_DIR"
printf ' API:     %s\n' "$API_URL"
[ "$SKIP_BUILD" = 1 ] && printf ' 跳过构建: 是\n'
printf '=========================================\n'

cd "$FARM_INDEX_DIR"

log "写入生产环境配置"
cat > "$FARM_INDEX_DIR/.env.production" <<EOF
VITE_API_BASE_URL=${API_URL}
EOF
ok "VITE_API_BASE_URL=${API_URL}"

if [ "$SKIP_BUILD" = 0 ]; then
  log "安装依赖检查"
  if [ ! -d "$FARM_INDEX_DIR/node_modules" ]; then
    if command -v npm >/dev/null 2>&1; then
      npm install
    else
      die "未找到 npm，且 node_modules 不存在"
    fi
  fi

  log "打包 farm-index"
  if command -v npm >/dev/null 2>&1; then
    npm run build
  else
    die "未找到 npm"
  fi
  ok "构建完成"
fi

[ -d "$FARM_INDEX_DIR/dist" ] || die "找不到 dist 目录，请先构建"

log "预检 SSH 连接 ${SERVER_USER}@${SERVER_HOST}"
ssh -o ConnectTimeout=5 -o BatchMode=yes "${SERVER_USER}@${SERVER_HOST}" "true" \
  || die "无法免密登录，请先配置: ssh-copy-id ${SERVER_USER}@${SERVER_HOST}"

log "打包 dist"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TARBALL="/tmp/farm-index-dist-${TIMESTAMP}.tar.gz"
REMOTE_TARBALL="/tmp/farm-index-dist-${TIMESTAMP}.tar.gz"

COPYFILE_DISABLE=1 tar czf "$TARBALL" \
  --exclude '.DS_Store' \
  --exclude '._*' \
  -C "$FARM_INDEX_DIR/dist" .
ok "本地包: $TARBALL"

log "上传 dist 包"
ssh "${SERVER_USER}@${SERVER_HOST}" "rm -f '${REMOTE_TARBALL}'"
scp -q "$TARBALL" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_TARBALL}"
rm -f "$TARBALL"
ok "已上传: ${REMOTE_TARBALL}"

log "远程解压同步"
ssh "${SERVER_USER}@${SERVER_HOST}" "
  set -e
  mkdir -p '${REMOTE_DIR}'
  if [ -n \"\$(find '${REMOTE_DIR}' -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)\" ]; then
    BACKUP='/tmp/farm-index-backup-${TIMESTAMP}'
    cp -a '${REMOTE_DIR}' \"\${BACKUP}\"
    echo \"  备份: \${BACKUP}\"
  fi
  find '${REMOTE_DIR}' -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  tar xzf '${REMOTE_TARBALL}' -C '${REMOTE_DIR}'
  rm -f '${REMOTE_TARBALL}'
"
ok "dist 解压同步完成"

FILE_COUNT="$(ssh "${SERVER_USER}@${SERVER_HOST}" "find '${REMOTE_DIR}' -type f | wc -l | tr -d ' '")"

printf '\n=========================================\n'
printf ' \033[32m部署完成!\033[0m\n'
printf '=========================================\n'
printf ' 路径:   %s@%s:%s\n' "$SERVER_USER" "$SERVER_HOST" "$REMOTE_DIR"
printf ' API:    %s\n' "$API_URL"
printf ' 文件数: %s\n' "$FILE_COUNT"
printf ' 回滚:   ssh %s@%s \"cp -a /tmp/farm-index-backup-%s/* %s/\"\n' \
  "$SERVER_USER" "$SERVER_HOST" "$TIMESTAMP" "$REMOTE_DIR"
