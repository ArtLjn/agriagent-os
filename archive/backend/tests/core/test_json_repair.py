"""Tests for JSON repair utility."""

from app.shared.json_repair import extract_json, repair_json


class TestJsonRepair:
    def test_extract_from_markdown_code_block(self):
        text = '```json\n{"a": 1}\n```'
        assert extract_json(text) == '{"a": 1}'

    def test_extract_plain_json(self):
        text = '{"a": 1}'
        assert extract_json(text) == '{"a": 1}'

    def test_repair_missing_braces(self):
        text = '{"a": 1, "b": {'
        assert repair_json(text) == '{"a": 1, "b": {}}'

    def test_repair_trailing_comma(self):
        text = '{"a": 1,}'
        assert repair_json(text) == '{"a": 1}'

    def test_repair_nested_trailing_comma(self):
        text = '{"a": [1, 2,]}'
        assert repair_json(text) == '{"a": [1, 2]}'
