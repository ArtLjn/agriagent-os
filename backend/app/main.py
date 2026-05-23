from fastapi import FastAPI

from app.core.config import settings
from app.core.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.project_name)


@app.get("/health")
def health_check():
    return {"status": "ok"}
