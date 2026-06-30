"""Entry point: build the auth-enabled FastMCP proxy and run it.

A single FastMCPProxy both enforces GitHub OAuth (via GitHubProvider) and proxies
the official github-mcp-server. The backend runs in `http` mode as a child process
on localhost; each request's client is built with the connecting user's GitHub token.
"""

import contextlib
import ctypes
import logging
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator

from fastmcp.server.providers.proxy import FastMCPProxy

from app.access import OrgMembershipMiddleware
from app.auth import build_auth
from app.backend import build_client_factory
from app.config import Settings, load_settings
from app.observability import ObservabilityMiddleware, configure_observability


def build_server(settings: Settings) -> FastMCPProxy:
    """Build the auth-enabled proxy server.

    When ``allowed_github_org`` is set, tool access is gated to active members
    of that GitHub organization.

    Args:
        settings: Runtime settings.

    Returns:
        FastMCPProxy: Server that authenticates users and proxies github-mcp-server.
    """
    if not settings.oauth_enabled and not settings.mcp_api_keys:
        raise RuntimeError(
            'No auth configured: set the GitHub OAuth credentials (GITHUB_OAUTH_CLIENT_ID, '
            'GITHUB_OAUTH_CLIENT_SECRET, BASE_URL, JWT_SIGNING_KEY) for OAuth, and/or set '
            'MCP_API_KEYS for key-based auth.'
        )
    if settings.oauth_enabled and not settings.allowed_github_org and not settings.allow_ungated:
        raise RuntimeError(
            'No access gate configured for OAuth users: set ALLOWED_GITHUB_ORG to restrict '
            'OAuth access to an org, or set ALLOW_UNGATED=1 to explicitly allow any authenticated '
            'GitHub user. Refusing to start ungated by default.'
        )
    server = FastMCPProxy(
        client_factory=build_client_factory(settings),
        auth=build_auth(settings),
        name='GitHubProxy',
    )
    # Org-membership gating applies to OAuth users (it needs the user's GitHub token);
    # key-authenticated requests carry no GitHub identity and bypass it inside the
    # middleware, the key itself being their gate.
    if settings.oauth_enabled and settings.allowed_github_org:
        server.add_middleware(OrgMembershipMiddleware(settings.allowed_github_org))
    server.add_middleware(ObservabilityMiddleware())
    return server


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> None:
    """Block until a TCP port accepts connections or the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.25)
    raise TimeoutError(f'Backend github-mcp-server did not start on {host}:{port}')


def _linux_die_with_parent() -> Callable[[], None] | None:
    """Return a preexec_fn that asks the kernel to SIGTERM the child if we die.

    Uses Linux prctl(PR_SET_PDEATHSIG). uvicorn's signal handling can bypass our
    cleanup ``finally`` on SIGTERM (e.g. a Heroku dyno restart), which would orphan
    the backend; this guarantees the kernel reaps it. No-op on non-Linux platforms.
    """
    if not sys.platform.startswith('linux'):
        return None

    def preexec() -> None:
        pr_set_pdeathsig = 1
        ctypes.CDLL('libc.so.6', use_errno=True).prctl(pr_set_pdeathsig, signal.SIGTERM)

    return preexec


@contextlib.contextmanager
def run_backend(settings: Settings) -> Iterator[subprocess.Popen]:
    """Start github-mcp-server in http mode for the lifetime of the context.

    No global token is passed — each proxied request carries its own bearer token.

    Args:
        settings: Runtime settings holding the binary path and backend port.

    Yields:
        The running backend process.
    """
    port = settings.backend_port
    process = subprocess.Popen(
        [
            settings.github_mcp_binary,
            'http',
            '--port',
            str(port),
        ],
        preexec_fn=_linux_die_with_parent(),
    )
    try:
        _wait_for_port('127.0.0.1', port)
        yield process
    finally:
        process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=10)


def main() -> None:
    """Start the backend subprocess and run the MCP server over HTTP."""
    logging.basicConfig(level=logging.INFO)
    configure_observability()
    settings = load_settings()
    server = build_server(settings)
    with run_backend(settings):
        server.run(transport='http', host='0.0.0.0', port=settings.port)


if __name__ == '__main__':
    main()
