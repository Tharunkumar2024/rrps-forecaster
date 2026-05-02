"""Inventory planning service — deterministic estimation for Week 1."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.tables import Ingredient, MenuItem, RecipeMap
from app.schemas.forecast import ForecastResponse
from app.schemas.inventory_plan import IngredientNeed, InventoryPlanResponse

SAFETY_STOCK_FACTOR = 1.10  # 10% buffer on top of raw estimate

# Rough assumption: each cover orders ~1.5 dishes on average
DISHES_PER_COVER = 1.5


async def generate_inventory_plan(
    db: AsyncSession,
    forecast: ForecastResponse,
) -> InventoryPlanResponse:
    """Estimate ingredient quantities for a forecast date.

    Logic:
      total_covers_for_day → estimated_dishes → ingredient demand via recipe_map
      → add 10 % safety stock.
    """
    total_covers = sum(h.predicted_covers for h in forecast.hourly_forecast)
    if total_covers == 0:
        return InventoryPlanResponse(plan_date=forecast.forecast_date, ingredients=[])

    estimated_dishes = total_covers * DISHES_PER_COVER

    # Load all menu items with their recipe mappings
    stmt = select(MenuItem).options(selectinload(MenuItem.recipe_entries).selectinload(RecipeMap.ingredient))
    result = await db.execute(stmt)
    menu_items = result.scalars().all()

    if not menu_items:
        return InventoryPlanResponse(plan_date=forecast.forecast_date, ingredients=[])

    # Assume even distribution across menu items for the MVP
    dishes_per_item = estimated_dishes / len(menu_items)

    # Accumulate ingredient needs
    ingredient_totals: dict[str, dict] = {}
    for item in menu_items:
        for recipe in item.recipe_entries:
            ing = recipe.ingredient
            key = ing.name
            if key not in ingredient_totals:
                ingredient_totals[key] = {
                    "quantity_kg": 0.0,
                    "shelf_life_days": ing.shelf_life_days,
                    "lead_time_days": ing.lead_time_days,
                }
            ingredient_totals[key]["quantity_kg"] += recipe.quantity * dishes_per_item

    # Apply safety stock
    needs: list[IngredientNeed] = []
    for name, data in ingredient_totals.items():
        needs.append(
            IngredientNeed(
                ingredient_name=name,
                quantity_kg=round(data["quantity_kg"] * SAFETY_STOCK_FACTOR, 2),
                shelf_life_days=data["shelf_life_days"],
                lead_time_days=data["lead_time_days"],
            )
        )

    return InventoryPlanResponse(plan_date=forecast.forecast_date, ingredients=needs)
