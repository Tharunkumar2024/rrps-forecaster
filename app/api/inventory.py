"""Inventory API route."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.inventory_plan import InventoryPlanResponse
from app.services.forecast_service import generate_forecast
from app.services.inventory_planner import generate_inventory_plan

router = APIRouter(tags=["Inventory Planning"])


@router.get(
    "/inventory-plan",
    response_model=InventoryPlanResponse,
    summary="Get ingredient procurement plan",
    description="Returns estimated ingredient quantities needed for the forecast date, including safety stock.",
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
        # Step 1: Get the demand forecast
        forecast = await generate_forecast(db, target_date)
        # Step 2: Pass forecast to Inventory optimization engine
        return await generate_inventory_plan(db, forecast)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inventory plan generation failed: {exc}")
