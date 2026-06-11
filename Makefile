# Coffee Pie — Development Makefile
# Quick commands for common tasks.

.PHONY: up down logs build clean test lint help

# ── Docker Compose ──────────────────────────────

up: .env
	docker compose up -d
	@echo "Services starting... wait 10s then: make status"

down:
	docker compose down

logs:
	docker compose logs -f --tail=50

build:
	docker compose build --no-cache

clean:
	docker compose down -v
	rm -rf .env

status:
	@docker compose ps
	@echo ""
	@echo "Endpoints:"
	@echo "  Orchestrator: http://localhost:8000"
	@echo "  DC Agent:     http://localhost:9090"
	@echo "  Proxmox mock: http://localhost:8001"
	@echo "  Sunshine mock: localhost:47989"

restart:
	docker compose restart orchestrator dc-agent actor

# ── Database ────────────────────────────────────

db-shell:
	docker compose exec postgres psql -U coffeepie -d coffeepie

db-reset:
	docker compose down -v postgres
	docker compose up -d postgres
	@sleep 5
	docker compose up -d orchestrator

# ── Rust tools ──────────────────────────────────

tools-build:
	cd tools/benchmark   && cargo build --release
	cd tools/security    && cargo build --release
	cd tools/dev         && cargo build --release
	cd tools/admin       && cargo build --release
	cd tools/monitoring  && cargo build --release

tools-test:
	cd tools/benchmark   && cargo test
	cd tools/security    && cargo test
	cd tools/dev         && cargo test
	cd tools/admin       && cargo test
	cd tools/monitoring  && cargo test

tools-lint:
	cd tools/benchmark   && cargo clippy -- -D warnings
	cd tools/security    && cargo clippy -- -D warnings
	cd tools/dev         && cargo clippy -- -D warnings
	cd tools/admin       && cargo clippy -- -D warnings
	cd tools/monitoring  && cargo clippy -- -D warnings

# ── Python services ─────────────────────────────

orch-test:
	docker compose exec orchestrator python manage.py test

orch-lint:
	cd coffeepie_orchestrator/server && ruff check .

# ── Frontend ────────────────────────────────────

frontend-build:
	cd coffeepie_frontend && cmake -B build -S . && cmake --build build

# ── Integration tests ──────────────────────────

test-integration:
	@echo "Starting services for integration tests..."
	docker compose up -d postgres redis proxmox-mock sunshine-mock
	@sleep 8
	cd tests/integration && pip install -q -r requirements.txt && pytest -v --timeout=120 --tb=short
	@docker compose down -v

# ── All ─────────────────────────────────────────

test: tools-test orch-test
	@echo "Unit tests passed. Run 'make test-integration' for full stack."

lint: tools-lint orch-lint
	@echo "All lints passed."

# ── Setup ───────────────────────────────────────

.env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example — edit if needed."; \
	fi

setup: .env
	@echo "Building Docker images..."
	docker compose build
	@echo "Starting services..."
	docker compose up -d
	@sleep 10
	@echo "Running migrations..."
	docker compose exec -T orchestrator python manage.py migrate --noinput
	@echo ""
	@echo "✓ Coffee Pie development environment ready!"
	@echo "  make logs    — follow all logs"
	@echo "  make status  — show endpoints"
	@echo "  make test    — run all tests"

help:
	@echo "Coffee Pie Development Commands"
	@echo "==============================="
	@echo "  make setup       — first-time setup (build + start)"
	@echo "  make up          — start all services"
	@echo "  make down        — stop all services"
	@echo "  make logs        — follow logs"
	@echo "  make status      — show service status and endpoints"
	@echo "  make restart     — restart app services"
	@echo "  make build       — rebuild all images"
	@echo "  make clean       — stop and remove volumes"
	@echo ""
	@echo "  make test        — run all tests"
	@echo "  make lint        — run all linters"
	@echo "  make tools-build — build all Rust tools"
	@echo ""
	@echo "  make db-shell    — PostgreSQL shell"
	@echo "  make db-reset    — reset database"
