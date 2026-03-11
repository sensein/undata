#!/bin/sh
set -e

# Run Alembic migrations before starting the server
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Start the server
exec uvicorn src.main:app --host 0.0.0.0 --port 8002
