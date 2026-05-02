"""Unit tests for the Staff Optimization Engine."""

import pytest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.schemas.forecast import ForecastResponse, HourlyForecast
from app.services.staff_planner import generate_staff_plan, _optimize_hour


def test_staff_ortools_optimal():
    """U-005: Optimize staff with typical demand."""
    efficiency_map = {"waiter": 15.0, "chef": 20.0, "host": 50.0}
    predicted_covers = 50
    
    roles = _optimize_hour(predicted_covers, efficiency_map)
    role_dict = {r.role: r.count for r in roles}
    
    # 50 covers / 15 waiter eff = 3.33 -> 4 waiters
    # 50 covers * 1.5 dishes = 75 dishes / 20 chef eff = 3.75 -> 4 chefs
    # 50 covers / 50 host eff = 1 host
    assert role_dict["waiter"] == 4
    assert role_dict["chef"] == 4
    assert role_dict["host"] == 1


def test_staff_zero_demand():
    """U-006: Staff logic when demand is 0."""
    efficiency_map = {"waiter": 15.0, "chef": 20.0, "host": 50.0}
    roles = _optimize_hour(0, efficiency_map)
    assert len(roles) == 0


def test_staff_high_demand():
    """U-007: Staff logic for extreme covers (unboundedness check)."""
    efficiency_map = {"waiter": 15.0, "chef": 20.0, "host": 50.0}
    roles = _optimize_hour(1500, efficiency_map)
    role_dict = {r.role: r.count for r in roles}
    
    assert role_dict["waiter"] == 100  # 1500 / 15
    assert role_dict["chef"] == 113  # 1500 * 1.5 = 2250 / 20
    assert role_dict["host"] == 30   # 1500 / 50


def test_staff_ortools_fail_fallback():
    """U-008: Solver fails to find feasible plan (simulate internal solver exception)."""
    efficiency_map = {"waiter": 15.0, "chef": 20.0, "host": 50.0}
    
    # Mock CpSolver.Solve to return INFEASIBLE (which raises RuntimeError in our code)
    with patch("ortools.sat.python.cp_model.CpSolver.Solve", return_value=3): # 3 = INFEASIBLE
        with pytest.raises(RuntimeError) as exc_info:
            _optimize_hour(50, efficiency_map)
        
        assert "OR-Tools failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_staff_service_fallback(test_db):
    """Test the outer generate_staff_plan handling the failure properly and falling back."""
    forecast = ForecastResponse(
        forecast_date=date(2026, 5, 10),
        hourly_forecast=[HourlyForecast(hour=12, predicted_covers=50)]
    )
    
    # Force _optimize_hour to throw exception, trigger fallback
    with patch("app.services.staff_planner._optimize_hour", side_effect=Exception("Solver crashed")):
        plan = await generate_staff_plan(test_db, forecast)
        
    assert plan.plan_date == date(2026, 5, 10)
    assert len(plan.hourly_plan) == 1
    
    # Even though optimizer crashed, we still get the math fallback plan!
    roles = {r.role: r.count for r in plan.hourly_plan[0].roles}
    assert roles["waiter"] == 4
    assert roles["chef"] == 4


def test_api_staff_default_date(client: TestClient):
    """A-007: GET /staff-plan with missing target_date defaults properly."""
    with patch("app.api.staff.generate_staff_plan") as mock_gen, \
         patch("app.api.staff.generate_forecast"):
        
        from app.schemas.staff_plan import StaffPlanResponse
        mock_gen.return_value = StaffPlanResponse(plan_date=date(2026,1,1), hourly_plan=[])
        
        response = client.get("/api/v1/staff-plan")
        
    assert response.status_code == 200
