.PHONY: help install lock frontend backend db-init db-start db-stop db-status migrate migration lint test test-db check

PYTHON := backend/.venv/bin/python
ALEMBIC := backend/.venv/bin/alembic
RUFF := backend/.venv/bin/ruff

help:
	@printf '%s\n' \
	  'install     Install locked frontend and backend dependencies' \
	  'lock        Refresh Python dependency locks (review the diff)' \
	  'db-init     Initialize an isolated local PostgreSQL cluster' \
	  'db-start    Start local PostgreSQL and create the iou database' \
	  'db-stop     Stop local PostgreSQL' \
	  'db-status   Show local PostgreSQL status' \
	  'migrate     Apply committed migrations' \
	  'migration   Generate a migration: make migration message="add loans"' \
	  'frontend    Run Vite on http://localhost:5173' \
	  'backend     Run FastAPI on http://127.0.0.1:8000' \
	  'lint        Run frontend and backend linters' \
	  'test        Run backend unit/API tests (no database needed)' \
	  'test-db     Run database smoke tests (requires PostgreSQL)' \
	  'check       Lint, unit/API tests, and frontend production build'

install:
	uv venv --python python3.12 --allow-existing backend/.venv
	uv pip sync --python $(PYTHON) backend/requirements-dev.txt
	npm --prefix frontend ci

lock:
	cd backend && uv pip compile --python-version 3.12 requirements.in -o requirements.txt
	cd backend && uv pip compile --python-version 3.12 --constraint requirements.txt requirements-dev.in -o requirements-dev.txt

frontend:
	npm --prefix frontend run dev

backend:
	PYTHONPATH=backend/src $(PYTHON) -m uvicorn iou.api:app --reload --host 127.0.0.1 --port 8000

db-init:
	./scripts/db.sh init

db-start:
	./scripts/db.sh start

db-stop:
	./scripts/db.sh stop

db-status:
	./scripts/db.sh status

migrate:
	$(ALEMBIC) -c backend/alembic.ini upgrade head

migration:
	@test -n "$(message)" || (echo 'Usage: make migration message="add loans"' >&2; exit 1)
	$(ALEMBIC) -c backend/alembic.ini revision --autogenerate -m "$(message)"

lint:
	npm --prefix frontend run lint
	$(RUFF) check backend
	$(RUFF) format --check backend

test:
	$(PYTHON) -m pytest -c backend/pyproject.toml -m 'not database'

test-db:
	$(PYTHON) -m pytest -c backend/pyproject.toml -m database

check: lint test
	npm --prefix frontend run build
