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
        "TESTING": False,
        "ENABLE_API_DOCS": None,
        "ALLOWED_HOSTS": [],
    }
    base.update(overrides)
    return Settings.model_validate(base)


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

    assert settings.trusted_hosts == ["localhost", "127.0.0.1", "::1", "testserver"]


def test_browser_upload_origins_follow_frontend_not_api_hosts():
    settings = build_settings(
        ENVIRONMENT="development",
        FRONTEND_URL="http://localhost:3000/dashboard",
        NEXT_PUBLIC_API_BASE_URL="http://localhost:8000",
        CORS_ORIGINS=[
            "http://localhost:3000",
            "http://localhost:8000",
            "https://staging.thespecialwedding.io",
        ],
    )

    assert settings.browser_upload_origins == [
        "http://localhost:3000",
        "https://staging.thespecialwedding.io",
    ]


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


def test_env_cors_origins_accepts_comma_separated_values(monkeypatch):
    monkeypatch.setenv(
        "SECRET_KEY",
        "test-secret-key-this-is-long-enough-for-validation-testing-purposes-2026",
    )
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://[::1]:8000",
    ]


def test_env_allowed_hosts_accepts_comma_separated_values(monkeypatch):
    monkeypatch.setenv(
        "SECRET_KEY",
        "test-secret-key-this-is-long-enough-for-validation-testing-purposes-2026",
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com,app.example.com,*.example.com")

    settings = Settings(_env_file=None)

    assert settings.trusted_hosts == [
        "api.example.com",
        "app.example.com",
        "*.example.com",
    ]


def test_security_log_settings_default_to_repo_writable_paths():
    settings = build_settings()

    assert settings.security_log_to_file is True
    assert settings.security_log_file == "logs/security_audit.log"


def test_security_log_file_can_be_overridden():
    settings = build_settings(SECURITY_LOG_FILE="/tmp/custom-security.log")

    assert settings.security_log_file == "/tmp/custom-security.log"
