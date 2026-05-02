"""API route definitions — thin controllers, all logic delegated to services."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.forecast import ForecastResponse
from app.schemas.inventory_plan import InventoryPlanResponse
from app.schemas.staff_plan import StaffPlanResponse
from app.services.forecast_service import generate_forecast
from app.services.inventory_service import generate_inventory_plan
from app.services.staff_service import generate_staff_plan

router = APIRouter()


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Get hourly demand forecast",
    description="Returns predicted customer covers for each hour of the requested date.",
)
async def get_forecast(
    target_date: date = Query(
        default=None,
        description="Date to forecast (YYYY-MM-DD). Defaults to tomorrow.",
    ),
    db: AsyncSession = Depends(get_db),
) -> ForecastResponse:
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    try:
        return await generate_forecast(db, target_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Forecast generation failed: {exc}")


@router.get(
    "/staff-plan",
    response_model=StaffPlanResponse,
    summary="Get staff scheduling recommendation",
    description="Returns recommended staff count per role per hour based on the demand forecast.",
)
async def get_staff_plan(
    target_date: date = Query(
        default=None,
        description="Date to plan staff for (YYYY-MM-DD). Defaults to tomorrow.",
    ),
    db: AsyncSession = Depends(get_db),
) -> StaffPlanResponse:
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    try:
        forecast = await generate_forecast(db, target_date)
        return await generate_staff_plan(db, forecast)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Staff plan generation failed: {exc}")


@router.get(
    "/inventory-plan",
    response_model=InventoryPlanResponse,
    summary="Get ingredient procurement plan",
    description="Returns estimated ingredient quantities needed for the forecast date.",
)
async def get_inventory_plan(
    target_date: date = Query(
        default=None,
        description="Date to plan inventory for (YYYY-MM-DD). Defaults to tomorrow.",
    ),
    db: AsyncSession = Depends(get_db),
) -> InventoryPlanResponse:
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    try:
        forecast = await generate_forecast(db, target_date)
        return await generate_inventory_plan(db, forecast)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inventory plan generation failed: {exc}")
