"""
Tests for BlogUploadService.upload_from_url.

Covers the server-side image ingestion path that BabyLoveGrowth sync
uses to re-host hero images on our R2/CDN instead of depending on
third-party hosts at render time.

All tests stub httpx (via respx) and the MediaStorage upload path
(via monkeypatching) — no real network, no real R2.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from app.services.blog_upload_service import (
    ALLOWED_BLOG_IMAGE_TYPES,
    MAX_BLOG_IMAGE_SIZE_BYTES,
    BlogUploadFromUrlError,
    BlogUploadService,
)


# ─────────────────────────────────────── Test fixtures ───────────────────────


@pytest.fixture
def fake_storage(monkeypatch):
    """Replace MediaStorage with a mock so upload_fileobj is a no-op
    that records the call. Also stub build_public_url to a predictable
    CDN URL for assertion purposes.
    """
    captured: dict[str, Any] = {"uploads": []}

    def _fake_upload_fileobj(fileobj, target, key, extra_args=None):
        captured["uploads"].append(
            {
                "key": key,
                "target": target,
                "extra_args": extra_args or {},
                "body": fileobj.read(),
            }
        )

    mock_storage = MagicMock()
    mock_storage.upload_fileobj.side_effect = _fake_upload_fileobj
    mock_storage.target.return_value = MagicMock(bucket_name="test-blog-bucket")
    mock_storage.build_public_url.side_effect = lambda target, key: (
        f"https://cdn.test.example.com/{key}"
    )

    monkeypatch.setattr(
        "app.services.blog_upload_service.MediaStorage",
        lambda: mock_storage,
    )

    service = BlogUploadService()
    return service, captured


@pytest.fixture(autouse=True)
def public_dns_resolution(monkeypatch):
    """Keep SSRF DNS checks deterministic while respx owns the HTTP layer."""

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", port),
            )
        ]

    monkeypatch.setattr(
        "app.services.blog_upload_service.socket.getaddrinfo",
        _fake_getaddrinfo,
    )


def _img_bytes(size: int = 1024) -> bytes:
    """Just N bytes of payload — content-type validation looks at the
    response header, not magic bytes."""
    return b"\x89PNG\r\n\x1a\n" + b"x" * (size - 8)


# ──────────────────────────────────── Happy path ─────────────────────────────


@respx.mock
def test_happy_path_jpeg(fake_storage):
    service, captured = fake_storage
    url = "https://cdn.example.com/foo.jpg"
    body = _img_bytes(2048)

    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"content-type": "image/jpeg", "content-length": str(len(body))},
        )
    )

    result = asyncio.run(service.upload_from_url(url, folder="blog/synced/test"))

    assert result["key"].startswith("blog/synced/test/")
    assert result["key"].endswith("_foo.jpg")
    assert result["cdn_url"].startswith(
        "https://cdn.test.example.com/blog/synced/test/"
    )
    # Body was actually pushed to R2 with the right content-type
    assert len(captured["uploads"]) == 1
    upload = captured["uploads"][0]
    assert upload["body"] == body
    assert upload["extra_args"]["ContentType"] == "image/jpeg"


@respx.mock
def test_happy_path_png(fake_storage):
    service, _ = fake_storage
    url = "https://cdn.example.com/photo.png"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=_img_bytes(512),
            headers={"content-type": "image/png"},
        )
    )

    result = asyncio.run(service.upload_from_url(url))
    assert result["key"].endswith("_photo.png")


@respx.mock
def test_happy_path_webp(fake_storage):
    service, _ = fake_storage
    url = "https://cdn.example.com/banner.webp"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=_img_bytes(512),
            headers={"content-type": "image/webp"},
        )
    )

    result = asyncio.run(service.upload_from_url(url))
    assert result["key"].endswith("_banner.webp")


@respx.mock
def test_content_type_with_charset_parameter_is_accepted(fake_storage):
    """Some CDNs respond with `image/jpeg; charset=binary`. The
    parser must strip the parameters."""
    service, _ = fake_storage
    url = "https://cdn.example.com/foo.jpg"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=_img_bytes(256),
            headers={"content-type": "image/jpeg; charset=binary"},
        )
    )

    result = asyncio.run(service.upload_from_url(url))
    assert "blog/synced" in result["key"]


@respx.mock
def test_url_with_query_string_strips_query_from_basename(fake_storage):
    service, _ = fake_storage
    url = "https://cdn.example.com/foo.png?v=12345&t=abc"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=_img_bytes(256),
            headers={"content-type": "image/png"},
        )
    )

    result = asyncio.run(service.upload_from_url(url))
    # Basename in key must NOT contain the query string
    assert "?" not in result["key"]
    assert "v=12345" not in result["key"]
    assert result["key"].endswith("_foo.png")


@respx.mock
def test_url_with_no_extension_gets_extension_from_content_type(fake_storage):
    service, _ = fake_storage
    url = "https://cdn.example.com/static/random-id-no-ext"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=_img_bytes(256),
            headers={"content-type": "image/webp"},
        )
    )

    result = asyncio.run(service.upload_from_url(url))
    assert result["key"].endswith(".webp")


# ────────────────────────── Error paths — source HTTP failures ───────────────


@respx.mock
def test_404_raises_blog_upload_error(fake_storage):
    service, captured = fake_storage
    url = "https://cdn.example.com/missing.jpg"
    respx.get(url).mock(return_value=httpx.Response(404))

    with pytest.raises(BlogUploadFromUrlError, match="HTTP 404"):
        asyncio.run(service.upload_from_url(url))
    assert captured["uploads"] == []  # Nothing pushed to R2


@respx.mock
def test_500_raises_blog_upload_error(fake_storage):
    service, captured = fake_storage
    url = "https://cdn.example.com/server-blew-up.jpg"
    respx.get(url).mock(return_value=httpx.Response(500))

    with pytest.raises(BlogUploadFromUrlError, match="HTTP 500"):
        asyncio.run(service.upload_from_url(url))
    assert captured["uploads"] == []


@respx.mock
def test_connection_error_raises_blog_upload_error(fake_storage):
    service, captured = fake_storage
    url = "https://cdn.example.com/network-fail.jpg"
    respx.get(url).mock(side_effect=httpx.ConnectError("conn refused"))

    with pytest.raises(BlogUploadFromUrlError, match="HTTP error"):
        asyncio.run(service.upload_from_url(url))
    assert captured["uploads"] == []


@respx.mock
def test_timeout_raises_blog_upload_error(fake_storage):
    service, captured = fake_storage
    url = "https://cdn.example.com/slow.jpg"
    respx.get(url).mock(side_effect=httpx.ReadTimeout("too slow"))

    with pytest.raises(BlogUploadFromUrlError, match="HTTP error"):
        asyncio.run(service.upload_from_url(url, timeout_seconds=0.5))
    assert captured["uploads"] == []


# ────────────────────────── Error paths — content-type ───────────────────────


@respx.mock
def test_html_response_rejected(fake_storage):
    service, captured = fake_storage
    url = "https://cdn.example.com/not-an-image"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=b"<html><body>404</body></html>",
            headers={"content-type": "text/html"},
        )
    )

    with pytest.raises(BlogUploadFromUrlError, match="not in allowlist"):
        asyncio.run(service.upload_from_url(url))
    assert captured["uploads"] == []


@respx.mock
def test_gif_rejected(fake_storage):
    """GIF isn't in ALLOWED_BLOG_IMAGE_TYPES — should be rejected."""
    service, _ = fake_storage
    url = "https://cdn.example.com/anim.gif"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=b"GIF89a" + b"\x00" * 32,
            headers={"content-type": "image/gif"},
        )
    )

    with pytest.raises(BlogUploadFromUrlError, match="not in allowlist"):
        asyncio.run(service.upload_from_url(url))


@respx.mock
def test_svg_rejected(fake_storage):
    """SVG carries embedded scripts and is intentionally NOT in
    the allowlist. Verify rejection rather than silent acceptance."""
    service, _ = fake_storage
    url = "https://cdn.example.com/icon.svg"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=b"<svg></svg>",
            headers={"content-type": "image/svg+xml"},
        )
    )

    with pytest.raises(BlogUploadFromUrlError, match="not in allowlist"):
        asyncio.run(service.upload_from_url(url))


@respx.mock
def test_missing_content_type_rejected(fake_storage):
    service, _ = fake_storage
    url = "https://cdn.example.com/no-type.jpg"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=_img_bytes(256), headers={})
    )

    with pytest.raises(BlogUploadFromUrlError, match="not in allowlist"):
        asyncio.run(service.upload_from_url(url))


# ────────────────────────── Error paths — SSRF guard ─────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/private.png",
        "http://127.0.0.1/private.png",
        "http://10.0.0.5/private.png",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/private.png",
    ],
)
def test_private_or_non_http_source_urls_are_rejected_before_fetch(fake_storage, url):
    service, captured = fake_storage

    with pytest.raises(BlogUploadFromUrlError):
        asyncio.run(service.upload_from_url(url))

    assert captured["uploads"] == []


@respx.mock
def test_redirect_to_private_address_is_rejected_before_followup_request(fake_storage):
    service, captured = fake_storage
    source_url = "https://cdn.example.com/redirect"
    private_url = "http://127.0.0.1/private.png"
    respx.get(source_url).mock(
        return_value=httpx.Response(302, headers={"location": private_url})
    )
    private_route = respx.get(private_url).mock(
        return_value=httpx.Response(
            200,
            content=_img_bytes(256),
            headers={"content-type": "image/png"},
        )
    )

    with pytest.raises(BlogUploadFromUrlError, match="non-public|not allowed"):
        asyncio.run(service.upload_from_url(source_url))

    assert captured["uploads"] == []
    assert not private_route.called


def test_private_dns_resolution_is_rejected(fake_storage, monkeypatch):
    service, captured = fake_storage

    def _private_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", port))]

    monkeypatch.setattr(
        "app.services.blog_upload_service.socket.getaddrinfo",
        _private_getaddrinfo,
    )

    with pytest.raises(BlogUploadFromUrlError, match="non-public"):
        asyncio.run(service.upload_from_url("https://cdn.example.com/private.png"))

    assert captured["uploads"] == []


# ────────────────────────── Error paths — size cap ───────────────────────────


@respx.mock
def test_oversized_via_declared_content_length(fake_storage):
    service, captured = fake_storage
    url = "https://cdn.example.com/huge.jpg"
    oversized = MAX_BLOG_IMAGE_SIZE_BYTES + 1
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=b"\x00",  # The actual body is small; the header lies
            headers={
                "content-type": "image/jpeg",
                "content-length": str(oversized),
            },
        )
    )

    with pytest.raises(BlogUploadFromUrlError, match="Declared content-length"):
        asyncio.run(service.upload_from_url(url))
    assert captured["uploads"] == []


@respx.mock
def test_oversized_via_streamed_size(fake_storage):
    """If the server lies about content-length (declares small but
    sends large), the running size check during streaming must still
    abort. This protects against chunked transfer responses and
    deliberately deceptive servers.

    Forces this via a content-length header that under-reports the
    actual body size, so the early-pre-check passes but the streaming
    tally catches it. max_bytes=1024 keeps the fixture small.
    """
    service, captured = fake_storage
    url = "https://cdn.example.com/sneaky.jpg"
    body = b"x" * 10_000

    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=body,
            # Lie: declare 512 (under cap), actually send 10000 (over cap).
            headers={"content-type": "image/jpeg", "content-length": "512"},
        )
    )

    with pytest.raises(BlogUploadFromUrlError, match="Streamed size exceeded"):
        asyncio.run(service.upload_from_url(url, max_bytes=1024))
    assert captured["uploads"] == []


# ────────────────────────── R2 layer failures ────────────────────────────────


@respx.mock
def test_r2_not_configured_raises_blog_upload_error(monkeypatch):
    """If S3_BLOG_BUCKET_NAME is unset, MediaStorage.upload_fileobj
    raises RuntimeError via require_target. That must surface as our
    domain error so the sync caller can degrade gracefully."""
    mock_storage = MagicMock()
    mock_storage.upload_fileobj.side_effect = RuntimeError(
        "Storage target 'blog_assets' is not available."
    )
    mock_storage.target.return_value = MagicMock(bucket_name=None)
    mock_storage.build_public_url.return_value = "https://cdn/example"

    monkeypatch.setattr(
        "app.services.blog_upload_service.MediaStorage",
        lambda: mock_storage,
    )

    service = BlogUploadService()
    url = "https://cdn.example.com/foo.jpg"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=_img_bytes(256),
            headers={"content-type": "image/jpeg"},
        )
    )

    with pytest.raises(BlogUploadFromUrlError, match="BLOG_ASSETS not configured"):
        asyncio.run(service.upload_from_url(url))


# ────────────────────────── Allowlist contract ───────────────────────────────


def test_allowlist_contains_expected_types():
    """Lock the public contract down — if anyone widens or narrows
    this set, they have to update this test deliberately."""
    assert ALLOWED_BLOG_IMAGE_TYPES == {"image/jpeg", "image/png", "image/webp"}


def test_size_cap_is_5mb():
    assert MAX_BLOG_IMAGE_SIZE_BYTES == 5 * 1024 * 1024
