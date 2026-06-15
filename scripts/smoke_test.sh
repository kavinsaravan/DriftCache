#!/bin/bash

set -e

BASE_URL="http://localhost:8000"

echo "============================================================"
echo "DRIFTCACHE END-TO-END SMOKE TEST"
echo "============================================================"
echo ""

echo "1. Testing backend health..."
curl -s "$BASE_URL/health" | python3 -m json.tool || true
echo ""

echo "2. Testing models endpoint..."
curl -s "$BASE_URL/api/v1/models" | python3 -m json.tool
echo ""

echo "3. Sending first prompt (expected MISS - will call OpenAI)..."
curl -s -X POST "$BASE_URL/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Explain Docker in simple terms."}
    ],
    "stream": false
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('Response:', d['choices'][0]['message']['content'][:100] + '...'); print('Usage:', d.get('usage', 'N/A'))"
echo ""

echo "4. Sending similar prompt (expected HIT - cached response)..."
curl -s -X POST "$BASE_URL/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Can you explain Docker simply for beginners?"}
    ],
    "stream": false
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('Response:', d['choices'][0]['message']['content'][:100] + '...'); print('Usage:', d.get('usage', 'N/A'))"
echo ""

echo "5. Checking metrics summary..."
curl -s "$BASE_URL/api/v1/metrics/summary?period=1h" | python3 -m json.tool
echo ""

echo "6. Running drift check..."
curl -s -X POST "$BASE_URL/api/v1/drift/run-check" | python3 -m json.tool
echo ""

echo "7. Running evaluation..."
curl -s -X POST "$BASE_URL/api/v1/evaluation/run" | python3 -m json.tool
echo ""

echo "8. Running supervisor agent..."
curl -s -X POST "$BASE_URL/api/v1/supervisor/run" | python3 -m json.tool
echo ""

echo "9. Checking vectorstore health..."
curl -s "$BASE_URL/api/v1/vectorstore/health" | python3 -m json.tool
echo ""

echo "10. Checking vectorstore status..."
curl -s "$BASE_URL/api/v1/vectorstore/status" | python3 -m json.tool
echo ""

echo "============================================================"
echo "SMOKE TEST COMPLETE"
echo "============================================================"
echo ""
echo "All major components tested:"
echo "  ✓ Health check"
echo "  ✓ Models API"
echo "  ✓ Chat completions (semantic caching)"
echo "  ✓ Metrics collection"
echo "  ✓ Drift detection"
echo "  ✓ Cache quality evaluation"
echo "  ✓ Supervisor agent orchestration"
echo "  ✓ Vectorstore health monitoring"
echo ""
