all: help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

fmt: ## Format and auto-fix lint issues
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Lint without modifying files
	uv run ruff check .

typecheck: ## Strict type-check src/ with pyright
	uv run pyright

test: ## Run the test suite (parallel)
	uv run pytest
