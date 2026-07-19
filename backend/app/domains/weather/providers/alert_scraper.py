"""中国气象局预警爬虫 — 免费获取官方气象预警。

使用中国气象局官方 API：https://weather.cma.cn/api/map/alarm
无需 API Key，完全免费。
"""

import json
import logging
from typing import Literal

import httpx

from app.domains.weather.providers.base import WeatherAlert

logger = logging.getLogger(__name__)

_CMA_ALARM_API = "https://weather.cma.cn/api/map/alarm"

# 预警类型代码最后一位数字表示级别：1=红色, 2=橙色, 3=黄色, 4=蓝色
_SEVERITY_MAP: dict[str, Literal["red", "orange", "yellow", "blue"]] = {
    "1": "red",
    "2": "orange",
    "3": "yellow",
    "4": "blue",
}


class AlertScraper:
    """中国气象局预警爬虫。"""

    def fetch_alerts(self, city_name: str) -> list[WeatherAlert]:
        """获取指定城市的官方气象预警。

        Args:
            city_name: 城市中文名（如"苏州"、"宁德"）。

        Returns:
            WeatherAlert 列表，无预警或出错时返回空列表。
        """
        try:
            resp = httpx.get(
                _CMA_ALARM_API,
                headers={
                    "Referer": "https://weather.cma.cn/",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                timeout=10,
                verify=False,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("预警爬虫请求失败: %s", exc)
            return []

        return self._parse_alerts(resp.text, city_name)

    def _parse_alerts(self, json_text: str, city_name: str) -> list[WeatherAlert]:
        """解析中国气象局 API 返回的预警数据。

        Args:
            json_text: API 返回的 JSON 文本。
            city_name: 要过滤的城市名。

        Returns:
            WeatherAlert 列表。
        """
        alerts: list[WeatherAlert] = []

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning("预警数据 JSON 解析失败")
            return alerts

        if data.get("code") != 0:
            logger.warning("预警 API 返回错误: code=%s", data.get("code"))
            return alerts

        raw_list = data.get("data", [])
        for item in raw_list:
            # 检查是否包含目标城市名
            headline = item.get("headline", "")
            title = item.get("title", "")
            if (
                city_name
                and city_name
                not in (
                    "当前地块",
                    "地块",
                )
                and city_name not in headline
                and city_name not in title
            ):
                continue

            # 从 type 提取严重程度（最后一位）
            alert_type = item.get("type", "")
            severity = "blue"  # 默认蓝色
            if alert_type and len(alert_type) >= 7:
                last_digit = alert_type[-1]
                severity = _SEVERITY_MAP.get(last_digit, "blue")

            alerts.append(
                WeatherAlert(
                    title=headline or title,
                    description=item.get("description", ""),
                    severity=severity,
                )
            )

        return alerts
