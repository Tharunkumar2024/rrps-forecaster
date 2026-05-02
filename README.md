# RRPS Forecaster

AI-Powered Restaurant Demand, Staffing, and Inventory Optimization System.

## Prerequisites
- Python 3.11+
- Docker (optional, for PostgreSQL in production)

## Quick Start

### 1. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### 2. Run Database Migrations
```bash
alembic upgrade head
```

### 3. Generate Synthetic Data (1 year of hourly POS data)
```bash
python -m app.scripts.generate_data
```

### 4. Start the API Server
```bash
python main.py
```

### 5. Open Swagger UI
Navigate to: [http://localhost:8000/docs](http://localhost:8000/docs)

## API Endpoints

| Method | Endpoint                | Description                        |
|--------|-------------------------|------------------------------------|
| GET    | `/health`               | Liveness check                     |
| GET    | `/api/v1/forecast`      | Hourly demand forecast             |
| GET    | `/api/v1/staff-plan`    | Staff scheduling recommendation    |
| GET    | `/api/v1/inventory-plan`| Ingredient procurement plan        |

## Database

- **Local Dev:** SQLite (zero setup, file-based at `rrps_dev.db`)
- **Production:** PostgreSQL (update `DATABASE_URL` in `.env`)

## Project Structure
```
app/
  api/          # FastAPI route definitions
  core/         # Config, settings
  db/           # SQLAlchemy engine, base
  models/       # ORM table models
  schemas/      # Pydantic request/response models
  scripts/      # Data generation & utility scripts
  services/     # Business logic layer
alembic/        # Database migrations
```
