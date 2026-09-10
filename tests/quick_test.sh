#!/bin/bash
echo "=== Quick Test of DriftCache API ==="
echo ""

echo "1. Testing health endpoint..."
curl -s https://driftcache-api.onrender.com/health | python3 -m json.tool
echo ""

echo "2. Testing API status..."
curl -s https://driftcache-api.onrender.com/api/v1/status | python3 -m json.tool
echo ""

echo "3. Testing metrics (should return empty data)..."
curl -s "https://driftcache-api.onrender.com/api/v1/metrics/summary?period=24h" | python3 -m json.tool
echo ""

echo "4. Testing chat completion (may take 10-30 seconds)..."
timeout 45 curl -X POST https://driftcache-api.onrender.com/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say hello in 3 words"}],
    "max_tokens": 20
  }' | python3 -m json.tool 2>/dev/null || echo "TIMEOUT or ERROR"
echo ""
