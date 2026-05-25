"""测试成本解析的动态分类注入功能。"""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session

from app.models.cost_category import CostCategory
from app.models.farm import Farm
from app.services.cost_service import parse_record
from app.core.database import SessionLocal


@pytest.fixture
def db():
    """创建数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_farm():
    """测试农场对象。"""
    return Farm(id=1, name="默认农场")


@pytest.fixture
def custom_cost_categories(db: Session, test_farm: Farm):
    """创建自定义成本分类。"""
    categories = [
        CostCategory(name="有机肥", type="cost", farm_id=test_farm.id),
        CostCategory(name="生物农药", type="cost", farm_id=test_farm.id),
        CostCategory(name="采摘人工", type="cost", farm_id=test_farm.id),
        CostCategory(name="有机销售", type="income", farm_id=test_farm.id),
    ]
    for category in categories:
        db.add(category)
    db.commit()
    return categories


class TestParseRecordWithDynamicCategories:
    """测试解析记录时的动态分类注入。"""

    @pytest.mark.asyncio
    async def test_parse_record_includes_custom_categories(
        self, db: Session, test_farm: Farm, custom_cost_categories
    ):
        """测试解析记录时包含自定义分类。"""
        description = "买了有机肥花了300块"

        # Mock LLM 调用
        with patch("app.services.cost_service.get_llm") as mock_get_llm, patch(
            "app.services.cost_service.llm_invoke_with_breaker"
        ) as mock_invoke:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            # 捕获实际发送给 LLM 的 prompt
            captured_prompt = None

            async def side_effect(llm, messages):
                nonlocal captured_prompt
                captured_prompt = messages[0]["content"]
                # 创建一个 mock 的 LangChain 消息对象
                from langchain_core.messages import AIMessage
                return AIMessage(
                    content='{"record_type": "cost", "category": "有机肥", "amount": "300", "record_date": "2026-05-25", "note": null}'
                )

            mock_invoke.side_effect = side_effect

            # 调用解析函数，传入 farm_id 和 db
            result = await parse_record(description, farm_id=test_farm.id, db=db)

            # 验证 prompt 包含自定义分类
            assert captured_prompt is not None
            assert "有机肥" in captured_prompt
            assert "生物农药" in captured_prompt
            assert "采摘人工" in captured_prompt
            assert "有机销售" in captured_prompt

            # 验证解析结果
            assert result.record_type == "cost"
            assert result.category == "有机肥"
            assert result.amount == "300"

    @pytest.mark.asyncio
    async def test_parse_record_without_farm_id_uses_defaults(
        self, db: Session, test_farm: Farm, custom_cost_categories
    ):
        """测试不提供 farm_id 时使用默认分类。"""
        description = "买了化肥花了200块"

        with patch("app.services.cost_service.get_llm") as mock_get_llm, patch(
            "app.services.cost_service.llm_invoke_with_breaker"
        ) as mock_invoke:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            captured_prompt = None

            async def side_effect(llm, messages):
                nonlocal captured_prompt
                captured_prompt = messages[0]["content"]
                from langchain_core.messages import AIMessage
                return AIMessage(
                    content='{"record_type": "cost", "category": "化肥", "amount": "200", "record_date": "2026-05-25", "note": null}'
                )

            mock_invoke.side_effect = side_effect

            # 不传入 farm_id 和 db
            result = await parse_record(description)

            # 验证 prompt 使用默认分类
            assert captured_prompt is not None
            assert "种子、化肥、农药、人工、水电、地租、其他" in captured_prompt
            assert "有机肥" not in captured_prompt  # 不应包含自定义分类

            # 验证解析结果
            assert result.record_type == "cost"
            assert result.category == "化肥"
            assert result.amount == "200"

    @pytest.mark.asyncio
    async def test_parse_record_empty_custom_categories_uses_defaults(
        self, db: Session, test_farm: Farm
    ):
        """测试农场没有自定义分类时使用默认分类。"""
        description = "销售蔬菜收入500块"

        with patch("app.services.cost_service.get_llm") as mock_get_llm, patch(
            "app.services.cost_service.llm_invoke_with_breaker"
        ) as mock_invoke:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            captured_prompt = None

            async def side_effect(llm, messages):
                nonlocal captured_prompt
                captured_prompt = messages[0]["content"]
                from langchain_core.messages import AIMessage
                return AIMessage(
                    content='{"record_type": "income", "category": "销售", "amount": "500", "record_date": "2026-05-25", "note": null}'
                )

            mock_invoke.side_effect = side_effect

            # 传入 farm_id 和 db，但没有自定义分类
            result = await parse_record(description, farm_id=test_farm.id, db=db)

            # 验证 prompt 使用默认分类
            assert captured_prompt is not None
            assert "销售、补贴、其他" in captured_prompt

            # 验证解析结果
            assert result.record_type == "income"
            assert result.category == "销售"
            assert result.amount == "500"
