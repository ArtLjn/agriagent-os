"""Token usage 提取测试。"""

from langchain_core.messages import AIMessage

from app.agent.runtime.messages import extract_token_usage


class TestExtractTokenUsage:
    def test_extracts_langchain_usage_metadata(self) -> None:
        message = AIMessage(
            content="ok",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        )

        usage = extract_token_usage(message)

        assert usage == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "usage_source": "usage_metadata",
        }

    def test_extracts_provider_token_usage(self) -> None:
        message = AIMessage(
            content="ok",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                }
            },
        )

        usage = extract_token_usage(message)

        assert usage == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "usage_source": "provider",
        }

    def test_returns_none_when_usage_missing(self) -> None:
        message = AIMessage(content="ok")

        assert extract_token_usage(message) is None
