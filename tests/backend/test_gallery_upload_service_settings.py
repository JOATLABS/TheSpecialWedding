import importlib

from app.core.settings import settings
import app.services.gallery_upload_service as gallery_upload_service


def test_gallery_service_uses_settings_when_shell_env_missing(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("MEDIA_DOMAIN", raising=False)

    monkeypatch.setattr(settings, "s3_bucket_name", "bucket-from-settings")
    monkeypatch.setattr(
        settings, "s3_endpoint_url", "https://example-account.r2.cloudflarestorage.com"
    )
    monkeypatch.setattr(settings, "s3_access_key_id", "test-access-key")
    monkeypatch.setattr(settings, "s3_secret_access_key", "test-secret-key")
    monkeypatch.setattr(settings, "s3_region", "auto")
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:3000")
    monkeypatch.setattr(settings, "media_domain", "media.example.com")

    reloaded = importlib.reload(gallery_upload_service)
    service = reloaded.GalleryUploadService()

    assert service.bucket_name == "bucket-from-settings"
    assert (
        service.s3.meta.endpoint_url
        == "https://example-account.r2.cloudflarestorage.com"
    )
    assert service.frontend_url == "http://localhost:3000"
    assert reloaded.MEDIA_DOMAIN == "https://media.example.com"

    importlib.reload(gallery_upload_service)
