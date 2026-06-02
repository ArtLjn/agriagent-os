"""测试语义提取器。"""


from app.simulation.semantic_extractor import (
    CLAIM_PATTERNS,
    OP_TYPE_TO_TABLE,
    extract_claims,
    get_table_for_op,
)


class TestExtractClaims:
    def test_extract_create_cost(self):
        reply = "好的，已记账：化肥 200元，日期 2026-05-26"
        claims = extract_claims(reply)
        assert len(claims) >= 1
        assert any(c.op_type == "create_cost" for c in claims)

    def test_extract_create_template(self):
        reply = "✅ 辣椒模板已创建，包含5个生长阶段"
        claims = extract_claims(reply)
        assert any(c.op_type == "create_template" for c in claims)

    def test_extract_create_cycle(self):
        reply = "茬口已创建，从2026-03-01开始"
        claims = extract_claims(reply)
        assert any(c.op_type == "create_cycle" for c in claims)

    def test_extract_multiple_claims(self):
        reply = "已记账化肥200元。同时已记录今天的浇水农事。"
        claims = extract_claims(reply)
        op_types = [c.op_type for c in claims]
        assert "create_cost" in op_types
        assert "log_activity" in op_types

    def test_extract_empty_reply(self):
        claims = extract_claims("")
        assert claims == []

    def test_extract_no_match(self):
        reply = "我不太明白你的意思"
        claims = extract_claims(reply)
        assert claims == []

    def test_claim_has_keywords_matched(self):
        reply = "已记账化肥200元"
        claims = extract_claims(reply)
        cost_claims = [c for c in claims if c.op_type == "create_cost"]
        assert len(cost_claims) == 1
        assert "已记账" in cost_claims[0].keywords_matched

    def test_claim_has_description(self):
        reply = "已记账化肥200元"
        claims = extract_claims(reply)
        assert all(len(c.description) > 0 for c in claims)

    def test_regex_pattern_matching(self):
        reply = "创建辣椒茬口成功"
        claims = extract_claims(reply)
        op_types = [c.op_type for c in claims]
        assert "create_cycle" in op_types


class TestGetTableForOp:
    def test_known_op_types(self):
        assert get_table_for_op("create_cost") == "cost_records"
        assert get_table_for_op("create_template") == "crop_templates"
        assert get_table_for_op("create_cycle") == "crop_cycles"
        assert get_table_for_op("update_stage") == "cycle_stages"
        assert get_table_for_op("log_activity") == "farm_logs"
        assert get_table_for_op("settle_debt") == "cost_records"

    def test_unknown_op_type(self):
        assert get_table_for_op("unknown_op") is None


class TestClaimPatterns:
    def test_all_patterns_have_entries(self):
        assert len(CLAIM_PATTERNS) > 0
        for op_type, keywords in CLAIM_PATTERNS.items():
            assert len(keywords) > 0
            assert op_type in OP_TYPE_TO_TABLE
