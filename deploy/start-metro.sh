#!/bin/bash
# ============================================================
# FarmManagerMobile — Android 开发启动脚本（含实时热更新）
# ============================================================
# 用法:
#   ./deploy/start-metro.sh        # 正常启动
#   ./deploy/start-metro.sh --reset-cache   # 清除缓存后启动
#
# Metro 快捷键（启动后在此终端使用）:
#   r  → 强制刷新
#   d  → 打开开发者菜单
#   a  → 运行 Android
#   Ctrl+C → 停止 Metro
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")/../FarmManagerMobile" && pwd)"
RESET_CACHE=false

for arg in "$@"; do
    case "$arg" in
        --reset-cache) RESET_CACHE=true ;;
    esac
done

echo "========================================"
echo "  FarmManagerMobile — Android 启动"
echo "========================================"

# 1. 清理已有 Metro（避免端口 8081 冲突）
echo "→ 检查已有 Metro 进程..."
METRO_PIDS=$(lsof -ti:8081 2>/dev/null || true)
if [ -n "$METRO_PIDS" ]; then
    echo "  清理占用 8081 端口的进程..."
    kill -9 $METRO_PIDS 2>/dev/null || true
    sleep 1
fi

# 2. 启动 Android 应用（--no-packager 不自动启 Metro，我们自己启）
echo "→ 启动 Android 应用..."
cd "$PROJECT_DIR"
npx react-native run-android --no-packager &
APP_PID=$!

# 3. 等待应用编译
echo "→ 等待应用编译..."
sleep 5

# 4. 前台启动 Metro（热更新在此生效）
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
