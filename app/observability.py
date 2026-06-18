"""Optional Logfire observability, fully opt-in via the LOGFIRE_TOKEN env var.

``configure_observability()`` is called once from ``main()``. With no token set it
configures Logfire in local-only mode (``send_to_logfire='if-token-present'``) so the
server, tests and local runs are unaffected; nothing is exported. With a token it
instruments httpx — tracing every backend github-mcp-server and GitHub API call with
status and latency — and ``ObservabilityMiddleware`` opens a span per proxied tool call.

httpx instrumentation uses the conservative defaults (no header or body capture), so
each user's GitHub bearer token is never sent to Logfire.
"""

import logfire
import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

_configured = False


def configure_observability() -> None:
    """Configure Logfire once. A no-op exporter unless LOGFIRE_TOKEN is set."""
    global _configured
    logfire.configure(
        send_to_logfire='if-token-present',
        service_name='git-mcp',
        console=False,
    )
    logfire.instrument_httpx()
    _configured = True


class ObservabilityMiddleware(Middleware):
    """Open a Logfire span around each proxied tool call.

    The span is named after the tool and records its timing and any error. It is a
    no-op unless ``configure_observability()`` ran with a token present, so the
    middleware is always safe to install regardless of whether Logfire is enabled.
    """

    async def on_call_tool(self, context: MiddlewareContext[mt.CallToolRequestParams], call_next: CallNext):
        """Wrap the proxied tool call in a span named after the tool."""
        if not _configured:
            return await call_next(context)
        with logfire.span('tool {tool_name}', tool_name=context.message.name):
            return await call_next(context)
