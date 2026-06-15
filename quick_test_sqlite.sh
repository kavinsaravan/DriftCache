#!/bin/bash
set -e

echo "=== DriftCache Quick Local Test (SQLite) ==="
echo ""

# Step 1: Check Redis
echo "[1/5] Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
  echo "✗ Redis not running. Start it with: redis-server"
  exit 1
fi
echo "✓ Redis ready"

# Step 2: Install backend dependencies
echo "[2/5] Installing backend dependencies..."
cd /Users/kavins/Projects/DriftCache/backend
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Step 3: Set environment for SQLite
echo "[3/5] Configuring for SQLite..."
export DATABASE_URL="sqlite:///./driftcache.db"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export OPENAI_API_KEY=$(grep OPENAI_API_KEY ../.env | cut -d '=' -f2)
export EMBEDDING_MODEL="text-embedding-3-small"
export LLM_MODEL="gpt-4o-mini"
export DEFAULT_SIMILARITY_THRESHOLD="0.90"
export ENVIRONMENT="development"

# Create SQLite database
rm -f driftcache.db
echo "✓ SQLite database ready"

# Step 4: Start backend in background (SQLite mode)
echo "[4/5] Starting FastAPI backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/driftcache_backend.log 2>&1 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"
sleep 5

# Step 5: Test backend
echo "[5/5] Testing backend..."
if curl -s http://localhost:8000/status | grep -q "operational"; then
  echo "✓ Backend is operational"
else
  echo "✗ Backend failed to start. Check logs:"
  tail -20 /tmp/driftcache_backend.log
  kill $BACKEND_PID 2>/dev/null || true
  exit 1
fi

echo ""
echo "=== System Ready! ==="
echo ""
echo "Backend running at: http://localhost:8000"
echo "Backend logs: tail -f /tmp/driftcache_backend.log"
echo "Backend PID: $BACKEND_PID"
echo "Database: SQLite (driftcache.db)"
echo ""
echo "To run benchmarks:"
echo "  cd /Users/kavins/Projects/DriftCache"
echo "  source backend/venv/bin/activate"
echo "  pip install requests colorama aiohttp"
echo "  python benchmarks/semantic_cache_benchmark.py"
echo ""
echo "To stop:"
echo "  kill $BACKEND_PID"
