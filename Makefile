.PHONY: help up down logs backend-shell frontend-shell db-migrate db-upgrade test clean

help:
	@echo "GallagherMHP Command Platform - Available commands:"
	@echo ""
	@echo "  make up              - Start all services with Docker Compose"
	@echo "  make down            - Stop all services"
	@echo "  make logs            - View logs from all services"
	@echo "  make backend-shell   - Open shell in backend container"
	@echo "  make frontend-shell  - Open shell in frontend container"
	@echo "  make db-migrate      - Generate new migration"
	@echo "  make db-upgrade      - Run database migrations"
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

db-migrate:
	docker-compose exec backend alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	docker-compose exec backend alembic upgrade head

test:
	docker-compose exec backend pytest --cov=app

clean:
	docker-compose down -v
	@echo "All containers and volumes removed"

