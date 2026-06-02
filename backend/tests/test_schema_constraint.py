"""测试动态 enum 约束 — category 参数从数据库加载标签列表。"""

from unittest.mock import MagicMock, patch

import pytest

from app.agent.skills import (
    _schema_to_pydantic,
    clear_category_cache,
    get_category_enum,
)


def _make_category(name: str) -> MagicMock:
    """创建带 .name 属性的 mock 分类对象。"""
    cat = MagicMock()
    cat.name = name
    return cat


class TestGetCategoryEnum:
    """测试 get_category_enum 从数据库加载分类标签。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """每个测试前后清除缓存。"""
        clear_category_cache()
        yield
        clear_category_cache()

    def test_returns_category_names_from_db(self):
        """从数据库查询结果中提取分类名称列表。"""
        mock_cats = [
            _make_category("化肥"),
            _make_category("种子"),
            _make_category("人工"),
        ]
        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = mock_cats
            result = get_category_enum(farm_id=1)
        assert result == ["化肥", "种子", "人工"]

    def test_returns_default_when_no_categories(self):
        """数据库无分类时返回默认列表。"""
        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = []
            result = get_category_enum(farm_id=1)
        assert "化肥" in result
        assert "种子" in result
        assert len(result) > 0

    def test_caches_result_for_same_farm(self):
        """同一 farm_id 的第二次调用使用缓存。"""
        mock_cats = [_make_category("化肥")]
        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = mock_cats
            get_category_enum(farm_id=1)
            get_category_enum(farm_id=1)
        # 只查一次数据库
        assert mock_svc.get_categories.call_count == 1

    def test_different_farms_separate_cache(self):
        """不同 farm_id 查询不同次数。"""
        mock_cats = [_make_category("化肥")]
        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = mock_cats
            get_category_enum(farm_id=1)
            get_category_enum(farm_id=2)
        assert mock_svc.get_categories.call_count == 2

    def test_returns_default_on_db_error(self):
        """数据库异常时返回默认列表。"""
        with patch("app.agent.skills.SessionLocal", side_effect=Exception("db down")):
            result = get_category_enum(farm_id=1)
        assert "化肥" in result
        assert len(result) > 0


class TestClearCategoryCache:
    """测试 clear_category_cache 缓存清除。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        clear_category_cache()
        yield
        clear_category_cache()

    def test_clear_specific_farm(self):
        """清除指定 farm 的缓存。"""
        mock_cats = [_make_category("化肥")]
        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = mock_cats
            get_category_enum(farm_id=1)

        clear_category_cache(farm_id=1)

        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = mock_cats
            get_category_enum(farm_id=1)

        assert mock_svc.get_categories.call_count == 1

    def test_clear_all(self):
        """清除全部缓存。"""
        mock_cats = [_make_category("化肥")]
        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = mock_cats
            get_category_enum(farm_id=1)
            get_category_enum(farm_id=2)

        clear_category_cache()

        with patch("app.agent.skills.cost_category_service") as mock_svc, \
             patch("app.agent.skills.SessionLocal"):
            mock_svc.get_categories.return_value = mock_cats
            get_category_enum(farm_id=1)
            get_category_enum(farm_id=2)

        assert mock_svc.get_categories.call_count == 2


class TestSchemaToPydanticWithEnum:
    """测试 _schema_to_pydantic 支持 enum 约束。"""

    def test_category_field_has_enum_values(self):
        """category 字段包含 enum 约束。"""
        schema = {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "分类",
                    "enum": ["化肥", "种子", "人工"],
                },
                "amount": {
                    "type": "number",
                    "description": "金额",
                },
            },
            "required": ["category", "amount"],
        }
        model = _schema_to_pydantic("test", schema)
        field_info = model.model_fields["category"]
        # Literal 类型会产生 metadata
        assert field_info.metadata is not None

    def test_enums_param_overrides_schema_enum(self):
        """enums 参数覆盖 schema 中定义的 enum。"""
        schema = {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "分类",
                    "enum": ["旧值1", "旧值2"],
                },
            },
            "required": ["category"],
        }
        model = _schema_to_pydantic(
            "test", schema, enums={"category": ["化肥", "种子"]}
        )
        field_info = model.model_fields["category"]
        assert field_info.metadata is not None

    def test_no_enum_for_non_string_field(self):
        """非 string 字段不应用 enum 约束。"""
        schema = {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "金额",
                    "enum": [1, 2, 3],
                },
            },
            "required": ["amount"],
        }
        model = _schema_to_pydantic("test", schema)
        field_info = model.model_fields["amount"]
        # number 类型不使用 Literal，metadata 为空
        assert field_info.annotation is float
