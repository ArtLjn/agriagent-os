#!/usr/bin/env bash
# SearXNG 一键部署脚本
# 适用于 Ubuntu 22.04/24.04，需 root 权限
# 用法: curl -fsSL <url> | bash 或 bash deploy-searxng.sh

set -euo pipefail

# ========== 配置 ==========
SEARXNG_PORT="${SEARXNG_PORT:-8888}"
SEARXNG_IMAGE="searxng/searxng:latest"
SEARXNG_DIR="/opt/searxng"
# ==========================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------- 检查 root ----------
if [[ $EUID -ne 0 ]]; then
    error "请使用 root 用户运行此脚本"
fi

# ---------- 安装 Docker ----------
if ! command -v docker &>/dev/null; then
    info "安装 Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    info "Docker 安装完成"
else
    info "Docker 已安装: $(docker --version)"
fi

# ---------- 创建目录 ----------
mkdir -p "${SEARXNG_DIR}"

# ---------- 写入配置 ----------
info "生成 SearXNG 配置..."

cat > "${SEARXNG_DIR}/settings.yml" <<'SETTINGS'
use_default_settings: true

general:
  instance_name: "Farm Search"
  debug: false

search:
  safe_search: 0
  autocomplete: ""
  default_lang: "zh-CN"
  formats:
    - html
    - json

server:
  secret_key: "farm-manager-searxng-2026"
  bind_address: "0.0.0.0"
  port: 8080
  limiter: false
  image_proxy: true

ui:
  static_use_hash: true

outgoing:
  request_timeout: 10
  max_request_timeout: 15
  useragent_suffix: ""
  enable_http2: true

engines:
  - name: google
    engine: google
    shortcut: g
    disabled: false

  - name: bing
    engine: bing
    shortcut: b
    disabled: false

  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
    disabled: false

  - name: wikipedia
    engine: wikipedia
    shortcut: wp
    disabled: false

  - name: wikidata
    engine: wikidata
    shortcut: wd
    disabled: false
SETTINGS

cat > "${SEARXNG_DIR}/docker-compose.yml" <<COMPOSE
services:
  searxng:
    image: ${SEARXNG_IMAGE}
    container_name: searxng
    restart: unless-stopped
    ports:
      - "${SEARXNG_PORT}:8080"
    volumes:
      - ${SEARXNG_DIR}/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:${SEARXNG_PORT}/
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
COMPOSE

# ---------- 部署 ----------
info "拉取 SearXNG 镜像..."
docker compose -f "${SEARXNG_DIR}/docker-compose.yml" pull

info "启动 SearXNG..."
docker compose -f "${SEARXNG_DIR}/docker-compose.yml" up -d

# ---------- 等待就绪 ----------
info "等待服务启动..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${SEARXNG_PORT}/healthz" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# ---------- 验证 ----------
echo ""
if curl -sf "http://localhost:${SEARXNG_PORT}/search?q=test&format=json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'结果数: {len(d.get(\"results\", []))}')" 2>/dev/null; then
    info "SearXNG 部署成功！"
else
    warn "服务已启动但 JSON API 可能需要几秒生效，请手动验证"
fi

# ---------- 防火墙 ----------
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow "${SEARXNG_PORT}"/tcp >/dev/null 2>&1
    info "已开放 UFW 端口 ${SEARXNG_PORT}"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port="${SEARXNG_PORT}"/tcp >/dev/null 2>&1
    firewall-cmd --reload >/dev/null 2>&1
    info "已开放 firewalld 端口 ${SEARXNG_PORT}"
fi

# ---------- 输出 ----------
HOST_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=========================================="
echo -e "${GREEN} SearXNG 部署完成${NC}"
echo "=========================================="
echo ""
echo "  Web 界面:  http://${HOST_IP}:${SEARXNG_PORT}"
echo "  JSON API:  curl 'http://${HOST_IP}:${SEARXNG_PORT}/search?q=关键词&format=json'"
echo ""
echo "  配置目录:  ${SEARXNG_DIR}"
echo "  管理命令:"
echo "    查看日志:  docker logs -f searxng"
echo "    重启服务:  docker restart searxng"
echo "    停止服务:  docker compose -f ${SEARXNG_DIR}/docker-compose.yml down"
echo "    更新镜像:  docker compose -f ${SEARXNG_DIR}/docker-compose.yml pull && docker compose -f ${SEARXNG_DIR}/docker-compose.yml up -d"
echo ""
echo "  Skill 对接: 修改 web-search skill 的 _API_URL 为:"
echo "    http://${HOST_IP}:${SEARXNG_PORT}/search"
echo ""
