# git-mcp — project guide for Claude

## What this is

A **remote MCP server** that lets Claude talk to GitHub on behalf of each end user.

Two responsibilities:

1. **Auth** — it runs Claude's custom-connector OAuth flow against a **GitHub OAuth App**
   (via FastMCP's `GitHubProvider`). Each user logs into GitHub through Claude; the server
   ends up holding that user's GitHub access token.
2. **Proxy** — it proxies the **official `github/github-mcp-server`** (run in `http` mode),
   forwarding each request with the authenticated user's GitHub token. All of GitHub's
   official MCP tools are exposed to Claude, executed as that user.

Architecture:

```
Claude custom connector ──HTTPS /mcp──▶ FastMCPProxy (this app)
   auth = GitHubProvider (OAuth App) → per-user GitHub token via get_access_token().token
   client_factory (per request) → Authorization: Bearer <user token>
                                          ▼
                       github-mcp-server (official, http mode, 127.0.0.1:8082)
                                          ▼
                                   GitHub API (as the user)
```

Key files: `app/config.py` (env), `app/auth.py` (`GitHubProvider`), `app/backend.py`
(per-request `make_backend_client()`), `app/server.py` (`FastMCPProxy` + spawns the
backend subprocess).

## Stack & workflow

- Python 3.12+, managed with **`uv`**. Lint/format with **`ruff`**, type-check with **`ty`**,
  test with **`pytest`** (always `-n auto`).
- `make install-dev` — install deps + pre-commit hooks.
- `make lint` — ruff check + format check + ty. **Always run `make lint` after changing code.**
- `make test` / `make test-cov` — run tests.
- `make run-backend` — run the official github-mcp-server locally (Docker, http mode).
- `make run-dev` — run this MCP server.

## Conventions

Code style and testing rules live in `.claude/rules/`:
- `code-style/` — module-level imports, docstrings over comments, type hints, no ternaries
  for non-trivial branches, never `from __future__ import annotations`.
- `testing/` — assert whole structures, `@patch` decorator, no inline comments in tests,
  drive real code paths E2E and mock only external boundaries (GitHub, the backend process).

## Pinning

Both moving pieces are version-sensitive — keep them pinned:
- `fastmcp` (proxy/auth APIs changed across v2→v3; this repo targets v3.4.2+,
  `fastmcp.server.providers.proxy`).
- `ghcr.io/github/github-mcp-server` Docker image (pin a tag/digest).
