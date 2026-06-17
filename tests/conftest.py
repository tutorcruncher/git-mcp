import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    """A complete Settings instance for tests, with no external dependencies."""
    return Settings(
        github_client_id='Ov23li_test',
        github_client_secret='secret_test',
        base_url='https://example.test',
        github_scopes=['repo', 'read:org'],
        backend_mcp_url='http://127.0.0.1:8082/mcp',
        github_toolsets='repos,issues',
        read_only=False,
        jwt_signing_key='test-signing-key',
        port=8000,
        github_mcp_binary='github-mcp-server',
        allowed_github_org=None,
    )
