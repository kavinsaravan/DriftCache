# DriftCache Demo Scenarios

This directory contains scripted demo scenarios that showcase DriftCache's capabilities through concrete examples.

## Quick Start

```bash
# 1. Ensure DriftCache is running
docker compose up -d

# 2. Seed the cache with baseline data
python demo/seed_cache.py

# 3. Run the demos
python demo/run_demo.py --all
```

## Demo Scenarios

### Scenario 1: Semantic Cache Savings

**What it shows:** Basic semantic caching with cost and latency reduction.

**Story:**
1. User asks: "Explain Redis simply" → **MISS** → Provider called → Response cached
2. User asks: "What is Redis in simple terms?" → **HIT** → Cached response returned
3. **Result:** Cost saved, latency reduced from ~1,800ms to ~9ms

**Run it:**
```bash
python demo/run_demo.py --scenario semantic
```

**Dashboard shows:**
- Cache hit count increases
- Cost saved increases  
- Latency drops dramatically
- Similarity score (e.g., 0.94)
- Matched prompt displayed

**Why it matters:** This is the simplest explanation of the project. Anyone can understand the value proposition.

---

### Scenario 2: Threshold Tradeoff

**What it shows:** How similarity threshold controls quality vs. savings.

**Story:**
1. At threshold 0.85 → More cache hits, higher risk of false positives
2. At threshold 0.95 → Fewer cache hits, safer but more provider calls
3. **Result:** Understanding the precision-recall tradeoff

**Run it:**
```bash
python demo/run_demo.py --scenario threshold
```

**Dashboard shows:**
- Hit rate changes with threshold
- Precision changes
- False hit rate changes
- Cost savings impact

**Why it matters:** Proves you understand ML systems tradeoffs, not just "make it cache more."

---

### Scenario 3: Drift Detection

**What it shows:** Semantic drift monitoring when query patterns shift.

**Story:**
1. Baseline: Software engineering queries (Docker, Kubernetes, APIs)
2. Drift induction: Healthcare/legal/finance queries (HIPAA, SEC, mortgages)
3. Drift detection runs → Embedding distribution shifts detected
4. **Result:** Drift score rises, alert created

**Run it:**
```bash
python demo/generate_drift.py drift
```

**Dashboard shows:**
- Drift score spike
- Centroid shift increase
- Similarity distribution changes
- Cache hit rate drops (off-domain queries)

**Why it matters:** Shows the system monitors semantic behavior over time, not just caching.

---

### Scenario 4: Autonomous Threshold Optimization

**What it shows:** Agent-based autonomous optimization.

**Story:**
1. Drift detected → Cache precision drops
2. Supervisor Agent runs → Analyzes system state
3. Threshold Optimization Agent evaluates candidates (0.88, 0.90, 0.92, 0.93)
4. Decision: Raise threshold from 0.90 to 0.93
5. Validation shows false hit rate improves
6. **Result:** System self-optimizes without human intervention

**Run it:**
```bash
python demo/generate_drift.py optimization
```

**Dashboard shows:**
- Agent action log
- Old threshold: 0.90
- New threshold: 0.93
- Reason: "High drift + precision degradation"
- Before/after precision metrics

**Why it matters:** This is the strongest demo. It shows autonomous infrastructure management using LangGraph agents.

---

### Scenario 5: Index Rebuild

**What it shows:** Self-healing vector infrastructure.

**Story:**
1. Many cache entries invalidated → Stale vector ratio increases to 32%
2. Index health monitoring detects degradation
3. Index Rebuild Agent decides: REBUILD_NOW
4. Safe workflow: Build new → Validate → Swap → Backup old
5. **Result:** New index version deployed, latency improves

**Run it:**
```bash
python demo/generate_drift.py rebuild
```

**Dashboard shows:**
- Old index version: v1
- New index version: v2
- Stale ratio: 32% → 0%
- Rebuild job status: completed
- Retrieval latency: 58ms → 8ms

**Why it matters:** Makes the system feel production-grade with self-healing capabilities.

---

## Demo Scripts

### seed_cache.py
Populates cache with baseline data for demos.

**What it does:**
- Seeds 10 software engineering queries
- Creates semantic duplicate cache entries
- Establishes baseline drift state

**Usage:**
```bash
python demo/seed_cache.py
```

### run_demo.py
Main demo orchestrator for basic scenarios (1-2).

**Features:**
- Colored terminal output
- Step-by-step progression
- Clear explanations of what's happening
- Shows cache HIT/MISS status
- Displays latency and similarity scores

**Usage:**
```bash
# Run all basic demos
python demo/run_demo.py --all

# Run specific scenario
python demo/run_demo.py --scenario semantic
python demo/run_demo.py --scenario threshold
```

### generate_drift.py
Advanced demo orchestrator for autonomous scenarios (3-5).

**Features:**
- Induces semantic drift
- Triggers autonomous agents
- Shows before/after metrics
- Demonstrates self-healing

**Usage:**
```bash
# Run all autonomous demos
python demo/generate_drift.py all

# Run specific scenario
python demo/generate_drift.py drift
python demo/generate_drift.py optimization
python demo/generate_drift.py rebuild
```

## Demo Prompts

### prompts/semantic_duplicates.json
5 topics × 4 variations = 20 prompts
- Redis, Docker, Microservices, REST API, Kubernetes
- Tests semantic matching accuracy

### prompts/drift_prompts.json
- Baseline: 10 software engineering prompts
- Drift: 10 healthcare/legal/finance prompts
- Recovery: 10 software prompts
- Tests drift detection sensitivity

### prompts/threshold_scenarios.json
- Clear matches: Should match at any threshold
- Moderate similarity: Matches at 0.85, maybe not 0.95
- Low similarity: Should NOT match (precision test)
- Tests threshold selection tradeoffs

## Complete Demo Flow

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Seed baseline data
python demo/seed_cache.py

# 3. Run basic demos
python demo/run_demo.py --all

# 4. Run autonomous demos
python demo/generate_drift.py all

# 5. Open dashboard to see metrics
open http://localhost
```

## Dashboard Views

When running demos, watch the dashboard for:

**Metrics Page:**
- Cache hit rate increasing
- Latency comparison (cache vs provider)
- Cost savings accumulating

**Drift Page:**
- Drift score changes
- Embedding distribution visualization
- Alert history

**Agents Page:**
- Supervisor run history
- Threshold optimization actions
- Index rebuild jobs
