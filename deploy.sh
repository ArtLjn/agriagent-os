#!/usr/bin/env bash
set -euo pipefail

SERVER="root@47.98.253.236"
REMOTE_DIR="/opt/farm-manager"

echo "==> 打包后端代码..."
tar czf /tmp/farm-manager-backend.tar.gz \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='*.db' \
    --exclude='.claude' \
    -C "$(dirname "$0")" \
    backend/ \
    docker-compose.yml

echo "==> 上传到服务器..."
ssh "${SERVER}" "mkdir -p ${REMOTE_DIR}"
scp /tmp/farm-manager-backend.tar.gz "${SERVER}:${REMOTE_DIR}/"

echo "==> 远程部署..."
ssh "${SERVER}" bash -s <<REMOTE_SCRIPT
set -euo pipefail
cd ${REMOTE_DIR}

echo "  --> 解压..."
tar xzf farm-manager-backend.tar.gz
rm farm-manager-backend.tar.gz

echo "  --> 写入配置（从 config.yaml.example 生成，需要你手动填入 API Key）..."
if [ ! -f backend/config.yaml ]; then
    cp backend/config.yaml.example backend/config.yaml
    echo "  ⚠️  请编辑 ${REMOTE_DIR}/backend/config.yaml 填入 ai.api_key"
fi

echo "  --> 构建并启动..."
docker compose up -d --build

echo "  --> 等待健康检查..."
for i in \$(seq 1 15); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ✅ 部署成功！"
        echo "  → API: http://47.98.253.236:8000"
        echo "  → 健康检查: http://47.98.253.236:8000/health"
        echo "  → 文档: http://47.98.253.236:8000/docs"
        exit 0
    fi
    sleep 2
done

echo "  ❌ 健康检查超时，查看日志："
docker compose logs --tail=30
exit 1
REMOTE_SCRIPT

rm -f /tmp/farm-manager-backend.tar.gz
echo "==> 完成"
