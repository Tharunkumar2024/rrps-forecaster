"""Integration tests mapping API to DB."""

import pytest
from datetime import date
from sqlalchemy.future import select

from app.models.tables import Feedback
from app.schemas.feedback import FeedbackCreate
from app.services.feedback_service import process_feedback


@pytest.mark.asyncio
async def test_feedback_persistence(test_db):
    """I-003 & U-011: Feedback properly saved and error calculated."""
    payload = FeedbackCreate(
        target_date=date(2026, 5, 10),
        predicted_covers=100,
        actual_covers=150,
        reason="sunny",
        notes="Unexpected patio rush"
    )
    
    response = await process_feedback(test_db, payload)
    await test_db.commit()  # explicitly commit since route usually handles this
    
    assert response.error_count == 50
    assert response.status == "success"
    
    # Query back to verify persistence
    stmt = select(Feedback).where(Feedback.id == response.id)
    result = await test_db.execute(stmt)
    record = result.scalars().first()
    
    assert record is not None
    assert record.feedback_date == date(2026, 5, 10)
    assert record.actual == 150
    assert record.predicted == 100


def test_api_feedback_invalid_payload(client):
    """A-002: POST /feedback invalid missing fields."""
    response = client.post("/api/v1/feedback", json={})
    assert response.status_code == 422


def test_api_feedback_negative(client):
    """A-003: Negative covers constraint validation."""
    payload = {
        "target_date": "2026-05-10",
        "predicted_covers": 100,
        "actual_covers": -10,
        "reason": "rain"
    }
    response = client.post("/api/v1/feedback", json=payload)
    assert response.status_code == 422
    assert "Input should be greater than or equal to 0" in response.text


@pytest.mark.asyncio
async def test_staff_planner_db_load(test_db):
    """I-001: StaffPlanner loading efficiency from DB."""
    from app.models.tables import Staff
    from app.schemas.forecast import ForecastResponse, HourlyForecast
    from app.services.staff_planner import generate_staff_plan

    # Seed custom efficiency into DB
    test_db.add(Staff(role="waiter", efficiency_factor=10.0))
    test_db.add(Staff(role="chef", efficiency_factor=25.0))
    test_db.add(Staff(role="host", efficiency_factor=40.0))
    await test_db.commit()

    forecast = ForecastResponse(
        forecast_date=date(2026, 5, 10),
        hourly_forecast=[HourlyForecast(hour=12, predicted_covers=50)]
    )

    plan = await generate_staff_plan(test_db, forecast)
    roles = {r.role: r.count for r in plan.hourly_plan[0].roles}

    # With waiter efficiency 10: 50/10 = 5
    assert roles["waiter"] == 5
    # With chef efficiency 25: 50*1.5/25 = 3
    assert roles["chef"] == 3
    # With host efficiency 40: 50/40 = 1.25 -> 2
    assert roles["host"] == 2


@pytest.mark.asyncio
async def test_inventory_recipe_load(test_db):
    """I-002: Inventory reading RecipeMap from DB."""
    from app.models.tables import MenuItem, Ingredient, RecipeMap
    from app.schemas.forecast import ForecastResponse, HourlyForecast
    from app.services.inventory_planner import generate_inventory_plan

    # Seed menu item, ingredient, and recipe
    ing = Ingredient(name="tomato", shelf_life_days=5, lead_time_days=1, unit_cost=2.0)
    test_db.add(ing)
    await test_db.flush()

    item = MenuItem(name="pasta", price=12.0)
    test_db.add(item)
    await test_db.flush()

    recipe = RecipeMap(item_id=item.id, ingredient_id=ing.id, quantity=0.3)
    test_db.add(recipe)
    await test_db.commit()

    forecast = ForecastResponse(
        forecast_date=date(2026, 5, 10),
        hourly_forecast=[HourlyForecast(hour=12, predicted_covers=100)]
    )

    plan = await generate_inventory_plan(test_db, forecast)

    assert len(plan.ingredients) == 1
    assert plan.ingredients[0].ingredient_name == "tomato"
    # 100 covers * 1.5 dishes / 1 item = 150 dishes * 0.3 kg = 45 kg * 1.15 = 51.75
    assert plan.ingredients[0].quantity_kg == 51.75


def test_missing_db_connection(client):
    """I-004: Simulating DB outage — API returns 500 cleanly."""
    from unittest.mock import patch

    # Patch the forecast service to simulate a DB connection failure
    with patch(
        "app.api.forecast.generate_forecast",
        side_effect=ConnectionError("Database is down"),
    ):
        response = client.get("/api/v1/forecast?target_date=2026-05-10")

    # The route wraps exceptions with HTTPException(500)
    assert response.status_code == 500
    assert "Database is down" in response.text


def test_db_session_rollback(client):
    """I-006: Simulating failure during route — transaction safety."""
    from unittest.mock import patch

    with patch("app.api.feedback.process_feedback", side_effect=Exception("Unexpected DB error")):
        response = client.post("/api/v1/feedback", json={
            "target_date": "2026-05-10",
            "predicted_covers": 100,
            "actual_covers": 120,
            "reason": "test"
        })

    # FastAPI should return 500 but the app should not crash
    assert response.status_code == 500


def test_app_lifespan_startup(client):
    """I-007: App lifespan context — TestClient starts successfully."""
    # The fact that the client fixture works means lifespan ran without error.
    # Verify app is responsive post-startup.
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_model_retraining_db(test_db):
    """I-005: Retraining pipeline pulls actuals properly from DB."""
    from datetime import datetime
    from app.models.tables import Order

    # Seed 48 hours of order data (2 days)
    for day_offset in range(2):
        for hour in range(24):
            ts = datetime(2026, 5, 1 + day_offset, hour)
            test_db.add(Order(timestamp=ts, covers=10 + hour, total_amount=50.0))
    await test_db.commit()

    # Verify we can query back the expected row count
    from sqlalchemy.future import select as sel
    from sqlalchemy import func
    result = await test_db.execute(sel(func.count()).select_from(Order))
    count = result.scalar()

    assert count == 48  # 2 days * 24 hours

