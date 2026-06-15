#!/bin/bash
# FarmManager 一键发版脚本
# 流程: 版本自增 → 同步 pubspec → 构建 APK → 上传服务器 → git commit/tag/push
#
# 用法:
#   deploy/release.sh                          # 默认完整发版
#   deploy/release.sh --changelog="修复xxx"     # 指定更新说明
#   deploy/release.sh --remote-dir=/tmp/apk     # 临时指定服务器目录
#   deploy/release.sh --no-build                # 跳过构建(使用已有 APK)
#   deploy/release.sh --no-deploy               # 跳过上传服务器
#   deploy/release.sh --no-tag                  # 跳过 git tag
#
# 环境变量(可选):
#   SERVER_HOST=43.155.217.74      SSH 主机
#   SERVER_USER=root               SSH 用户
#   REMOTE_APK_DIR=/root/workspace/farm-apk  服务器 APK 目录

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$PROJECT_ROOT/VERSION"
PUBSPEC="$PROJECT_ROOT/mobile-app/pubspec.yaml"
APP_NAME="FarmManager"

# === 服务器配置(环境变量覆盖) ===
SERVER_HOST="${SERVER_HOST:-43.155.217.74}"
SERVER_USER="${SERVER_USER:-root}"
REMOTE_APK_DIR="${REMOTE_APK_DIR:-/root/workspace/farm-apk}"
REMOTE_VERSION_FILE="${REMOTE_VERSION_FILE:-/root/workspace/farm-manager/VERSION}"
DOWNLOAD_URL="http://${SERVER_HOST}:8098"

# === 参数 ===
CHANGELOG=""
SKIP_BUILD=0
SKIP_DEPLOY=0
SKIP_TAG=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --changelog=*)  CHANGELOG="${1#--changelog=}" ;;
    --remote-dir=*) REMOTE_APK_DIR="${1#--remote-dir=}" ;;
    --no-build)     SKIP_BUILD=1 ;;
    --no-deploy)    SKIP_DEPLOY=1 ;;
    --no-tag)       SKIP_TAG=1 ;;
    -h|--help)
      sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
  shift
done

log()  { printf '\n\033[1m>>> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# === 读取当前版本 ===
[ -f "$VERSION_FILE" ] || die "找不到 VERSION 文件"
OLD_NAME="$(grep '^VERSION_NAME=' "$VERSION_FILE" | cut -d= -f2-)"
OLD_CODE="$(grep '^VERSION_CODE=' "$VERSION_FILE" | cut -d= -f2-)"
[ -n "$OLD_NAME" ] && [ -n "$OLD_CODE" ] || die "VERSION 文件格式错误"

# === 版本自增(patch +1, code +1)===
IFS='.' read -r MAJOR MINOR PATCH <<< "$OLD_NAME"
NEW_NAME="${MAJOR}.${MINOR}.$((PATCH + 1))"
NEW_CODE="$((OLD_CODE + 1))"
[ -z "$CHANGELOG" ] && CHANGELOG="更新至 v${NEW_NAME}"

printf '\n=========================================\n'
printf ' FarmManager 发版\n'
printf '=========================================\n'
printf ' 版本:  v%s (%s) → v%s (%s)\n' "$OLD_NAME" "$OLD_CODE" "$NEW_NAME" "$NEW_CODE"
printf ' 说明:  %s\n' "$CHANGELOG"
[ "$SKIP_BUILD"  = 1 ] && printf ' ⚠ 跳过构建\n'
[ "$SKIP_DEPLOY" = 1 ] && printf ' ⚠ 跳过部署\n'
[ "$SKIP_TAG"    = 1 ] && printf ' ⚠ 跳过 tag\n'
printf '=========================================\n'

# === Step 1: 写 VERSION 文件 ===
log "更新版本号文件"
cat > "$VERSION_FILE" << EOF
VERSION_NAME=${NEW_NAME}
VERSION_CODE=${NEW_CODE}
CHANGELOG=${CHANGELOG}
EOF
ok "VERSION → v${NEW_NAME} (${NEW_CODE})"

if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' -E "s/^version: .*/version: ${NEW_NAME}+${NEW_CODE}/" "$PUBSPEC"
else
  sed -i    -E "s/^version: .*/version: ${NEW_NAME}+${NEW_CODE}/" "$PUBSPEC"
fi
ok "pubspec.yaml → ${NEW_NAME}+${NEW_CODE}"

# === Step 2: 构建 APK ===
APK_PATH=""
if [ "$SKIP_BUILD" = 1 ]; then
  log "跳过构建,查找已有 APK"
  APK_PATH="$(ls -t "$PROJECT_ROOT"/${APP_NAME}-v*-release-*.apk 2>/dev/null | head -1 || true)"
  [ -n "$APK_PATH" ] && [ -f "$APK_PATH" ] || die "找不到已有 APK"
  ok "使用: $(basename "$APK_PATH")"
else
  log "构建 release APK"
  bash "$SCRIPT_DIR/build-apk.sh" --release
  APK_PATH="$(ls -t "$PROJECT_ROOT"/${APP_NAME}-v${NEW_NAME}-release-*.apk 2>/dev/null | head -1 || true)"
  [ -n "$APK_PATH" ] && [ -f "$APK_PATH" ] || die "构建后找不到 APK"
  ok "构建完成: $(basename "$APK_PATH") ($(du -h "$APK_PATH" | cut -f1))"
fi

# === Step 3: 上传到服务器 ===
if [ "$SKIP_DEPLOY" = 0 ]; then
  log "上传到服务器 ${SERVER_HOST}:${REMOTE_APK_DIR}"

  REMOTE_APK="${REMOTE_APK_DIR}/${APP_NAME}-v${NEW_NAME}.apk"
  ssh -o ConnectTimeout=5 "${SERVER_USER}@${SERVER_HOST}" "mkdir -p '${REMOTE_APK_DIR}'" \
    || die "SSH 连接失败,请先配置免密: ssh-copy-id ${SERVER_USER}@${SERVER_HOST}"

  scp -q "$APK_PATH" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_APK}"
  ok "已上传: ${REMOTE_APK}"

  # 同步软链 + VERSION 文件
  ssh "${SERVER_USER}@${SERVER_HOST}" "ln -sf '${REMOTE_APK}' '${REMOTE_APK_DIR}/app-release.apk'"
  ok "软链已更新 → app-release.apk"

  scp -q "$VERSION_FILE" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_VERSION_FILE}" 2>/dev/null \
    && ok "服务器 VERSION 已同步" || printf '  \033[33m!\033[0m 服务器 VERSION 路径不可写,已跳过\n'

  printf '\n  下载链接: %s/app-release.apk\n' "$DOWNLOAD_URL"
fi

# === Step 4: git commit + tag + push ===
log "提交 git 变更"
git add "$VERSION_FILE" "$PUBSPEC"
git commit -m "release: v${NEW_NAME}

${CHANGELOG}" >/dev/null 2>&1 || ok "无变更或已提交"

if [ "$SKIP_TAG" = 0 ]; then
  git tag -a "v${NEW_NAME}" -m "release: v${NEW_NAME} (${NEW_CODE})" 2>/dev/null \
    && ok "tag v${NEW_NAME} 已创建" || ok "tag 已存在,跳过"
  git push origin "v${NEW_NAME}" 2>/dev/null || true
fi
git push origin main 2>/dev/null || true
ok "代码已推送"

# === 完成 ===
printf '\n=========================================\n'
printf ' \033[32m发版完成!\033[0m\n'
printf '=========================================\n'
printf ' 版本:    v%s (%s)\n' "$NEW_NAME" "$NEW_CODE"
printf ' 更新说明: %s\n' "$CHANGELOG"
[ "$SKIP_DEPLOY" = 0 ] && printf ' APK:     %s/app-release.apk\n' "$DOWNLOAD_URL"
printf ' Git Tag: v%s\n' "$NEW_NAME"
