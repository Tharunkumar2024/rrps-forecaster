"""API route definitions — aggregates modular sub-routers."""

from fastapi import APIRouter

from app.api import feedback, forecast, inventory, staff

router = APIRouter()

router.include_router(forecast.router)
router.include_router(staff.router)
router.include_router(inventory.router)
router.include_router(feedback.router)
