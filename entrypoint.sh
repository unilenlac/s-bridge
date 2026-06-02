#!/bin/sh
set -e

echo "Running database migrations via Alembic..."
alembic upgrade head

echo "Starting FastAPI application via Uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8500
