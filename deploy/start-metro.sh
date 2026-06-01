#!/bin/bash
# ============================================================
# FarmManagerMobile — Android 开发启动脚本（含实时热更新）
# ============================================================
# 用法:
#   ./deploy/start-metro.sh             # 正常启动（默认 API：阿里云）
#   ./deploy/start-metro.sh --local     # 使用局域网地址
#   ./deploy/start-metro.sh --home      # 使用家庭局域网地址
#   ./deploy/start-metro.sh --reset-cache           # 清除缓存后启动
#   ./deploy/start-metro.sh --local --reset-cache   # 组合使用
#
# Metro 快捷键（启动后在此终端使用）:
#   r  → 强制刷新
#   d  → 打开开发者菜单
#   a  → 运行 Android
#   Ctrl+C → 停止 Metro
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")/../FarmManagerMobile" && pwd)"
CLIENT_FILE="$PROJECT_DIR/src/api/client.ts"
RESET_CACHE=false
API_URL=""

PROD_API_URL="http://47.98.253.236:8000"
COMPANY_API_URL="http://172.16.57.244:8099"
HOME_API_URL="http://10.167.110.141:8099"

for arg in "$@"; do
    case "$arg" in
        --reset-cache) RESET_CACHE=true ;;
        --local) API_URL="$COMPANY_API_URL" ;;
        --home)  API_URL="$HOME_API_URL" ;;
    esac
done

# 未指定 API 地址时，默认使用生产地址
[ -z "$API_URL" ] && API_URL="$PROD_API_URL"

echo "========================================"
echo "  FarmManagerMobile — Android 启动"
echo "  API 地址: $API_URL"
echo "========================================"

# 1. 更新 API 地址
echo "→ 更新 API 地址..."
if [ -f "$CLIENT_FILE" ]; then
    CURRENT_URL=$(grep -oP "const API_BASE_URL = '\K[^']*" "$CLIENT_FILE" 2>/dev/null || true)
    if [ "$CURRENT_URL" = "$API_URL" ]; then
        echo "  API 地址已是 $API_URL，无需修改"
    else
        sed -i '' "s|const API_BASE_URL = '.*';|const API_BASE_URL = '${API_URL}';|" "$CLIENT_FILE"
        echo "  已切换为: $API_URL"
    fi
else
    echo "  警告: 未找到 $CLIENT_FILE"
fi

# 2. 清理已有 Metro（避免端口 8081 冲突）
echo "→ 检查已有 Metro 进程..."
METRO_PIDS=$(lsof -ti:8081 2>/dev/null || true)
if [ -n "$METRO_PIDS" ]; then
    echo "  清理占用 8081 端口的进程..."
    kill -9 $METRO_PIDS 2>/dev/null || true
    sleep 1
fi

# 3. 启动 Android 应用（--no-packager 不自动启 Metro，我们自己启）
echo "→ 启动 Android 应用..."
cd "$PROJECT_DIR"
npx react-native run-android --no-packager &
APP_PID=$!

# 4. 等待应用编译
echo "→ 等待应用编译..."
sleep 5

# 5. 前台启动 Metro（热更新在此生效）
echo "→ 启动 Metro bundler..."
echo ""
echo "  实时热更新已开启"
echo "  修改代码保存后自动刷新"
echo ""
echo "  快捷键: r=刷新 | d=开发者菜单 | Ctrl+C=停止"
echo "========================================"
echo ""

if [ "$RESET_CACHE" = true ]; then
    npx react-native start --reset-cache
else
    npx react-native start
fi
