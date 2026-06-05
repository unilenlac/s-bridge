# Auto-detect container orchestration engine
COMPOSE := $(shell command -v podman-compose 2> /dev/null || echo "docker compose")

.DEFAULT_GOAL := help

.PHONY: build
build: ## Build the Docker image via compose
	$(COMPOSE) build

.PHONY: up
up: ## Start the application stack in Compose (background)
	$(COMPOSE) up -d

.PHONY: down
down: ## Stop the application stack and remove containers
	$(COMPOSE) down

.PHONY: logs
logs: ## Follow container logs
	$(COMPOSE) logs -f

.PHONY: shell
shell: ## Access the bash shell in the running container for debugging
	$(COMPOSE) exec web bash

.PHONY: clean
clean: ## Clean up temporary files, cache directories, and virtual environment
	rm -rf .pytest_cache .ruff_cache .venv build/ dist/ *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +


.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies and set up virtual environment using uv
	uv sync

.PHONY: dev
dev: ## Run the FastAPI application locally with hot-reload (listens on 127.0.0.1)
	uv run uvicorn main:app --reload --host 127.0.0.1 --port 8500

.PHONY: lint
lint: ## Run Ruff check for code quality and style issues
	uv run ruff check .

.PHONY: format
format: ## Format the code base using Ruff
	uv run ruff format .

.PHONY: test
test: ## Run the pytest suite locally
	uv run pytest

.PHONY: db-migrate
db-migrate: ## Apply database migrations to head using Alembic
	uv run alembic upgrade head

.PHONY: db-revision
db-revision: ## Create a new database migration. Usage: make db-revision msg="migration description"
ifndef msg
	$(error msg is required. Usage: make db-revision msg="description")
endif
	uv run alembic revision --autogenerate -m "$(msg)"
