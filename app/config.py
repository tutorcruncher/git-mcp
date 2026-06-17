"""Environment-backed configuration for the GitHub MCP proxy server."""

import os
from dataclasses import dataclass


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

    @property
    def backend_port(self) -> int:
        """Port the backend github-mcp-server listens on (parsed from its URL)."""
        from urllib.parse import urlparse

        parsed = urlparse(self.backend_mcp_url)
        return parsed.port or 8082


def load_settings() -> Settings:
    """Build a Settings instance from the current environment."""
    return Settings(
        github_client_id=_require('GITHUB_OAUTH_CLIENT_ID'),
        github_client_secret=_require('GITHUB_OAUTH_CLIENT_SECRET'),
        base_url=_require('BASE_URL').rstrip('/'),
        github_scopes=os.environ.get('GITHUB_SCOPES', 'repo read:org read:user').split(),
        backend_mcp_url=os.environ.get('BACKEND_MCP_URL', 'http://127.0.0.1:8082/mcp'),
        github_toolsets=os.environ.get('GITHUB_TOOLSETS', 'all'),
        read_only=os.environ.get('READ_ONLY', '0') == '1',
        jwt_signing_key=_require('JWT_SIGNING_KEY'),
        port=int(os.environ.get('PORT', '8000')),
        github_mcp_binary=os.environ.get('GITHUB_MCP_BINARY', 'github-mcp-server'),
    )
