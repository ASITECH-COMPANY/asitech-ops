# ASITECH OPS — developer shortcuts. Run `make help`.
.DEFAULT_GOAL := help
COMPOSE := docker compose
BACKEND := $(COMPOSE) run --rm backend

.PHONY: help up down logs migrate superuser backend-test backend-lint frontend-test frontend-lint landing-build landing-check test lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the development stack
	$(COMPOSE) up --build

down: ## Stop the development stack
	$(COMPOSE) down

logs: ## Follow logs
	$(COMPOSE) logs -f --tail=100

migrate: ## Apply database migrations
	$(BACKEND) python manage.py migrate

superuser: ## Create the first platform administrator
	$(BACKEND) python manage.py createsuperuser

backend-test: ## Run backend tests (inside Docker, against PostgreSQL)
	$(BACKEND) pytest

backend-lint: ## Lint backend code
	$(BACKEND) ruff check .

frontend-test: ## Run dashboard unit tests
	cd frontend && npm test

frontend-lint: ## Lint and type-check the dashboard
	cd frontend && npm run lint && npm run typecheck

landing-build: ## Build the landing page
	cd landing && npm run build

landing-check: ## Build and verify the landing page
	cd landing && npm run build && npm run check

test: backend-test frontend-test ## Run all tests
lint: backend-lint frontend-lint ## Run all linters
