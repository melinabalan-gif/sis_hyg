"""Composición de routers de la versión 1."""

from fastapi import APIRouter

from hys_api.api.v1.health import router as health_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
