#!/bin/bash
set -e

echo "Starting DriftCache Backend..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h $DATABASE_HOST -p 5432 -U $DATABASE_USER; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "PostgreSQL is ready!"

# Wait for Redis to be ready
echo "Waiting for Redis..."
until redis-cli -h $REDIS_HOST ping; do
  echo "Redis is unavailable - sleeping"
  sleep 2
done
echo "Redis is ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
