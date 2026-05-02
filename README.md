# RRPS Forecaster AI 🚀

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![OR-Tools](https://img.shields.io/badge/Optimization-Google_OR--Tools-orange.svg)](https://developers.google.com/optimization)
[![XGBoost](https://img.shields.io/badge/ML-XGBoost-blueviolet.svg)](https://xgboost.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, feedback-driven AI system designed to eliminate restaurant waste by optimizing demand forecasting, staff scheduling, and inventory procurement. 

Unlike traditional static dashboards, RRPS Forecaster is a **Continuous Learning System**. It accepts ground-truth feedback from restaurant managers and mathematically corrects its historical datasets to improve future predictions.

---

## ✨ Core Features

1. **Demand Forecasting (XGBoost)**: Predicts hourly customer covers based on historical trends, seasonality, and day-of-week cyclic features. Includes a heuristic rule-based fallback if the model is unavailable.
2. **Staff Optimization (Google OR-Tools)**: Uses Constraint Programming (CP-SAT) to generate the mathematically optimal schedule, minimizing labor costs while guaranteeing SLA coverage during peak rushes.
3. **Net Inventory Procurement**: Calculates exactly how much food to order by combining forecasted demand, 15% safety stock, ingredient shelf-life perishing limits, supplier lead times, and current physical stock.
4. **Manager Feedback Loop**: A robust API that ingests actual cover data. The offline training pipeline automatically scales historical data against this ground-truth before rebuilding the feature matrix, ensuring the model self-corrects over time.
5. **Premium UI Dashboard**: A sleek, dark-mode glassmorphic frontend utilizing `Chart.js` to visualize operational metrics.

---

## 🛠 Tech Stack

- **Backend Framework**: FastAPI (Async)
- **Database**: PostgreSQL (Production) / SQLite (Dev)
- **ORM & Migrations**: SQLAlchemy 2.0 & Alembic
- **Machine Learning**: XGBoost, Scikit-Learn, Pandas
- **Optimization Engine**: Google OR-Tools (CP-SAT Solver)
- **Frontend**: Vanilla JS, HTML5, Vanilla CSS (Glassmorphism design)
- **Observability**: Prometheus (`prometheus-fastapi-instrumentator`)

---

## 🚦 Quick Start (Local Development)

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Initialization
By default, the system uses a local SQLite database (`rrps_dev.db`).
```bash
# Run Alembic migrations to build the schema
alembic upgrade head
```

### 3. Generate Training Data
Generate 1 year of synthetic hourly POS data to train the model.
```bash
python -m app.scripts.generate_data
```

### 4. Train the ML Model
Train the XGBoost forecaster. This step will save a `.pkl` artifact in the `/models` directory.
```bash
python -m app.scripts.train_forecast_model
```

### 5. Start the Server
```bash
python main.py
```
- **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **UI Dashboard**: [http://localhost:8000](http://localhost:8000)

---

## 🧪 Running Tests

The system includes a comprehensive pytest suite (Unit, Integration, and E2E) validating the API, the ML fallbacks, and the deterministic OR-Tools constraints.

```bash
python -m pytest tests/ -v
```

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| **GET** | `/health` | Kubernetes-style liveness probe. |
| **GET** | `/metrics` | Prometheus metrics scrape endpoint. |
| **GET** | `/api/v1/model-info` | Returns AI model health, WMAPE accuracy, and active features. |
| **GET** | `/api/v1/forecast` | Returns predicted hourly covers for a target date. |
| **GET** | `/api/v1/staff-plan` | Returns the optimized staffing schedule (Waiters, Chefs, etc.). |
| **POST** | `/api/v1/inventory-plan` | Accepts `current_stock` and returns the Net Procurement needed. |
| **POST** | `/api/v1/feedback` | Ingests manager corrections (actuals vs predictions) into the DB. |

---

## 🏗 Architecture & Project Structure

```text
rrps-forecaster/
├── app/
│   ├── api/              # FastAPI route controllers
│   ├── core/             # Application config and logging
│   ├── db/               # SQLAlchemy session and base
│   ├── models/           # Database schema definitions
│   ├── schemas/          # Pydantic validation models
│   ├── scripts/          # Offline data generation & ML training pipelines
│   └── services/         # Core business logic (Forecast, Staff, Inventory)
├── frontend/             # Vanilla JS/CSS/HTML Premium Dashboard UI
├── tests/                # Pytest suite (unit, integration, e2e)
├── alembic/              # Database migration versions
├── docs/                 # Architecture reviews, HLD, LLD, and PRD
├── requirements.txt      # Python dependencies
└── main.py               # Application entry point
```

## 📈 Production Orchestration Note
The `train_forecast_model.py` script is strictly decoupled from the FastAPI web server to prevent memory starvation and concurrency race conditions. In a production environment, this script should be invoked via an external orchestrator (e.g., **Apache Airflow**, **Prefect**, or a Kubernetes CronJob) nightly to ingest the latest `/feedback` records.
