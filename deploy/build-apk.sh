#!/bin/bash
# FarmManager Flutter APK 打包脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MOBILE_DIR="$PROJECT_ROOT/mobile-app"
OUTPUT_DIR="$MOBILE_DIR/build/app/outputs/flutter-apk"
DIST_DIR="$PROJECT_ROOT"
APP_NAME="FarmManager"
GRADLE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}/farm-manager/gradle"

# 默认 API 地址
PROD_API_URL="https://api.farm.lllcnm.cn"
COMPANY_API_URL="http://172.16.57.244:8099"
HOME_API_URL="http://10.167.110.141:8099"
API_URL="$PROD_API_URL"
BUILD_TYPE="release"
DRY_RUN=0
SKIP_PUB_GET=0
CLEAN_BUILD=0

usage() {
  cat <<'EOF'
用法:
  deploy/build-apk.sh [选项]

构建选项:
  --release              打 release APK（默认）
  --debug                打 debug APK
  --clean                构建前执行 flutter clean
  --skip-pub-get         跳过 flutter pub get
  --dry-run              只打印将执行的构建命令，不真正打包
  --gradle-home DIR      指定隔离的 Gradle 缓存目录（默认 ~/.cache/farm-manager/gradle）

API 地址:
  --api URL              自定义 API 地址
  --api=URL              自定义 API 地址
  --local                使用公司局域网地址
  --home                 使用家庭局域网地址

输出:
  --output-dir DIR       复制 APK 到指定目录（默认项目根目录）

其他:
  -h, --help             显示帮助
EOF
}

log_step() {
  printf '\n[%s/%s] %s\n' "$1" "$2" "$3"
}

fail() {
  echo "错误: $*" >&2
  echo "使用 --help 查看用法" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "未找到命令: $1"
  fi
}

read_version_name() {
  local version_name
  version_name="$(grep -E '^VERSION_NAME=' "$PROJECT_ROOT/VERSION" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  if [ -n "$version_name" ]; then
    echo "$version_name"
    return
  fi

  version_name="$(grep -E '^version:' "$MOBILE_DIR/pubspec.yaml" | head -1 | awk '{print $2}' | cut -d+ -f1)"
  echo "${version_name:-latest}"
}

resolve_apk_file() {
  local expected="$OUTPUT_DIR/app-${BUILD_TYPE}.apk"
  if [ -f "$expected" ]; then
    echo "$expected"
    return
  fi

  find "$OUTPUT_DIR" -maxdepth 1 -type f -name "*.apk" -print 2>/dev/null | sort | head -1
}

# 解析参数
while [ "$#" -gt 0 ]; do
  case "$1" in
    --release) BUILD_TYPE="release"; shift ;;
    --debug) BUILD_TYPE="debug"; shift ;;
    --clean) CLEAN_BUILD=1; shift ;;
    --skip-pub-get) SKIP_PUB_GET=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --gradle-home=*)
      GRADLE_HOME="${1#--gradle-home=}"
      [ -n "$GRADLE_HOME" ] || fail "--gradle-home 不能为空"
      shift
      ;;
    --gradle-home)
      shift
      [ -n "${1:-}" ] || fail "--gradle-home 需要提供目录"
      GRADLE_HOME="$1"
      shift
      ;;
    --local) API_URL="$COMPANY_API_URL"; shift ;;
    --home) API_URL="$HOME_API_URL"; shift ;;
    --api=*)
      API_URL="${1#--api=}"
      [ -n "$API_URL" ] || fail "--api 不能为空"
      shift
      ;;
    --api)
      shift
      [ -n "${1:-}" ] || fail "--api 需要提供 URL"
      API_URL="$1"
      shift
      ;;
    --output-dir=*)
      DIST_DIR="${1#--output-dir=}"
      [ -n "$DIST_DIR" ] || fail "--output-dir 不能为空"
      shift
      ;;
    --output-dir)
      shift
      [ -n "${1:-}" ] || fail "--output-dir 需要提供目录"
      DIST_DIR="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      echo "使用 --help 查看用法" >&2
      exit 1
      ;;
  esac
done

if [[ "$API_URL" != http://* && "$API_URL" != https://* ]]; then
  fail "API 地址必须以 http:// 或 https:// 开头: $API_URL"
fi

if [[ "$DIST_DIR" != /* ]]; then
  DIST_DIR="$PROJECT_ROOT/$DIST_DIR"
fi

if [[ "$GRADLE_HOME" != /* ]]; then
  GRADLE_HOME="$PROJECT_ROOT/$GRADLE_HOME"
fi

VERSION_NAME="$(read_version_name)"
TIMESTAMP="$(date +%Y%m%d%H%M)"
COPY_NAME="${APP_NAME}-v${VERSION_NAME}-${BUILD_TYPE}-${TIMESTAMP}.apk"
COPY_PATH="$DIST_DIR/$COPY_NAME"
BUILD_MODE_FLAG="--$BUILD_TYPE"

echo "========================================="
echo " FarmManager Flutter APK 打包"
echo "========================================="
echo " 构建类型: $BUILD_TYPE"
echo " API 地址: $API_URL"
echo " 应用版本: v$VERSION_NAME"
echo " 输出目录: $DIST_DIR"
echo " Gradle缓存: $GRADLE_HOME"
echo "========================================="

if [ ! -d "$MOBILE_DIR" ]; then
  fail "未找到 Flutter 项目目录: $MOBILE_DIR"
fi

BUILD_COMMAND=(
  flutter build apk "$BUILD_MODE_FLAG"
  "--dart-define=API_BASE_URL=$API_URL"
)

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  echo "DRY RUN: 将执行以下操作"
  echo "  cd $MOBILE_DIR"
  if [ "$CLEAN_BUILD" -eq 1 ]; then
    echo "  flutter clean"
  fi
  if [ "$SKIP_PUB_GET" -eq 0 ]; then
    echo "  flutter pub get"
  fi
  printf '  GRADLE_USER_HOME=%q' "$GRADLE_HOME"
  printf ' %q' "${BUILD_COMMAND[@]}"
  printf '\n'
  echo "  cp <APK> $COPY_PATH"
  exit 0
fi

require_command flutter
mkdir -p "$DIST_DIR"
mkdir -p "$GRADLE_HOME"
cd "$MOBILE_DIR"

TOTAL_STEPS=3
CURRENT_STEP=1

if [ "$CLEAN_BUILD" -eq 1 ]; then
  TOTAL_STEPS=$((TOTAL_STEPS + 1))
fi

if [ "$SKIP_PUB_GET" -eq 1 ]; then
  TOTAL_STEPS=$((TOTAL_STEPS - 1))
fi

if [ "$CLEAN_BUILD" -eq 1 ]; then
  log_step "$CURRENT_STEP" "$TOTAL_STEPS" "清理 Flutter 构建缓存..."
  flutter clean
  CURRENT_STEP=$((CURRENT_STEP + 1))
fi

if [ "$SKIP_PUB_GET" -eq 0 ]; then
  log_step "$CURRENT_STEP" "$TOTAL_STEPS" "安装 Flutter 依赖..."
  flutter pub get
  CURRENT_STEP=$((CURRENT_STEP + 1))
fi

# 使用隔离但持久的 GRADLE_USER_HOME，避开全局 init.gradle，同时复用 Gradle 下载缓存。
log_step "$CURRENT_STEP" "$TOTAL_STEPS" "开始构建 ${BUILD_TYPE} APK..."
GRADLE_USER_HOME="$GRADLE_HOME" "${BUILD_COMMAND[@]}"
CURRENT_STEP=$((CURRENT_STEP + 1))

log_step "$CURRENT_STEP" "$TOTAL_STEPS" "整理 APK 产物..."
echo "========================================="

# 查找 APK 文件
APK_FILE="$(resolve_apk_file)"

if [ -n "$APK_FILE" ] && [ -f "$APK_FILE" ]; then
  APK_SIZE=$(du -h "$APK_FILE" | cut -f1)
  cp "$APK_FILE" "$COPY_PATH"
  echo " APK 大小: $APK_SIZE"
  echo " 原始路径: $APK_FILE"
  echo " 复制到:   $COPY_PATH"
else
  echo " 未找到 APK，请检查构建日志"
  ls -la "$OUTPUT_DIR/" 2>/dev/null || true
  exit 1
fi

echo "========================================="
echo ""
echo "如需安装到连接的设备:"
echo "  adb install -r \"$COPY_PATH\""
echo ""
echo "如需推送到阿里云服务器:"
echo "  deploy/upload-apk.sh \"$COPY_PATH\" \"$VERSION_NAME\""
