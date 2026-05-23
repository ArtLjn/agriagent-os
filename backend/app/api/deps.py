from app.core.database import SessionLocal


def get_db():
    """获取数据库会话，用于 FastAPI 依赖注入。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
