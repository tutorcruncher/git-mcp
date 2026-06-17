"""Per-request proxy client factory for the backend github-mcp-server.

The official github-mcp-server runs in `http` mode and reads the GitHub token
from each request's `Authorization: Bearer` header (plus `X-MCP-Toolsets` /
`X-MCP-Readonly`). This module builds a fresh ProxyClient per request, injecting
the authenticated user's GitHub token so the backend acts as that user.
"""

from collections.abc import Callable

from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.providers.proxy import ProxyClient

from app.config import Settings


def build_backend_headers(token: str, toolsets: str, read_only: bool) -> dict[str, str]:
    """Build the headers forwarded to the backend github-mcp-server.

    Args:
        token: The user's GitHub access token.
        toolsets: Comma-separated toolset names (or "all").
        read_only: Whether to restrict the backend to read-only tools.

    Returns:
        The request headers, including the bearer credential and toolset controls.
    """
    headers = {
        'Authorization': f'Bearer {token}',
        'X-MCP-Toolsets': toolsets,
    }
    if read_only:
        headers['X-MCP-Readonly'] = 'true'
    return headers


def build_client_factory(settings: Settings) -> Callable[[], ProxyClient]:
    """Return a zero-arg factory that builds a per-request backend ProxyClient.

    FastMCPProxy calls the returned factory inside the active request context, so
    ``get_access_token()`` resolves to the connecting user's token there.

    Args:
        settings: Runtime settings holding the backend URL and toolset config.

    Returns:
        A callable suitable for ``FastMCPProxy(client_factory=...)``.
    """

    def make_backend_client() -> ProxyClient:
        """Build a backend client bound to the current request's GitHub token."""
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError('No authenticated GitHub token in request context')
        headers = build_backend_headers(
            token=access_token.token,
            toolsets=settings.github_toolsets,
            read_only=settings.read_only,
        )
        client = ProxyClient(StreamableHttpTransport(url=settings.backend_mcp_url, headers=headers))
        # ProxyClient forwards the inbound request's headers to the backend by
        # default. That leaks Claude's own Authorization (the FastMCP-issued JWT)
        # and session headers to github-mcp-server, which rejects them with 400.
        # Disable forwarding so only our injected GitHub token + toolset headers
        # reach the backend.
        client.transport.forward_incoming_headers = False
        return client

    return make_backend_client
