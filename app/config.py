"""Environment-backed configuration for the GitHub MCP proxy server."""

import os
from dataclasses import dataclass, field


def _require(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from the environment.

    Attributes:
        github_client_id: GitHub OAuth App client id.
        github_client_secret: GitHub OAuth App client secret.
        base_url: Public HTTPS base URL of this server (OAuth callback root).
        github_scopes: GitHub OAuth scopes the proxied tools require.
        backend_mcp_url: URL of the backend github-mcp-server (http mode).
        github_toolsets: Toolsets to expose, forwarded as X-MCP-Toolsets.
        read_only: Whether to force read-only tools (X-MCP-Readonly).
        jwt_signing_key: Signing key for FastMCP-issued JWTs.
        port: Port the MCP server binds to.
        github_mcp_binary: Path/name of the github-mcp-server executable.
        allowed_github_org: If set, only active members of this GitHub org may
            use the tools.
        allow_ungated: Explicit opt-in to run WITHOUT an org gate. When false
            (default) and no org is set, the server refuses to start so a missing
            ALLOWED_GITHUB_ORG fails closed rather than exposing tools to all.
        allowed_redirect_uris: OAuth client redirect URIs permitted during
            dynamic client registration / authorization.
        redis_url: Redis connection URL for persisting OAuth state across restarts.
            When set, OAuth client registrations and tokens survive process restarts
            (essential on hosts with an ephemeral filesystem, e.g. Heroku dyno
            cycling). When unset, FastMCP falls back to its default on-disk store.
        mcp_api_keys: Static API keys for key-based auth. When non-empty, the server
            authenticates clients by a Bearer key instead of GitHub OAuth, and the
            GitHub OAuth credentials / org gating are not used (a valid key is the
            gate). When empty, the server falls back to GitHub OAuth + org gating.
        github_backend_token: Static GitHub token (PAT) the proxy forwards to the
            backend github-mcp-server in key-auth mode (there is no per-user OAuth
            token then). Required when mcp_api_keys is set; ignored in OAuth mode.
    """

    github_client_id: str
    github_client_secret: str
    base_url: str
    github_scopes: list[str]
    backend_mcp_url: str
    github_toolsets: str
    read_only: bool
    jwt_signing_key: str
    port: int
    github_mcp_binary: str
    allowed_github_org: str | None
    allow_ungated: bool
    allowed_redirect_uris: list[str]
    redis_url: str | None
    mcp_api_keys: list[str] = field(default_factory=list)
    github_backend_token: str | None = None

    @property
    def key_auth_enabled(self) -> bool:
        """True when static API-key auth is configured (takes precedence over OAuth)."""
        return bool(self.mcp_api_keys)

    @property
    def backend_port(self) -> int:
        """Port the backend github-mcp-server listens on (parsed from its URL)."""
        from urllib.parse import urlparse

        parsed = urlparse(self.backend_mcp_url)
        return parsed.port or 8082


def _load_api_keys() -> list[str]:
    """Parse MCP_API_KEYS (comma- or whitespace-separated) into a list of keys."""
    return [key for key in os.environ.get('MCP_API_KEYS', '').replace(',', ' ').split() if key]


def load_settings() -> Settings:
    """Build a Settings instance from the current environment.

    In key-auth mode (``MCP_API_KEYS`` set) the GitHub OAuth credentials are not
    required, so the server can run with just API keys + a backend GitHub token. In
    OAuth mode they remain required and a missing one fails fast.
    """
    api_keys = _load_api_keys()
    key_auth = bool(api_keys)

    def _oauth_required(name: str) -> str:
        """Required in OAuth mode; optional (default empty) in key-auth mode."""
        return (os.environ.get(name) or '') if key_auth else _require(name)

    return Settings(
        github_client_id=_oauth_required('GITHUB_OAUTH_CLIENT_ID'),
        github_client_secret=_oauth_required('GITHUB_OAUTH_CLIENT_SECRET'),
        base_url=_oauth_required('BASE_URL').rstrip('/'),
        github_scopes=os.environ.get('GITHUB_SCOPES', 'repo read:org read:user').split(),
        backend_mcp_url=os.environ.get('BACKEND_MCP_URL', 'http://127.0.0.1:8082/mcp'),
        github_toolsets=os.environ.get('GITHUB_TOOLSETS', 'all'),
        read_only=os.environ.get('READ_ONLY', '0') == '1',
        jwt_signing_key=_oauth_required('JWT_SIGNING_KEY'),
        port=int(os.environ.get('PORT', '8000')),
        github_mcp_binary=os.environ.get('GITHUB_MCP_BINARY', 'github-mcp-server'),
        allowed_github_org=os.environ.get('ALLOWED_GITHUB_ORG') or None,
        allow_ungated=os.environ.get('ALLOW_UNGATED', '0') == '1',
        allowed_redirect_uris=os.environ.get(
            'ALLOWED_REDIRECT_URIS', 'https://claude.ai/api/mcp/auth_callback'
        ).split(),
        redis_url=os.environ.get('REDIS_URL') or None,
        mcp_api_keys=api_keys,
        github_backend_token=os.environ.get('GITHUB_BACKEND_TOKEN') or None,
    )
