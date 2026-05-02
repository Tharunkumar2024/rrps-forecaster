"""Generate 1 year of synthetic restaurant data and insert into PostgreSQL.

Usage:
    python -m app.scripts.generate_data

This script uses SYNC SQLAlchemy (not async) because it's a one-shot CLI tool.
"""

import random
import uuid
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.models.tables import (
    Ingredient,
    MenuItem,
    Order,
    OrderItem,
    RecipeMap,
    Staff,
)

settings = get_settings()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MENU_ITEMS = [
    {"name": "Margherita Pizza", "price": 12.99},
    {"name": "Chicken Biryani", "price": 14.99},
    {"name": "Caesar Salad", "price": 9.99},
    {"name": "Grilled Salmon", "price": 18.99},
    {"name": "Pasta Carbonara", "price": 13.49},
    {"name": "Butter Chicken", "price": 15.99},
    {"name": "Veggie Burger", "price": 11.49},
    {"name": "Tom Yum Soup", "price": 8.99},
]

INGREDIENTS = [
    {"name": "flour", "shelf_life_days": 30, "lead_time_days": 2, "unit_cost": 1.5},
    {"name": "tomato", "shelf_life_days": 5, "lead_time_days": 1, "unit_cost": 2.0},
    {"name": "cheese", "shelf_life_days": 14, "lead_time_days": 2, "unit_cost": 4.0},
    {"name": "chicken", "shelf_life_days": 3, "lead_time_days": 1, "unit_cost": 6.0},
    {"name": "rice", "shelf_life_days": 60, "lead_time_days": 3, "unit_cost": 1.0},
    {"name": "salmon", "shelf_life_days": 2, "lead_time_days": 1, "unit_cost": 12.0},
    {"name": "pasta", "shelf_life_days": 90, "lead_time_days": 3, "unit_cost": 1.2},
    {"name": "lettuce", "shelf_life_days": 4, "lead_time_days": 1, "unit_cost": 1.5},
    {"name": "cream", "shelf_life_days": 7, "lead_time_days": 1, "unit_cost": 3.0},
    {"name": "spices", "shelf_life_days": 180, "lead_time_days": 5, "unit_cost": 8.0},
    {"name": "butter", "shelf_life_days": 14, "lead_time_days": 2, "unit_cost": 3.5},
    {"name": "onion", "shelf_life_days": 14, "lead_time_days": 1, "unit_cost": 0.8},
]

# Which ingredients go into which menu item (item_index → [(ingredient_index, qty_kg)])
RECIPE_MAPPING: dict[int, list[tuple[int, float]]] = {
    0: [(0, 0.3), (1, 0.2), (2, 0.15)],       # Margherita Pizza
    1: [(3, 0.25), (4, 0.3), (9, 0.02), (11, 0.1)],  # Chicken Biryani
    2: [(7, 0.15), (2, 0.05)],                  # Caesar Salad
    3: [(5, 0.2), (10, 0.05), (7, 0.1)],        # Grilled Salmon
    4: [(6, 0.25), (8, 0.1), (2, 0.1)],         # Pasta Carbonara
    5: [(3, 0.25), (1, 0.15), (10, 0.1), (8, 0.1), (9, 0.02)],  # Butter Chicken
    6: [(0, 0.2), (7, 0.1), (1, 0.1), (11, 0.1)],  # Veggie Burger
    7: [(3, 0.15), (9, 0.02), (11, 0.05)],      # Tom Yum Soup
}

STAFF_ROLES = [
    {"role": "waiter", "efficiency_factor": 15.0},
    {"role": "chef", "efficiency_factor": 20.0},
    {"role": "host", "efficiency_factor": 50.0},
]

# Hourly traffic weights (index = hour of day)
HOURLY_WEIGHTS = np.array([
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.05, 0.10, 0.15, 0.10, 0.08,
    0.30, 0.80, 1.00, 0.60, 0.20,
    0.15, 0.40, 0.70, 1.00, 0.90,
    0.50, 0.20, 0.05,
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_hourly_covers(
    dt: datetime,
    base_daily: float = 25.0,
) -> int:
    """Generate realistic cover count for a given hour.

    Applies: hourly weight, weekend boost, simple weather noise, random noise.
    """
    hour = dt.hour
    day_of_week = dt.weekday()
    weight = HOURLY_WEIGHTS[hour]

    if weight == 0.0:
        return 0

    covers = base_daily * weight

    # Weekend boost (Fri/Sat)
    if day_of_week >= 4:
        covers *= 1.4

    # Simulate weather effect — ~20% of days have "rain" that reduces traffic
    is_raining = random.random() < 0.20
    if is_raining:
        covers *= 0.7

    # Monthly seasonality — slight bump in Dec, dip in Jan
    month = dt.month
    if month == 12:
        covers *= 1.25
    elif month in (1, 2):
        covers *= 0.85

    # Random noise
    covers += np.random.normal(0, max(2, covers * 0.15))

    return max(0, int(round(covers)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    """Generate and insert all synthetic data."""
    engine = create_engine(
        settings.database_url_sync,
        echo=False,
    )

    # Create all tables (idempotent)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # -------------------------------------------------------------------
        # 1. Master data: menu items, ingredients, recipes, staff
        # -------------------------------------------------------------------
        print("[+] Inserting master data...")

        menu_items_db: list[MenuItem] = []
        for item in MENU_ITEMS:
            mi = MenuItem(id=str(uuid.uuid4()), name=item["name"], price=item["price"])
            menu_items_db.append(mi)
            session.add(mi)

        ingredients_db: list[Ingredient] = []
        for ing in INGREDIENTS:
            ig = Ingredient(id=str(uuid.uuid4()), **ing)
            ingredients_db.append(ig)
            session.add(ig)

        session.flush()  # flush so FKs resolve

        for item_idx, mappings in RECIPE_MAPPING.items():
            for ing_idx, qty in mappings:
                rm = RecipeMap(
                    id=str(uuid.uuid4()),
                    item_id=menu_items_db[item_idx].id,
                    ingredient_id=ingredients_db[ing_idx].id,
                    quantity=qty,
                )
                session.add(rm)

        for role_def in STAFF_ROLES:
            session.add(Staff(id=str(uuid.uuid4()), **role_def))

        session.flush()

        # -------------------------------------------------------------------
        # 2. Transactional data: 1 year of hourly orders
        # -------------------------------------------------------------------
        print("[+] Generating 1 year of synthetic order data...")

        start_date = datetime(2025, 5, 1, 0, 0, 0)
        end_date = datetime(2026, 5, 1, 0, 0, 0)
        current = start_date

        total_orders = 0
        batch: list = []

        while current < end_date:
            covers = _generate_hourly_covers(current)

            if covers > 0:
                # Simulate an aggregated "order" per hour
                avg_price = np.mean([m["price"] for m in MENU_ITEMS])
                total_amount = round(covers * avg_price * random.uniform(0.8, 1.2), 2)

                order = Order(
                    id=str(uuid.uuid4()),
                    timestamp=current,
                    covers=covers,
                    total_amount=total_amount,
                )
                session.add(order)

                # Add 1-3 random order items per hourly order
                num_items = random.randint(1, 3)
                chosen_items = random.sample(menu_items_db, min(num_items, len(menu_items_db)))
                for mi in chosen_items:
                    oi = OrderItem(
                        id=str(uuid.uuid4()),
                        order_id=order.id,
                        item_id=mi.id,
                        quantity=random.randint(1, max(1, covers // 3)),
                    )
                    session.add(oi)

                total_orders += 1

            # Flush in batches of 500 to keep memory low
            if total_orders % 500 == 0 and total_orders > 0:
                session.flush()

            current += timedelta(hours=1)

        session.commit()
        print(f"[OK] Done! Inserted {total_orders} hourly order records across ~365 days.")


if __name__ == "__main__":
    run()
