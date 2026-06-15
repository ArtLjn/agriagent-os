#!/usr/bin/env bash
# admin-web 部署脚本 — 打包并上传到腾讯云服务器
#
# 用法:
#   deploy/admin-web-deploy.sh                # 默认打包 + 上传
#   deploy/admin-web-deploy.sh --no-build     # 跳过打包,直接上传现有 dist
#   deploy/admin-web-deploy.sh --api-url=https://api.farm.lllcnm.cn
#
# 环境变量(可选):
#   SERVER_HOST=43.155.217.74                 SSH 主机
#   SERVER_USER=root                          SSH 用户
#   REMOTE_DIR=/root/workspace/static/farm-admin-web  远程静态目录

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ADMIN_WEB_DIR="$PROJECT_ROOT/admin-web"

# === 服务器配置(环境变量覆盖) ===
SERVER_HOST="${SERVER_HOST:-43.155.217.74}"
SERVER_USER="${SERVER_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/root/workspace/static/farm-admin-web}"
API_URL="${API_URL:-https://api.farm.lllcnm.cn}"

# === 参数 ===
SKIP_BUILD=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-build)         SKIP_BUILD=1 ;;
    --api-url=*)        API_URL="${1#--api-url=}" ;;
    -h|--help)
      sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
  shift
done

log()  { printf '\n\033[1m>>> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

printf '\n=========================================\n'
printf ' admin-web 部署\n'
printf '=========================================\n'
printf ' 服务器:  %s@%s\n' "$SERVER_USER" "$SERVER_HOST"
printf ' 远程目录: %s\n' "$REMOTE_DIR"
printf ' API:     %s\n' "$API_URL"
[ "$SKIP_BUILD" = 1 ] && printf ' ⚠ 跳过构建\n'
printf '=========================================\n'

cd "$ADMIN_WEB_DIR"

# === Step 1: 写 .env.production ===
log "写入 .env.production"
cat > "$ADMIN_WEB_DIR/.env.production" << EOF
VITE_API_BASE_URL=${API_URL}
EOF
ok "API_URL = ${API_URL}"

# === Step 2: 打包 ===
if [ "$SKIP_BUILD" = 0 ]; then
  log "打包 admin-web"
  if command -v pnpm >/dev/null 2>&1; then
    pnpm build
  elif command -v npm >/dev/null 2>&1; then
    npm run build
  else
    die "未找到 pnpm 或 npm"
  fi
  ok "构建完成"
fi

[ -d "$ADMIN_WEB_DIR/dist" ] || die "找不到 dist 目录,请先构建"

# === Step 3: 预检 SSH ===
log "预检 SSH 连接 ${SERVER_USER}@${SERVER_HOST}..."
ssh -o ConnectTimeout=5 -o BatchMode=yes "${SERVER_USER}@${SERVER_HOST}" "true" \
  || die "无法免密登录,请先配置: ssh-copy-id ${SERVER_USER}@${SERVER_HOST}"

# === Step 4: 远程备份 + 清理 + 上传 ===
log "上传到服务器..."
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# 确保远程目录存在,并备份旧版本
ssh "${SERVER_USER}@${SERVER_HOST}" "
  set -e
  mkdir -p '${REMOTE_DIR}'
  if [ -d '${REMOTE_DIR}' ] && [ -n \"\$(ls -A '${REMOTE_DIR}' 2>/dev/null)\" ]; then
    BACKUP='/tmp/farm-admin-web-backup-${TIMESTAMP}'
    cp -a '${REMOTE_DIR}' \"\${BACKUP}\"
    echo \"  备份: \${BACKUP}\"
    rm -rf '${REMOTE_DIR}'/*
  fi
"

# 使用 rsync(优先)或 scp 上传
if command -v rsync >/dev/null 2>&1; then
  COPYFILE_DISABLE=1 rsync -az --delete \
    --exclude '.DS_Store' \
    --exclude '._*' \
    "$ADMIN_WEB_DIR/dist/" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR}/"
  ok "rsync 上传完成"
else
  # scp 兜底:打包后上传再解压
  TARBALL="/tmp/farm-admin-web-dist.tar.gz"
  COPYFILE_DISABLE=1 tar czf "$TARBALL" \
    --exclude '.DS_Store' \
    --exclude '._*' \
    -C "$ADMIN_WEB_DIR/dist" .
  scp -q "$TARBALL" "${SERVER_USER}@${SERVER_HOST}:/tmp/farm-admin-web-dist.tar.gz"
  ssh "${SERVER_USER}@${SERVER_HOST}" "tar xzf /tmp/farm-admin-web-dist.tar.gz -C '${REMOTE_DIR}' && rm -f /tmp/farm-admin-web-dist.tar.gz"
  rm -f "$TARBALL"
  ok "scp 上传完成"
fi

# === 完成 ===
printf '\n=========================================\n'
printf ' \033[32m部署完成!\033[0m\n'
printf '=========================================\n'
printf ' 路径:   %s@%s:%s\n' "$SERVER_USER" "$SERVER_HOST" "$REMOTE_DIR"
printf ' API:    %s\n' "$API_URL"
printf ' 文件数: %s\n' "$(ssh "${SERVER_USER}@${SERVER_HOST}" "find '${REMOTE_DIR}' -type f | wc -l | tr -d ' '")"
printf ' 回滚:   ssh %s@%s \"cp -a /tmp/farm-admin-web-backup-%s/* %s/\"\n' \
  "$SERVER_USER" "$SERVER_HOST" "$TIMESTAMP" "$REMOTE_DIR"
