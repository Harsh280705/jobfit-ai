.PHONY: up down backend frontend worker test seed eval migrate

up:
	docker compose up --build

down:
	docker compose down -v

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

worker:
	cd backend && celery -A app.workers.celery_app.celery worker --loglevel=info

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python ../scripts/seed_data.py

eval:
	cd backend && python ../scripts/run_evaluation.py

test:
	cd backend && pytest -q
