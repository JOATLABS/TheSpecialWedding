from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from app.core.settings import settings
from app.services.ad_upload_service import AdUploadService
from app.services.blog_upload_service import BlogUploadService
from app.services.gallery_media_service import GalleryUploadService
from app.services.guest_media_service import GuestMediaStorage
from app.services.media_storage import MediaStorage, StorageTarget
from app.utils.upload_image import upload_image


R2_ACCOUNT_ID = "0123456789abcdef0123456789abcdef"


class FakeS3Client:
    def __init__(self, endpoint_url: str | None, *, list_error_code: str | None = None):
        self.meta = SimpleNamespace(endpoint_url=endpoint_url)
        self.uploads: list[dict] = []
        self.copies: list[dict] = []
        self.presigns: list[dict] = []
        self.gets: list[dict] = []
        self.list_error_code = list_error_code

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
        self.presigns.append(
            {
                "client_method": ClientMethod,
                "params": Params,
                "expires_in": ExpiresIn,
            }
        )
        return (
            f"{ClientMethod}:{Params['Bucket']}:{Params['Key']}:"
            f"{Params.get('ContentType', '')}:{ExpiresIn}"
        )

    def upload_fileobj(self, fileobj, bucket_name, key, ExtraArgs=None):
        self.uploads.append(
            {
                "bucket_name": bucket_name,
                "key": key,
                "extra_args": ExtraArgs or {},
                "payload": fileobj.read(),
            }
        )

    def list_objects_v2(self, **kwargs):
        if self.list_error_code:
            raise ClientError(
                {
                    "Error": {
                        "Code": self.list_error_code,
                        "Message": "Access denied",
                    }
                },
                "ListObjectsV2",
            )
        return {"Contents": [], "IsTruncated": False}

    def delete_object(self, **kwargs):
        return None

    def head_object(self, **kwargs):
        return {"ContentLength": 1}

    def get_object(self, **kwargs):
        self.gets.append(kwargs)
        return {"Body": SimpleNamespace(read=lambda: b"payload")}

    def copy_object(self, **kwargs):
        self.copies.append(kwargs)
        return None


def _install_fake_s3(monkeypatch, *, list_error_code: str | None = None):
    fake_client = FakeS3Client(
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        list_error_code=list_error_code,
    )
    MediaStorage._health_cache.clear()
    monkeypatch.setattr(
        "app.services.media_storage.boto3.client", lambda *args, **kwargs: fake_client
    )
    return fake_client


def _set_storage_settings(monkeypatch):
    monkeypatch.setattr(
        settings,
        "s3_endpoint_url",
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    )
    monkeypatch.setattr(settings, "s3_access_key_id", "test-access-key")
    monkeypatch.setattr(settings, "s3_secret_access_key", "test-secret-key")
    monkeypatch.setattr(settings, "s3_region", "auto")
    monkeypatch.setattr(settings, "s3_bucket_name", "gallery-bucket")
    monkeypatch.setattr(settings, "s3_guest_media_bucket_name", "guest-bucket")
    monkeypatch.setattr(settings, "s3_ad_bucket_name", "ad-bucket")
    monkeypatch.setattr(settings, "s3_blog_bucket_name", "blog-bucket")
    monkeypatch.setattr(
        settings,
        "s3_storefront_staging_bucket_name",
        "storefront-staging-bucket",
        raising=False,
    )
    monkeypatch.setattr(settings, "media_domain", "gallery.example.com")
    monkeypatch.setattr(settings, "guest_media_domain", "guest.example.com")
    monkeypatch.setattr(settings, "ad_media_domain", "ads.example.com")
    monkeypatch.setattr(settings, "blog_media_domain", "blog.example.com")


def test_media_storage_resolves_targets_without_cross_target_fallbacks(monkeypatch):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)

    storage = MediaStorage()

    assert storage.target(StorageTarget.PRIMARY).bucket_name == "gallery-bucket"
    assert (
        storage.target(StorageTarget.PRIMARY).public_domain
        == "https://gallery.example.com"
    )
    assert storage.target(StorageTarget.GUEST_MEDIA).bucket_name == "guest-bucket"
    assert (
        storage.target(StorageTarget.GUEST_MEDIA).public_domain
        == "https://guest.example.com"
    )
    assert storage.target(StorageTarget.AD_ASSETS).bucket_name == "ad-bucket"
    assert (
        storage.target(StorageTarget.AD_ASSETS).public_domain
        == "https://ads.example.com"
    )
    assert storage.target(StorageTarget.BLOG_ASSETS).bucket_name == "blog-bucket"
    assert (
        storage.target(StorageTarget.BLOG_ASSETS).public_domain
        == "https://blog.example.com"
    )
    storefront_staging = storage.target(StorageTarget.STOREFRONT_STAGING)
    assert storefront_staging.bucket_name == "storefront-staging-bucket"
    assert storefront_staging.public_domain is None
    with pytest.raises(RuntimeError, match="staging objects are private"):
        storage.build_public_url(
            StorageTarget.STOREFRONT_STAGING,
            "storefront/owner/_staging/upload.webp",
        )
    assert storage.allowed_public_hosts(
        StorageTarget.PRIMARY,
        StorageTarget.AD_ASSETS,
        StorageTarget.BLOG_ASSETS,
        StorageTarget.STOREFRONT_STAGING,
    ) == ["gallery.example.com", "ads.example.com", "blog.example.com"]

    guest_health = storage.target_health(StorageTarget.GUEST_MEDIA)
    assert guest_health.status == "ready"
    assert guest_health.issue is None


def test_gallery_ad_and_blog_services_use_target_buckets_and_public_urls(monkeypatch):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)

    gallery_service = GalleryUploadService()
    ad_service = AdUploadService()
    blog_service = BlogUploadService()

    assert gallery_service.bucket_name == "gallery-bucket"
    assert (
        gallery_service.build_public_url("gallery/test.jpg")
        == "https://gallery.example.com/gallery/test.jpg"
    )

    ad_upload = ad_service.create_presigned_upload_url(
        filename="creative.png",
        vendor_id="vendor-123",
        content_type="image/png",
    )
    assert ad_upload["upload_url"].startswith("put_object:ad-bucket:ads/vendor-123/")
    assert ad_upload["cdn_url"].startswith("https://ads.example.com/ads/vendor-123/")
    logo_upload = ad_service.create_presigned_upload_url(
        filename="logo.png",
        vendor_id="vendor-123",
        content_type="image/png",
        asset_kind="vendor_logo",
    )
    assert logo_upload["upload_url"].startswith(
        "put_object:ad-bucket:vendor-profiles/vendor-123/logo/"
    )
    assert logo_upload["cdn_url"].startswith(
        "https://ads.example.com/vendor-profiles/vendor-123/logo/"
    )

    blog_upload = blog_service.create_presigned_upload_url(
        filename="header.png",
        folder="knowledge-base",
        content_type="image/png",
    )
    assert blog_upload["upload_url"].startswith(
        "put_object:blog-bucket:knowledge-base/"
    )
    assert blog_upload["cdn_url"].startswith("https://blog.example.com/knowledge-base/")


def test_media_storage_copy_can_condition_on_the_validated_source_etag(monkeypatch):
    fake_client = _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)

    storage = MediaStorage()
    storage.copy_object(
        StorageTarget.BLOG_ASSETS,
        source_key="storefront/owner/_staging/upload.webp",
        destination_key="storefront/owner/hero/asset.webp",
        source_target=StorageTarget.STOREFRONT_STAGING,
        source_etag='"validated-etag"',
    )

    assert fake_client.copies == [
        {
            "Bucket": "blog-bucket",
            "CopySource": {
                "Bucket": "storefront-staging-bucket",
                "Key": "storefront/owner/_staging/upload.webp",
            },
            "CopySourceIfMatch": '"validated-etag"',
            "Key": "storefront/owner/hero/asset.webp",
        }
    ]


def test_media_storage_presigned_put_can_bind_declared_content_length(monkeypatch):
    fake_client = _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)

    storage = MediaStorage()
    storage.generate_presigned_put_url(
        StorageTarget.STOREFRONT_STAGING,
        key="storefront/owner/_staging/upload.webp",
        expires_in=300,
        content_type="image/webp",
        content_length=4096,
    )

    assert fake_client.presigns[-1]["params"] == {
        "Bucket": "storefront-staging-bucket",
        "Key": "storefront/owner/_staging/upload.webp",
        "ContentType": "image/webp",
        "ContentLength": 4096,
    }


def test_media_storage_get_can_bind_validated_source_etag(monkeypatch):
    fake_client = _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)

    storage = MediaStorage()
    payload = storage.get_object_bytes(
        StorageTarget.STOREFRONT_STAGING,
        "storefront/owner/_staging/upload.webp",
        source_etag='"validated-etag"',
    )

    assert payload == b"payload"
    assert fake_client.gets == [
        {
            "Bucket": "storefront-staging-bucket",
            "Key": "storefront/owner/_staging/upload.webp",
            "IfMatch": '"validated-etag"',
        }
    ]


def test_guest_media_storage_and_upload_image_use_centralized_targets(
    monkeypatch, tmp_path: Path
):
    fake_client = _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)

    guest_storage = GuestMediaStorage()
    upload_url = guest_storage.create_presigned_upload_url(
        key="guest-media/wedding/file.jpg",
        content_type="image/jpeg",
    )
    assert upload_url.startswith(
        "put_object:guest-bucket:guest-media/wedding/file.jpg:image/jpeg"
    )

    local_file = tmp_path / "sample.png"
    local_file.write_bytes(b"image-bytes")
    public_url = upload_image(str(local_file), folder="gallery")

    assert public_url.startswith("https://gallery.example.com/gallery/")
    assert fake_client.uploads[-1]["bucket_name"] == "gallery-bucket"


def test_media_storage_fails_closed_when_target_bucket_is_inaccessible(
    monkeypatch, tmp_path: Path
):
    _install_fake_s3(monkeypatch, list_error_code="AccessDenied")
    _set_storage_settings(monkeypatch)

    storage = MediaStorage()
    guest_health = storage.target_health(StorageTarget.GUEST_MEDIA)

    assert guest_health.status == "unavailable"
    assert "guest-bucket" in (guest_health.issue or "")
    assert "AccessDenied" in (guest_health.issue or "")

    guest_storage = GuestMediaStorage()
    assert guest_storage.is_configured is False
    assert guest_storage.status == "unavailable"
    assert "AccessDenied" in (guest_storage.issue or "")

    with pytest.raises(RuntimeError, match="AccessDenied"):
        storage.generate_presigned_put_url(
            StorageTarget.GUEST_MEDIA,
            key="guest-media/wedding/file.jpg",
            expires_in=300,
            content_type="image/jpeg",
        )

    with pytest.raises(RuntimeError, match="AccessDenied"):
        sample_file = tmp_path / "broken.png"
        sample_file.write_bytes(b"payload")
        upload_image(str(sample_file), folder="gallery")


@pytest.mark.asyncio
async def test_browser_upload_health_requires_put_cors_for_each_origin(monkeypatch):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_account_id", "account-id")
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")

    storage = MediaStorage()

    async def fake_fetch_bucket_cors_rules(bucket_name: str):
        assert bucket_name == "guest-bucket"
        return [
            {
                "allowed": {
                    "methods": ["PUT", "GET"],
                    "origins": ["http://localhost:3000"],
                    "headers": ["content-type"],
                }
            }
        ]

    monkeypatch.setattr(
        storage, "_fetch_bucket_cors_rules", fake_fetch_bucket_cors_rules
    )

    upload_health = await storage.browser_upload_health(
        StorageTarget.GUEST_MEDIA,
        ["http://localhost:3000", "https://staging.thespecialwedding.io"],
    )

    assert upload_health.status == "misconfigured"
    assert "https://staging.thespecialwedding.io" in (upload_health.issue or "")
    assert "Content-Type" in (upload_health.issue or "")


@pytest.mark.asyncio
async def test_browser_upload_health_accepts_wildcard_cors_headers(monkeypatch):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_account_id", "account-id")
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")

    storage = MediaStorage()

    async def fake_fetch_bucket_cors_rules(bucket_name: str):
        assert bucket_name == "blog-bucket"
        return [
            {
                "allowed": {
                    "methods": ["PUT"],
                    "origins": ["*"],
                    "headers": ["*"],
                }
            }
        ]

    monkeypatch.setattr(
        storage, "_fetch_bucket_cors_rules", fake_fetch_bucket_cors_rules
    )

    upload_health = await storage.browser_upload_health(
        StorageTarget.BLOG_ASSETS,
        ["http://localhost:3000"],
    )

    assert upload_health.status == "ready"
    assert upload_health.issue is None


@pytest.mark.asyncio
async def test_storefront_staging_privacy_requires_private_domains_and_expiry(
    monkeypatch,
):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_account_id", R2_ACCOUNT_ID)
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")
    storage = MediaStorage()
    responses = {
        "domains/managed": {"enabled": False},
        "domains/custom": {"domains": []},
        "lifecycle": {
            "rules": [
                {
                    "enabled": True,
                    "conditions": {"prefix": "storefront/"},
                    "deleteObjectsTransition": {
                        "condition": {"type": "Age", "maxAge": 86_400}
                    },
                }
            ]
        },
    }

    async def fake_fetch(
        bucket_name: str, suffix: str, *, account_id: str, jurisdiction: str
    ):
        assert bucket_name == "storefront-staging-bucket"
        assert account_id == R2_ACCOUNT_ID
        assert jurisdiction == "default"
        return responses[suffix]

    monkeypatch.setattr(storage, "_fetch_r2_bucket_control", fake_fetch)

    await storage.require_private_storefront_staging(force_refresh=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"domains/managed": {"enabled": True}}, "managed public access"),
        ({"domains/managed": {}}, "managed public access"),
        ({"domains/custom": {}}, "custom domain status"),
        ({"domains/custom": {"domains": None}}, "custom domain status"),
        (
            {
                "domains/custom": {
                    "domains": [{"domain": "public.example", "enabled": True}]
                }
            },
            "custom domain",
        ),
        (
            {"domains/custom": {"domains": [{"domain": "unknown.example"}]}},
            "custom domain",
        ),
        ({"domains/custom": {"domains": ["malformed"]}}, "custom domain"),
        ({"lifecycle": {"rules": []}}, "expiry lifecycle"),
    ],
)
async def test_storefront_staging_privacy_fails_closed_on_public_or_unbounded_bucket(
    monkeypatch, override, message
):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_account_id", R2_ACCOUNT_ID)
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")
    storage = MediaStorage()
    responses = {
        "domains/managed": {"enabled": False},
        "domains/custom": {"domains": []},
        "lifecycle": {
            "rules": [
                {
                    "enabled": True,
                    "conditions": {"prefix": "storefront/"},
                    "deleteObjectsTransition": {
                        "condition": {"type": "Age", "maxAge": 86_400}
                    },
                }
            ]
        },
        **override,
    }

    async def fake_fetch(
        _bucket_name: str,
        suffix: str,
        *,
        account_id: str,
        jurisdiction: str,
    ):
        assert account_id == R2_ACCOUNT_ID
        assert jurisdiction == "default"
        return responses[suffix]

    monkeypatch.setattr(storage, "_fetch_r2_bucket_control", fake_fetch)

    with pytest.raises(RuntimeError, match=message):
        await storage.require_private_storefront_staging(force_refresh=True)


@pytest.mark.asyncio
async def test_storefront_staging_privacy_fails_closed_when_status_is_unreadable(
    monkeypatch,
):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_account_id", R2_ACCOUNT_ID)
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")
    storage = MediaStorage()

    async def unreadable(
        _bucket_name: str,
        _suffix: str,
        *,
        account_id: str,
        jurisdiction: str,
    ):
        assert account_id == R2_ACCOUNT_ID
        assert jurisdiction == "default"
        raise RuntimeError("Cloudflare unavailable")

    monkeypatch.setattr(storage, "_fetch_r2_bucket_control", unreadable)

    with pytest.raises(RuntimeError, match="could not be verified"):
        await storage.require_private_storefront_staging(force_refresh=True)


@pytest.mark.parametrize(
    ("endpoint", "expected_jurisdiction"),
    [
        (f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com", "default"),
        (f"https://{R2_ACCOUNT_ID}.eu.r2.cloudflarestorage.com", "eu"),
        (f"https://{R2_ACCOUNT_ID}.fedramp.r2.cloudflarestorage.com", "fedramp"),
    ],
)
def test_r2_endpoint_identity_accepts_only_official_account_scoped_hosts(
    endpoint, expected_jurisdiction
):
    assert MediaStorage._parse_r2_endpoint_identity(endpoint) == (
        R2_ACCOUNT_ID,
        expected_jurisdiction,
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        f"http://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        f"https://user@{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com:443",
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com/path",
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com?query=1",
        f"https://{R2_ACCOUNT_ID}.unknown.r2.cloudflarestorage.com",
        "https://not-an-account.r2.cloudflarestorage.com",
        "https://storage.example.com",
        "not-a-url",
    ],
)
def test_r2_endpoint_identity_rejects_noncanonical_or_ambiguous_endpoints(endpoint):
    with pytest.raises(RuntimeError, match="official account-scoped R2 endpoint"):
        MediaStorage._parse_r2_endpoint_identity(endpoint)


@pytest.mark.asyncio
async def test_storefront_privacy_rejects_control_account_mismatch_before_api_calls(
    monkeypatch,
):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_account_id", "f" * 32)
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")
    storage = MediaStorage()
    calls = []

    async def should_not_fetch(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("control API must not be called for an account mismatch")

    monkeypatch.setattr(storage, "_fetch_r2_bucket_control", should_not_fetch)

    with pytest.raises(RuntimeError, match="same Cloudflare account"):
        await storage.require_private_storefront_staging(force_refresh=True)
    assert calls == []


@pytest.mark.asyncio
async def test_storefront_privacy_passes_jurisdiction_and_partitions_cache(
    monkeypatch,
):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_account_id", R2_ACCOUNT_ID)
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")
    monkeypatch.setattr(
        settings,
        "s3_endpoint_url",
        f"https://{R2_ACCOUNT_ID}.eu.r2.cloudflarestorage.com",
    )
    MediaStorage._storefront_privacy_cache.clear()
    storage = MediaStorage()
    calls = []
    responses = {
        "domains/managed": {"enabled": False},
        "domains/custom": {"domains": []},
        "lifecycle": {
            "rules": [
                {
                    "enabled": True,
                    "conditions": {"prefix": "storefront/"},
                    "deleteObjectsTransition": {
                        "condition": {"type": "Age", "maxAge": 86_400}
                    },
                }
            ]
        },
    }

    async def fake_fetch(
        bucket_name: str, suffix: str, *, account_id: str, jurisdiction: str
    ):
        calls.append((bucket_name, suffix, account_id, jurisdiction))
        return responses[suffix]

    monkeypatch.setattr(storage, "_fetch_r2_bucket_control", fake_fetch)

    await storage.require_private_storefront_staging(force_refresh=True)

    assert len(calls) == 3
    assert {call[3] for call in calls} == {"eu"}
    assert any(key[1] == "eu" for key in MediaStorage._storefront_privacy_cache)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("jurisdiction", "expected_header"),
    [("default", None), ("eu", "eu"), ("fedramp", "fedramp")],
)
async def test_r2_control_request_binds_jurisdiction_header(
    monkeypatch, jurisdiction, expected_header
):
    _install_fake_s3(monkeypatch)
    _set_storage_settings(monkeypatch)
    monkeypatch.setattr(settings, "cloudflare_api_token", "api-token")
    storage = MediaStorage()
    requests = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "result": {"enabled": False}}

    class FakeAsyncClient:
        def __init__(self, *, timeout):
            assert timeout == 10.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, *, headers):
            requests.append((url, headers))
            return FakeResponse()

    monkeypatch.setattr("app.services.media_storage.httpx.AsyncClient", FakeAsyncClient)

    await storage._fetch_r2_bucket_control(
        "storefront-staging-bucket",
        "domains/managed",
        account_id=R2_ACCOUNT_ID,
        jurisdiction=jurisdiction,
    )

    assert len(requests) == 1
    assert f"/accounts/{R2_ACCOUNT_ID}/" in requests[0][0]
    assert requests[0][1]["Authorization"] == "Bearer api-token"
    assert requests[0][1].get("cf-r2-jurisdiction") == expected_header
