"""农业术语英文白名单 — 允许在中文输出中保留的英文单词。"""

_AGRICULTURAL_TERMS = {
    "watermelon", "tomato", "potato", "cucumber", "melon",
    "bean", "pepper", "eggplant", "carrot", "onion",
    "lettuce", "spinach", "celery", "broccoli", "cauliflower",
    "corn", "wheat", "rice", "soybean", "cotton",
    "fertilizer", "pesticide", "herbicide", "fungicide",
    "greenhouse", "drip", "irrigation", "mulch",
    "ph", "ec", "tds", "ppm", "co2",
    "n", "p", "k", "ca", "mg", "fe", "zn", "b", "mn",
    "ai", "llm", "api", "json", "html", "url",
}


def is_whitelisted(word: str) -> bool:
    """检查单词是否在农业术语白名单中。"""
    return word.lower() in _AGRICULTURAL_TERMS


__all__ = ["is_whitelisted", "_AGRICULTURAL_TERMS"]
