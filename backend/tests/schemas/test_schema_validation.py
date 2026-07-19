from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domains.finance.cost_schemas import CostRecordCreate, CostRecordUpdate, CostParseResponse
from app.domains.conversation.agent_schemas import ChatRequest


class TestCostRecordCreate:
    def test_valid_record(self):
        record = CostRecordCreate(
            record_type="cost",
            category="化肥",
            amount=Decimal("100.50"),
            record_date="2024-01-01",
        )
        assert record.record_type == "cost"

    def test_invalid_record_type(self):
        with pytest.raises(ValidationError) as exc:
            CostRecordCreate(
                record_type="invalid",
                category="化肥",
                amount=Decimal("100"),
                record_date="2024-01-01",
            )
        assert "record_type 必须是" in str(exc.value)

    def test_amount_too_large(self):
        with pytest.raises(ValidationError) as exc:
            CostRecordCreate(
                record_type="cost",
                category="化肥",
                amount=Decimal("10000001"),
                record_date="2024-01-01",
            )
        assert "Input should be less than or equal to 10000000" in str(exc.value)

    def test_amount_negative(self):
        with pytest.raises(ValidationError) as exc:
            CostRecordCreate(
                record_type="cost",
                category="化肥",
                amount=Decimal("-10"),
                record_date="2024-01-01",
            )
        assert "Input should be greater than 0" in str(exc.value)

    def test_amount_precision(self):
        with pytest.raises(ValidationError) as exc:
            CostRecordCreate(
                record_type="cost",
                category="化肥",
                amount=Decimal("100.123"),
                record_date="2024-01-01",
            )
        assert "最多保留两位小数" in str(exc.value)


class TestCostRecordUpdate:
    def test_valid_partial_update(self):
        update = CostRecordUpdate(category="种子")
        assert update.category == "种子"

    def test_invalid_record_type(self):
        with pytest.raises(ValidationError) as exc:
            CostRecordUpdate(record_type="invalid")
        assert "record_type 必须是" in str(exc.value)

    def test_amount_precision(self):
        with pytest.raises(ValidationError) as exc:
            CostRecordUpdate(amount=Decimal("100.123"))
        assert "最多保留两位小数" in str(exc.value)


class TestCostParseResponse:
    def test_valid_response(self):
        response = CostParseResponse(
            record_type="income",
            category="销售",
            amount="5000",
            record_date="2024-01-01",
        )
        assert response.record_type == "income"

    def test_invalid_record_type(self):
        with pytest.raises(ValidationError) as exc:
            CostParseResponse(
                record_type="invalid",
                category="销售",
                amount="5000",
                record_date="2024-01-01",
            )
        assert "record_type 必须是" in str(exc.value)

    def test_amount_not_number(self):
        with pytest.raises(ValidationError) as exc:
            CostParseResponse(
                record_type="cost",
                category="化肥",
                amount="abc",
                record_date="2024-01-01",
            )
        assert "amount 必须是有效的数字字符串" in str(exc.value)

    def test_amount_zero(self):
        with pytest.raises(ValidationError) as exc:
            CostParseResponse(
                record_type="cost",
                category="化肥",
                amount="0",
                record_date="2024-01-01",
            )
        assert "amount 必须大于 0" in str(exc.value)

    def test_amount_too_large(self):
        with pytest.raises(ValidationError) as exc:
            CostParseResponse(
                record_type="cost",
                category="化肥",
                amount="10000001",
                record_date="2024-01-01",
            )
        assert "amount 不能超过 10,000,000" in str(exc.value)


class TestChatRequest:
    def test_message_too_long(self):
        with pytest.raises(ValidationError) as exc:
            ChatRequest(message="x" * 2001)
        assert "String should have at most 2000 characters" in str(exc.value)

    def test_empty_message(self):
        with pytest.raises(ValidationError) as exc:
            ChatRequest(message="")
        assert "String should have at least 1 character" in str(exc.value)
