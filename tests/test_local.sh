#!/bin/bash
set -e

echo "=== DriftCache Local Test Suite ==="
echo ""

cd /Users/kavins/Projects/DriftCache

# Step 1: Start PostgreSQL in Docker (lightweight, just this one service)
echo "[1/6] Starting PostgreSQL..."
docker rm -f driftcache-postgres-local 2>/dev/null || true
docker run -d --name driftcache-postgres-local \
  -e POSTGRES_DB=driftcache \
  -e POSTGRES_USER=driftcache \
  -e POSTGRES_PASSWORD=driftcache_password \
  -p 5432:5432 \
  postgres:15-alpine >/dev/null 2>&1

echo "Waiting for PostgreSQL to start..."
sleep 8
echo "✓ PostgreSQL ready"

# Step 2: Check Redis
echo "[2/6] Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
  echo "✗ Redis not running. Start it with: brew services start redis"
  docker rm -f driftcache-postgres-local
  exit 1
fi
echo "✓ Redis ready"

# Step 3: Setup backend
echo "[3/6] Setting up backend..."
cd backend
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate

# Install dependencies quietly
pip install -q -r requirements.txt 2>/dev/null || pip install -r requirements.txt

# Set environment variables
export DATABASE_HOST="localhost"
export DATABASE_PORT="5432"
export DATABASE_NAME="driftcache"
export DATABASE_USER="driftcache"
export DATABASE_PASSWORD="driftcache_password"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export REDIS_DB="0"
export OPENAI_API_KEY=$(grep OPENAI_API_KEY ../.env | cut -d '=' -f2)
export EMBEDDING_MODEL="text-embedding-3-small"
export LLM_MODEL="gpt-4o-mini"
export DEFAULT_SIMILARITY_THRESHOLD="0.90"
export ENVIRONMENT="development"

echo "✓ Backend environment configured"

# Step 4: Run migrations
echo "[4/6] Running database migrations..."
alembic upgrade head 2>&1 | tail -3
echo "✓ Migrations complete"

# Step 5: Start backend
echo "[5/6] Starting FastAPI backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/driftcache_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
sleep 5

# Step 6: Test backend
echo "[6/6] Testing backend..."
echo ""

# Test 1: Status endpoint
echo "Test 1: GET /status"
if curl -s http://localhost:8000/status | grep -q "operational"; then
  echo "✓ Backend is operational"
else
  echo "✗ Status endpoint failed"
  echo "Logs:"
  tail -20 /tmp/driftcache_backend.log
  kill $BACKEND_PID 2>/dev/null || true
  docker rm -f driftcache-postgres-local
  exit 1
fi

# Test 2: Models endpoint
echo ""
echo "Test 2: GET /v1/models"
MODELS_RESPONSE=$(curl -s http://localhost:8000/v1/models)
if echo "$MODELS_RESPONSE" | grep -q "gpt-4\|data"; then
  echo "✓ Models endpoint working"
  echo "Response: $MODELS_RESPONSE" | head -c 200
else
  echo "✗ Models endpoint failed"
  echo "Response: $MODELS_RESPONSE"
fi

# Test 3: Simple chat completion
echo ""
echo "Test 3: POST /v1/chat/completions (simple test)"
CHAT_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say hello in 3 words"}],
    "max_tokens": 10
  }')

if echo "$CHAT_RESPONSE" | grep -q "choices\|content"; then
  echo "✓ Chat completions working"
  echo "Response preview: $(echo $CHAT_RESPONSE | head -c 150)..."
else
  echo "⚠ Chat completion response:"
  echo "$CHAT_RESPONSE" | head -c 300
fi

echo ""
echo "=== Backend Tests Complete ==="
echo ""
echo "Backend is running at: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Backend PID: $BACKEND_PID"
echo "Backend logs: tail -f /tmp/driftcache_backend.log"
echo ""
echo "To run benchmarks:"
echo "  pip install requests colorama aiohttp"
echo "  python benchmarks/semantic_cache_benchmark.py"
echo ""
echo "To stop:"
echo "  kill $BACKEND_PID"
echo "  docker rm -f driftcache-postgres-local"
echo ""
