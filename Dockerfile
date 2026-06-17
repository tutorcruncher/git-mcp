# --- Stage 1: grab the official github-mcp-server binary ---------------------
# Pinned by digest (v1.3.0). The binary runs in-process with users' GitHub
# tokens, so this is the highest-trust dependency — never use a floating tag.
FROM ghcr.io/github/github-mcp-server:v1.3.0@sha256:5c83359327a0bacc3d34db730bea6557d39d341cee0bf6c58c9a896e33150e80 AS ghmcp

# --- Stage 2: the Python MCP proxy app ---------------------------------------
FROM python:3.12-slim-bookworm

# uv for dependency management (copied from the official uv image, pinned by digest).
COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /uvx /usr/local/bin/

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
