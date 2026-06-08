# Aaditech UFO — Local Development Makefile
# Usage: make <target>
# Requires: Docker, Docker Compose, Python 3.12, Node 20

.PHONY: help setup up down logs test test-backend test-frontend build seed shell clean

help:
	@echo ""
	@echo "Aaditech UFO — Local Dev Commands"
	@echo "==================================="
	@echo "  make setup          Copy .env.local and pull Docker images"
	@echo "  make up             Start all services (Postgres + Redis + Flask)"
	@echo "  make up-full        Start with Nginx gateway on :8080"
	@echo "  make down           Stop all services"
	@echo "  make logs           Tail all service logs"
	@echo "  make build          Rebuild Docker images after code changes"
	@echo "  make seed           Seed default admin user"
	@echo "  make test           Run all tests (backend + frontend)"
	@echo "  make test-backend   Run pytest only"
	@echo "  make test-frontend  Run TypeScript check + Vite build"
	@echo "  make shell          Open bash in the running app container"
	@echo "  make clean          Remove containers, volumes, built assets"
	@echo ""

# ─── Environment ────────────────────────────────────────────────────────────────

setup:
	@if [ ! -f .env ]; then \
		cp .env.local .env; \
		echo "✓ .env created from .env.local — edit secrets before use"; \
	else \
		echo "✓ .env already exists, skipping"; \
	fi
	docker compose pull --quiet

# ─── Docker services ────────────────────────────────────────────────────────────

up: setup
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
	@echo ""
	@echo "Services started:"
	@echo "  Flask API   → http://localhost:5000"
	@echo "  Postgres    → localhost:5432"
	@echo "  Redis       → localhost:6379"
	@echo ""
	@echo "Run 'make logs' to follow logs, 'make seed' to create admin user"

up-full: setup
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
	@echo "Gateway (nginx) → http://localhost:8080"

down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

logs:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

build:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache

shell:
	docker compose exec app bash

# ─── Seeding ────────────────────────────────────────────────────────────────────

seed:
	docker compose exec app python -m scripts.seed_default_admin
	@echo ""
	@echo "Default admin credentials:"
	@echo "  Tenant Slug : default"
	@echo "  Email       : admin@example.com"
	@echo "  Password    : ChangeMe123!"
	@echo "  URL         : http://localhost:5000/app"

# ─── Testing (no Docker required — uses SQLite) ─────────────────────────────────

test: test-backend test-frontend
	@echo "All tests passed!"

test-backend:
	@echo "Running backend tests..."
	DATABASE_URL=sqlite:///test_local.db \
	SECRET_KEY=local-test-secret \
	JWT_SECRET_KEY=local-test-jwt \
	FLASK_ENV=testing \
	RATELIMIT_ENABLED=False \
	pytest --tb=short -q
	@rm -f test_local.db

test-frontend:
	@echo "Running frontend type check..."
	cd frontend && npx tsc --noEmit
	@echo "Running Vite build..."
	cd frontend && npx vite build
	@echo "Frontend OK"

# ─── Cleanup ────────────────────────────────────────────────────────────────────

clean:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans
	rm -rf frontend/dist frontend/node_modules __pycache__ .coverage test_local.db
	find . -name "*.pyc" -delete
	@echo "Cleaned up"
