import dataclasses
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from app.backend import build_backend_headers, build_client_factory


@dataclass
class FakeToken:
    """Stand-in for fastmcp's AccessToken in tests."""

    token: str
    claims: dict | None = None


def test_build_backend_headers_default():
    """Headers carry the bearer token and toolsets, no readonly when disabled."""
    headers = build_backend_headers(token='gho_abc', toolsets='repos,issues', read_only=False)

    assert headers == {
        'Authorization': 'Bearer gho_abc',
        'X-MCP-Toolsets': 'repos,issues',
    }


def test_build_backend_headers_read_only():
    """Read-only mode adds the X-MCP-Readonly header."""
    headers = build_backend_headers(token='gho_abc', toolsets='all', read_only=True)

    assert headers == {
        'Authorization': 'Bearer gho_abc',
        'X-MCP-Toolsets': 'all',
        'X-MCP-Readonly': 'true',
    }


@patch('app.backend.get_access_token')
def test_factory_injects_request_user_token(mock_get_token, settings):
    """The factory builds a backend client bound to the current request's token."""
    mock_get_token.return_value = FakeToken(token='gho_user1')

    client = build_client_factory(settings)()

    assert client.transport.headers == {
        'Authorization': 'Bearer gho_user1',
        'X-MCP-Toolsets': 'repos,issues',
    }
    assert str(client.transport.url) == 'http://127.0.0.1:8082/mcp'


@patch('app.backend.get_access_token')
def test_factory_disables_header_forwarding(mock_get_token, settings):
    """The backend client must not forward Claude's inbound headers to github-mcp-server."""
    mock_get_token.return_value = FakeToken(token='gho_user1')

    client = build_client_factory(settings)()

    assert client.transport.forward_incoming_headers is False


@patch('app.backend.get_access_token')
def test_factory_is_per_user(mock_get_token, settings):
    """Two requests with different tokens yield clients with different bearers."""
    factory = build_client_factory(settings)

    mock_get_token.return_value = FakeToken(token='gho_user1')
    client1 = factory()
    mock_get_token.return_value = FakeToken(token='gho_user2')
    client2 = factory()

    assert client1.transport.headers['Authorization'] == 'Bearer gho_user1'
    assert client2.transport.headers['Authorization'] == 'Bearer gho_user2'


@patch('app.backend.get_access_token')
def test_factory_without_token_raises(mock_get_token, settings):
    """A request with no authenticated token is rejected."""
    mock_get_token.return_value = None

    with pytest.raises(PermissionError):
        build_client_factory(settings)()


@patch('app.backend.get_access_token')
def test_factory_uses_backend_pat_for_key_request(mock_get_token, settings):
    """A key-authenticated request injects the static backend PAT, not a user token."""
    mock_get_token.return_value = FakeToken(token='k', claims={'auth_mode': 'key', 'client_id': 'api-key-1'})
    key_settings = dataclasses.replace(settings, github_backend_token='ghp_backend')

    client = build_client_factory(key_settings)()

    assert client.transport.headers == {
        'Authorization': 'Bearer ghp_backend',
        'X-MCP-Toolsets': 'repos,issues',
    }
    assert client.transport.forward_incoming_headers is False


@patch('app.backend.get_access_token')
def test_factory_key_request_requires_backend_token(mock_get_token, settings):
    """A key-authenticated request with no GITHUB_BACKEND_TOKEN fails with a clear error."""
    mock_get_token.return_value = FakeToken(token='k', claims={'auth_mode': 'key'})
    key_settings = dataclasses.replace(settings, github_backend_token=None)

    with pytest.raises(PermissionError, match='GITHUB_BACKEND_TOKEN'):
        build_client_factory(key_settings)()


@patch('app.backend.get_access_token')
def test_factory_oauth_request_uses_user_token_in_dual_mode(mock_get_token, settings):
    """An OAuth request (no key claim) forwards the user's token even when keys are configured."""
    mock_get_token.return_value = FakeToken(token='gho_user1', claims={'login': 'octocat'})
    dual_settings = dataclasses.replace(settings, mcp_api_keys=['k'], github_backend_token='ghp_backend')

    client = build_client_factory(dual_settings)()

    assert client.transport.headers['Authorization'] == 'Bearer gho_user1'
