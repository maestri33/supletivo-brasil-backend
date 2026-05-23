from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_orm
from app.api.router import router

app = FastAPI(title=settings.service_name)

init_orm(app)

app.include_router(router)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
