from pathlib import Path


def test_user_quota_columns_have_alembic_migration():
    """用户 token 配额字段必须由 Alembic 迁移同步到数据库。"""
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_sources = "\n".join(path.read_text() for path in versions_dir.glob("*.py"))

    assert "token_monthly_limit" in migration_sources
    assert "token_weekly_limit" in migration_sources
