.PHONY: install init-db up down pipeline api frontend frontend-build dev test lint verify

PYTHON := .venv/bin/python
export PYTHONPATH := src

install:
	$(PYTHON) -m pip install -e ".[dev]"
	cd frontend && npm install

init-db:
	$(PYTHON) scripts/init_db.py --fresh

up:
	docker compose up -d postgres mlflow

down:
	docker compose down

pipeline:
	$(PYTHON) scripts/run_pipeline.py

frontend-build:
	cd frontend && npm run build

api: frontend-build
	$(PYTHON) -m uvicorn pmip.api.main:app --reload --host 0.0.0.0 --port 8000

dev:
	bash scripts/dev.sh

frontend:
	cd frontend && npm run dev

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check src/

verify:
	$(PYTHON) scripts/verify.py
