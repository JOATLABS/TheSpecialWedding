from types import SimpleNamespace

import pytest

from app.jobs.vendor_scraper import logo_uploader
from app.services.media_storage import StorageTarget


class FakeMediaStorage:
    def __init__(self):
        self.uploads: list[dict] = []

    def target(self, target):
        assert target == StorageTarget.AD_ASSETS
        return SimpleNamespace(
            bucket_name="ad-bucket",
            public_domain="https://ads.example.com",
        )

    def upload_fileobj(self, fileobj, target, key, extra_args=None):
        self.uploads.append(
            {
                "target": target,
                "key": key,
                "payload": fileobj.read(),
                "extra_args": extra_args or {},
            }
        )

    def build_public_url(self, target, key):
        assert target == StorageTarget.AD_ASSETS
        return f"https://ads.example.com/{key}"


class FakeResponse:
    def __init__(self):
        self.content = b"logo-bytes"
        self.headers = {"content-type": "image/png"}

    def raise_for_status(self):
        return None


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.response = FakeResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url):
        return self.response


@pytest.mark.asyncio
async def test_logo_uploader_uses_ad_storage_target(monkeypatch):
    fake_storage = FakeMediaStorage()
    monkeypatch.setattr(logo_uploader, "_media_storage", fake_storage)
    monkeypatch.setattr(logo_uploader.httpx, "AsyncClient", FakeAsyncClient)

    result = await logo_uploader.download_and_upload_logo(
        photo_url="https://example.com/logo.png",
        business_name="Acme Photo Booth",
        city="Austin",
    )

    assert result is not None
    assert result.startswith("https://ads.example.com/scraped-vendors/")
    assert fake_storage.uploads[0]["target"] == StorageTarget.AD_ASSETS
    assert fake_storage.uploads[0]["extra_args"] == {"ContentType": "image/png"}
