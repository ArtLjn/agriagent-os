import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, crop, cycle, log, cost, weather
from app.core.config import settings
from app.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crop.router)
app.include_router(cycle.router)
app.include_router(log.router)
app.include_router(cost.router)
app.include_router(agent.router)
app.include_router(weather.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
