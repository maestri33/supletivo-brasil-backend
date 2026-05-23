from contextlib import asynccontextmanager

import fastapi_structured_logging
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from tortoise.contrib.fastapi import RegisterTortoise

from app.routers.public.auth import router as auth_router
from app.routers.authenticated import (
    captured_router,
    personal_router,
    educational_router,
    birth_router,
    address_router,
)
from app.schemas import APIModel

fastapi_structured_logging.setup_logging(log_level="INFO")
logger = fastapi_structured_logging.get_logger()


# ============================================================================
# Health
# ============================================================================

class HealthOut(APIModel):
    status: str
    service: str = "candidate"


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("candidate_starting")
    async with RegisterTortoise(
        app,
        db_url="sqlite://db.sqlite3",
        modules={"models": ["app.models"]},
        generate_schemas=True,
        add_exception_handlers=True,
    ):
        yield
    logger.info("candidate_stopped")


# ============================================================================
# App
# ============================================================================

app = FastAPI(
    title="candidate",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(captured_router)
app.include_router(personal_router)
app.include_router(educational_router)
app.include_router(birth_router)
app.include_router(address_router)


@app.get("/health", response_model=HealthOut)
async def health():
    return {"status": "ok", "service": "candidate"}


@app.get("/ready", response_model=HealthOut)
async def ready():
    return {"status": "ok", "service": "candidate"}
