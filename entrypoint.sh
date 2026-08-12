#!/bin/sh
set -e

echo "Running database migrations via Alembic..."
alembic upgrade head

echo "Starting FastAPI application via Uvicorn..."
exec python main.py
