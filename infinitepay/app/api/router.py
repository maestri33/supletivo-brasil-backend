from fastapi import APIRouter

from app.api.demilitarized.checkout import router as checkout_router
from app.api.public.webhooks import router as webhooks_router

router = APIRouter(prefix="/api/v1")
router.include_router(checkout_router, prefix="/checkout", tags=["checkout"])
router.include_router(webhooks_router, prefix="/webhook", tags=["webhook"])
