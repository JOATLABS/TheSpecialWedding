import asyncio
import json

from starlette.requests import Request

from app.middleware.rate_limiting import RateLimitMiddleware


async def _dummy_app(scope, receive, send):
    return None


def build_middleware(
    *,
    calls: int = 500,
    period: int = 60,
    auth_calls: int = 20,
    auth_period: int = 60,
    login_ip_calls: int = 30,
    login_principal_calls: int = 5,
    login_period: int = 60,
) -> RateLimitMiddleware:
    return RateLimitMiddleware(
        _dummy_app,
        calls=calls,
        period=period,
        auth_calls=auth_calls,
        auth_period=auth_period,
        login_ip_calls=login_ip_calls,
        login_principal_calls=login_principal_calls,
        login_period=login_period,
    )


def build_request(path: str, payload: dict[str, str] | None = None) -> Request:
    body = json.dumps(payload or {}).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope, receive)


def test_public_and_authenticated_route_families_use_distinct_rate_limit_buckets():
    middleware = build_middleware()

    public_metadata = middleware._get_rate_limit_config("/weddings/privacy-info/james-and-mel")
    public_gallery = middleware._get_rate_limit_config("/gallery")
    admin_api = middleware._get_rate_limit_config("/admin/planner/weddings")
    couple_api = middleware._get_rate_limit_config("/couple/portal/dashboard")
    fallback_api = middleware._get_rate_limit_config("/healthz/custom")

    assert public_metadata == ("public_wedding_metadata", 500, 60, False)
    assert public_gallery == ("public_gallery", 500, 60, False)
    assert admin_api == ("admin_api", 500, 60, False)
    assert couple_api == ("couple_api", 500, 60, False)
    assert fallback_api == ("api", 500, 60, False)


def test_dynamic_guest_verification_paths_use_the_auth_bucket():
    middleware = build_middleware(auth_calls=12, auth_period=90)

    guest_verify = middleware._get_rate_limit_config("/weddings/verify-guest-access/james-and-mel")
    guest_session = middleware._get_rate_limit_config("/weddings/guest-access/session/james-and-mel")

    assert guest_verify == ("guest_access", 12, 90, True)
    assert guest_session == ("guest_access_session", 500, 60, False)


def test_exact_auth_routes_still_override_route_family_defaults():
    middleware = build_middleware(auth_calls=20, auth_period=60, login_ip_calls=30, login_principal_calls=5)

    admin_login = middleware._get_rate_limit_config("/admin/token")
    couple_login = middleware._get_rate_limit_config("/couple/login")
    admin_refresh = middleware._get_rate_limit_config("/admin/token/refresh")

    assert admin_login == ("admin_login_identity", 5, 60, True)
    assert couple_login == ("couple_login_identity", 5, 60, True)
    assert admin_refresh == ("admin_token_refresh", 40, 60, True)


def test_login_routes_apply_ip_backstop_in_addition_to_identity_bucket():
    middleware = build_middleware(login_ip_calls=30, login_principal_calls=5, login_period=60)

    assert middleware._get_additional_rate_limit_configs("/admin/token") == [
        ("admin_login_ip", 30, 60, True)
    ]
    assert middleware._get_additional_rate_limit_configs("/couple/login") == [
        ("couple_login_ip", 30, 60, True)
    ]


def test_login_identity_bucket_uses_email_subject_when_available():
    middleware = build_middleware()
    request = build_request("/admin/token", {"email": "Planner@Example.com", "password": "secret"})

    subject = asyncio.run(middleware._get_bucket_subject(request, "admin_login_identity", "127.0.0.1"))

    assert subject == "planner@example.com"
