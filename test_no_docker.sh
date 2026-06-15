#!/bin/bash
set -e

echo "=== DriftCache Local Test (No Docker, SQLite) ==="
echo ""

cd /Users/kavins/Projects/DriftCache/backend

# Step 1: Check Redis
echo "[1/5] Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
  echo "✗ Redis not running. Please start it:"
  echo "  brew services start redis"
  echo "  OR: redis-server"
  exit 1
fi
echo "✓ Redis ready"

# Step 2: Setup Python environment
echo "[2/5] Setting up Python environment..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
# Install only essential packages for SQLite mode (skip complex dependencies)
pip install -q fastapi uvicorn sqlalchemy alembic redis python-dotenv anthropic openai langchain langchain-anthropic langgraph sentence-transformers faiss-cpu scikit-learn tenacity httpx pydantic pydantic-settings
echo "✓ Dependencies installed (SQLite mode - core packages only)"

# Step 3: Configure for SQLite
echo "[3/5] Configuring for SQLite..."
export DATABASE_URL="sqlite:///./driftcache.db"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export OPENAI_API_KEY=$(grep OPENAI_API_KEY ../.env | cut -d '=' -f2)
export EMBEDDING_MODEL="text-embedding-3-small"
export LLM_MODEL="gpt-4o-mini"
export DEFAULT_SIMILARITY_THRESHOLD="0.90"

# Remove old database
rm -f driftcache.db
echo "✓ Configuration ready"

# Step 4: Run migrations
echo "[4/5] Running migrations..."
alembic upgrade head 2>&1 | grep -E "(Migrating|Running|upgrade|✓)" | tail -5
echo "✓ Database migrated"

# Step 5: Start backend
echo "[5/5] Starting backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/driftcache_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

sleep 5

# Test backend
echo ""
echo "Testing backend..."
if curl -s http://localhost:8000/status | grep -q "operational"; then
  echo "✓ Backend is running!"
else
  echo "✗ Backend failed. Logs:"
  tail -20 /tmp/driftcache_backend.log
  kill $BACKEND_PID 2>/dev/null || true
  exit 1
fi

echo ""
echo "=== System Ready! ==="
echo ""
echo "Backend: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Logs: tail -f /tmp/driftcache_backend.log"
echo ""
echo "Test it:"
echo "  curl http://localhost:8000/v1/models"
echo ""
echo "Run benchmarks:"
echo "  cd /Users/kavins/Projects/DriftCache"
echo "  source backend/venv/bin/activate"
echo "  pip install requests colorama aiohttp"
echo "  python benchmarks/semantic_cache_benchmark.py"
echo ""
echo "Stop:"
echo "  kill $BACKEND_PID"
echo ""
