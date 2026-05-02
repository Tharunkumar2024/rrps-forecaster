"""Offline training pipeline for the demand forecast model.

Usage:
    python -m app.scripts.train_forecast_model

Trains an XGBoost regressor on historical hourly order data,
evaluates on a held-out test set, and saves the model artifact.
"""

import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from sqlalchemy import create_engine, text
from xgboost import XGBRegressor

from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Operating hours: the restaurant is open from 6 AM to 11 PM.
# Hours outside this range always have 0 covers — training on them adds noise.
OPERATING_HOURS = set(range(6, 24))


# ---------------------------------------------------------------------------
# 1. Data loading
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw order data and feedback data from the database."""
    engine = create_engine(settings.database_url_sync, echo=False)

    query_orders = text("""
        SELECT timestamp, covers
        FROM orders
        ORDER BY timestamp
    """)
    query_feedback = text("""
        SELECT feedback_date, actual
        FROM feedback
    """)

    with engine.connect() as conn:
        orders_df = pd.read_sql(query_orders, conn)
        feedback_df = pd.read_sql(query_feedback, conn)

    if orders_df.empty:
        logger.error("No order data found in database. Run generate_data first.")
        sys.exit(1)

    logger.info("Loaded %d raw order records and %d feedback records", len(orders_df), len(feedback_df))
    return orders_df, feedback_df


def apply_feedback_scaling(orders_df: pd.DataFrame, feedback_df: pd.DataFrame) -> pd.DataFrame:
    """Scale hourly covers in orders_df based on actuals from feedback_df."""
    if feedback_df.empty:
        return orders_df

    orders_df = orders_df.copy()
    orders_df["date"] = pd.to_datetime(orders_df["timestamp"]).dt.date
    feedback_df["date"] = pd.to_datetime(feedback_df["feedback_date"]).dt.date

    # Group orders by date to get the original daily total
    daily_totals = orders_df.groupby("date")["covers"].sum().reset_index()
    daily_totals.rename(columns={"covers": "original_daily_covers"}, inplace=True)

    # Merge feedback and calculate scaling factor
    merged = pd.merge(daily_totals, feedback_df, on="date", how="left")
    merged["scaling_factor"] = 1.0
    
    # Where we have feedback, calculate scaling factor: actual / original (avoid division by zero)
    mask = merged["actual"].notna() & (merged["original_daily_covers"] > 0)
    merged.loc[mask, "scaling_factor"] = merged.loc[mask, "actual"] / merged.loc[mask, "original_daily_covers"]
    
    # Handle case where original is 0 but actual is > 0 (can't simply scale, would need to distribute)
    # For simplicity, we just won't scale if original was exactly 0.

    # Merge scaling factor back to orders
    orders_df = pd.merge(orders_df, merged[["date", "scaling_factor"]], on="date", how="left")
    
    # Apply scaling
    orders_df["covers"] = orders_df["covers"] * orders_df["scaling_factor"]
    
    # Clean up
    orders_df.drop(columns=["date", "scaling_factor"], inplace=True)
    
    return orders_df


# ---------------------------------------------------------------------------
# 2. Feature engineering
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer time-based features from the order timestamps.

    Each row represents one hour with the target being 'covers'.
    Features capture daily, weekly, and monthly patterns.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Aggregate to hourly (idempotent since synthetic data is already hourly)
    df = (
        df.set_index("timestamp")
        .resample("h")["covers"]
        .sum()
        .reset_index()
    )
    df.rename(columns={"timestamp": "ds", "covers": "y"}, inplace=True)

    # Time features
    df["hour"] = df["ds"].dt.hour
    df["day_of_week"] = df["ds"].dt.dayofweek       # Mon=0, Sun=6
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_friday"] = (df["day_of_week"] == 4).astype(int)
    df["month"] = df["ds"].dt.month
    df["day_of_month"] = df["ds"].dt.day
    df["week_of_year"] = df["ds"].dt.isocalendar().week.astype(int)

    # Peak hour indicators
    df["is_lunch_peak"] = df["hour"].isin([12, 13, 14]).astype(int)
    df["is_dinner_peak"] = df["hour"].isin([18, 19, 20, 21]).astype(int)

    # Cyclical encodings for hour and day-of-week
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # Lag features (covers from same hour yesterday, 7 days ago)
    df["lag_24h"] = df["y"].shift(24)
    df["lag_168h"] = df["y"].shift(168)  # 1 week

    # Rolling averages
    df["rolling_24h_mean"] = df["y"].shift(1).rolling(window=24, min_periods=1).mean()
    df["rolling_7d_mean"] = df["y"].shift(1).rolling(window=168, min_periods=1).mean()

    # Drop rows with NaN from lag/rolling
    df.dropna(inplace=True)

    # Filter to operating hours only — non-operating hours always produce 0
    df = df[df["hour"].isin(OPERATING_HOURS)].reset_index(drop=True)

    logger.info("Feature matrix shape (operating hours only): %s", df.shape)
    return df


# ---------------------------------------------------------------------------
# 3. Training
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "hour", "day_of_week", "is_weekend", "is_friday",
    "month", "day_of_month", "week_of_year",
    "is_lunch_peak", "is_dinner_peak",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "month_sin", "month_cos",
    "lag_24h", "lag_168h",
    "rolling_24h_mean", "rolling_7d_mean",
]


def train_model(df: pd.DataFrame) -> tuple:
    """Train/test split, fit XGBoost, return (model, mape, mae, test_df)."""
    # Chronological split — 80% train, 20% test
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    x_train = train_df[FEATURE_COLS]
    y_train = train_df["y"]
    x_test = test_df[FEATURE_COLS]
    y_test = test_df["y"]

    logger.info("Train size: %d, Test size: %d", len(train_df), len(test_df))

    model = XGBRegressor(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbosity=0,
    )

    model.fit(
        x_train, y_train,
        eval_set=[(x_test, y_test)],
        verbose=False,
    )

    # Predict on test set
    y_pred = model.predict(x_test)
    y_pred = np.maximum(y_pred, 0).round()  # covers can't be negative

    # MAE — always meaningful
    mae = mean_absolute_error(y_test, y_pred)

    # MAPE — filter zero actuals to avoid division by zero
    mask = y_test > 0
    if mask.sum() == 0:
        logger.warning("No non-zero actuals in test set - MAPE undefined")
        mape = 0.0
    else:
        mape = mean_absolute_percentage_error(y_test[mask], y_pred[mask])

    # WMAPE (Weighted MAPE) — better for low-count data
    # = sum(|actual - pred|) / sum(actual)
    total_actual = y_test.sum()
    wmape = np.abs(y_test.values - y_pred).sum() / total_actual if total_actual > 0 else 0.0

    return model, mape, wmape, mae, test_df


# ---------------------------------------------------------------------------
# 4. Save model
# ---------------------------------------------------------------------------

def save_model(model: XGBRegressor, mape: float) -> Path:
    """Save the trained model and metadata to disk."""
    model_dir = settings.model_dir
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = settings.forecast_model_path
    artifact = {
        "model": model,
        "feature_cols": FEATURE_COLS,
        "operating_hours": sorted(OPERATING_HOURS),
        "mape": mape,
    }
    joblib.dump(artifact, model_path)
    logger.info("Model saved to %s", model_path)
    return model_path


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def run() -> None:
    """Execute the full training pipeline."""
    logger.info("=" * 60)
    logger.info("FORECAST MODEL TRAINING PIPELINE")
    logger.info("=" * 60)

    # Load
    orders_df, feedback_df = load_data()
    
    # Apply feedback corrections
    raw_df = apply_feedback_scaling(orders_df, feedback_df)

    # Feature engineering
    feature_df = build_features(raw_df)

    # Train
    model, mape, wmape, mae, test_df = train_model(feature_df)

    # Evaluate
    logger.info("-" * 40)
    logger.info("MAE  on test set: %.2f covers", mae)
    logger.info("MAPE on test set: %.2f%% (sensitive to low-volume hours)", mape * 100)
    logger.info("WMAPE on test set: %.2f%% (volume-weighted, primary metric)", wmape * 100)
    if wmape < 0.20:
        logger.info("[PASS] WMAPE is below 20%% target")
    else:
        logger.warning("[WARN] WMAPE exceeds 20%% target")
        # Improvement suggestions (in comments only):
        # - Add actual weather data as regressors
        # - Try lag features at more granularities (2h, 4h)
        # - Increase n_estimators or tune learning_rate
        # - Add holiday/event flags from external calendar
    logger.info("-" * 40)

    # Save
    save_model(model, wmape)

    logger.info("Training pipeline complete.")


if __name__ == "__main__":
    run()
