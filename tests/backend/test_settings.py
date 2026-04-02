"""
Settings Tests

Focus on environment-sensitive settings that gate production behavior.
"""

from app.core.settings import Settings
from app.main import build_root_response


def build_settings(**overrides) -> Settings:
    base = {
        "SECRET_KEY": "test-secret-key-this-is-long-enough-for-validation-testing-purposes-2026",
        "CORS_ORIGINS": ["http://localhost:3000"],
        "ENVIRONMENT": "development",
    }
    base.update(overrides)
    return Settings(**base)


def test_api_docs_enabled_by_default_outside_production():
    settings = build_settings(ENVIRONMENT="development")
    assert settings.api_docs_enabled is True


def test_api_docs_disabled_by_default_in_production():
    settings = build_settings(ENVIRONMENT="production")
    assert settings.api_docs_enabled is False


def test_api_docs_can_be_explicitly_enabled_in_production():
    settings = build_settings(ENVIRONMENT="production", ENABLE_API_DOCS=True)
    assert settings.api_docs_enabled is True


def test_root_response_hides_docs_url_when_docs_disabled():
    settings = build_settings(ENVIRONMENT="production")
    response = build_root_response(settings)

    assert "docs_url" not in response


def test_root_response_includes_docs_url_when_docs_enabled():
    settings = build_settings(ENVIRONMENT="development")
    response = build_root_response(settings)

    assert response["docs_url"] == "/docs"


def test_trusted_hosts_are_derived_from_frontend_api_and_cors_urls():
    settings = build_settings(
        ENVIRONMENT="production",
        FRONTEND_URL="https://app.example.com",
        NEXT_PUBLIC_API_BASE_URL="https://api.example.com",
        CORS_ORIGINS=["https://admin.example.com", "https://app.example.com"],
    )

    assert settings.trusted_hosts == [
        "app.example.com",
        "api.example.com",
        "admin.example.com",
    ]


def test_trusted_hosts_include_local_dev_defaults():
    settings = build_settings(
        ENVIRONMENT="development",
        NEXT_PUBLIC_API_BASE_URL="http://localhost:8000",
        CORS_ORIGINS=["http://localhost:3000"],
    )

    assert settings.trusted_hosts == ["localhost", "127.0.0.1", "testserver"]


def test_allowed_hosts_override_accepts_comma_separated_values():
    settings = build_settings(
        ENVIRONMENT="production",
        ALLOWED_HOSTS="api.example.com,app.example.com,*.example.com",
    )

    assert settings.trusted_hosts == [
        "api.example.com",
        "app.example.com",
        "*.example.com",
    ]
