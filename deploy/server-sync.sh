#!/usr/bin/env bash
# 日常同步 — 快速同步后端代码到阿里云并重启服务
# 用法: bash deploy/server-sync.sh
set -euo pipefail

SERVER="root@47.98.253.236"
REMOTE_DIR="/root/workspace/farm-manager/backend"
PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { log "ERROR: $*"; exit 1; }

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
    backend/prompts

log "上传到服务器..."
scp -q /tmp/farm-backend-sync.tar.gz "${SERVER}:/tmp/farm-backend-sync.tar.gz"

# --- 2. 远程部署 ---
log "远程部署..."
ssh "${SERVER}" "TIMESTAMP='${TIMESTAMP}' REMOTE_DIR='${REMOTE_DIR}' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

rlog()  { echo "  [$(date '+%H:%M:%S')] $*"; }
rdie()  { rlog "ERROR: $*"; exit 1; }

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

# --- 备份旧代码 + config ---
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
rlog "备份已保存到 ${BACKUP_DIR}"

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

# --- 虚拟环境 ---
rlog "检查虚拟环境..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
    rlog "已创建虚拟环境"
fi
source .venv/bin/activate

# --- 安装依赖 ---
rlog "安装依赖..."
pip install -q --upgrade pip || rdie "pip 升级失败"
rlog "  安装 skillify-sdk..."
pip install -q -e ./skillify-sdk 2>&1 || pip install -q ./skillify-sdk 2>&1 || rdie "skillify-sdk 安装失败"
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
" || rdie "建表失败，请检查数据库配置"

# --- 重启服务 ---
rlog "重启服务 (systemctl)..."
systemctl restart farm-manager

# --- 健康检查 ---
rlog "等待启动..."
for i in $(seq 1 20); do
    # 优先尝试 /api/v1/health，fallback 到 /docs
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "  部署成功！"
        echo "  API:    http://47.98.253.236:8000"
        echo "  文档:   http://47.98.253.236:8000/docs"
        echo "  日志:   journalctl -u farm-manager -f"
        echo "  回滚:   cp -a ${BACKUP_DIR}/* ${REMOTE_DIR}/ && systemctl restart farm-manager"
        exit 0
    fi
    # 也可用 /docs 作为备选健康检查
    if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
        echo "  部署成功！（/docs）"
        echo "  API:    http://47.98.253.236:8000"
        echo "  日志:   journalctl -u farm-manager -f"
        echo "  回滚:   cp -a ${BACKUP_DIR}/* ${REMOTE_DIR}/ && systemctl restart farm-manager"
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
journalctl -u farm-manager -n 50 --no-pager
echo ""
echo "  尝试 import 测试..."
source .venv/bin/activate
python3 -c "import sys; sys.path.insert(0, '.'); from app.main import app; print('Import OK')" 2>&1
echo ""
echo "  回滚命令: cp -a ${BACKUP_DIR}/* ${REMOTE_DIR}/ && systemctl restart farm-manager"
exit 1
REMOTE_SCRIPT

rm -f /tmp/farm-backend-sync.tar.gz
log "同步完成"
