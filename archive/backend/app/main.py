import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bootstrap import create_app  # noqa: E402
from app.shared.config import settings  # noqa: E402

app = create_app()


if __name__ == "__main__":
    import os
    import uvicorn

    backend_root = Path(__file__).resolve().parent.parent
    reload_enabled = os.getenv("UVICORN_RELOAD", "").lower() in {"1", "true", "yes"}
    reload_options = {}
    if reload_enabled:
        reload_options = {
            "reload_dirs": [str(backend_root / "app")],
            "reload_includes": ["app/**/*.py"],
            "reload_excludes": [
                "*.pyc",
                "__pycache__/*",
                "logs/*",
                "tests/*",
                "tests/*.db-shm",
                "tests/*.db-wal",
            ],
        }

    uvicorn.run(
        "app.main:app" if reload_enabled else app,
        host=settings.server.host,
        port=settings.server.port,
        reload=reload_enabled,
        log_config=None,
        **reload_options,
    )
