from dataclasses import dataclass
from unittest.mock import patch

import pytest

from app.backend import build_backend_headers, build_client_factory


@dataclass
class FakeToken:
    """Stand-in for fastmcp's AccessToken in tests."""

    token: str


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
