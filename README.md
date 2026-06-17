# git-mcp

A remote **MCP server** that connects Claude to GitHub on behalf of each end user.

1. **Auth** — runs Claude's custom-connector OAuth flow against a **GitHub OAuth App**
   (FastMCP `GitHubProvider`). Each user logs into GitHub through Claude.
2. **Proxy** — proxies the official [`github/github-mcp-server`](https://github.com/github/github-mcp-server)
   (run in `http` mode), forwarding each request with the authenticated user's GitHub
   token. All of GitHub's official MCP tools are exposed to Claude, executed as that user.

```
Claude custom connector ──HTTPS /mcp──▶ FastMCPProxy (this app)
   auth = GitHubProvider (OAuth App) → per-user GitHub token (get_access_token().token)
   client_factory (per request) → Authorization: Bearer <user token>
                                          ▼
                       github-mcp-server (official, http mode, 127.0.0.1:8082)
                                          ▼
                                   GitHub API (as the user)
```

## Stack

Python 3.12+ · [`uv`](https://docs.astral.sh/uv/) · `ruff` · `ty` · `pytest` · `fastmcp` (pinned).

## Setup

```bash
make install-dev      # uv sync + pre-commit hooks
cp .env.example .env  # then fill in the values
```

### Create the GitHub OAuth App

GitHub → Settings → Developer settings → **OAuth Apps** → New OAuth App.

- **Homepage URL**: your `BASE_URL` (e.g. `https://your-app.herokuapp.com`)
- **Authorization callback URL**: `<BASE_URL>/auth/callback`

Copy the Client ID / secret into `.env` (`GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`).

## Develop

```bash
make lint        # ruff check + format check + ty
make test        # pytest -n auto
make format      # auto-fix + format + ty
```

## Run locally

The app spawns `github-mcp-server http` as a subprocess, so you need the binary on
`PATH` (or set `GITHUB_MCP_BINARY`). Easiest is a local build/binary from the
[releases](https://github.com/github/github-mcp-server/releases); alternatively run the
backend yourself in Docker via `make run-backend` and point `BACKEND_MCP_URL` at it
(then comment out the subprocess spawn for local testing).

```bash
make run-dev     # binds 0.0.0.0:$PORT (default 8000), serves /mcp
```

Test the OAuth + tool flow with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
# connect to http://localhost:8000/mcp → completes GitHub OAuth → lists tools
```

## Deploy to Heroku (container)

Both processes share `localhost`, so they run in one dyno via a multi-stage image.

```bash
heroku create your-app
heroku stack:set container -a your-app
heroku config:set -a your-app \
  GITHUB_OAUTH_CLIENT_ID=... \
  GITHUB_OAUTH_CLIENT_SECRET=... \
  BASE_URL=https://your-app.herokuapp.com \
  JWT_SIGNING_KEY="$(openssl rand -hex 32)" \
  GITHUB_TOOLSETS=repos,issues,pull_requests,users,context \
  GITHUB_SCOPES="repo read:org read:user"
git push heroku main
```

`BASE_URL` and the OAuth App callback (`<BASE_URL>/auth/callback`) must match the
deployed URL exactly.

## Add to Claude

Add `https://your-app.herokuapp.com/mcp` as a **custom connector** (Streamable HTTP).
Claude runs the OAuth flow; after you authorize the GitHub OAuth App, the GitHub tools
become available, acting as your GitHub user.

## Pinning

Keep both moving pieces pinned:
- `fastmcp` (proxy/auth API moves across versions; targets v3.4.2+).
- `ghcr.io/github/github-mcp-server` image (pin a digest in the `Dockerfile`).

## Configuration

See `.env.example`. Notable: `GITHUB_TOOLSETS` (or `all`), `READ_ONLY=1` to force
read-only tools, `GITHUB_SCOPES` for the OAuth scopes the proxied tools need.
