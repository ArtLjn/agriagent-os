#!/bin/bash
# FarmManagerMobile APK 安装脚本
# 自动查找最新 APK 并安装到连接的设备/模拟器

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APK_PATTERN="$PROJECT_ROOT/FarmManager-*.apk"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. 检查 adb 是否可用
if ! command -v adb &> /dev/null; then
    log_err "adb 命令未找到，请安装 Android SDK 并添加到 PATH"
    exit 1
fi
log_ok "adb 已就绪"

# 2. 检查设备连接
DEVICES=$(adb devices | grep -v "List of devices" | grep "device$" | wc -l | tr -d ' ')
if [ "$DEVICES" -eq 0 ]; then
    log_err "没有检测到连接的设备/模拟器"
    echo "  请连接设备或启动模拟器后重试"
    exit 1
fi

if [ "$DEVICES" -gt 1 ]; then
    log_warn "检测到 $DEVICES 个设备，将安装到第一个设备"
fi
DEVICE_SERIAL=$(adb devices | grep -v "List of devices" | grep "device$" | head -1 | awk '{print $1}')
log_ok "目标设备: $DEVICE_SERIAL"

# 3. 查找最新 APK
if [ -n "${1:-}" ]; then
    # 用户指定了 APK 路径
    APK_FILE="$1"
    if [ ! -f "$APK_FILE" ]; then
        log_err "指定的 APK 不存在: $APK_FILE"
        exit 1
    fi
else
    # 自动查找最新 APK
    APK_FILE=$(ls -t $APK_PATTERN 2>/dev/null | head -1)
    if [ -z "$APK_FILE" ]; then
        log_err "未找到 APK 文件，请先运行 ./build-apk.sh 构建"
        echo "  搜索路径: $APK_PATTERN"
        exit 1
    fi
fi

APK_NAME=$(basename "$APK_FILE")
APK_SIZE=$(du -h "$APK_FILE" | cut -f1)
log_ok "找到 APK: $APK_NAME ($APK_SIZE)"

# 4. 检查应用是否已安装，如果是则先卸载
PACKAGE_NAME="com.farmmanagermobile"
if adb -s "$DEVICE_SERIAL" shell pm list packages | grep -q "$PACKAGE_NAME"; then
    log_warn "应用已安装，先卸载旧版本..."
    adb -s "$DEVICE_SERIAL" uninstall "$PACKAGE_NAME" || true
fi

# 5. 安装 APK
log_info "正在安装..."
if adb -s "$DEVICE_SERIAL" install -r "$APK_FILE"; then
    log_ok "安装成功!"
else
    log_err "安装失败"
    exit 1
fi

# 6. 启动应用
log_info "启动应用..."
adb -s "$DEVICE_SERIAL" shell am start -n "$PACKAGE_NAME/.MainActivity" || true

log_ok "完成! 应用已安装并启动"
