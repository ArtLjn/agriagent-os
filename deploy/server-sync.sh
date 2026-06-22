#!/usr/bin/env bash
# 日常同步 — 快速同步后端代码到远程服务器并重启服务
# 用法: bash deploy/server-sync.sh
set -euo pipefail

# --- 服务器配置 ---
SERVER_USER="root"
SERVER_HOST="43.155.217.74"
SERVER="${SERVER_USER}@${SERVER_HOST}"
REMOTE_DIR="/root/workspace/farm-manager/backend"
SERVICE_NAME="farm-manager"
APP_PORT=8000

PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { log "ERROR: $*"; exit 1; }

# --- 0. 预检 SSH 连接 ---
log "预检 SSH 连接 ${SERVER}..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${SERVER}" "true" 2>/dev/null; then
    die "无法免密登录 ${SERVER}。请先配置: ssh-copy-id ${SERVER}"
fi

# --- 1. 本地打包 ---
log "打包后端代码..."
COPYFILE_DISABLE=1 tar czf /tmp/farm-backend-sync.tar.gz \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    --exclude='.venv' \
    --exclude='.claude' \
    --exclude='.git' \
    --exclude='._*' \
    -C "${PROJECT_ROOT}" \
    backend/app \
    backend/alembic \
    backend/alembic.ini \
    backend/requirements.txt \
    backend/skillify-sdk \
    backend/config.yaml \
    backend/config.yaml.example \
    backend/providers.json \
    backend/prompts \
    shared/location

log "上传到服务器..."
# 清理可能残留的旧包（sticky bit 下 scp 无法覆盖非当前用户拥有的文件）
ssh -o ConnectTimeout=5 "${SERVER}" "rm -f /tmp/farm-backend-sync.tar.gz" 2>/dev/null || true
scp -q /tmp/farm-backend-sync.tar.gz "${SERVER}:/tmp/farm-backend-sync.tar.gz"

# --- 2. 远程部署 ---
log "远程部署..."
ssh "${SERVER}" \
    "TIMESTAMP='${TIMESTAMP}' REMOTE_DIR='${REMOTE_DIR}' SERVICE_NAME='${SERVICE_NAME}' APP_PORT='${APP_PORT}' SERVER_HOST='${SERVER_HOST}' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

rlog()  { echo "  [$(date '+%H:%M:%S')] $*"; }
rdie()  { rlog "ERROR: $*"; exit 1; }

# --- 确保部署目录存在 ---
mkdir -p "${REMOTE_DIR}"
cd "${REMOTE_DIR}" || rdie "无法进入 ${REMOTE_DIR}"

# --- 并发锁 ---
LOCKFILE="/tmp/farm-sync.lock"
if [ -f "${LOCKFILE}" ]; then
    LOCK_PID=$(cat "${LOCKFILE}" 2>/dev/null || true)
    if [ -n "${LOCK_PID}" ] && kill -0 "${LOCK_PID}" 2>/dev/null; then
        rdie "另一个部署正在运行 (PID=${LOCK_PID})，退出"
    fi
    rlog "清理过期锁文件"
fi
echo $$ > "${LOCKFILE}"
trap 'rm -f "${LOCKFILE}"' EXIT

# --- 解压 ---
rlog "解压..."
tar xzf /tmp/farm-backend-sync.tar.gz 2>&1 | grep -v 'LIBARCHIVE.xattr' || true
rm -f /tmp/farm-backend-sync.tar.gz

# --- 备份旧代码 + config + shared 数据 ---
rlog "备份旧代码..."
BACKUP_DIR="/tmp/farm-backup-${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"
for d in app alembic skillify-sdk prompts; do
    [ -d "$d" ] && cp -a "$d" "${BACKUP_DIR}/"
done
[ -f alembic.ini ] && cp alembic.ini "${BACKUP_DIR}/"
[ -f config.yaml ] && cp config.yaml "${BACKUP_DIR}/"
[ -f providers.json ] && cp providers.json "${BACKUP_DIR}/"
[ -f requirements.txt ] && cp requirements.txt "${BACKUP_DIR}/"
# shared 目录位于 REMOTE_DIR 上一级（仓库根）
if [ -d "../shared" ]; then
    rm -rf "${BACKUP_DIR}/shared"
    cp -a "../shared" "${BACKUP_DIR}/shared"
fi
rlog "备份已保存到 ${BACKUP_DIR}"

# --- 自动回滚函数（建表或启动失败时调用）---
rollback() {
    rlog "执行自动回滚..."
    for d in app alembic skillify-sdk prompts; do
        [ -d "${BACKUP_DIR}/$d" ] && rm -rf "$d" && cp -a "${BACKUP_DIR}/$d" .
    done
    [ -f "${BACKUP_DIR}/alembic.ini" ] && cp "${BACKUP_DIR}/alembic.ini" .
    [ -f "${BACKUP_DIR}/config.yaml" ] && cp "${BACKUP_DIR}/config.yaml" .
    [ -f "${BACKUP_DIR}/providers.json" ] && cp "${BACKUP_DIR}/providers.json" .
    [ -f "${BACKUP_DIR}/requirements.txt" ] && cp "${BACKUP_DIR}/requirements.txt" .
    if [ -d "${BACKUP_DIR}/shared" ]; then
        rm -rf "../shared"
        cp -a "${BACKUP_DIR}/shared" "../shared"
    fi
    systemctl restart "${SERVICE_NAME}" 2>/dev/null || true
    rlog "已回滚到 ${BACKUP_DIR}"
}

# --- 覆盖代码 ---
rlog "覆盖代码..."
rm -rf app alembic skillify-sdk prompts
mv backend/app .
mv backend/alembic .
mv backend/alembic.ini .
mv backend/skillify-sdk .
mv backend/prompts .
mv backend/requirements.txt .
mv backend/config.yaml .
mv backend/config.yaml.example .
[ -f backend/providers.json ] && mv backend/providers.json .
# shared 部署到仓库根（REMOTE_DIR 上一级），代码通过 parents[3] 解析
if [ -d shared ]; then
    mkdir -p ../shared
    rm -rf ../shared/location
    mv shared/location ../shared/
    rm -rf shared
fi
rm -rf backend

# --- 配置兜底 ---
rlog "检查配置文件..."
if [ ! -f config.yaml ]; then
    if [ -f "${BACKUP_DIR}/config.yaml" ]; then
        cp "${BACKUP_DIR}/config.yaml" config.yaml
    else
        rlog "无 config.yaml，使用 example"
        cp config.yaml.example config.yaml
    fi
fi
if [ ! -f providers.json ] && [ -f "${BACKUP_DIR}/providers.json" ]; then
    cp "${BACKUP_DIR}/providers.json" providers.json
fi
if [ ! -f config.yaml ]; then
    cp config.yaml.example config.yaml
fi

# --- 虚拟环境（Python 3.12）---
rlog "检查虚拟环境..."
if [ ! -x .venv/bin/python ]; then
    rm -rf .venv
    python3.12 -m venv .venv
    # 兜底：deadsnakes Python 3.12 在 Ubuntu 22.04 上有时不创建 python 软链接
    [ -e .venv/bin/python ]    || ln -s /usr/bin/python3.12 .venv/bin/python
    [ -e .venv/bin/python3 ]   || ln -s /usr/bin/python3.12 .venv/bin/python3
    [ -e .venv/bin/python3.12 ] || ln -s /usr/bin/python3.12 .venv/bin/python3.12
    rlog "已创建虚拟环境 (Python 3.12)"
fi
source .venv/bin/activate
hash -r

# --- 安装依赖 ---
rlog "安装依赖..."
pip install -q --upgrade pip || rdie "pip 升级失败"
rlog "  安装 skillify-sdk..."
pip install -q -e ./skillify-sdk 2>&1 || pip install -q ./skillify-sdk 2>&1 || { rollback; rdie "skillify-sdk 安装失败，已回滚"; }
rlog "  安装其他依赖..."
grep -v "^skillify" requirements.txt > /tmp/requirements-no-skillify.txt
if ! pip install -q -r /tmp/requirements-no-skillify.txt 2>&1; then
    rlog "依赖安装有警告，尝试继续..."
fi

# --- 数据库备份 ---
rlog "检查数据库..."
if [ -f farm_manager.db ]; then
    cp farm_manager.db "farm_manager.db.bak.${TIMESTAMP}"
fi

# --- 自动建表 ---
rlog "自动建表..."
python3 -c "
import sys
sys.path.insert(0, '.')
from app.core.database import engine, Base
import app.models
Base.metadata.create_all(bind=engine)
print('  数据库表已同步')
" || { rollback; rdie "建表失败，已回滚"; }

# --- 注册 systemd unit（首次部署或 unit 缺失时）---
SYSTEMD_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
if ! systemctl list-unit-files --no-pager 2>/dev/null | grep -q "^${SERVICE_NAME}\.service"; then
    rlog "首次部署：注册 systemd unit..."
    cat > "${SYSTEMD_UNIT}" <<UNIT_EOF
[Unit]
Description=Farm Manager API (FastAPI + Uvicorn)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${REMOTE_DIR}
ExecStart=${REMOTE_DIR}/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT}
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=${REMOTE_DIR}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT_EOF
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" >/dev/null 2>&1 || true
    rlog "systemd unit 已注册并 enable"
fi

# --- 重启服务 ---
rlog "重启服务 (systemctl)..."
systemctl restart "${SERVICE_NAME}"

# --- 健康检查 ---
rlog "等待启动..."
for i in $(seq 1 20); do
    # 优先尝试 /health（应用根路由），fallback 到 /docs
    if curl -sf "http://localhost:${APP_PORT}/health" > /dev/null 2>&1; then
        echo "  部署成功！"
        echo "  API:    http://${SERVER_HOST}:${APP_PORT}"
        echo "  文档:   http://${SERVER_HOST}:${APP_PORT}/docs"
        echo "  日志:   journalctl -u ${SERVICE_NAME} -f"
        echo "  回滚:   cp -a ${BACKUP_DIR}/* ${REMOTE_DIR}/ && systemctl restart ${SERVICE_NAME}"
        exit 0
    fi
    # 也可用 /docs 作为备选健康检查
    if curl -sf "http://localhost:${APP_PORT}/docs" > /dev/null 2>&1; then
        echo "  部署成功！（/docs）"
        echo "  API:    http://${SERVER_HOST}:${APP_PORT}"
        echo "  日志:   journalctl -u ${SERVICE_NAME} -f"
        echo "  回滚:   cp -a ${BACKUP_DIR}/* ${REMOTE_DIR}/ && systemctl restart ${SERVICE_NAME}"
        exit 0
    fi
    # 每 4 秒打印进度
    if [ $((i % 2)) -eq 0 ]; then
        rlog "  等待中... ($((i * 2))s)"
    fi
    sleep 2
done

# --- 失败处理 ---
echo "  启动超时，最近日志："
journalctl -u "${SERVICE_NAME}" -n 50 --no-pager
echo ""
echo "  尝试 import 测试..."
source .venv/bin/activate
python3 -c "import sys; sys.path.insert(0, '.'); from app.main import app; print('Import OK')" 2>&1

# --- 自动回滚（启动失败时）---
echo ""
echo "  健康检查失败，执行自动回滚..."
rollback
echo "  回滚命令（手动）: cp -a ${BACKUP_DIR}/* ${REMOTE_DIR}/ && systemctl restart ${SERVICE_NAME}"
exit 1
REMOTE_SCRIPT

rm -f /tmp/farm-backend-sync.tar.gz
log "同步完成"
