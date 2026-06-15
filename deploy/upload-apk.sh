#!/bin/bash
# APK 上传脚本 — 上传到阿里云 ECS 服务器
# 用法: ./upload-apk.sh [APK路径] [版本号]
#   ./upload-apk.sh ./FarmManager-v1.0.5-release.apk 1.0.5

set -e

# 服务器配置（按需修改）
SERVER_IP="43.155.217.74"
SERVER_USER="root"
REMOTE_DIR="/root/workspace/farm-apk"
DOWNLOAD_URL="http://${SERVER_IP}:8098"

APK_PATH="${1:-}"
VERSION="${2:-}"

if [ -z "$APK_PATH" ]; then
  # 自动查找最新的 APK
  APK_PATH=$(find . -maxdepth 2 -name "FarmManager-*-release*.apk" -type f 2>/dev/null | sort -r | head -1)
  if [ -z "$APK_PATH" ]; then
    echo "错误: 找不到 APK 文件"
    echo "用法: $0 [APK路径] [版本号]"
    exit 1
  fi
  echo "自动发现 APK: $APK_PATH"
fi

if [ ! -f "$APK_PATH" ]; then
  echo "错误: APK 文件不存在: $APK_PATH"
  exit 1
fi

# 如果没有指定版本，尝试从文件名提取
if [ -z "$VERSION" ]; then
  VERSION=$(echo "$APK_PATH" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's/^v//')
  if [ -z "$VERSION" ]; then
    VERSION="latest"
  fi
fi

FILENAME="app-release-v${VERSION}.apk"

echo "========================================="
echo " APK 上传到服务器"
echo "========================================="
echo " 本地文件: $APK_PATH"
echo " 版本:     v$VERSION"
echo " 目标:     ${SERVER_IP}:${REMOTE_DIR}/${FILENAME}"
echo " 下载链接: ${DOWNLOAD_URL}/${FILENAME}"
echo "========================================="

# 上传到服务器
scp "$APK_PATH" "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/${FILENAME}"

# 同时创建 app-release.apk 软链（最新版本）
ssh "${SERVER_USER}@${SERVER_IP}" "ln -sf ${REMOTE_DIR}/${FILENAME} ${REMOTE_DIR}/app-release.apk"

echo ""
echo "上传完成!"
echo "下载链接: ${DOWNLOAD_URL}/${FILENAME}"
echo "最新版本: ${DOWNLOAD_URL}/app-release.apk"
echo ""
echo "请记得更新 VERSION 文件并重新部署后端。"
