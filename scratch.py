import asyncio
from datetime import date
from app.db.session import async_session_factory
from app.services.forecast_service import _build_inference_features

async def main():
    async with async_session_factory() as db:
        df = await _build_inference_features(db, date(2026, 4, 15))
        
        print("Total rows:", len(df))
        print("Target rows:", len(df))
        print(df[["ds", "y", "lag_168h", "rolling_7d_mean"]].head(24))
        
        # Check nulls for operating hours
        op_df = df[df["hour"].isin(range(6, 24))]
        print("Nulls in op_df:")
        print(op_df.isnull().sum())

if __name__ == "__main__":
    asyncio.run(main())
