import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok"}
