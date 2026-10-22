#!/bin/bash
set -e

echo "Starting DriftCache API..."

# Wait for PostgreSQL with timeout (max 60 seconds)
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for PostgreSQL to be ready..."
    timeout=60
    counter=0
    until pg_isready -d "$DATABASE_URL" > /dev/null 2>&1 || [ $counter -eq $timeout ]; do
        echo "PostgreSQL is unavailable - sleeping (${counter}s/${timeout}s)"
        sleep 2
        counter=$((counter + 2))
    done

    if [ $counter -eq $timeout ]; then
        echo "Warning: PostgreSQL not ready after ${timeout}s, starting anyway..."
    else
        echo "PostgreSQL is ready!"
    fi
fi

# Wait for Redis with timeout (max 30 seconds)
if [ -n "$REDIS_URL" ]; then
    echo "Waiting for Redis to be ready..."
    timeout=30
    counter=0
    until redis-cli -u "$REDIS_URL" ping > /dev/null 2>&1 || [ $counter -eq $timeout ]; do
        echo "Redis is unavailable - sleeping (${counter}s/${timeout}s)"
        sleep 2
        counter=$((counter + 2))
    done

    if [ $counter -eq $timeout ]; then
        echo "Warning: Redis not ready after ${timeout}s, starting anyway..."
    else
        echo "Redis is ready!"
    fi
fi

# Start the application (migrations run in app startup)
echo "Starting uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
