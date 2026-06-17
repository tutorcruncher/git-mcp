# --- Stage 1: grab the official github-mcp-server binary ---------------------
# Pin to a digest in production, e.g.
#   ghcr.io/github/github-mcp-server@sha256:<digest>
FROM ghcr.io/github/github-mcp-server:latest AS ghmcp

# --- Stage 2: the Python MCP proxy app ---------------------------------------
FROM python:3.12-slim-bookworm

# uv for dependency management (copied from the official uv image).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first (layer-cached on lockfile changes only).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code.
COPY app ./app

# The official github-mcp-server binary, invoked by app.server as a subprocess.
COPY --from=ghmcp /server/github-mcp-server /usr/local/bin/github-mcp-server
ENV GITHUB_MCP_BINARY=/usr/local/bin/github-mcp-server

# Heroku provides $PORT at runtime; app.server binds 0.0.0.0:$PORT.
CMD ["python", "-m", "app.server"]
