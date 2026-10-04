PYTHON ?= python3
API_BASE_URL ?= http://localhost:8000
DEMO_SCENARIO ?= semantic
DEMO_ARGS ?=

.PHONY: help install up down api frontend test test-integration demo smoke benchmark load-test check

help:
	@echo "DriftCache commands"
	@echo "  make install           Install backend and frontend dependencies"
	@echo "  make up                Start the full Docker stack"
	@echo "  make down              Stop the Docker stack"
	@echo "  make api               Run the backend locally"
	@echo "  make frontend          Run the frontend locally"
	@echo "  make test              Run backend tests except live integration tests"
	@echo "  make test-integration  Run tests that require a running API"
	@echo "  make smoke             Check API health"
	@echo "  make demo              Run DEMO_SCENARIO (health, semantic, seed, drift, all)"
	@echo "  make benchmark         Run the semantic-cache benchmark"
	@echo "  make load-test         Run the concurrent load test"
	@echo "  make check             Compile Python and validate the Makefile"

install:
	cd backend && $(PYTHON) -m pip install -r requirements.txt
	cd frontend && npm install

up:
	docker compose up --build

down:
	docker compose down

api:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && mkdir -p pytest-results && $(PYTHON) -m pytest tests -m "not integration and not slow" --junitxml=pytest-results/junit.xml

test-integration:
	cd backend && $(PYTHON) -m pytest tests -m integration

demo:
	$(PYTHON) scripts/demo.py --base-url $(API_BASE_URL) $(DEMO_SCENARIO) $(DEMO_ARGS)

smoke:
	$(PYTHON) scripts/demo.py --base-url $(API_BASE_URL) health

benchmark:
	$(PYTHON) benchmarks/semantic_cache_benchmark.py --api-url $(API_BASE_URL)

load-test:
	$(PYTHON) benchmarks/load_test.py --api-url $(API_BASE_URL)

check:
	PYTHONPYCACHEPREFIX=/tmp/driftcache-pyc $(PYTHON) -m compileall -q backend/app scripts/demo.py benchmarks
	$(MAKE) --no-print-directory help >/dev/null
