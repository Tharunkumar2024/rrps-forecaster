"""Initial schema — all tables from LLD

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-05-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- orders ---
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("covers", sa.Integer, nullable=False),
        sa.Column("total_amount", sa.Float, nullable=False),
    )
    op.create_index("ix_orders_timestamp_date", "orders", ["timestamp"])

    # --- menu_items ---
    op.create_table(
        "menu_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("price", sa.Float, nullable=False),
    )

    # --- order_items ---
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_item_id", "order_items", ["item_id"])

    # --- ingredients ---
    op.create_table(
        "ingredients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("shelf_life_days", sa.Integer, nullable=False),
        sa.Column("lead_time_days", sa.Integer, nullable=False),
        sa.Column("unit_cost", sa.Float, nullable=False),
    )

    # --- recipe_map ---
    op.create_table(
        "recipe_map",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.Column("ingredient_id", sa.String(36), sa.ForeignKey("ingredients.id"), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
    )
    op.create_index("ix_recipe_map_item_id", "recipe_map", ["item_id"])
    op.create_index("ix_recipe_map_ingredient_id", "recipe_map", ["ingredient_id"])

    # --- staff ---
    op.create_table(
        "staff",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("efficiency_factor", sa.Float, nullable=False),
    )

    # --- forecasts ---
    op.create_table(
        "forecasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("forecast_date", sa.Date, nullable=False),
        sa.Column("hour", sa.Integer, nullable=False),
        sa.Column("predicted_covers", sa.Integer, nullable=False),
    )
    op.create_index("ix_forecasts_date_hour", "forecasts", ["forecast_date", "hour"], unique=True)

    # --- actuals ---
    op.create_table(
        "actuals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("record_date", sa.Date, nullable=False),
        sa.Column("hour", sa.Integer, nullable=False),
        sa.Column("actual_covers", sa.Integer, nullable=False),
    )
    op.create_index("ix_actuals_date_hour", "actuals", ["record_date", "hour"], unique=True)

    # --- feedback ---
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("feedback_date", sa.Date, nullable=False),
        sa.Column("predicted", sa.Integer, nullable=False),
        sa.Column("actual", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_feedback_date", "feedback", ["feedback_date"])


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("actuals")
    op.drop_table("forecasts")
    op.drop_table("staff")
    op.drop_table("recipe_map")
    op.drop_table("order_items")
    op.drop_table("ingredients")
    op.drop_table("menu_items")
    op.drop_table("orders")
