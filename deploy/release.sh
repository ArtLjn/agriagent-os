#!/bin/bash
# FarmManager 一键发版脚本
# 用法:
#   ./release.sh                                    — 自动 bump 补丁版本
#   ./release.sh --version=1.2.0                    — 指定版本号
#   ./release.sh --changelog="修复记账刷新问题"      — 指定更新说明
#   ./release.sh --skip-build                        — 跳过构建（仅推送已打好的 APK）
#
# 完整流程: bump 版本 → 构建APK → 创建 Gitee Release → 上传 APK

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
VERSION_FILE="$PROJECT_ROOT/VERSION"
APK_REPO="morning-ljn/farm-manager-dev-apk"
APK_FILENAME="app-release.apk"

# 从环境变量或默认值读取 Gitee Token
GITEE_TOKEN="${GITEE_TOKEN:-}"

# 参数解析
TARGET_VERSION=""
CHANGELOG=""
SKIP_BUILD=false

for arg in "$@"; do
  case "$arg" in
    --version=*)     TARGET_VERSION="${arg#--version=}" ;;
    --changelog=*)   CHANGELOG="${arg#--changelog=}" ;;
    --skip-build)    SKIP_BUILD=true ;;
    --token=*)       GITEE_TOKEN="${arg#--token=}" ;;
    *)               echo "未知参数: $arg"; exit 1 ;;
  esac
done

# 检查 Gitee Token
if [ -z "$GITEE_TOKEN" ]; then
  echo "错误: 需要提供 Gitee Token"
  echo "  用法: GITEE_TOKEN=xxx ./release.sh"
  echo "  或:   ./release.sh --token=xxx"
  exit 1
fi

# 读取当前版本
if [ ! -f "$VERSION_FILE" ]; then
  echo "错误: 找不到 VERSION 文件"
  exit 1
fi
source "$VERSION_FILE"
OLD_VERSION="${VERSION_NAME:-1.0.0}"
OLD_CODE="${VERSION_CODE:-1}"

# 计算新版本号
if [ -n "$TARGET_VERSION" ]; then
  NEW_VERSION="$TARGET_VERSION"
else
  # 自动 bump 补丁版本: 1.0.0 → 1.0.1
  IFS='.' read -r major minor patch <<< "$OLD_VERSION"
  NEW_VERSION="${major}.${minor}.$((patch + 1))"
fi
NEW_CODE=$((OLD_CODE + 1))

if [ -z "$CHANGELOG" ]; then
  CHANGELOG="更新至 v${NEW_VERSION}"
fi

echo "========================================="
echo " Farm Manager 发版"
echo "========================================="
echo " 版本: v${OLD_VERSION} (${OLD_CODE}) → v${NEW_VERSION} (${NEW_CODE})"
echo " 更新说明: ${CHANGELOG}"
echo "========================================="

# 1. 更新 VERSION 文件
echo ""
echo "[1/4] 更新 VERSION 文件..."
cat > "$VERSION_FILE" << EOF
VERSION_NAME=${NEW_VERSION}
VERSION_CODE=${NEW_CODE}
CHANGELOG=${CHANGELOG}
EOF
echo "  已写入: v${NEW_VERSION} (${NEW_CODE})"

# 2. 构建 APK
APK_PATH=""
if [ "$SKIP_BUILD" = true ]; then
  echo ""
  echo "[2/4] 跳过构建，查找已有 APK..."
  APK_PATH=$(find "$PROJECT_ROOT" -maxdepth 1 -name "FarmManager-v*-release.apk" -newer "$VERSION_FILE" 2>/dev/null | head -1)
  if [ -z "$APK_PATH" ]; then
    APK_PATH=$(find "$PROJECT_ROOT" -maxdepth 1 -name "FarmManager-v*-release.apk" 2>/dev/null | head -1)
  fi
  if [ -z "$APK_PATH" ]; then
    echo "  错误: 找不到 APK 文件，请先运行 ./deploy/build-apk.sh"
    exit 1
  fi
  echo "  使用: $APK_PATH"
else
  echo ""
  echo "[2/4] 构建 APK..."
  bash "$PROJECT_ROOT/deploy/build-apk.sh"
  APK_PATH="$PROJECT_ROOT/FarmManager-v${NEW_VERSION}-release.apk"
  if [ ! -f "$APK_PATH" ]; then
    # 兜底：找最新的
    APK_PATH=$(ls -t "$PROJECT_ROOT"/FarmManager-*release.apk 2>/dev/null | head -1)
  fi
  if [ -z "$APK_PATH" ] || [ ! -f "$APK_PATH" ]; then
    echo "  错误: APK 构建失败"
    exit 1
  fi
  echo "  APK: $APK_PATH ($(du -h "$APK_PATH" | cut -f1))"
fi

# 3. 创建 Gitee Release
echo ""
echo "[3/4] 创建 Gitee Release v${NEW_VERSION}..."
RELEASE_RESP=$(curl -s -X POST \
  "https://gitee.com/api/v5/repos/${APK_REPO}/releases" \
  -d "access_token=${GITEE_TOKEN}" \
  -d "tag_name=v${NEW_VERSION}" \
  -d "name=v${NEW_VERSION}" \
  -d "body=${CHANGELOG}" \
  -d "target_commitish=main")

RELEASE_ID=$(echo "$RELEASE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || true)
if [ -z "$RELEASE_ID" ]; then
  echo "  错误: 创建 Release 失败"
  echo "$RELEASE_RESP" | python3 -m json.tool 2>/dev/null || echo "$RELEASE_RESP"
  exit 1
fi
echo "  Release ID: $RELEASE_ID"

# 4. 上传 APK 到 Release
echo ""
echo "[4/4] 上传 APK..."
UPLOAD_RESP=$(curl -s -X POST \
  "https://gitee.com/api/v5/repos/${APK_REPO}/releases/${RELEASE_ID}/attach_files" \
  -H "Content-Type: multipart/form-data" \
  -F "access_token=${GITEE_TOKEN}" \
  -F "file=@${APK_PATH};filename=${APK_FILENAME}")

DOWNLOAD_URL=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('url','') if isinstance(d,list) else d.get('url',''))" 2>/dev/null || true)
if [ -n "$DOWNLOAD_URL" ]; then
  echo "  上传成功!"
else
  echo "  警告: 上传可能失败，请手动检查"
  echo "$UPLOAD_RESP" | python3 -m json.tool 2>/dev/null || echo "$UPLOAD_RESP"
fi

echo ""
echo "========================================="
echo " 发版完成!"
echo "========================================="
echo " 版本:       v${NEW_VERSION} (${NEW_CODE})"
echo " 更新说明:   ${CHANGELOG}"
echo " 下载链接:   https://gitee.com/${APK_REPO}/releases/tag/v${NEW_VERSION}"
echo ""
echo " 下一步:"
echo "   1. git add VERSION && git commit -m 'release: v${NEW_VERSION}'"
echo "   2. 部署后端 (VERSION 文件已更新，/api/app/version 会返回新版本)"
echo "========================================="
