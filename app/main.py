from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import Base, engine
from app.routers import analyze, dashboard, health, help_route, sad


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="MurphyTrend", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(dashboard.router)
app.include_router(analyze.router)
app.include_router(sad.router)
app.include_router(help_route.router)
app.include_router(health.router)

templates = Jinja2Templates(directory="app/templates")
