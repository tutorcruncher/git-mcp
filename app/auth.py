"""Authentication for the MCP proxy: GitHub OAuth, static API keys, or both.

Auth is driven by what's configured, and OAuth and key-based auth are no longer
mutually exclusive — a single deployment can serve both at once:

- **GitHub OAuth** (when the OAuth credentials are set): GitHubProvider makes this
  server an OAuth 2.1 resource/authorization server to Claude's custom connector,
  proxying the flow to a GitHub OAuth App; the per-user upstream token
  (get_access_token().token) is forwarded to the backend. OAuth state is persisted
  via a pluggable key-value store — with ``REDIS_URL`` it survives restarts
  (otherwise the default on-disk store is lost on ephemeral filesystems like
  Heroku dyno cycling).

- **Key-based** (when ``MCP_API_KEYS`` is set): clients present a static Bearer
  key. There's no per-user GitHub token, so the proxy forwards a configured static
  PAT (``GITHUB_BACKEND_TOKEN``) to the backend. This is the simplest way to
  connect a headless client/agent.

When **both** are configured, ``DualAuthProvider`` serves the full OAuth flow *and*
accepts the static keys, so an OAuth client (Claude Desktop) and a headless key
client (a built app) can use the same server simultaneously. Key requests are
tagged ``auth_mode='key'`` so the org gate and backend factory can tell them apart
from OAuth requests. When only keys are set (no OAuth credentials), a plain
StaticTokenVerifier is used.
"""

from urllib.parse import urlparse

from cryptography.fernet import Fernet
from fastmcp.server.auth import AccessToken, AuthProvider
from fastmcp.server.auth.jwt_issuer import derive_jwt_key
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from app.config import Settings

AUTH_MODE_CLAIM = 'auth_mode'
KEY_AUTH_MODE = 'key'


def _build_client_storage(settings: Settings) -> AsyncKeyValue | None:
    """Build a persistent, encrypted OAuth-state store, or None for the default.

    Returns a Redis-backed store wrapped in Fernet encryption when ``redis_url``
    is set, so OAuth state survives restarts and is encrypted at rest with a key
    derived from the JWT signing key (matching FastMCP's default-store scheme).
    Heroku's managed Redis serves ``rediss://`` with a self-signed certificate,
    so TLS verification is relaxed for that scheme. Returns None when no Redis is
    configured, letting GitHubProvider use its built-in on-disk store.

    Args:
        settings: Runtime settings holding the optional Redis URL and signing key.

    Returns:
        AsyncKeyValue | None: The storage backend, or None to use the default.
    """
    if not settings.redis_url:
        return None

    if urlparse(settings.redis_url).scheme == 'rediss':
        store = RedisStore(url=settings.redis_url, ssl_cert_reqs='none', ssl_check_hostname=False)
    else:
        store = RedisStore(url=settings.redis_url)

    encryption_key = derive_jwt_key(
        high_entropy_material=settings.jwt_signing_key,
        salt='fastmcp-storage-encryption-key',
    )
    return FernetEncryptionWrapper(
        key_value=store,
        fernet=Fernet(key=encryption_key),
        raise_on_decryption_error=False,
    )


def _static_token_map(api_keys: list[str], scopes: list[str]) -> dict[str, dict]:
    """Build the static-token map for the configured API keys.

    Each key authenticates as a distinct ``api-key-N`` client_id so logs/traces can
    tell connections apart, and is tagged ``auth_mode='key'`` so downstream code (the
    org gate, the backend factory) can distinguish key requests from OAuth requests.
    The keys carry ``scopes`` so they satisfy any ``required_scopes`` the bearer-auth
    middleware enforces when running alongside OAuth (dual mode).

    Args:
        api_keys: The configured static API keys.
        scopes: Scopes to attach to each key's access token.

    Returns:
        A mapping of key to its StaticTokenVerifier-style token data.
    """
    return {
        key: {'client_id': f'api-key-{index}', 'scopes': list(scopes), AUTH_MODE_CLAIM: KEY_AUTH_MODE}
        for index, key in enumerate(api_keys, start=1)
    }


class DualAuthProvider(GitHubProvider):
    """GitHubProvider that additionally accepts a set of static API keys.

    The GitHub OAuth flow works exactly as in ``GitHubProvider`` — all of its routes
    and JWT verification are inherited unchanged, so Claude's custom connector
    authenticates as before. In addition, a request bearing one of the configured
    static keys is verified locally as an ``api-key-N`` client tagged
    ``auth_mode='key'``. This lets an OAuth client (Claude Desktop) and a headless
    key client (a built app) use the same deployment at once.
    """

    def __init__(self, api_keys: list[str], **github_kwargs) -> None:
        super().__init__(**github_kwargs)
        self._static_tokens = _static_token_map(api_keys, self.required_scopes)

    async def verify_token(self, token: str) -> AccessToken | None:
        """Accept a configured static key, else fall back to GitHub OAuth verification."""
        token_data = self._static_tokens.get(token)
        if token_data is not None:
            return AccessToken(
                token=token,
                client_id=token_data['client_id'],
                scopes=token_data['scopes'],
                claims=token_data,
            )
        return await super().verify_token(token)


def build_key_verifier(settings: Settings) -> StaticTokenVerifier:
    """Build a static-token verifier from the configured API keys.

    Used when only keys are configured (no OAuth credentials). Possession of a valid
    key is the only gate (no org membership check); the GitHub the proxied tools see
    is determined by the configured backend PAT.

    Args:
        settings: Runtime settings holding ``mcp_api_keys``.

    Returns:
        StaticTokenVerifier: Verifier to pass as ``FastMCP(auth=...)``.
    """
    return StaticTokenVerifier(tokens=_static_token_map(settings.mcp_api_keys, []))


def _github_provider_kwargs(settings: Settings) -> dict:
    """Build the keyword arguments shared by GitHubProvider and DualAuthProvider."""
    return {
        'client_id': settings.github_client_id,
        'client_secret': settings.github_client_secret,
        'base_url': settings.base_url,
        'required_scopes': settings.github_scopes,
        'jwt_signing_key': settings.jwt_signing_key,
        'allowed_client_redirect_uris': settings.allowed_redirect_uris,
        'client_storage': _build_client_storage(settings),
    }


def build_auth(settings: Settings) -> AuthProvider:
    """Build the auth provider from configuration.

    - OAuth credentials only: a plain ``GitHubProvider`` (OAuth flow, callback URL
      ``<base_url>/auth/callback``).
    - OAuth credentials *and* ``MCP_API_KEYS``: a ``DualAuthProvider`` that serves
      OAuth and also accepts the static keys.
    - ``MCP_API_KEYS`` only (no OAuth credentials): a ``StaticTokenVerifier``.

    Args:
        settings: Runtime settings holding the OAuth App credentials and/or API keys.

    Returns:
        AuthProvider: Configured auth provider to pass as ``FastMCP(auth=...)``.
    """
    if not settings.oauth_enabled:
        return build_key_verifier(settings)
    if settings.mcp_api_keys:
        return DualAuthProvider(api_keys=settings.mcp_api_keys, **_github_provider_kwargs(settings))
    return GitHubProvider(**_github_provider_kwargs(settings))
