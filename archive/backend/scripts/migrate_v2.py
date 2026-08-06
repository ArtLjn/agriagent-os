"""V2 数据迁移 — 创建用户、关联农场。

用法:
    python scripts/migrate_v2.py --dry-run  # 预览
    python scripts/migrate_v2.py            # 执行
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.farm import Farm
from app.models.user import User


def migrate(dry_run: bool = False) -> None:
    """执行迁移。"""
    db = SessionLocal()
    try:
        # Step 1: 检查 users 表是否已存在数据
        existing = db.query(User).first()
        if existing:
            print("用户表已有数据，跳过迁移。")
            return

        # Step 2: 从 farms(1) 创建默认用户
        farm = db.query(Farm).filter(Farm.id == 1).first()
        if not farm:
            print("未找到默认农场，跳过。")
            return

        owner_name = getattr(farm, "owner_name", None) or "默认农户"
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            phone="00000000000",
            password_hash="!",
            nickname=owner_name,
            role="admin",
        )
        db.add(user)

        # Step 3: 关联 farm.user_id
        farm.user_id = user_id

        if dry_run:
            print(f"[DRY-RUN] 将创建用户: {owner_name} ({user_id})")
            print(f"[DRY-RUN] 将关联 Farm(1) → user_id={user_id}")
            db.rollback()
        else:
            db.commit()
            print(f"迁移完成: 用户 {owner_name}, Farm(1) 关联 user_id={user_id}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
