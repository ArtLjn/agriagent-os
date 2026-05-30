#!/usr/bin/env bash
# 日常同步 — 快速同步后端代码到阿里云并重启服务
# 用法: bash deploy/server-sync.sh
set -euo pipefail

SERVER="root@47.98.253.236"
REMOTE_DIR="/root/workspace/farm-manager/backend"
PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"

echo "==> 打包后端代码..."
tar czf /tmp/farm-backend-sync.tar.gz \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='*.db' \
    --exclude='.venv' \
    --exclude='.claude' \
    --exclude='.git' \
    --exclude='._*' \
    -C "${PROJECT_ROOT}" \
    backend/app \
    backend/requirements.txt \
    backend/skillify-sdk \
    backend/config.yaml.example \
    backend/prompts

echo "==> 上传到服务器..."
scp /tmp/farm-backend-sync.tar.gz "${SERVER}:/tmp/farm-backend-sync.tar.gz"

echo "==> 远程解压 + 重启..."
ssh "${SERVER}" bash -s <<'REMOTE_SCRIPT'
set -euo pipefail
cd /root/workspace/farm-manager/backend

echo "  --> 解压..."
tar xzf /tmp/farm-backend-sync.tar.gz
rm -f /tmp/farm-backend-sync.tar.gz

echo "  --> 备份 config.yaml..."
cp config.yaml /tmp/config.yaml.bak 2>/dev/null || true

echo "  --> 覆盖代码..."
rm -rf app skillify-sdk prompts
mv backend/app . 2>/dev/null || true
mv backend/skillify-sdk . 2>/dev/null || true
mv backend/prompts . 2>/dev/null || true
mv backend/requirements.txt . 2>/dev/null || true
mv backend/config.yaml.example . 2>/dev/null || true
rm -rf backend

echo "  --> 恢复 config.yaml..."
cp /tmp/config.yaml.bak config.yaml 2>/dev/null || true

echo "  --> 检查虚拟环境..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
    echo "      已创建虚拟环境"
fi
source .venv/bin/activate

echo "  --> 安装依赖..."
pip install -q --upgrade pip
# 先安装本地 skillify-sdk
pip install -q -e ./skillify-sdk 2>/dev/null || pip install -q ./skillify-sdk
# 再安装其他依赖（跳过 skillify，因为已本地安装）
grep -v "^skillify" requirements.txt > /tmp/requirements-no-skillify.txt
pip install -q -r /tmp/requirements-no-skillify.txt

echo "  --> 检查数据库结构..."
if [ -f farm_manager.db ]; then
    if ! sqlite3 farm_manager.db "PRAGMA table_info(farms);" | grep -q "user_id"; then
        echo "      数据库结构过旧，备份并重建..."
        mv farm_manager.db "farm_manager.db.bak.$(date +%s)"
    fi
fi

echo "  --> 自动建表..."
python3 -c "
import sys
sys.path.insert(0, '.')
from app.core.database import engine, Base
import app.models
Base.metadata.create_all(bind=engine)
print('      数据库表已同步')
" 2>/dev/null || echo "      建表跳过（可能需要手动处理）"

echo "  --> 重启服务 (systemctl)..."
systemctl restart farm-manager

echo "  --> 等待启动..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
        echo "  ✅ 部署成功！"
        echo "  → API:   http://47.98.253.236:8000"
        echo "  → 文档:  http://47.98.253.236:8000/docs"
        echo "  → 日志:  journalctl -u farm-manager -f"
        exit 0
    fi
    sleep 2
done

echo "  ❌ 启动超时，最近日志："
journalctl -u farm-manager -n 50 --no-pager || true
echo ""
echo "  尝试直接运行查看错误："
cd /root/workspace/farm-manager/backend
source .venv/bin/activate
python3 -c "import sys; sys.path.insert(0, '.'); from app.main import app; print('Import OK')" 2>&1 || true
exit 1
REMOTE_SCRIPT

rm -f /tmp/farm-backend-sync.tar.gz
echo "==> 同步完成"
