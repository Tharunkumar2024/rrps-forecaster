"""Inventory planning service using deterministic mapping and safety stock."""

import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.tables import Ingredient, MenuItem, RecipeMap
from app.schemas.forecast import ForecastResponse
from app.schemas.inventory_plan import IngredientNeed, InventoryPlanResponse

logger = logging.getLogger(__name__)

# Configurable safety stock (e.g., 15% buffer)
SAFETY_STOCK_FACTOR = 1.15

# Assumption: average dishes ordered per cover
DISHES_PER_COVER = 1.5


async def generate_inventory_plan(
    db: AsyncSession,
    forecast: ForecastResponse,
    current_stock: dict[str, float] = None,
) -> InventoryPlanResponse:
    """Calculate ingredient quantities needed for a forecasted demand.
    
    1. Converts covers to dishes.
    2. Maps dishes to ingredients using RecipeMap.
    3. Adds safety stock padding.
    4. Subtracts current stock.
    """
    if current_stock is None:
        current_stock = {}

    total_covers = sum(h.predicted_covers for h in forecast.hourly_forecast)
    if total_covers == 0:
        return InventoryPlanResponse(plan_date=forecast.forecast_date, ingredients=[])

    estimated_dishes = total_covers * DISHES_PER_COVER

    # Load all menu items with their recipe mappings
    stmt = select(MenuItem).options(selectinload(MenuItem.recipe_entries).selectinload(RecipeMap.ingredient))
    result = await db.execute(stmt)
    menu_items = result.scalars().all()

    if not menu_items:
        logger.warning("No menu items found in DB. Returning empty inventory plan.")
        return InventoryPlanResponse(plan_date=forecast.forecast_date, ingredients=[])

    # For deterministic distribution, assume equal probability of any menu item being ordered
    dishes_per_item = estimated_dishes / len(menu_items)

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

    # Apply safety stock, subtract current stock, and construct response
    needs: list[IngredientNeed] = []
    for name, data in ingredient_totals.items():
        base_qty = data["quantity_kg"]
        safe_qty = base_qty * SAFETY_STOCK_FACTOR
        
        # Subtract current stock
        stock_on_hand = current_stock.get(name, 0.0)
        procurement_qty = max(0.0, safe_qty - stock_on_hand)
        
        needs.append(
            IngredientNeed(
                ingredient_name=name,
                quantity_kg=round(procurement_qty, 2),
                shelf_life_days=data["shelf_life_days"],
                lead_time_days=data["lead_time_days"],
            )
        )

    # Sort descending by quantity for better UX
    needs.sort(key=lambda x: x.quantity_kg, reverse=True)

    return InventoryPlanResponse(plan_date=forecast.forecast_date, ingredients=needs)
