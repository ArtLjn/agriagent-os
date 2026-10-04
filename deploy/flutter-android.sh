#!/usr/bin/env bash
# 一键启动 Flutter Android App，默认连接 Pixel 9 Pro XL / emulator-5554，支持热重载。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/agri_mobile_app"
DEVICE_ID="${DEVICE_ID:-emulator-5554}"
EMULATOR_ID="${EMULATOR_ID:-Pixel_9_Pro_XL}"
# Android 模拟器通过 10.0.2.2 访问电脑回环地址；USB 真机使用 ADB 转发。
LOCAL_API_HOST="127.0.0.1"
if [[ "$DEVICE_ID" == emulator-* ]]; then
  LOCAL_API_HOST="10.0.2.2"
fi
BUSINESS_API_URL="${BUSINESS_API_URL:-http://$LOCAL_API_HOST:9876/api/v2}"
AGENT_API_URL="${AGENT_API_URL:-http://$LOCAL_API_HOST:8000/api/v2}"

cd "$APP_DIR"

export GRADLE_USER_HOME="${GRADLE_USER_HOME:-/tmp/codex-gradle-home}"

if [ -x "$APP_DIR/android/gradlew" ]; then
  "$APP_DIR/android/gradlew" --stop >/dev/null 2>&1 || true
fi

GRADLE_WORK_CACHE_DIR="$GRADLE_USER_HOME/caches/8.14"
if [ -d "$GRADLE_WORK_CACHE_DIR" ]; then
  echo "清理 Gradle 8.14 可再生工作缓存：$GRADLE_WORK_CACHE_DIR"
  rm -rf "$GRADLE_WORK_CACHE_DIR" 2>/dev/null || {
    sleep 1
    rm -rf "$GRADLE_WORK_CACHE_DIR" 2>/dev/null || true
  }
fi

if ! adb devices | grep -q "^${DEVICE_ID}[[:space:]]*device"; then
  echo "启动安卓模拟器：$EMULATOR_ID"
  flutter emulators --launch "$EMULATOR_ID"
  adb wait-for-device
  until [ "$(adb -s "$DEVICE_ID" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
    sleep 2
  done
fi

for api_url in "$BUSINESS_API_URL" "$AGENT_API_URL"; do
  # 仅本机地址需要隧道，自定义远程服务器仍直接连接。
  if [[ "$api_url" =~ ^https?://(127\.0\.0\.1|localhost):([0-9]+)(/|$) ]]; then
    api_port="${BASH_REMATCH[2]}"
    if ! adb -s "$DEVICE_ID" reverse "tcp:$api_port" "tcp:$api_port"; then
      echo "错误 [BACKEND_TUNNEL_FAILED]：设备 $DEVICE_ID 无法转发本机后端端口 $api_port" >&2
      exit 1
    fi
    echo "本机后端转发：$DEVICE_ID tcp:$api_port → 电脑 tcp:$api_port"
  fi
done

echo "启动 Flutter App：$DEVICE_ID"
echo "Business API：$BUSINESS_API_URL"
echo "Agent API：$AGENT_API_URL"
echo "热重载：按 r    热重启：按 R    退出：按 q    保留 App 运行：按 d"

flutter run \
  -d "$DEVICE_ID" \
  --hot \
  --dart-define=BUSINESS_API_BASE_URL="$BUSINESS_API_URL" \
  --dart-define=AGENT_API_BASE_URL="$AGENT_API_URL"
