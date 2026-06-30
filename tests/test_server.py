import dataclasses

import pytest

from app.server import build_server


def test_build_server_refuses_when_ungated(settings):
    """With no org gate and no explicit opt-in, the server refuses to start."""
    ungated = dataclasses.replace(settings, allowed_github_org=None, allow_ungated=False)

    with pytest.raises(RuntimeError, match='No access gate configured'):
        build_server(ungated)


def test_build_server_builds_with_org_gate(settings):
    """An org-gated configuration builds a server."""
    server = build_server(settings)

    assert server.name == 'GitHubProxy'


def test_build_server_allows_explicit_ungated_optin(settings):
    """ALLOW_UNGATED opt-in lets the server start without an org gate."""
    ungated = dataclasses.replace(settings, allowed_github_org=None, allow_ungated=True)

    server = build_server(ungated)

    assert server.name == 'GitHubProxy'


def test_build_server_key_auth_is_its_own_gate(settings):
    """Key-based auth lets the server start with no org gate / opt-in, using a key verifier."""
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

    key_only = dataclasses.replace(
        settings,
        allowed_github_org=None,
        allow_ungated=False,
        mcp_api_keys=['secret-key'],
        github_backend_token='ghp_backend',
    )

    server = build_server(key_only)

    assert server.name == 'GitHubProxy'
    assert isinstance(server.auth, StaticTokenVerifier)


def test_build_server_key_auth_skips_org_middleware(settings):
    """In key mode the GitHub org-membership middleware is not added (no GitHub identity)."""
    from app.access import OrgMembershipMiddleware

    key_mode = dataclasses.replace(settings, mcp_api_keys=['secret-key'], github_backend_token='ghp_backend')
    server = build_server(key_mode)

    assert not any(isinstance(m, OrgMembershipMiddleware) for m in server.middleware)
