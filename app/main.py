from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import analyze, changelog, dashboard, health, help_route, tribute, soxl


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Murphy Trend", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(dashboard.router)
app.include_router(analyze.router)
app.include_router(help_route.router)
app.include_router(health.router)
app.include_router(tribute.router)
app.include_router(changelog.router)
app.include_router(soxl.router)

