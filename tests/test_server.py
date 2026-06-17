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
