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


def test_build_server_key_only_is_its_own_gate(settings):
    """Key-only auth (no OAuth creds) starts with no org gate / opt-in, using a key verifier."""
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

    key_only = dataclasses.replace(
        settings,
        github_client_id='',
        github_client_secret='',
        base_url='',
        jwt_signing_key='',
        allowed_github_org=None,
        allow_ungated=False,
        mcp_api_keys=['secret-key'],
        github_backend_token='ghp_backend',
    )

    server = build_server(key_only)

    assert server.name == 'GitHubProxy'
    assert isinstance(server.auth, StaticTokenVerifier)


def test_build_server_key_only_skips_org_middleware(settings):
    """In key-only mode the GitHub org-membership middleware is not added (no GitHub identity)."""
    from app.access import OrgMembershipMiddleware

    key_only = dataclasses.replace(
        settings,
        github_client_id='',
        github_client_secret='',
        base_url='',
        jwt_signing_key='',
        mcp_api_keys=['secret-key'],
        github_backend_token='ghp_backend',
    )
    server = build_server(key_only)

    assert not any(isinstance(m, OrgMembershipMiddleware) for m in server.middleware)


def test_build_server_dual_mode_keeps_org_middleware(settings):
    """With both OAuth and keys, the org gate stays installed (it gates OAuth users)."""
    from app.access import OrgMembershipMiddleware
    from app.auth import DualAuthProvider

    dual = dataclasses.replace(settings, mcp_api_keys=['secret-key'], github_backend_token='ghp_backend')
    server = build_server(dual)

    assert isinstance(server.auth, DualAuthProvider)
    assert any(isinstance(m, OrgMembershipMiddleware) for m in server.middleware)


def test_build_server_refuses_with_no_auth_at_all(settings):
    """No OAuth credentials and no API keys means no way to authenticate: refuse to start."""
    none = dataclasses.replace(
        settings,
        github_client_id='',
        github_client_secret='',
        base_url='',
        jwt_signing_key='',
        mcp_api_keys=[],
    )

    with pytest.raises(RuntimeError, match='No auth configured'):
        build_server(none)
