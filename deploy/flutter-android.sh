#!/usr/bin/env bash
# 一键启动 Flutter Android App，默认连接 Pixel_7 / emulator-5554，支持热重载。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/mobile-app"
DEVICE_ID="emulator-5554"
EMULATOR_ID="Pixel_7"

cd "$APP_DIR"

export GRADLE_USER_HOME="${GRADLE_USER_HOME:-/tmp/codex-gradle-home}"

if ! adb devices | grep -q "^${DEVICE_ID}[[:space:]]*device"; then
  echo "启动安卓模拟器：$EMULATOR_ID"
  flutter emulators --launch "$EMULATOR_ID"
  adb wait-for-device
  until [ "$(adb -s "$DEVICE_ID" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
    sleep 2
  done
fi

adb -s "$DEVICE_ID" reverse tcp:8000 tcp:8000 >/dev/null 2>&1 || true

echo "启动 Flutter App：$DEVICE_ID"
echo "热重载：按 r    热重启：按 R    退出：按 q    保留 App 运行：按 d"

flutter run -d "$DEVICE_ID" --hot
