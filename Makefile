all: help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


fmt: ## Formats everything
	black .

test: ## Runs the offline tests
	python -m unittest discover -s tests -v

test-live: ## Runs the offline tests plus smoke tests against the real API
	TRAPI_LIVE_TESTS=1 python -m unittest discover -s tests -v
