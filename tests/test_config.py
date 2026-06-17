import pytest

from app.config import load_settings


def test_load_settings_reads_environment(monkeypatch):
    """load_settings parses all fields from the environment."""
    monkeypatch.setenv('GITHUB_OAUTH_CLIENT_ID', 'Ov23li_env')
    monkeypatch.setenv('GITHUB_OAUTH_CLIENT_SECRET', 'secret_env')
    monkeypatch.setenv('BASE_URL', 'https://app.example.test/')
    monkeypatch.setenv('GITHUB_SCOPES', 'repo read:user')
    monkeypatch.setenv('BACKEND_MCP_URL', 'http://127.0.0.1:9000/mcp')
    monkeypatch.setenv('GITHUB_TOOLSETS', 'repos')
    monkeypatch.setenv('READ_ONLY', '1')
    monkeypatch.setenv('JWT_SIGNING_KEY', 'k')
    monkeypatch.setenv('PORT', '1234')
    monkeypatch.setenv('GITHUB_MCP_BINARY', '/bin/ghmcp')
    monkeypatch.setenv('ALLOWED_GITHUB_ORG', 'tutorcruncher')
    monkeypatch.setenv('ALLOW_UNGATED', '1')
    monkeypatch.setenv('ALLOWED_REDIRECT_URIS', 'https://claude.ai/api/mcp/auth_callback https://example.test/cb')

    settings = load_settings()

    assert settings.github_client_id == 'Ov23li_env'
    assert settings.github_client_secret == 'secret_env'
    assert settings.base_url == 'https://app.example.test'
    assert settings.github_scopes == ['repo', 'read:user']
    assert settings.backend_mcp_url == 'http://127.0.0.1:9000/mcp'
    assert settings.github_toolsets == 'repos'
    assert settings.read_only is True
    assert settings.jwt_signing_key == 'k'
    assert settings.port == 1234
    assert settings.github_mcp_binary == '/bin/ghmcp'
    assert settings.backend_port == 9000
    assert settings.allowed_github_org == 'tutorcruncher'
    assert settings.allow_ungated is True
    assert settings.allowed_redirect_uris == [
        'https://claude.ai/api/mcp/auth_callback',
        'https://example.test/cb',
    ]


def test_defaults_fail_closed(monkeypatch):
    """ALLOWED_GITHUB_ORG/ALLOW_UNGATED default to a gated, fail-closed posture."""
    for var in ('GITHUB_OAUTH_CLIENT_ID', 'GITHUB_OAUTH_CLIENT_SECRET', 'BASE_URL', 'JWT_SIGNING_KEY'):
        monkeypatch.setenv(var, 'x')
    for var in ('ALLOWED_GITHUB_ORG', 'ALLOW_UNGATED', 'ALLOWED_REDIRECT_URIS'):
        monkeypatch.delenv(var, raising=False)

    settings = load_settings()

    assert settings.allowed_github_org is None
    assert settings.allow_ungated is False
    assert settings.allowed_redirect_uris == ['https://claude.ai/api/mcp/auth_callback']


def test_load_settings_missing_required_raises(monkeypatch):
    """A missing required variable raises a clear error naming the variable."""
    monkeypatch.delenv('GITHUB_OAUTH_CLIENT_ID', raising=False)

    with pytest.raises(RuntimeError, match='GITHUB_OAUTH_CLIENT_ID'):
        load_settings()
