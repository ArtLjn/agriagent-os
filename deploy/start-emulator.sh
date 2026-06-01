#!/bin/bash
# Android 模拟器启动脚本
# 用法:
#   ./start-emulator.sh              — 启动默认 AVD (Pixel_7)
#   ./start-emulator.sh --list       — 列出所有 AVD
#   ./start-emulator.sh --cold       — 冷启动（清除快照）
#   ./start-emulator.sh --name=xxx   — 启动指定 AVD

set -euo pipefail

EMULATOR="$HOME/Library/Android/sdk/emulator/emulator"
ADB="$HOME/Library/Android/sdk/platform-tools/adb"

# 检查工具
if [ ! -f "$EMULATOR" ]; then
  echo "错误: 找不到 emulator 工具"
  echo "  路径: $EMULATOR"
  echo "  请确认 Android SDK 已安装"
  exit 1
fi

# 列出 AVD
if [ "${1:-}" = "--list" ]; then
  echo "可用 AVD 列表:"
  "$EMULATOR" -list-avds | while read -r avd; do
    echo "  • $avd"
  done
  exit 0
fi

# 解析参数
AVD_NAME="Pixel_7"
COLD_BOOT=false

for arg; do
  case "$arg" in
    --cold)      COLD_BOOT=true ;;
    --name=*)    AVD_NAME="${arg#--name=}" ;;
    --help|-h)   echo "用法: $0 [--list] [--cold] [--name=AVD_NAME]"; exit 0 ;;
    *)           echo "未知参数: $arg"; exit 1 ;;
  esac
done

# 检查 AVD 是否存在
if ! "$EMULATOR" -list-avds | grep -qx "$AVD_NAME"; then
  echo "错误: AVD '$AVD_NAME' 不存在"
  echo ""
  echo "可用 AVD:"
  "$EMULATOR" -list-avds | while read -r avd; do
    echo "  • $avd"
  done
  exit 1
fi

echo "========================================="
echo " Android 模拟器启动"
echo "========================================="
echo " AVD:      $AVD_NAME"
echo " 冷启动:   $COLD_BOOT"
echo "========================================="

# 构建启动参数
ARGS="-avd $AVD_NAME -gpu auto -no-boot-anim"
if [ "$COLD_BOOT" = true ]; then
  ARGS="$ARGS -no-snapshot-load"
  echo " [冷启动模式 — 跳过快照加载]"
fi

# 后台启动模拟器
nohup "$EMULATOR" $ARGS > /tmp/emulator-$AVD_NAME.log 2>&1 &
echo ""
echo " 模拟器已在后台启动..."
echo " 日志: /tmp/emulator-$AVD_NAME.log"
echo ""

# 等待设备上线
echo " 等待设备就绪..."
for i in {1..60}; do
  if [ -f "$ADB" ] && "$ADB" devices | grep -q "emulator"; then
    DEVICE_STATE=$($ADB shell getprop sys.boot_completed 2>/dev/null || true)
    if [ "$DEVICE_STATE" = "1" ]; then
      echo ""
      echo " 模拟器已就绪!"
      echo "========================================="
      "$ADB" devices
      echo "========================================="
      exit 0
    fi
  fi
  printf "."
  sleep 1
done

echo ""
echo " 警告: 等待超时，模拟器可能还在启动中"
echo " 请稍后手动检查: adb devices"
