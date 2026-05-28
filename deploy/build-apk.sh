#!/bin/bash
# FarmManagerMobile APK 打包脚本
# 用法:
#   ./build-apk.sh              — 打 release APK (默认指向阿里云)
#   ./build-apk.sh --debug      — 打 debug APK
#   ./build-apk.sh --api=URL    — 自定义 API 地址
#   ./build-apk.sh --local      — 使用局域网地址 (172.16.57.244)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
MOBILE_DIR="$PROJECT_ROOT/FarmManagerMobile"
CLIENT_FILE="$MOBILE_DIR/src/api/client.ts"
ANDROID_DIR="$MOBILE_DIR/android"
OUTPUT_DIR="$MOBILE_DIR/android/app/build/outputs/apk"

# 默认 API 地址
PROD_API_URL="http://47.98.253.236:8000"
COMPANY_API_URL="http://172.16.57.244:8099"
HOME_API_URL="http://10.167.110.141:8099"
API_URL="$PROD_API_URL"
BUILD_TYPE="release"

# 解析参数
for arg in "$@"; do
  case "$arg" in
    --debug)   BUILD_TYPE="debug" ;;
    --local)   API_URL="$COMPANY_API_URL" ;;
    --home)    API_URL="$HOME_API_URL" ;;
    --api=*)   API_URL="${arg#--api=}" ;;
    *)         echo "未知参数: $arg"; exit 1 ;;
  esac
done

echo "========================================="
echo " FarmManagerMobile APK 打包"
echo "========================================="
echo " 构建类型: $BUILD_TYPE"
echo " API 地址: $API_URL"
echo "========================================="

# 1. 更新 API 地址
echo ""
echo "[1/5] 更新 API 地址..."
CURRENT_URL=$(grep -oP "const API_BASE_URL = '\K[^']*" "$CLIENT_FILE" 2>/dev/null || true)
if [ "$CURRENT_URL" = "$API_URL" ]; then
  echo "  API 地址已是 $API_URL，无需修改"
else
  sed -i '' "s|const API_BASE_URL = '.*';|const API_BASE_URL = '${API_URL}';|" "$CLIENT_FILE"
  echo "  已切换为: $API_URL"
fi

# 2. 安装依赖
echo ""
echo "[2/5] 安装 npm 依赖..."
cd "$MOBILE_DIR"
if [ ! -d "node_modules" ] || [ package.json -nt node_modules/.package-lock.json ] 2>/dev/null; then
  npm install
else
  echo "  依赖已是最新"
fi

# 3. 清理旧构建
echo ""
echo "[3/5] 清理旧构建..."
cd "$ANDROID_DIR"
./gradlew clean 2>/dev/null
echo "  清理完成"

# 4. 构建 APK
echo ""
echo "[4/5] 开始构建 ${BUILD_TYPE} APK..."
if [ "$BUILD_TYPE" = "release" ]; then
  ./gradlew assembleRelease --warning-mode none
else
  ./gradlew assembleDebug --warning-mode none
fi

# 5. 输出结果
echo ""
echo "[5/5] 构建完成!"
echo "========================================="

# 查找 APK 文件
APK_FILE="$OUTPUT_DIR/${BUILD_TYPE}/app-${BUILD_TYPE}.apk"
if [ -f "$APK_FILE" ]; then
  APK_SIZE=$(du -h "$APK_FILE" | cut -f1)
  # 复制到项目根目录方便查找
  COPY_NAME="FarmManager-${BUILD_TYPE}-$(date +%Y%m%d%H%M).apk"
  cp "$APK_FILE" "$PROJECT_ROOT/$COPY_NAME"
  echo " APK 大小: $APK_SIZE"
  echo " 原始路径: $APK_FILE"
  echo " 复制到:   $PROJECT_ROOT/$COPY_NAME"
else
  echo " 未找到 APK，请检查构建日志"
  exit 1
fi

echo "========================================="
echo ""
echo "如需安装到连接的设备:"
echo "  adb install $APK_FILE"
echo ""
echo "如需推送到阿里云服务器:"
echo "  scp $APK_FILE root@47.98.253.236:/tmp/"
