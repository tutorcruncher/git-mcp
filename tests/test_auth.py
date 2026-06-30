import dataclasses
from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from app.auth import DualAuthProvider, build_auth

OAUTH_DISABLED = {'github_client_id': '', 'github_client_secret': '', 'base_url': '', 'jwt_signing_key': ''}


def test_build_auth_without_redis_uses_default_store(settings):
    """With no Redis configured, the provider falls back to FastMCP's on-disk store."""
    provider = build_auth(settings)

    assert isinstance(provider, GitHubProvider)
    storage = provider._client_storage
    assert isinstance(storage, FernetEncryptionWrapper)
    assert not isinstance(storage.key_value, RedisStore)


def test_build_auth_with_redis_persists_encrypted_state(settings):
    """A configured Redis URL wires an encrypted Redis-backed OAuth state store."""
    settings = dataclasses.replace(settings, redis_url='redis://redis.example.test:6379/0')

    provider = build_auth(settings)

    assert isinstance(provider, GitHubProvider)
    storage = provider._client_storage
    assert isinstance(storage, FernetEncryptionWrapper)
    assert isinstance(storage.key_value, RedisStore)


def test_build_auth_uses_static_verifier_when_keys_only(settings):
    """With only MCP_API_KEYS set (no OAuth credentials), build_auth returns a key verifier."""
    settings = dataclasses.replace(settings, mcp_api_keys=['key-one', 'key-two'], **OAUTH_DISABLED)

    provider = build_auth(settings)

    assert isinstance(provider, StaticTokenVerifier)
    assert not isinstance(provider, GitHubProvider)
    assert set(provider.tokens) == {'key-one', 'key-two'}
    assert {claims['client_id'] for claims in provider.tokens.values()} == {'api-key-1', 'api-key-2'}
    assert all(claims['auth_mode'] == 'key' for claims in provider.tokens.values())


def test_build_auth_dual_mode_when_oauth_and_keys_set(settings):
    """With both OAuth credentials and MCP_API_KEYS, build_auth returns a DualAuthProvider."""
    settings = dataclasses.replace(settings, mcp_api_keys=['key-one', 'key-two'])

    provider = build_auth(settings)

    assert isinstance(provider, DualAuthProvider)
    assert isinstance(provider, GitHubProvider)
    assert set(provider._static_tokens) == {'key-one', 'key-two'}


async def test_dual_provider_accepts_static_key_with_required_scopes(settings):
    """A configured static key verifies locally, tagged auth_mode=key and carrying the scopes."""
    settings = dataclasses.replace(settings, mcp_api_keys=['key-one'])
    provider = build_auth(settings)

    token = await provider.verify_token('key-one')

    assert token is not None
    assert token.client_id == 'api-key-1'
    assert token.scopes == settings.github_scopes
    assert token.claims == {'client_id': 'api-key-1', 'scopes': settings.github_scopes, 'auth_mode': 'key'}


async def test_dual_provider_unknown_key_falls_through_to_oauth(settings):
    """A token that is not a configured key is delegated to GitHub OAuth verification."""
    settings = dataclasses.replace(settings, mcp_api_keys=['key-one'])
    provider = build_auth(settings)

    with patch(
        'fastmcp.server.auth.providers.github.GitHubProvider.verify_token', new_callable=AsyncMock
    ) as mock_super:
        mock_super.return_value = None
        result = await provider.verify_token('not-a-key')

    assert result is None
    mock_super.assert_awaited_once_with('not-a-key')


@patch('app.auth.derive_jwt_key')
def test_build_auth_redis_encryption_key_derives_from_signing_key(mock_derive, settings):
    """The at-rest encryption key is derived from the JWT signing key and storage salt."""
    mock_derive.return_value = Fernet.generate_key()
    settings = dataclasses.replace(settings, redis_url='redis://redis.example.test:6379/0')

    build_auth(settings)

    mock_derive.assert_called_once_with(
        high_entropy_material=settings.jwt_signing_key,
        salt='fastmcp-storage-encryption-key',
    )
