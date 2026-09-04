"""Composición de routers de la versión 1."""

from fastapi import APIRouter

from hys_api.api.v1.health import router as health_router
from hys_api.modules.pilot.router import router as pilot_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(pilot_router)
