"""SQLAlchemy ORM models — all tables defined in LLD."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _uuid() -> str:
    """Generate a new UUID string for primary keys."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    covers: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_orders_timestamp_date", "timestamp"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("menu_items.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship(back_populates="order_items")


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="menu_item")
    recipe_entries: Mapped[list["RecipeMap"]] = relationship(back_populates="menu_item")


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------

class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    shelf_life_days: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)

    recipe_entries: Mapped[list["RecipeMap"]] = relationship(back_populates="ingredient")


# ---------------------------------------------------------------------------
# Recipe Map (menu item → ingredients)
# ---------------------------------------------------------------------------

class RecipeMap(Base):
    __tablename__ = "recipe_map"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("menu_items.id"), nullable=False, index=True)
    ingredient_id: Mapped[str] = mapped_column(String(36), ForeignKey("ingredients.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="recipe_entries")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_entries")


# ---------------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------------

class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    efficiency_factor: Mapped[float] = mapped_column(Float, nullable=False)


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------

class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_covers: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_forecasts_date_hour", "forecast_date", "hour", unique=True),
    )


# ---------------------------------------------------------------------------
# Actuals
# ---------------------------------------------------------------------------

class Actual(Base):
    __tablename__ = "actuals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_covers: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_actuals_date_hour", "record_date", "hour", unique=True),
    )


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    feedback_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    predicted: Mapped[int] = mapped_column(Integer, nullable=False)
    actual: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
