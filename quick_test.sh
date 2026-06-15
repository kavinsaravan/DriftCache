#!/bin/bash
set -e

echo "=== DriftCache Quick Local Test ==="
echo ""

# Step 1: Start PostgreSQL in Docker
echo "[1/7] Starting PostgreSQL..."
docker rm -f driftcache-postgres-test 2>/dev/null || true
docker run -d --name driftcache-postgres-test \
  -e POSTGRES_DB=driftcache \
  -e POSTGRES_USER=driftcache \
  -e POSTGRES_PASSWORD=driftcache_password \
  -p 5432:5432 \
  postgres:15-alpine
sleep 10
echo "✓ PostgreSQL ready"

# Step 2: Check Redis
echo "[2/7] Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
  echo "✗ Redis not running. Start it with: redis-server"
  exit 1
fi
echo "✓ Redis ready"

# Step 3: Install backend dependencies
echo "[3/7] Installing backend dependencies..."
cd /Users/kavins/Projects/DriftCache/backend
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Step 4: Run migrations
echo "[4/7] Running database migrations..."
export DATABASE_HOST="localhost"
export DATABASE_USER="driftcache"
export DATABASE_PASSWORD="driftcache_password"
export DATABASE_NAME="driftcache"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export OPENAI_API_KEY=$(grep OPENAI_API_KEY ../.env | cut -d '=' -f2)

alembic upgrade head
echo "✓ Migrations complete"

# Step 5: Start backend in background
echo "[5/7] Starting FastAPI backend..."
export EMBEDDING_MODEL="text-embedding-3-small"
export LLM_MODEL="gpt-4o-mini"
export DEFAULT_SIMILARITY_THRESHOLD="0.90"
export ENVIRONMENT="development"

uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/driftcache_backend.log 2>&1 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"
sleep 5

# Step 6: Test backend
echo "[6/7] Testing backend..."
if curl -s http://localhost:8000/status | grep -q "operational"; then
  echo "✓ Backend is operational"
else
  echo "✗ Backend failed to start. Check logs: tail /tmp/driftcache_backend.log"
  kill $BACKEND_PID 2>/dev/null || true
  exit 1
fi

# Step 7: Ready for benchmarks
echo "[7/7] System ready!"
echo ""
echo "Backend running at: http://localhost:8000"
echo "Backend logs: tail -f /tmp/driftcache_backend.log"
echo "Backend PID: $BACKEND_PID"
echo ""
echo "To run benchmarks:"
echo "  cd /Users/kavins/Projects/DriftCache"
echo "  pip install requests colorama aiohttp"
echo "  python benchmarks/semantic_cache_benchmark.py"
echo ""
echo "To stop:"
echo "  kill $BACKEND_PID"
echo "  docker rm -f driftcache-postgres-test"
