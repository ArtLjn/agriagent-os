"""Python 版本兼容性测试。"""

from pathlib import Path


def test_app_does_not_import_stdlib_strenum_directly():
    """生产服务器仍为 Python 3.10，禁止直接依赖 enum.StrEnum。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.name == "compat.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "from enum import StrEnum" in text:
            offenders.append(str(path.relative_to(app_dir.parent)))

    assert offenders == []


def test_strenum_compat_behaves_like_string_enum():
    """兼容版 StrEnum 应保持字符串枚举行为。"""
    from app.prompt.models import PromptLayer

    assert PromptLayer.SAFETY == "safety"
    assert PromptLayer.SAFETY.value == "safety"
