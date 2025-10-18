.PHONY: help up down logs backend-shell frontend-shell db-revision db-upgrade db-downgrade test clean

rev ?= -1

help:
	@echo "GallagherMHP Command Platform - Available commands:"
	@echo ""
	@echo "  make up              - Start all services with Docker Compose"
	@echo "  make down            - Stop all services"
	@echo "  make logs            - View logs from all services"
	@echo "  make backend-shell   - Open shell in backend container"
	@echo "  make frontend-shell  - Open shell in frontend container"
	@echo "  make db-revision     - Autogenerate Alembic revision (m=\"message\")"
	@echo "  make db-upgrade      - Apply latest migrations"
	@echo "  make db-downgrade    - Roll back migrations (rev=...)"
	@echo "  make test            - Run backend tests"
	@echo "  make clean           - Clean up volumes and containers"

up:
	docker-compose up -d
	@echo "Services started. Access:"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/api/docs"

down:
	docker-compose down

logs:
	docker-compose logs -f

backend-shell:
	docker-compose exec backend /bin/sh

frontend-shell:
	docker-compose exec frontend /bin/sh

db-revision:
	@if [ -z "$(m)" ]; then echo 'Usage: make db-revision m="summary"'; exit 1; fi
	cd backend && alembic revision --autogenerate -m "$(m)"

db-upgrade:
	cd backend && alembic upgrade head

db-downgrade:
	cd backend && alembic downgrade $(rev)

test:
	docker-compose exec backend pytest --cov=app

clean:
	docker-compose down -v
	@echo "All containers and volumes removed"
