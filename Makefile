.PHONY: install install-dev test test-cov lint type-check format clean run-dev run-backend

# Install runtime dependencies
install:
	uv sync --no-dev

# Install all dependencies + pre-commit hooks
install-dev:
	uv sync
	uv run pre-commit install

# Run tests
test:
	uv run pytest -n auto

# Run tests with coverage
test-cov:
	uv run pytest -n auto --cov=app --cov-report=term-missing

# Lint code
lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check .

# Type check code
type-check:
	uv run ty check .

# Auto-fix and format
format:
	uv run ruff check --fix .
	uv run ruff format .
	uv run ty check .

# Run the MCP server (binds 0.0.0.0:$PORT, default 8000)
run-dev:
	uv run python -m app.server

# Run the official github-mcp-server backend locally for testing (http mode, 127.0.0.1:8082)
run-backend:
	docker run --rm -p 127.0.0.1:8082:8082 ghcr.io/github/github-mcp-server http --listen-host 0.0.0.0 --port 8082

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
