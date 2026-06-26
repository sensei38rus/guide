.PHONY: install test demo run-cli run-api docker-build docker-up lint clean

PYTHON      := python3
PIP         := $(PYTHON) -m pip
PYTEST      := $(PYTHON) -m pytest
DEMO_REPO   := /tmp/guide-demo-repo

# ─────────────────────────────────────────────────────────────────────────────
# Install
# ─────────────────────────────────────────────────────────────────────────────

install:  ## Install Guide and dev dependencies, then install hooks in this repo
	$(PIP) install --break-system-packages -e ".[dev]" 
	@echo ""
	@bash scripts/install_hooks.sh .
	

# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

test:  ## Run the full test suite
	$(PYTEST)

test-cov:  ## Run tests with coverage report
	$(PYTEST) --cov=guide --cov-report=term-missing

# ─────────────────────────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────────────────────────

demo:  ## Create a temporary git repo and run typical hook scenarios
	@bash scripts/run_demo.sh

# ─────────────────────────────────────────────────────────────────────────────
# Manual CLI runner
# ─────────────────────────────────────────────────────────────────────────────

run-cli:  ## Interactive CLI: validate a commit message from the command line
	@echo "Guide CLI — commit message checker"
	@echo "Enter a commit message (or press Ctrl-C to quit):"
	@read -r MSG && $(PYTHON) -m guide.cli check-msg "$$MSG"

# ─────────────────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────────────────

docker-build:  ## Build the demo Docker image
	docker build -t guide-demo:latest .

docker-up:  ## Start the demo environment in Docker
	docker compose up

# ─────────────────────────────────────────────────────────────────────────────
# Housekeeping
# ─────────────────────────────────────────────────────────────────────────────

lint:  ## Run basic linting (ruff if available, else pyflakes)
	@$(PYTHON) -m ruff check src/ tests/ 2>/dev/null || \
	 $(PYTHON) -m pyflakes src/ tests/ 2>/dev/null || \
	 echo "No linter found — skipping (install ruff for linting)"

clean:  ## Remove build artefacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
