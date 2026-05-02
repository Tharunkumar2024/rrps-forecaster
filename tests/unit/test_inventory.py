"""Unit tests for the Inventory Service."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.schemas.forecast import ForecastResponse, HourlyForecast
from app.services.inventory_planner import generate_inventory_plan


@pytest.mark.asyncio
async def test_inventory_exact_calc(test_db):
    """U-009 & U-016: Deterministic mapping and safety stock verification."""
    # Forecast total covers = 100
    forecast = ForecastResponse(
        forecast_date=date(2026, 5, 10),
        hourly_forecast=[
            HourlyForecast(hour=12, predicted_covers=40),
            HourlyForecast(hour=13, predicted_covers=60)
        ]
    )
    
    # 100 covers * 1.5 dishes/cover = 150 dishes total
    
    # Mocking DB response for MenuItems and their RecipeMaps
    mock_item = MagicMock()
    mock_recipe = MagicMock()
    mock_recipe.ingredient.name = "chicken"
    mock_recipe.ingredient.shelf_life_days = 3
    mock_recipe.ingredient.lead_time_days = 1
    mock_recipe.quantity = 0.2  # 0.2 kg of chicken per dish
    mock_item.recipe_entries = [mock_recipe]
    
    # We pretend the DB returned only 1 menu item, so all 150 dishes go to it
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_item]
    
    with patch.object(test_db, "execute", return_value=mock_result):
        plan = await generate_inventory_plan(test_db, forecast)
        
    assert plan.plan_date == date(2026, 5, 10)
    assert len(plan.ingredients) == 1
    
    # 150 dishes * 0.2 kg = 30 kg base
    # 30 kg * 1.15 safety factor = 34.5 kg
    assert plan.ingredients[0].ingredient_name == "chicken"
    assert plan.ingredients[0].quantity_kg == 34.5


@pytest.mark.asyncio
async def test_inventory_empty_menu(test_db):
    """U-010: Inventory logic when menu is empty."""
    forecast = ForecastResponse(
        forecast_date=date(2026, 5, 10),
        hourly_forecast=[HourlyForecast(hour=12, predicted_covers=100)]
    )
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    
    with patch.object(test_db, "execute", return_value=mock_result):
        plan = await generate_inventory_plan(test_db, forecast)
        
    assert plan.plan_date == date(2026, 5, 10)
    assert plan.ingredients == []


def test_api_inventory_default_date(client: TestClient):
    """A-008: GET /inventory-plan with missing target_date defaults properly."""
    with patch("app.api.inventory.generate_inventory_plan") as mock_gen, \
         patch("app.api.inventory.generate_forecast"):
        
        from app.schemas.inventory_plan import InventoryPlanResponse
        mock_gen.return_value = InventoryPlanResponse(plan_date=date(2026,1,1), ingredients=[])
        
        response = client.get("/api/v1/inventory-plan")
        
    assert response.status_code == 200
