"""Python 版本兼容性测试。"""

from pathlib import Path


def test_app_does_not_import_stdlib_strenum_directly():
    """生产服务器仍为 Python 3.10，禁止直接依赖 enum.StrEnum。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.as_posix().endswith("shared/compatibility.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if "from enum import StrEnum" in text:
            offenders.append(str(path.relative_to(app_dir.parent)))

    assert offenders == []


def test_app_does_not_import_stdlib_datetime_utc_directly():
    """生产服务器仍为 Python 3.10，禁止直接依赖 datetime.UTC。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.as_posix().endswith("shared/compatibility.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if "from datetime import UTC" in text or "datetime.UTC" in text:
            offenders.append(str(path.relative_to(app_dir.parent)))

    assert offenders == []


def test_strenum_compat_behaves_like_string_enum():
    """兼容版 StrEnum 应保持字符串枚举行为。"""
    from app.prompt.models import PromptLayer

    assert PromptLayer.SAFETY == "safety"
    assert PromptLayer.SAFETY.value == "safety"


def test_utc_compat_builds_timezone_aware_datetime():
    """兼容版 UTC 应可生成带时区时间。"""
    from app.memory.models import utc_now

    assert utc_now().tzinfo is not None
