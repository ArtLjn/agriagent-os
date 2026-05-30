from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/app", tags=["app"])

VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"


def _read_version():
    """从项目根目录 VERSION 文件读取版本信息。"""
    if not VERSION_FILE.exists():
        return "0.0.0", 0, ""
    lines = {}
    for line in VERSION_FILE.read_text().strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            lines[k.strip()] = v.strip()
    return (
        lines.get("VERSION_NAME", "0.0.0"),
        int(lines.get("VERSION_CODE", "0")),
        lines.get("CHANGELOG", ""),
    )


class VersionCheckResponse(BaseModel):
    latest_version: str
    latest_version_code: int
    download_url: str
    changelog: str
    force_update: bool = False


@router.get("/version", response_model=VersionCheckResponse)
async def check_version(current_version_code: int = 0):
    """App 启动时调用，检查是否有新版本。"""
    version, code, changelog = _read_version()
    download_url = settings.app.apk_download_url.format(version=version)
    return VersionCheckResponse(
        latest_version=version,
        latest_version_code=code,
        download_url=download_url,
        changelog=changelog,
        force_update=code > current_version_code + 5,
    )
