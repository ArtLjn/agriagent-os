#!/usr/bin/env bash
# SQLite 在线热备 + 7 天滚动保留

set -euo pipefail

DB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_FILE="$DB_DIR/app/farm_manager.db"
BACKUP_DIR="$DB_DIR/backups"
RETAIN_DAYS=7

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/farm_manager_$TIMESTAMP.db"

# SQLite 在线热备
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# 压缩
gzip "$BACKUP_FILE"

# 清理过期备份
find "$BACKUP_DIR" -name "farm_manager_*.db.gz" -mtime +$RETAIN_DAYS -delete

echo "备份完成: ${BACKUP_FILE}.gz"
