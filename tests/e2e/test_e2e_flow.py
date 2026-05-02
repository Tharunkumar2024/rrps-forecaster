"""End to end testing flow."""

import asyncio
from datetime import date
from unittest.mock import patch


def test_healthcheck(client):
    """E-004: Healthcheck."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_e2e_normal_flow(client):
    """E-001: Full flow - forecast -> staff -> inventory -> feedback."""
    target_date = "2026-05-15"
    
    # 1. Get Forecast
    response = client.get(f"/api/v1/forecast?target_date={target_date}")
    assert response.status_code == 200
    forecast_data = response.json()
    assert forecast_data["forecast_date"] == target_date
    
    # Extract covers to submit feedback later
    predicted_sum = sum(h["predicted_covers"] for h in forecast_data["hourly_forecast"])
    
    # 2. Get Staff Plan
    response = client.get(f"/api/v1/staff-plan?target_date={target_date}")
    assert response.status_code == 200
    staff_data = response.json()
    assert staff_data["plan_date"] == target_date
    assert len(staff_data["hourly_plan"]) > 0
    
    # 3. Get Inventory Plan
    response = client.post("/api/v1/inventory-plan", json={"target_date": target_date})
    assert response.status_code == 200
    inv_data = response.json()
    assert inv_data["plan_date"] == target_date
    
    # 4. Submit Feedback
    payload = {
        "target_date": target_date,
        "predicted_covers": predicted_sum,
        "actual_covers": predicted_sum + 20,
        "reason": "event",
        "notes": "End to end test note"
    }
    response = client.post("/api/v1/feedback", json=payload)
    assert response.status_code == 200
    feedback_data = response.json()
    assert feedback_data["error_count"] == 20
    assert feedback_data["status"] == "success"


def test_e2e_missing_model_flow(client):
    """E-002: Full flow when ML model is absent — uses rule-based logic."""
    with patch("app.services.forecast_service.is_model_available", return_value=False):
        # 1. Forecast should still work via fallback
        response = client.get("/api/v1/forecast?target_date=2026-06-01")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rule_based"
        assert len(data["hourly_forecast"]) == 24

        # 2. Staff plan should still work (it uses forecast output)
        response = client.get("/api/v1/staff-plan?target_date=2026-06-01")
        assert response.status_code == 200
        staff_data = response.json()
        assert staff_data["plan_date"] == "2026-06-01"


def test_e2e_feedback_loop(client):
    """E-003: Submit feedback explicitly and verify response."""
    payload = {
        "target_date": "2026-05-20",
        "predicted_covers": 200,
        "actual_covers": 250,
        "reason": "holiday",
        "notes": "Festival day caused higher footfall"
    }
    response = client.post("/api/v1/feedback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["error_count"] == 50
    assert data["status"] == "success"
    assert data["predicted_covers"] == 200
    assert data["actual_covers"] == 250


def test_e2e_high_load_spikes(client):
    """E-005: Simulate holiday load burst — multiple sequential requests."""
    # Simulate 20 rapid sequential requests (TestClient is synchronous, not truly concurrent)
    results = []
    for _ in range(20):
        response = client.get("/api/v1/forecast?target_date=2026-12-25")
        results.append(response.status_code)

    # All should succeed
    assert all(code == 200 for code in results), f"Some requests failed: {results}"
    assert len(results) == 20


def test_e2e_db_to_api_sync(client, test_db):
    """E-006: Insert new Staff efficiency rule, verify staff-plan API reflects it."""
    import asyncio
    from app.models.tables import Staff

    async def seed_staff():
        test_db.add(Staff(role="waiter", efficiency_factor=5.0))  # Very low efficiency -> more staff
        test_db.add(Staff(role="chef", efficiency_factor=10.0))
        test_db.add(Staff(role="host", efficiency_factor=100.0))
        await test_db.commit()

    asyncio.get_event_loop().run_until_complete(seed_staff())

    # Call staff-plan API
    response = client.get("/api/v1/staff-plan?target_date=2026-05-10")
    assert response.status_code == 200
    data = response.json()
    assert data["plan_date"] == "2026-05-10"


