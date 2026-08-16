#!/usr/bin/env bash
# 日常同步 v2 — 上传 v2 代码并重启 Business、Agent 服务
# 用法: bash deploy/server-sync.sh
set -euo pipefail

# --- 服务器配置 ---
SERVER_USER="${SERVER_USER:-root}"
SERVER_HOST="${SERVER_HOST:-43.155.217.74}"
SERVER="${SERVER_USER}@${SERVER_HOST}"
REMOTE_ROOT="/root/workspace/farm-manager"
REMOTE_DIR="${REMOTE_ROOT}/v2"
AGENT_SERVICE_NAME="farm-manager"
BUSINESS_SERVICE_NAME="farm-manager-business"
AGENT_PORT=8000
BUSINESS_PORT=9876

PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="/tmp/farm-manager-v2-sync.tar.gz"
LOCAL_AGENT_CONFIG=0
LOCAL_BUSINESS_CONFIG=0
[ -f "${PROJECT_ROOT}/v2/agent/config.yaml" ] && LOCAL_AGENT_CONFIG=1
[ -f "${PROJECT_ROOT}/v2/business/config.yaml" ] && LOCAL_BUSINESS_CONFIG=1

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { log "错误: $*" >&2; exit 1; }

cleanup() {
    rm -f "${ARCHIVE}"
}
trap cleanup EXIT

# --- 0. 预检 SSH 连接 ---
log "预检 SSH 连接 ${SERVER}..."
if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "${SERVER}" "true" 2>/dev/null; then
    die "无法免密登录 ${SERVER}。请先配置: ssh-copy-id ${SERVER}"
fi

# --- 1. 本地打包 v2 代码 ---
log "打包 v2 代码..."
COPYFILE_DISABLE=1 tar czf "${ARCHIVE}" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.egg-info' \
    --exclude='.DS_Store' \
    --exclude='v2/.venv' \
    --exclude='v2/.pytest_cache' \
    --exclude='v2/.ruff_cache' \
    --exclude='v2/logs' \
    --exclude='v2/.env' \
    --exclude='v2/.env.*' \
    --exclude='v2/._*' \
    --exclude='v2/.claude' \
    --exclude='v2/.git' \
    -C "${PROJECT_ROOT}" \
    v2

log "上传 v2 代码..."
ssh -o ConnectTimeout=8 "${SERVER}" "rm -f '${ARCHIVE}'" 2>/dev/null || true
scp -q -o ConnectTimeout=8 "${ARCHIVE}" "${SERVER}:${ARCHIVE}"

# --- 2. 远程部署 ---
log "远程部署 v2..."
ssh "${SERVER}" \
    "TIMESTAMP='${TIMESTAMP}' REMOTE_ROOT='${REMOTE_ROOT}' REMOTE_DIR='${REMOTE_DIR}' AGENT_SERVICE_NAME='${AGENT_SERVICE_NAME}' BUSINESS_SERVICE_NAME='${BUSINESS_SERVICE_NAME}' AGENT_PORT='${AGENT_PORT}' BUSINESS_PORT='${BUSINESS_PORT}' SERVER_HOST='${SERVER_HOST}' ARCHIVE='${ARCHIVE}' LOCAL_AGENT_CONFIG='${LOCAL_AGENT_CONFIG}' LOCAL_BUSINESS_CONFIG='${LOCAL_BUSINESS_CONFIG}' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

rlog()  { echo "  [$(date '+%H:%M:%S')] $*"; }
rdie()  { rlog "错误: $*" >&2; exit 1; }

BACKUP_DIR="/tmp/farm-manager-v2-backup-${TIMESTAMP}"
SYSTEMD_DIR="/etc/systemd/system"
OLD_PATHS=()

rollback() {
    set +e
    rlog "执行自动回滚..."

    systemctl stop "${AGENT_SERVICE_NAME}" "${BUSINESS_SERVICE_NAME}" 2>/dev/null || true

    # 删除本次解压的代码，再恢复部署前的代码目录。
    for path in agent business shared scripts sql docs tests pyproject.toml uv.lock providers.json; do
        rm -rf "${REMOTE_DIR}/${path}"
    done
    for path in "${OLD_PATHS[@]}"; do
        if [ -e "${BACKUP_DIR}/source/${path}" ]; then
            mkdir -p "$(dirname "${REMOTE_DIR}/${path}")"
            mv "${BACKUP_DIR}/source/${path}" "${REMOTE_DIR}/${path}"
        fi
    done

    if [ -f "${BACKUP_DIR}/config/agent.yaml" ]; then
        mkdir -p "${REMOTE_DIR}/agent"
        cp "${BACKUP_DIR}/config/agent.yaml" "${REMOTE_DIR}/agent/config.yaml"
    fi
    if [ -f "${BACKUP_DIR}/config/business.yaml" ]; then
        mkdir -p "${REMOTE_DIR}/business"
        cp "${BACKUP_DIR}/config/business.yaml" "${REMOTE_DIR}/business/config.yaml"
    fi

    for service in "${AGENT_SERVICE_NAME}" "${BUSINESS_SERVICE_NAME}"; do
        if [ -f "${BACKUP_DIR}/units/${service}.service" ]; then
            cp "${BACKUP_DIR}/units/${service}.service" "${SYSTEMD_DIR}/${service}.service"
        else
            rm -f "${SYSTEMD_DIR}/${service}.service"
        fi
    done
    systemctl daemon-reload 2>/dev/null || true
    if [ -f "${BACKUP_DIR}/units/${AGENT_SERVICE_NAME}.service" ]; then
        systemctl restart "${AGENT_SERVICE_NAME}" 2>/dev/null || true
    fi
    if [ -f "${BACKUP_DIR}/units/${BUSINESS_SERVICE_NAME}.service" ]; then
        systemctl restart "${BUSINESS_SERVICE_NAME}" 2>/dev/null || true
    fi
    rlog "已回滚，备份目录: ${BACKUP_DIR}"
}

mkdir -p "${REMOTE_ROOT}" "${REMOTE_DIR}" "${BACKUP_DIR}/source" "${BACKUP_DIR}/config" "${BACKUP_DIR}/units"
cd "${REMOTE_DIR}" || rdie "无法进入 ${REMOTE_DIR}"

# --- 并发锁 ---
LOCKFILE="/tmp/farm-manager-v2-sync.lock"
if [ -f "${LOCKFILE}" ]; then
    LOCK_PID=$(cat "${LOCKFILE}" 2>/dev/null || true)
    if [ -n "${LOCK_PID}" ] && kill -0 "${LOCK_PID}" 2>/dev/null; then
        rdie "另一个 v2 部署正在运行 (PID=${LOCK_PID})，退出"
    fi
    rlog "清理过期锁文件"
fi
echo $$ > "${LOCKFILE}"
trap 'rm -f "${LOCKFILE}"' EXIT

# --- 备份旧 v2 代码和配置 ---
rlog "备份旧 v2 代码..."
if [ -f agent/config.yaml ]; then
    cp agent/config.yaml "${BACKUP_DIR}/config/agent.yaml"
fi
if [ -f business/config.yaml ]; then
    cp business/config.yaml "${BACKUP_DIR}/config/business.yaml"
fi
for path in agent business shared scripts sql docs tests pyproject.toml uv.lock providers.json; do
    if [ -e "${REMOTE_DIR}/${path}" ]; then
        mv "${REMOTE_DIR}/${path}" "${BACKUP_DIR}/source/${path}"
        OLD_PATHS+=("${path}")
    fi
done

for service in "${AGENT_SERVICE_NAME}" "${BUSINESS_SERVICE_NAME}"; do
    if [ -f "${SYSTEMD_DIR}/${service}.service" ]; then
        cp "${SYSTEMD_DIR}/${service}.service" "${BACKUP_DIR}/units/${service}.service"
    fi
done

# --- 解压新代码 ---
rlog "解压 v2 代码..."
if ! tar xzf "${ARCHIVE}" -C "${REMOTE_ROOT}"; then
    rollback
    rdie "v2 代码解压失败"
fi
rm -f "${ARCHIVE}"

# 本地有配置时使用本地配置；本地没有时沿用远程配置。
if [ "${LOCAL_AGENT_CONFIG}" != "1" ] && [ -f "${BACKUP_DIR}/config/agent.yaml" ]; then
    cp "${BACKUP_DIR}/config/agent.yaml" "${REMOTE_DIR}/agent/config.yaml"
fi
if [ "${LOCAL_BUSINESS_CONFIG}" != "1" ] && [ -f "${BACKUP_DIR}/config/business.yaml" ]; then
    cp "${BACKUP_DIR}/config/business.yaml" "${REMOTE_DIR}/business/config.yaml"
fi

if [ ! -f "${REMOTE_DIR}/agent/config.yaml" ]; then
    rollback
    rdie "缺少 ${REMOTE_DIR}/agent/config.yaml，请先根据 config.example.yaml 创建并填写生产配置"
fi
if [ ! -f "${REMOTE_DIR}/business/config.yaml" ]; then
    rollback
    rdie "缺少 ${REMOTE_DIR}/business/config.yaml，请先根据 config.example.yaml 创建并填写生产配置"
fi

# --- 安装 v2 依赖 ---
cd "${REMOTE_DIR}" || { rollback; rdie "无法进入 ${REMOTE_DIR}"; }
UV_BIN="$(command -v uv || true)"
if [ -z "${UV_BIN}" ] && [ -x /root/.local/bin/uv ]; then
    UV_BIN="/root/.local/bin/uv"
fi
if [ -z "${UV_BIN}" ]; then
    rlog "远程未找到 uv，开始安装..."
    if ! command -v curl >/dev/null 2>&1 \
        || ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        rollback
        rdie "uv 自动安装失败，请检查远程网络或手动安装 uv 后重试"
    fi
    UV_BIN="/root/.local/bin/uv"
    if [ ! -x "${UV_BIN}" ]; then
        rollback
        rdie "uv 安装完成但找不到 ${UV_BIN}"
    fi
fi
rlog "同步 v2 Business 和 Agent 依赖..."
if ! "${UV_BIN}" sync --frozen --all-packages; then
    rollback
    rdie "uv sync 失败"
fi

# 在切换 systemd 前确认 Business 能连接数据库，并完成必要的初始管理员检查。
rlog "检查 Business 数据库..."
if ! .venv/bin/python -c 'from business.db import check_connection; from business.services.auth_service import ensure_admin_user; check_connection(); ensure_admin_user()'; then
    rollback
    rdie "Business 数据库检查失败"
fi

write_unit() {
    local service="$1"
    local description="$2"
    local module="$3"
    local port="$4"
    local after="network.target"
    local factory_flag=""
    [ "${service}" = "${AGENT_SERVICE_NAME}" ] && after="${BUSINESS_SERVICE_NAME}.service"
    [ "${service}" = "${BUSINESS_SERVICE_NAME}" ] && { module="business.server:create_app"; factory_flag="--factory"; }

    cat > "${SYSTEMD_DIR}/${service}.service" <<UNIT_EOF
[Unit]
Description=${description}
After=${after}

[Service]
Type=simple
User=root
WorkingDirectory=${REMOTE_DIR}
ExecStart=${REMOTE_DIR}/.venv/bin/uvicorn ${module} ${factory_flag} --host 0.0.0.0 --port ${port}
Restart=on-failure
RestartSec=5
TimeoutStartSec=90
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=${REMOTE_DIR}
EnvironmentFile=-${REMOTE_DIR}/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT_EOF
}

# farm-manager 这个服务名沿用旧脚本，保证 server-ctl.sh 仍可管理 Agent。
rlog "更新 systemd 服务..."
write_unit "${BUSINESS_SERVICE_NAME}" "Farm Manager v2 Business (REST + MCP)" "business.server" "${BUSINESS_PORT}"
write_unit "${AGENT_SERVICE_NAME}" "Farm Manager v2 Agent (SSE API)" "agent.main:app" "${AGENT_PORT}"
systemctl daemon-reload
systemctl enable "${BUSINESS_SERVICE_NAME}" "${AGENT_SERVICE_NAME}" >/dev/null

# 旧 farm-manager unit 会被上面的 Agent unit 覆盖，不再启动旧 backend。
rlog "重启 v2 服务..."
systemctl restart "${BUSINESS_SERVICE_NAME}"
systemctl restart "${AGENT_SERVICE_NAME}"

# --- 健康检查 ---
rlog "等待 v2 服务健康检查..."
for i in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${BUSINESS_PORT}/api/v2/readiness" >/dev/null 2>&1 \
        && curl -fsS "http://127.0.0.1:${AGENT_PORT}/api/v2/health" >/dev/null 2>&1; then
        echo "  v2 部署成功！"
        echo "  Agent:    http://${SERVER_HOST}:${AGENT_PORT}"
        echo "  Business: http://${SERVER_HOST}:${BUSINESS_PORT}/api/v2"
        echo "  日志:     journalctl -u ${AGENT_SERVICE_NAME} -f"
        echo "  备份:     ${BACKUP_DIR}"
        exit 0
    fi
    if [ $((i % 5)) -eq 0 ]; then
        rlog "等待中... ($((i * 2))s)"
    fi
    sleep 2
done

echo "  v2 启动超时，最近日志："
journalctl -u "${BUSINESS_SERVICE_NAME}" -n 40 --no-pager || true
journalctl -u "${AGENT_SERVICE_NAME}" -n 40 --no-pager || true
rollback
exit 1
REMOTE_SCRIPT

log "v2 同步完成"
