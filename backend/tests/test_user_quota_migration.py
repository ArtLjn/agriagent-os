from pathlib import Path


def test_user_quota_columns_have_alembic_migration():
    """用户 token 配额字段必须由 Alembic 迁移同步到数据库。"""
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_sources = "\n".join(
        path.read_text() for path in versions_dir.glob("*.py")
    )

    assert "token_monthly_limit" in migration_sources
    assert "token_weekly_limit" in migration_sources


def test_labor_cost_source_idempotency_has_alembic_migration():
    """人工成本来源幂等字段和索引必须由 Alembic 迁移同步。"""
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e7b2c4d6f8a2_add_labor_entry_client_request_id.py"
    )
    source = migration_path.read_text()

    assert "source_active_key" in source
    assert "UPDATE cost_records" in source
    assert "source_active_key = 'active'" in source
    assert "deleted_at IS NULL" in source
    assert "source_type IS NOT NULL" in source
    assert "source_id IS NOT NULL" in source
    assert "uq_cost_records_active_source" in source
    assert '["farm_id", "source_type", "source_id", "source_active_key"]' in source
    assert 'op.drop_index("uq_cost_records_active_source"' in source
    assert 'op.drop_column("cost_records", "source_active_key")' in source
    assert "client_request_id" in source
    assert "uq_labor_entries_farm_client_request" in source
    assert '["farm_id", "client_request_id"]' in source
    assert "UPDATE labor_entries" in source
    assert "GROUP BY farm_id, client_request_id" in source


def test_labor_entries_dedupe_update_avoids_mysql_direct_self_reference():
    """MySQL 禁止 UPDATE 目标表时在同层子查询直接读取同一张表。"""
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e7b2c4d6f8a2_add_labor_entry_client_request_id.py"
    )
    source = migration_path.read_text()

    assert "SELECT MIN(id)" in source
    assert "FROM (\n                              SELECT MIN(id)" in source


def test_review_issue_chain_ai_judge_has_schema_repair_migration():
    """ReviewIssueChain AI 预判字段必须有独立幂等修复迁移。"""
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260625_fix_review_issue_chain_ai_judge_column.py"
    )

    source = migration_path.read_text()

    assert "agent_review_issue_chains" in source
    assert "ai_judge" in source
    assert "op.add_column" in source
    assert "sa.JSON()" in source
