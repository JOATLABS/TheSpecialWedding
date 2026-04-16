import importlib
from types import SimpleNamespace

import pytest

from app.services import config_validator


@pytest.mark.asyncio
async def test_guest_media_domain_is_not_reported_as_missing_recommended_env(
    monkeypatch,
):
    for key in config_validator.CRITICAL_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    for key in config_validator.RECOMMENDED_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    monkeypatch.delenv("GUEST_MEDIA_DOMAIN", raising=False)

    calls = []
    clears = []

    async def fake_create_root_admin_notification(*, title, message, priority="high"):
        calls.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
            }
        )

    async def fake_clear_config_notifications():
        clears.append("cleared")

    class FakeMediaStorage:
        def target_health(self, target):
            return SimpleNamespace(bucket_name="ok", status="ready", issue=None)

        async def browser_upload_health(self, target, origins):
            return SimpleNamespace(status="ready", issue=None)

    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator,
        "clear_config_notifications",
        fake_clear_config_notifications,
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    importlib.reload(config_validator)
    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator,
        "clear_config_notifications",
        fake_clear_config_notifications,
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    result = await config_validator.validate_environment_and_notify()

    assert "GUEST_MEDIA_DOMAIN" not in config_validator.RECOMMENDED_ENV_VARS
    assert result["missing_critical"] == []
    assert result["missing_recommended"] == []
    assert calls == []
    assert clears == ["cleared"]


@pytest.mark.asyncio
async def test_storage_recommendations_are_target_aware(monkeypatch):
    for key in config_validator.CRITICAL_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    for key in config_validator.RECOMMENDED_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    monkeypatch.setattr(
        config_validator.settings, "s3_endpoint_url", "https://storage.example.com"
    )
    monkeypatch.setattr(config_validator.settings, "s3_access_key_id", "access")
    monkeypatch.setattr(config_validator.settings, "s3_secret_access_key", "secret")
    monkeypatch.setattr(config_validator.settings, "s3_bucket_name", "primary-bucket")
    monkeypatch.setattr(
        config_validator.settings, "s3_guest_media_bucket_name", "guest-bucket"
    )
    monkeypatch.setattr(config_validator.settings, "s3_ad_bucket_name", None)
    monkeypatch.setattr(config_validator.settings, "s3_blog_bucket_name", "blog-bucket")
    monkeypatch.setattr(config_validator.settings, "ad_media_domain", None)
    monkeypatch.setattr(config_validator.settings, "blog_media_domain", None)

    calls = []

    async def fake_create_root_admin_notification(*, title, message, priority="high"):
        calls.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
            }
        )

    async def fake_clear_config_notifications():
        raise AssertionError(
            "clear_config_notifications should not run when warnings exist"
        )

    class FakeMediaStorage:
        def target_health(self, target):
            if target == config_validator.StorageTarget.BLOG_ASSETS:
                return SimpleNamespace(
                    bucket_name="blog-bucket",
                    status="unavailable",
                    issue="Storage bucket 'blog-bucket' for target 'blog_assets' is configured but currently inaccessible (AccessDenied).",
                )
            return SimpleNamespace(bucket_name="ok", status="ready", issue=None)

        async def browser_upload_health(self, target, origins):
            return SimpleNamespace(status="ready", issue=None)

    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator, "clear_config_notifications", fake_clear_config_notifications
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    result = await config_validator.validate_environment_and_notify()

    assert (
        "S3_AD_BUCKET_NAME: Dedicated ad-assets R2 bucket"
        in result["missing_recommended"]
    )
    assert (
        "BLOG_MEDIA_DOMAIN: Public CDN/domain for blog asset URLs"
        in result["missing_recommended"]
    )
    assert any(
        item.startswith("S3_BLOG_BUCKET_NAME: Storage bucket 'blog-bucket'")
        for item in result["missing_recommended"]
    )
    assert not any("AD_MEDIA_DOMAIN" in item for item in result["missing_recommended"])
    assert (
        calls
        and calls[0]["title"] == "Configuration Warning: Missing Recommended Settings"
    )


@pytest.mark.asyncio
async def test_browser_upload_cors_warnings_are_target_aware(monkeypatch):
    for key in config_validator.CRITICAL_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    for key in config_validator.RECOMMENDED_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    monkeypatch.setattr(
        config_validator.settings, "frontend_url", "http://localhost:3000"
    )
    monkeypatch.setattr(
        config_validator.settings, "api_base_url", "http://localhost:8000"
    )
    monkeypatch.setattr(
        config_validator.settings, "cors_origins", ["http://localhost:3000"]
    )
    monkeypatch.setattr(
        config_validator.settings, "s3_endpoint_url", "https://storage.example.com"
    )
    monkeypatch.setattr(config_validator.settings, "s3_access_key_id", "access")
    monkeypatch.setattr(config_validator.settings, "s3_secret_access_key", "secret")
    monkeypatch.setattr(config_validator.settings, "s3_bucket_name", "primary-bucket")
    monkeypatch.setattr(
        config_validator.settings, "s3_guest_media_bucket_name", "guest-bucket"
    )
    monkeypatch.setattr(config_validator.settings, "s3_ad_bucket_name", "ad-bucket")
    monkeypatch.setattr(config_validator.settings, "s3_blog_bucket_name", "blog-bucket")

    calls = []

    async def fake_create_root_admin_notification(*, title, message, priority="high"):
        calls.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
            }
        )

    async def fake_clear_config_notifications():
        raise AssertionError(
            "clear_config_notifications should not run when warnings exist"
        )

    class FakeMediaStorage:
        def target_health(self, target):
            return SimpleNamespace(
                bucket_name="ok", status="ready", issue=None, is_ready=True
            )

        async def browser_upload_health(self, target, origins):
            if target == config_validator.StorageTarget.GUEST_MEDIA:
                return SimpleNamespace(
                    status="misconfigured",
                    issue=(
                        "Bucket 'guest-bucket' allows storage access but its CORS policy "
                        "does not allow browser PUT uploads with the Content-Type header "
                        "from: http://localhost:3000."
                    ),
                )
            return SimpleNamespace(status="ready", issue=None)

    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator, "clear_config_notifications", fake_clear_config_notifications
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    result = await config_validator.validate_environment_and_notify()

    assert any(
        item.startswith(
            "S3_GUEST_MEDIA_BUCKET_NAME: Bucket 'guest-bucket' allows storage access"
        )
        for item in result["missing_recommended"]
    )
    assert not any(
        "S3_BUCKET_NAME:" in item and "CORS policy" in item
        for item in result["missing_recommended"]
    )
    assert (
        calls
        and calls[0]["title"] == "Configuration Warning: Missing Recommended Settings"
    )
