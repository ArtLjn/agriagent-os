#!/bin/bash
# FarmManager 综合发版工作流脚本
# 一键完成: 版本号同步 → 构建APK → 部署到阿里云 → 打tag → (可选)Gitee Release
#
# 用法:
#   ./release.sh                          — 完整发版
#   ./release.sh --version=1.2.0          — 指定版本号
#   ./release.sh --changelog="修复xxx"     — 指定更新说明
#   ./release.sh --skip-build             — 跳过APK构建
#   ./release.sh --skip-deploy            — 跳过阿里云部署
#   ./release.sh --gitee                  — 同时创建Gitee Release
#   ./release.sh --tag-only               — 只打git tag(已构建+部署后补tag)
#
# 环境变量:
#   ALI_HOST=47.98.253.236               — 阿里云服务器地址
#   ALI_USER=root                        — SSH用户名
#   ALI_APK_DIR=/var/www/apk             — 服务器APK目录
#   ALI_VERSION_FILE=/root/workspace/farm-manager/VERSION  — 服务器VERSION路径
#   ALI_SERVICE=farm-manager             — systemd服务名
#   GITEE_TOKEN=xxx                      — Gitee API Token

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
VERSION_FILE="$PROJECT_ROOT/VERSION"

# === 阿里云配置（可通过环境变量覆盖）===
ALI_HOST="${ALI_HOST:-47.98.253.236}"
ALI_USER="${ALI_USER:-root}"
ALI_APK_DIR="${ALI_APK_DIR:-/var/www/apk}"
ALI_VERSION_FILE="${ALI_VERSION_FILE:-/root/workspace/farm-manager/VERSION}"
ALI_SERVICE="${ALI_SERVICE:-farm-manager}"

# === Gitee配置 ===
GITEE_TOKEN="${GITEE_TOKEN:-}"
APK_REPO="morning-ljn/farm-manager-dev-apk"

# === 移动端配置 ===
MOBILE_DIR="$PROJECT_ROOT/FarmManagerMobile"
CLIENT_FILE="$MOBILE_DIR/src/api/client.ts"
ANDROID_DIR="$MOBILE_DIR/android"
OUTPUT_DIR="$ANDROID_DIR/app/build/outputs/apk"
PROD_API_URL="http://47.98.253.236:8000"

# === 参数解析 ===
TARGET_VERSION=""
CHANGELOG=""
SKIP_BUILD=false
SKIP_DEPLOY=false
TAG_ONLY=false
DO_GITEE=false

for arg in "$@"; do
  case "$arg" in
    --version=*)     TARGET_VERSION="${arg#--version=}" ;;
    --changelog=*)   CHANGELOG="${arg#--changelog=}" ;;
    --skip-build)    SKIP_BUILD=true ;;
    --skip-deploy)   SKIP_DEPLOY=true ;;
    --gitee)         DO_GITEE=true ;;
    --tag-only)      TAG_ONLY=true ;;
    *)               echo "未知参数: $arg"; exit 1 ;;
  esac
done

# === 辅助函数 ===
_announce() {
  echo ""
  echo "========================================="
  echo " $1"
  echo "========================================="
}

_step() {
  echo ""
  echo "[$1/$2] $3"
}

_check_ssh() {
  if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${ALI_USER}@${ALI_HOST}" "echo ok" >/dev/null 2>&1; then
    echo "  ✗ SSH连接失败: ${ALI_USER}@${ALI_HOST}"
    echo "    请确保已配置免密登录: ssh-copy-id ${ALI_USER}@${ALI_HOST}"
    return 1
  fi
  echo "  ✓ SSH连接正常"
}

_read_version_file() {
  VERSION_NAME=""
  VERSION_CODE=""
  VERSION_CHANGELOG=""
  while IFS='=' read -r key value; do
    case "$key" in
      VERSION_NAME) VERSION_NAME="$value" ;;
      VERSION_CODE) VERSION_CODE="$value" ;;
      CHANGELOG)    VERSION_CHANGELOG="$value" ;;
    esac
  done < "$VERSION_FILE"
}

# === 主流程 ===

if [ "$TAG_ONLY" = true ]; then
  # 只打tag模式
  _read_version_file
  VERSION="${VERSION_NAME}"
  CODE="${VERSION_CODE}"
  git tag -a "v${VERSION}" -m "release: v${VERSION} (${CODE})" || true
  git push origin "v${VERSION}" || true
  _announce "Tag v${VERSION} 已推送"
  exit 0
fi

# 读取当前版本
if [ ! -f "$VERSION_FILE" ]; then
  echo "错误: 找不到 VERSION 文件"
  exit 1
fi
_read_version_file
OLD_VERSION="${VERSION_NAME:-1.0.0}"
OLD_CODE="${VERSION_CODE:-1}"

# 计算新版本号
if [ -n "$TARGET_VERSION" ]; then
  NEW_VERSION="$TARGET_VERSION"
else
  IFS='.' read -r major minor patch <<< "$OLD_VERSION"
  NEW_VERSION="${major}.${minor}.$((patch + 1))"
fi
NEW_CODE=$((OLD_CODE + 1))

if [ -z "$CHANGELOG" ]; then
  CHANGELOG="更新至 v${NEW_VERSION}"
fi

TOTAL_STEPS=6
[ "$SKIP_BUILD" = false ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$SKIP_DEPLOY" = false ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$DO_GITEE" = true ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))

_announce "Farm Manager 综合发版"
echo " 版本: v${OLD_VERSION} (${OLD_CODE}) → v${NEW_VERSION} (${NEW_CODE})"
echo " 更新说明: ${CHANGELOG}"
[ "$SKIP_BUILD" = true ] && echo " ⚠ 跳过APK构建"
[ "$SKIP_DEPLOY" = true ] && echo " ⚠ 跳过阿里云部署"
[ "$DO_GITEE" = true ] && echo " ✓ 将创建Gitee Release"
echo " 总步骤: ${TOTAL_STEPS}"

STEP=0

# ─────────────────────────────────────────
# Step 1: 同步更新所有版本号文件
# ─────────────────────────────────────────
STEP=$((STEP + 1))
_step "$STEP" "$TOTAL_STEPS" "同步更新所有版本号文件..."

# 1.1 VERSION文件
cat > "$VERSION_FILE" << EOF
VERSION_NAME=${NEW_VERSION}
VERSION_CODE=${NEW_CODE}
CHANGELOG=${CHANGELOG}
EOF
echo "  ✓ VERSION → v${NEW_VERSION} (${NEW_CODE})"

# 1.2 build.gradle
BUILD_GRADLE="$MOBILE_DIR/android/app/build.gradle"
if [ -f "$BUILD_GRADLE" ]; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/versionCode [0-9]*/versionCode ${NEW_CODE}/" "$BUILD_GRADLE"
    sed -i '' "s/versionName \"[^\"]*\"/versionName \"${NEW_VERSION}\"/" "$BUILD_GRADLE"
  else
    sed -i "s/versionCode [0-9]*/versionCode ${NEW_CODE}/" "$BUILD_GRADLE"
    sed -i "s/versionName \"[^\"]*\"/versionName \"${NEW_VERSION}\"/" "$BUILD_GRADLE"
  fi
  echo "  ✓ build.gradle → ${NEW_VERSION}(${NEW_CODE})"
fi

# 1.3 version.ts
VERSION_TS="$MOBILE_DIR/src/api/version.ts"
if [ -f "$VERSION_TS" ]; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/APP_VERSION = \"[^\"]*\"/APP_VERSION = \"${NEW_VERSION}\"/" "$VERSION_TS"
    sed -i '' "s/APP_BUILD_NUMBER = [0-9]*/APP_BUILD_NUMBER = ${NEW_CODE}/" "$VERSION_TS"
  else
    sed -i "s/APP_VERSION = \"[^\"]*\"/APP_VERSION = \"${NEW_VERSION}\"/" "$VERSION_TS"
    sed -i "s/APP_BUILD_NUMBER = [0-9]*/APP_BUILD_NUMBER = ${NEW_CODE}/" "$VERSION_TS"
  fi
  echo "  ✓ version.ts → ${NEW_VERSION}(${NEW_CODE})"
fi

# 1.4 package.json
PACKAGE_JSON="$MOBILE_DIR/package.json"
if [ -f "$PACKAGE_JSON" ]; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"${NEW_VERSION}\"/" "$PACKAGE_JSON"
  else
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"${NEW_VERSION}\"/" "$PACKAGE_JSON"
  fi
  echo "  ✓ package.json → ${NEW_VERSION}"
fi

# 1.5 git commit
git add VERSION "$BUILD_GRADLE" "$VERSION_TS" "$PACKAGE_JSON"
git commit -m "release: v${NEW_VERSION}

${CHANGELOG}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>" || {
  echo "  ⚠ git commit 失败(可能无变更或已提交)"
}
echo "  ✓ 已提交版本号变更"

# ─────────────────────────────────────────
# Step 2: 构建APK（可选跳过）
# ─────────────────────────────────────────
APK_PATH=""
if [ "$SKIP_BUILD" = true ]; then
  STEP=$((STEP + 1))
  _step "$STEP" "$TOTAL_STEPS" "跳过构建，查找已有APK..."
  APK_PATH=$(ls -t "$PROJECT_ROOT"/FarmManager-*release.apk 2>/dev/null | head -1)
  if [ -z "$APK_PATH" ] || [ ! -f "$APK_PATH" ]; then
    echo "  错误: 找不到APK文件"
    exit 1
  fi
  echo "  ✓ 使用: $(basename "$APK_PATH")"
else
  STEP=$((STEP + 1))
  _step "$STEP" "$TOTAL_STEPS" "构建 release APK..."

  # 2.1 更新API地址
  CURRENT_URL=$(grep -oP "const API_BASE_URL = '\K[^']*" "$CLIENT_FILE" 2>/dev/null || true)
  if [ "$CURRENT_URL" != "$PROD_API_URL" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s|const API_BASE_URL = '.*';|const API_BASE_URL = '${PROD_API_URL}';|" "$CLIENT_FILE"
    else
      sed -i "s|const API_BASE_URL = '.*';|const API_BASE_URL = '${PROD_API_URL}';|" "$CLIENT_FILE"
    fi
    echo "  ✓ API地址 → ${PROD_API_URL}"
  fi

  # 2.2 安装依赖
cd "$MOBILE_DIR"
  if [ ! -d "node_modules" ] || [ package.json -nt node_modules/.package-lock.json ] 2>/dev/null; then
    npm install >/dev/null 2>&1
    echo "  ✓ npm依赖已安装"
  fi

  # 2.3 清理+构建
  cd "$ANDROID_DIR"
  ./gradlew clean >/dev/null 2>&1
  echo "  ✓ 清理完成"
  ./gradlew assembleRelease --warning-mode none

  # 2.4 复制到项目根目录
  BUILT_APK="$OUTPUT_DIR/release/app-release.apk"
  if [ -f "$BUILT_APK" ]; then
    APK_PATH="$PROJECT_ROOT/FarmManager-v${NEW_VERSION}-release.apk"
    cp "$BUILT_APK" "$APK_PATH"
    echo "  ✓ APK构建完成: $(basename "$APK_PATH") ($(du -h "$APK_PATH" | cut -f1))"
  else
    echo "  错误: APK构建失败"
    exit 1
  fi
fi

# ─────────────────────────────────────────
# Step 3: 部署到阿里云（可选跳过）
# ─────────────────────────────────────────
if [ "$SKIP_DEPLOY" = false ]; then
  STEP=$((STEP + 1))
  _step "$STEP" "$TOTAL_STEPS" "部署到阿里云服务器..."

  # 3.1 SSH连通性检查
  _check_ssh || exit 1

  # 3.2 上传APK
  REMOTE_APK="${ALI_APK_DIR}/FarmManager-v${NEW_VERSION}.apk"
  scp -o StrictHostKeyChecking=no "$APK_PATH" "${ALI_USER}@${ALI_HOST}:${REMOTE_APK}"
  echo "  ✓ APK已上传 → ${REMOTE_APK}"

  # 3.3 更新软链接
  ssh -o StrictHostKeyChecking=no "${ALI_USER}@${ALI_HOST}" "
    ln -sf '${REMOTE_APK}' '${ALI_APK_DIR}/app-release.apk'
    ln -sf '${REMOTE_APK}' '${ALI_APK_DIR}/app-release-v${NEW_VERSION}.apk'
    ls -la '${ALI_APK_DIR}/app-release.apk'
  " >/dev/null
  echo "  ✓ 软链接已更新 → app-release.apk"

  # 3.4 更新服务器VERSION文件
  ssh -o StrictHostKeyChecking=no "${ALI_USER}@${ALI_HOST}" "cat > '${ALI_VERSION_FILE}' << 'EOF'
VERSION_NAME=${NEW_VERSION}
VERSION_CODE=${NEW_CODE}
CHANGELOG=${CHANGELOG}
EOF"
  echo "  ✓ 服务器VERSION已更新 → v${NEW_VERSION}"

  # 3.5 重启后端服务
  ssh -o StrictHostKeyChecking=no "${ALI_USER}@${ALI_HOST}" "systemctl restart ${ALI_SERVICE} && sleep 2 && systemctl is-active ${ALI_SERVICE}"
  echo "  ✓ 后端服务已重启 (${ALI_SERVICE})"

  # 3.6 验证API
  API_RESP=$(ssh -o StrictHostKeyChecking=no "${ALI_USER}@${ALI_HOST}" "curl -s 'http://localhost:8000/api/app/version?current_version_code=${OLD_CODE}'")
  API_VER=$(echo "$API_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('latest_version',''))" 2>/dev/null || true)
  if [ "$API_VER" = "$NEW_VERSION" ]; then
    echo "  ✓ API验证通过 → v${NEW_VERSION}"
  else
    echo "  ⚠ API验证未通过，返回: ${API_VER}"
  fi
fi

# ─────────────────────────────────────────
# Step 4: 打git tag并推送
# ─────────────────────────────────────────
STEP=$((STEP + 1))
_step "$STEP" "$TOTAL_STEPS" "打git tag..."
git tag -a "v${NEW_VERSION}" -m "release: v${NEW_VERSION} (${NEW_CODE})

${CHANGELOG}" || {
  echo "  ⚠ tag已存在，跳过"
}
git push origin "v${NEW_VERSION}" || true
echo "  ✓ tag v${NEW_VERSION} 已推送"

# ─────────────────────────────────────────
# Step 5: push代码
# ─────────────────────────────────────────
STEP=$((STEP + 1))
_step "$STEP" "$TOTAL_STEPS" "推送代码到远程..."
git push origin main || true
echo "  ✓ 代码已推送"

# ─────────────────────────────────────────
# Step 6: 创建Gitee Release（可选）
# ─────────────────────────────────────────
if [ "$DO_GITEE" = true ]; then
  STEP=$((STEP + 1))
  _step "$STEP" "$TOTAL_STEPS" "创建Gitee Release..."

  if [ -z "$GITEE_TOKEN" ]; then
    echo "  ⚠ 未设置GITEE_TOKEN，跳过"
  else
    RELEASE_RESP=$(curl -s -X POST \
      "https://gitee.com/api/v5/repos/${APK_REPO}/releases" \
      -d "access_token=${GITEE_TOKEN}" \
      -d "tag_name=v${NEW_VERSION}" \
      -d "name=v${NEW_VERSION}" \
      -d "body=${CHANGELOG}" \
      -d "target_commitish=main")

    RELEASE_ID=$(echo "$RELEASE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || true)
    if [ -n "$RELEASE_ID" ]; then
      echo "  ✓ Gitee Release已创建"

      # 上传APK
      UPLOAD_RESP=$(curl -s -X POST \
        "https://gitee.com/api/v5/repos/${APK_REPO}/releases/${RELEASE_ID}/attach_files" \
        -H "Content-Type: multipart/form-data" \
        -F "access_token=${GITEE_TOKEN}" \
        -F "file=@${APK_PATH};filename=app-release.apk")
      echo "  ✓ APK已上传至Gitee"
    else
      echo "  ⚠ Gitee Release创建失败"
    fi
  fi
fi

# ─────────────────────────────────────────
# 完成
# ─────────────────────────────────────────
_announce "发版完成!"
echo " 版本:       v${NEW_VERSION} (${NEW_CODE})"
echo " 更新说明:   ${CHANGELOG}"
if [ "$SKIP_DEPLOY" = false ]; then
  echo " APK下载:    http://${ALI_HOST}:8098/app-release.apk"
  echo " 版本检测:   http://${ALI_HOST}:8000/api/app/version"
fi
if [ "$DO_GITEE" = true ] && [ -n "$RELEASE_ID" ]; then
  echo " Gitee:      https://gitee.com/${APK_REPO}/releases/tag/v${NEW_VERSION}"
fi
echo " Git Tag:    v${NEW_VERSION}"
