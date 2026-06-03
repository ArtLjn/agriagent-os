"""天气 selector。"""

from app.context.models import ContextBlock


class WeatherSelector:
    """选择天气摘要，默认接收预先计算好的文本。"""

    def select(
        self, weather_summary: str | None = None, **_kwargs
    ) -> list[ContextBlock]:
        if not weather_summary:
            return []
        return [
            ContextBlock(
                key="weather",
                source="weather",
                purpose="天气摘要",
                content=weather_summary,
                priority=60,
                ttl_seconds=300,
            )
        ]


__all__ = ["WeatherSelector"]
