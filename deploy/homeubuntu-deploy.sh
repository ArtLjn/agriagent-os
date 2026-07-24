#!/usr/bin/env bash
# HomeUbuntu 一键部署：Docker Compose 部署 mysql/mongo/backend/admin-web，并接入宿主机 nginx。
#
# 用法：
#   SSH_PASSWORD=****** bash deploy/homeubuntu-deploy.sh
#   SSH_PASSWORD=****** bash deploy/homeubuntu-deploy.sh --nginx-port=8099
#
# 环境变量可覆盖：
#   SERVER_HOST=172.16.58.68
#   SERVER_USER=ljn
#   REMOTE_ROOT=/root/workspace/farm-manager
#   NGINX_PORT=8099
#   ADMIN_WEB_PORT=18080
#   BACKEND_PORT=18000

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVER_HOST="${SERVER_HOST:-172.16.58.68}"
SERVER_USER="${SERVER_USER:-ljn}"
SERVER="${SERVER_USER}@${SERVER_HOST}"
REMOTE_ROOT="${REMOTE_ROOT:-/root/workspace/farm-manager}"
NGINX_PORT="${NGINX_PORT:-8099}"
ADMIN_WEB_PORT="${ADMIN_WEB_PORT:-18080}"
BACKEND_PORT="${BACKEND_PORT:-18000}"
API_URL="${API_URL:-/api}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --server=*) SERVER="${1#--server=}"; SERVER_USER="${SERVER%@*}"; SERVER_HOST="${SERVER#*@}" ;;
    --remote-root=*) REMOTE_ROOT="${1#--remote-root=}" ;;
    --nginx-port=*) NGINX_PORT="${1#--nginx-port=}" ;;
    --admin-web-port=*) ADMIN_WEB_PORT="${1#--admin-web-port=}" ;;
    --backend-port=*) BACKEND_PORT="${1#--backend-port=}" ;;
    -h|--help)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
  shift
done

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TARBALL="/tmp/farm-manager-compose-${TIMESTAMP}.tar.gz"
REMOTE_TARBALL="/tmp/farm-manager-compose-${TIMESTAMP}.tar.gz"

log() { printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
ok() { printf '  ✓ %s\n' "$*"; }
die() { printf '  ✗ %s\n' "$*" >&2; exit 1; }

cleanup() {
  rm -f "${TARBALL}"
}
trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "本机缺少命令: $1"
}

ssh_base() {
  if [ -n "${SSH_PASSWORD:-}" ]; then
    SSHPASS="${SSH_PASSWORD}" sshpass -e ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$@"
  else
    ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$@"
  fi
}

scp_base() {
  if [ -n "${SSH_PASSWORD:-}" ]; then
    SSHPASS="${SSH_PASSWORD}" sshpass -e scp -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$@"
  else
    scp -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$@"
  fi
}

preflight() {
  require_cmd ssh
  require_cmd scp
  require_cmd tar
  require_cmd pnpm
  if [ -n "${SSH_PASSWORD:-}" ]; then
    require_cmd sshpass
  fi

  log "预检 SSH: ${SERVER}"
  ssh_base "${SERVER}" "hostname && whoami >/dev/null"
  ok "SSH 可用"
}

build_admin_web() {
  log "本机构建 admin-web，API_URL=${API_URL}"
  (cd "${PROJECT_ROOT}/admin-web" && VITE_API_BASE_URL="${API_URL}" pnpm build)
  ok "admin-web/dist 已生成"
}

package_project() {
  log "打包 Docker Compose 部署文件"
  COPYFILE_DISABLE=1 tar --no-xattrs -czf "${TARBALL}" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.DS_Store' \
    --exclude='._*' \
    --exclude='.git' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='node_modules' \
    --exclude='admin-web/.env.production' \
    --exclude='backend/.venv' \
    --exclude='backend/data' \
    --exclude='backend/providers.json' \
    --exclude='backend/var' \
    -C "${PROJECT_ROOT}" \
    .dockerignore \
    docker-compose.yaml \
    backend \
    admin-web \
    shared
  ok "已生成 ${TARBALL}"
}

upload_project() {
  log "上传部署包"
  ssh_base "${SERVER}" "rm -f '${REMOTE_TARBALL}'"
  scp_base "${TARBALL}" "${SERVER}:${REMOTE_TARBALL}"
  ok "上传完成"
}

remote_deploy() {
  log "远程部署"
  ssh_base "${SERVER}" \
    "sudo REMOTE_ROOT='${REMOTE_ROOT}' REMOTE_TARBALL='${REMOTE_TARBALL}' TIMESTAMP='${TIMESTAMP}' NGINX_PORT='${NGINX_PORT}' ADMIN_WEB_PORT='${ADMIN_WEB_PORT}' BACKEND_PORT='${BACKEND_PORT}' API_URL='${API_URL}' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

if [ -n "${SSH_PASSWORD:-}" ]; then
  SUDO="sudo -S"
else
  SUDO="sudo"
fi

rlog() { printf '  [%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
rdie() { printf '  ✗ %s\n' "$*" >&2; exit 1; }

run_sudo() {
  if [ -n "${SSH_PASSWORD:-}" ]; then
    printf '%s\n' "${SSH_PASSWORD}" | sudo -S "$@"
  else
    sudo "$@"
  fi
}

run_sudo_bash() {
  if [ -n "${SSH_PASSWORD:-}" ]; then
    printf '%s\n' "${SSH_PASSWORD}" | sudo -S bash -lc "$1"
  else
    sudo bash -lc "$1"
  fi
}

rand_secret() {
  openssl rand -hex 24 2>/dev/null || tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48
}

sync_backend_config() {
  [ -f backend/config.yaml ] || return 0

  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a

  DATABASE_URL="mysql+pymysql://${MYSQL_USER:-farm_manager}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE:-farm_manager}?charset=utf8mb4"
  MONGODB_URI="mongodb://${MONGO_INITDB_ROOT_USERNAME:-farm_manager}:${MONGO_INITDB_ROOT_PASSWORD}@mongo:27017/${MONGO_DATABASE:-farm_manager}?authSource=admin"
  export DATABASE_URL MONGODB_URI

  python3 - <<'PY'
import json
import os
import re
from pathlib import Path

path = Path("backend/config.yaml")
lines = path.read_text(encoding="utf-8").splitlines()


def replace_yaml_key(section: str, key: str, value: object) -> None:
    rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, str) else (
        "true" if value is True else "false" if value is False else str(value)
    )
    in_section = False
    section_indent = 0
    insert_at = None
    pattern = re.compile(rf"^(\s+{re.escape(key)}:\s*)(.*?)(\s+#.*)?$")

    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(section)}:\s*$", line):
            in_section = True
            section_indent = 0
            insert_at = index + 1
            continue
        if in_section and re.match(r"^\S", line):
            break
        if not in_section:
            continue
        if line.strip():
            insert_at = index + 1
        match = pattern.match(line)
        if match:
            comment = match.group(3) or ""
            lines[index] = f"{match.group(1)}{rendered}{comment}"
            return

    if insert_at is not None:
        lines.insert(insert_at, f"  {key}: {rendered}")
        return
    lines.extend([f"{section}:", f"  {key}: {rendered}"])


replace_yaml_key("database", "url", os.environ["DATABASE_URL"])
replace_yaml_key("mongodb", "enabled", True)
replace_yaml_key("mongodb", "uri", os.environ["MONGODB_URI"])
replace_yaml_key("mongodb", "database", os.environ.get("MONGO_DATABASE", "farm_manager"))
replace_yaml_key("mongodb", "tls", False)
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

  chmod 600 backend/config.yaml
}

if ! command -v docker >/dev/null 2>&1; then
  rdie "远端缺少 docker"
fi
docker compose version >/dev/null 2>&1 || rdie "远端缺少 docker compose"
command -v nginx >/dev/null 2>&1 || rdie "远端缺少 nginx"
command -v python3 >/dev/null 2>&1 || rdie "远端缺少 python3"

rlog "创建部署目录 ${REMOTE_ROOT}"
run_sudo mkdir -p "${REMOTE_ROOT}"
run_sudo chown -R "$(id -u):$(id -g)" "${REMOTE_ROOT}"

BACKUP_DIR="/tmp/farm-manager-compose-backup-${TIMESTAMP}"
if [ -d "${REMOTE_ROOT}" ] && [ -n "$(find "${REMOTE_ROOT}" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]; then
  rlog "备份旧部署到 ${BACKUP_DIR}"
  rm -rf "${BACKUP_DIR}"
  mkdir -p "${BACKUP_DIR}"
  cp -a "${REMOTE_ROOT}/." "${BACKUP_DIR}/"
fi

rlog "解压部署包"
tar xzf "${REMOTE_TARBALL}" -C "${REMOTE_ROOT}"
rm -f "${REMOTE_TARBALL}"

cd "${REMOTE_ROOT}"

if [ -f backend/config.yaml ]; then
  chmod 600 backend/config.yaml
fi

rlog "准备 Compose 环境变量"
if [ ! -f .env ]; then
  cat > .env <<ENV_EOF
MYSQL_ROOT_PASSWORD=$(rand_secret)
MYSQL_DATABASE=farm_manager
MYSQL_USER=farm_manager
MYSQL_PASSWORD=$(rand_secret)
MONGO_INITDB_ROOT_USERNAME=farm_manager
MONGO_INITDB_ROOT_PASSWORD=$(rand_secret)
MONGO_DATABASE=farm_manager
AUTH_JWT_SECRET=$(rand_secret)
AUTH_ADMIN_PHONE=${AUTH_ADMIN_PHONE:-}
AUTH_ADMIN_PASSWORD=${AUTH_ADMIN_PASSWORD:-}
AI_API_KEY=${AI_API_KEY:-}
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AI_MODEL=qwen3.6-35b-a3b
VITE_API_BASE_URL=${API_URL}
BACKEND_PORT=${BACKEND_PORT}
ADMIN_WEB_PORT=${ADMIN_WEB_PORT}
ENV_EOF
  chmod 600 .env
else
  grep -q '^BACKEND_PORT=' .env || echo "BACKEND_PORT=${BACKEND_PORT}" >> .env
  grep -q '^ADMIN_WEB_PORT=' .env || echo "ADMIN_WEB_PORT=${ADMIN_WEB_PORT}" >> .env
  grep -q '^VITE_API_BASE_URL=' .env || echo "VITE_API_BASE_URL=${API_URL}" >> .env
fi

sync_backend_config

rlog "启动 Docker Compose"
docker compose up -d --build

rlog "等待后端健康检查"
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    rlog "后端健康检查通过"
    break
  fi
  sleep 3
done
curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null || {
  docker compose logs --tail=120 backend
  rdie "后端健康检查失败"
}

rlog "写入宿主机 nginx 反代配置"
NGINX_SITE="/etc/nginx/sites-available/farm-manager"
run_sudo_bash "cat > '${NGINX_SITE}'" <<NGINX_EOF
server {
    listen ${NGINX_PORT};
    server_name _;

    client_max_body_size 50m;

    location ^~ /api/api/ {
        rewrite ^/api/api/(.*)$ /api/\$1 break;
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ^~ /api/ {
        rewrite ^/api/(.*)$ /\$1 break;
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:${ADMIN_WEB_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX_EOF
run_sudo ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/farm-manager
run_sudo nginx -t
run_sudo systemctl reload nginx

rlog "验证 nginx 入口"
curl -fsS "http://127.0.0.1:${NGINX_PORT}/" >/dev/null || rdie "nginx 入口验证失败"
curl -fsS "http://127.0.0.1:${NGINX_PORT}/api/health" >/dev/null || rdie "nginx API 反代验证失败"

rlog "远程部署完成"
REMOTE_SCRIPT
  ok "远程部署完成"
}

verify() {
  log "本机验收"
  curl -fsS "http://${SERVER_HOST}:${NGINX_PORT}/" >/dev/null && ok "admin-web 可访问: http://${SERVER_HOST}:${NGINX_PORT}/"
  curl -fsS "http://${SERVER_HOST}:${NGINX_PORT}/api/health" >/dev/null && ok "API 可访问: http://${SERVER_HOST}:${NGINX_PORT}/api/health"
}

printf '\n=========================================\n'
printf ' HomeUbuntu Docker Compose 部署\n'
printf '=========================================\n'
printf ' 服务器:        %s\n' "${SERVER}"
printf ' 远端目录:      %s\n' "${REMOTE_ROOT}"
printf ' nginx 端口:    %s\n' "${NGINX_PORT}"
printf ' admin-web端口: %s\n' "${ADMIN_WEB_PORT}"
printf ' backend端口:   %s\n' "${BACKEND_PORT}"
printf '=========================================\n'

preflight
build_admin_web
package_project
upload_project
remote_deploy
verify

log "部署完成"
