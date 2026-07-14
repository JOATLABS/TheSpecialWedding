from __future__ import annotations

import ast
import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testbed.verify_marketing_capture_workspace import (  # noqa: E402
    assert_setup_namespace_available,
)
from testbed import verify_marketing_capture_workspace as marketing_capture_driver  # noqa: E402
from testbed.cleanup_marketing_capture_workspace_state import (  # noqa: E402
    PLANNER_EMAIL,
    SEED_SCOPE,
    SEED_SOURCE,
    _capture_namespace_is_owned,
    _owned_identity_filter,
)
from testbed import testbed as testbed_cli  # noqa: E402


SEEDER = ROOT / "scripts" / "demo-videos" / "seed-demo-video-workspace.py"
DRIVER = ROOT / "testbed" / "verify_marketing_capture_workspace.py"
CLEANUP = ROOT / "testbed" / "cleanup_marketing_capture_workspace_state.py"
TESTBED_CLI = ROOT / "testbed" / "testbed.py"
PACKAGE_MANIFEST = ROOT / "package.json"
SEED_SOURCES = ROOT / "app" / "constants" / "seed_sources.py"
MARKETING_CAPTURE_MEDIA = ROOT / "app" / "constants" / "marketing_capture_media.py"
GALLERY_API = ROOT / "app" / "api" / "gallery_public.py"
GALLERY_ADMIN_API = ROOT / "app" / "api" / "gallery_admin.py"
GUEST_MEDIA_SERVICE = ROOT / "app" / "services" / "guest_media_service.py"
EXPECTED_CAPTURE_BUILD = "a" * 40


def _gallery_fixture_bytes(path: str) -> bytes:
    return (ROOT / "public" / path.removeprefix("/")).read_bytes()


def _resized_webp_bytes(path: str, size: tuple[int, int]) -> bytes:
    output = BytesIO()
    with Image.open(ROOT / "public" / path.removeprefix("/")) as image:
        image.resize(size).save(output, format="WEBP")
    return output.getvalue()


def _required_text(path: Path) -> str:
    assert path.exists(), (
        f"required marketing-capture file is missing: {path.relative_to(ROOT)}"
    )
    return path.read_text()


def _capture_app_shell(*, scripts: tuple[str, ...] = ()) -> str:
    script_tags = "".join(f'<script src="{source}"></script>' for source in scripts)
    return (
        '<html><head><meta name="tsw-app-build-commit" '
        f'content="{EXPECTED_CAPTURE_BUILD}">{script_tags}</head></html>'
    )


def _capture_readiness_payload(url: str):
    if url.endswith("/api/proxy/couple/profile"):
        return {
            "id": marketing_capture_driver.COUPLE_ID,
            "email": marketing_capture_driver.COUPLE_EMAIL,
            "partner1_name": "Sofia",
            "partner2_name": "Daniel",
            "wedding_id": marketing_capture_driver.PRIMARY_WEDDING_ID,
        }
    if url.endswith("/api/proxy/couple/portal/dashboard"):
        return {
            "archived": False,
            "wedding": {
                "id": marketing_capture_driver.PRIMARY_WEDDING_ID,
                "couple_names": "Sofia & Daniel",
            },
            "guest_stats": {"guest_list_total": 24},
        }
    if url.endswith("/api/proxy/admin/profile"):
        return {
            "id": marketing_capture_driver.PLANNER_USER_ID,
            "email": marketing_capture_driver.PLANNER_EMAIL,
            "company_name": "Marigold & Co. Weddings",
        }
    if url.endswith("/api/proxy/admin/planner/weddings"):
        return [
            {
                "_id": marketing_capture_driver.PRIMARY_WEDDING_ID,
                "slug": marketing_capture_driver.PRIMARY_SLUG,
                "couple_names": "Sofia & Daniel",
                "venue": "The Glasshouse at Riverbend",
            },
            {
                "_id": marketing_capture_driver.SECONDARY_WEDDING_ID,
                "slug": marketing_capture_driver.SECONDARY_SLUG,
                "couple_names": "Avery & Morgan",
                "venue": "",
            },
        ]
    if url.endswith("/api/proxy/admin/gallery/list"):
        return marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ITEMS
    if url.endswith("/api/proxy/couple-portal/conversations"):
        return {
            "conversations": [
                {
                    "id": marketing_capture_driver.COUPLE_ID,
                    "email": marketing_capture_driver.COUPLE_EMAIL,
                    "partner1_name": "Sofia",
                    "partner2_name": "Daniel",
                    "wedding_id": marketing_capture_driver.PRIMARY_WEDDING_ID,
                }
            ],
            "count": 1,
        }
    if url.endswith(
        f"/api/proxy/admin/weddings/{marketing_capture_driver.PRIMARY_WEDDING_ID}/budget"
    ):
        return {
            "wedding_id": marketing_capture_driver.PRIMARY_WEDDING_ID,
            "summary": {"total_budget": 82_500.0},
        }
    if url.endswith("/api/proxy/admin/forms/form_marketing_capture_couple_intake"):
        return {
            "id": "form_marketing_capture_couple_intake",
            "wedding_id": marketing_capture_driver.PRIMARY_WEDDING_ID,
            "name": "Couple Intake Questionnaire",
        }
    if url.endswith("/api/proxy/admin/team/members"):
        return {
            "members": [
                {
                    "id": marketing_capture_driver.TEAM_MEMBER_ID,
                    "owner_id": marketing_capture_driver.PLANNER_USER_ID,
                    "owner_email": marketing_capture_driver.PLANNER_EMAIL,
                    "user_id": marketing_capture_driver.TEAM_USER_ID,
                    "email": marketing_capture_driver.TEAM_EMAIL,
                    "first_name": "Maya",
                    "last_name": "Thompson",
                    "status": "active",
                    "role": "editor",
                    "wedding_access": "assigned",
                    "assigned_wedding_ids": [
                        marketing_capture_driver.PRIMARY_WEDDING_ID
                    ],
                }
            ],
            "total": 1,
            "skip": 0,
            "limit": 50,
        }
    if url.endswith("/api/proxy/admin/team/seats"):
        return {
            "total_seats": 5,
            "used_seats": 1,
            "available_seats": 4,
            "members_by_status": {"active": 1},
        }
    raise AssertionError(f"unexpected readiness URL {url}")


def _planner_team_scene() -> dict:
    return {
        "featureId": "team",
        "session": "planner",
        "route": "/admin/planner/team",
        "title": "Team management",
        "expectation": "The seeded team is visible.",
        "expectedVisibleText": "Team Management",
        "safeInteraction": None,
    }


def _planner_static_scene() -> dict:
    return {
        "featureId": "vendor-network",
        "session": "planner",
        "route": "/admin/vendors",
        "title": "Vendor network",
        "expectation": "The seeded vendor network is visible.",
        "expectedVisibleText": "Vendor Management",
        "safeInteraction": None,
    }


def _async_function(source: str, name: str) -> ast.AsyncFunctionDef:
    module = ast.parse(source)
    function = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == name
        ),
        None,
    )
    assert function is not None, f"missing async function: {name}"
    return function


def _dict_keys(node: ast.AST) -> set[str]:
    assert isinstance(node, ast.Dict)
    return {
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _load_seeder_module():
    spec = importlib.util.spec_from_file_location(
        "marketing_capture_workspace_seeder_contract", SEEDER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assigned_dicts(function: ast.AsyncFunctionDef) -> dict[str, ast.Dict]:
    assigned: dict[str, ast.Dict] = {}
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                assigned[target.id] = value
    return assigned


def test_marketing_capture_driver_and_cleanup_are_paired():
    _required_text(DRIVER)
    _required_text(CLEANUP)


def test_marketing_capture_driver_never_follows_http_redirects_automatically():
    module = ast.parse(_required_text(DRIVER))
    request_calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "requests"
        and node.func.attr in {"get", "post"}
    ]

    assert request_calls
    for call in request_calls:
        explicit_false = any(
            keyword.arg == "allow_redirects"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is False
            for keyword in call.keywords
        )
        guarded_request_kwargs = any(
            keyword.arg is None
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "request_kwargs"
            for keyword in call.keywords
        )
        assert explicit_false or guarded_request_kwargs, (
            f"requests.{call.func.attr} at line {call.lineno} can follow a redirect"
        )


def test_demo_seed_runs_the_dedicated_verified_marketing_workspace_driver():
    testbed_source = _required_text(TESTBED_CLI)
    package_source = _required_text(PACKAGE_MANIFEST)

    assert "testbed/verify_marketing_capture_workspace.py" not in testbed_source
    demo_seed_command = package_source.split('"demo:seed"', 1)[1].split("\n", 1)[0]
    assert "testbed/verify_marketing_capture_workspace.py" in demo_seed_command
    assert "scripts/demo-videos/seed-demo-video-workspace.py" not in demo_seed_command


def test_testbed_service_status_checks_process_and_http_readiness():
    testbed_source = _required_text(TESTBED_CLI)

    assert "pane_process_names" in testbed_source
    assert "service_is_ready" in testbed_source
    assert "/health/readyz" in testbed_source
    assert "failed readiness" in testbed_source


def test_testbed_frontend_process_uses_the_same_canonical_origin_as_readiness():
    cfg = SimpleNamespace(
        backend_port=8000,
        frontend_port=3100,
        frontend_origin="http://127.0.0.1:3100",
        frontend_cmd="npm run start -- --hostname 127.0.0.1",
        frontend_node_env="production",
        google_maps_api_key="",
    )

    command = testbed_cli.build_frontend_cmd(cfg)

    assert "NODE_ENV=production" in command
    assert "FRONTEND_URL=http://127.0.0.1:3100" in command
    assert "BACKEND_SERVICE_URL=http://127.0.0.1:8000" in command
    assert "INTERNAL_API_BASE_URL=http://127.0.0.1:8000" in command
    assert "GOOGLE_MAPS_API_KEY=''" in command
    assert "PORT=3100" in command


def test_marketing_capture_verifier_requires_the_canonical_running_capture_stack(
    monkeypatch,
):
    runtime_verifier = getattr(
        marketing_capture_driver,
        "verify_frontend_capture_runtime",
        None,
    )
    assert callable(runtime_verifier), (
        "the standalone capture verifier must prove the running Next/Node runtime"
    )
    observed: dict = {}

    def _not_ready(cfg, window):
        observed["session_name"] = cfg.session_name
        observed["frontend_origin"] = cfg.frontend_origin
        observed["frontend_node_env"] = cfg.frontend_node_env
        observed["window"] = window
        return False

    monkeypatch.setattr(testbed_cli, "service_is_ready", _not_ready)

    with pytest.raises(RuntimeError, match="Next start under Node 22"):
        runtime_verifier("http://127.0.0.1:3100")

    assert observed == {
        "session_name": "marketing-capture",
        "frontend_origin": "http://127.0.0.1:3100",
        "frontend_node_env": None,
        "window": testbed_cli.FRONTEND_WINDOW,
    }


def test_testbed_frontend_does_not_override_optional_environment_by_default():
    cfg = SimpleNamespace(
        backend_port=8000,
        frontend_port=3000,
        frontend_origin="http://127.0.0.1:3000",
        frontend_cmd="npm run dev",
        frontend_node_env="",
        google_maps_api_key=None,
    )

    command = testbed_cli.build_frontend_cmd(cfg)

    assert "NODE_ENV=" not in command
    assert "GOOGLE_MAPS_API_KEY=" not in command
    assert "FRONTEND_URL=http://127.0.0.1:3000" in command
    assert "BACKEND_SERVICE_URL=http://127.0.0.1:8000" in command
    assert "INTERNAL_API_BASE_URL=http://127.0.0.1:8000" in command
    assert "PORT=3000" in command


def test_testbed_backend_uses_the_canonical_frontend_origin_for_media_redirects():
    cfg = SimpleNamespace(
        backend_port=8000,
        frontend_origin="http://127.0.0.1:3100",
        python_bin="/capture/python",
        uvicorn_app="app.main:app",
        uvicorn_args="",
    )

    command = testbed_cli.build_backend_cmd(cfg)

    assert "FRONTEND_URL=http://127.0.0.1:3100" in command
    assert "--port 8000" in command


def test_marketing_capture_preflights_every_frontend_checkpoint(monkeypatch):
    requests_made: list[tuple[str, dict]] = []
    planner_token = "seeded-planner-jwt"
    couple_token = "seeded-couple-jwt"
    scenes = marketing_capture_driver.MARKETING_CAPTURE_E2E_CHECKPOINTS
    stable_text_by_route: dict[str, list[str]] = {}
    for scene in scenes:
        stable_text_by_route.setdefault(scene["route"], []).append(
            scene["expectedVisibleText"]
        )

    def _reachable(url, **kwargs):
        requests_made.append((url, kwargs))
        if "/api/proxy/" in url:
            payload = _capture_readiness_payload(url)
            return SimpleNamespace(
                status_code=200,
                headers={},
                text="readiness payload",
                json=lambda: payload,
            )
        if "/admin/" in url and kwargs.get("cookies") != {"admin_token": planner_token}:
            return SimpleNamespace(
                status_code=307,
                headers={"location": "/admin/login"},
                text="redirect",
            )
        return SimpleNamespace(
            status_code=200,
            headers={},
            text=(
                '<html><head><meta name="tsw-app-build-commit" '
                f'content="{EXPECTED_CAPTURE_BUILD}"></head><body>'
                + " ".join(
                    stable_text_by_route[url.removeprefix("http://127.0.0.1:3100")]
                )
                + "</body></html>"
            ),
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _reachable)

    marketing_capture_driver.verify_frontend_checkpoint_routes(
        "http://127.0.0.1:3100",
        EXPECTED_CAPTURE_BUILD,
        planner_token=planner_token,
        couple_token=couple_token,
    )

    expected_routes = [scene["route"] for scene in scenes]
    route_requests = [
        (url, kwargs) for url, kwargs in requests_made if "/api/proxy/" not in url
    ]
    assert len(marketing_capture_driver.MARKETING_CAPTURE_E2E_CHECKPOINTS) == 17
    assert [url for url, _kwargs in route_requests] == [
        f"http://127.0.0.1:3100{route}" for route in expected_routes
    ]
    for scene, (_url, kwargs) in zip(scenes, route_requests, strict=True):
        assert kwargs["allow_redirects"] is False
        assert kwargs["timeout"] == 15
        if scene["session"] == "planner":
            assert kwargs["cookies"] == {"admin_token": planner_token}
            assert "headers" not in kwargs
        elif scene["session"] == "couple":
            assert kwargs["cookies"] == {"couple_token": couple_token}
            assert "headers" not in kwargs
        else:
            assert "cookies" not in kwargs
            assert "headers" not in kwargs


def test_marketing_capture_checkpoint_rejects_generic_shell_without_stable_text(
    monkeypatch,
):
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_static_scene(),),
    )
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            headers={},
            text=_capture_app_shell(),
        ),
    )

    with pytest.raises(RuntimeError, match="stable visible text.*Vendor Management"):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://127.0.0.1:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="seeded-planner-jwt",
            couple_token="seeded-couple-jwt",
        )


def test_marketing_capture_checkpoint_reads_stable_text_from_served_route_bundle(
    monkeypatch,
):
    route = "/admin/vendors"
    script_path = "/_next/static/chunks/app/admin/vendors/page-demo.js"
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_static_scene(),),
    )

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        if url == f"http://127.0.0.1:3100{route}":
            return SimpleNamespace(
                status_code=200,
                headers={},
                text=_capture_app_shell(scripts=(script_path,)),
            )
        if url == f"http://127.0.0.1:3100{script_path}":
            return SimpleNamespace(
                status_code=200,
                headers={"content-type": "application/javascript"},
                text='self.__next_f.push(["Vendor Management"]);',
            )
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    marketing_capture_driver.verify_frontend_checkpoint_routes(
        "http://127.0.0.1:3100",
        EXPECTED_CAPTURE_BUILD,
        planner_token="seeded-planner-jwt",
        couple_token="seeded-couple-jwt",
    )

    assert [url for url, _kwargs in calls] == [
        f"http://127.0.0.1:3100{route}",
        f"http://127.0.0.1:3100{script_path}",
    ]
    assert all(
        kwargs["allow_redirects"] is False and kwargs["timeout"] == 15
        for _url, kwargs in calls
    )


def test_marketing_capture_team_checkpoint_proves_exact_seeded_member_and_seats(
    monkeypatch,
):
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_team_scene(),),
    )

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        if "/api/proxy/" in url:
            payload = _capture_readiness_payload(url)
            return SimpleNamespace(
                status_code=200,
                headers={},
                text="capture readiness payload",
                json=lambda: payload,
            )
        return SimpleNamespace(
            status_code=200,
            headers={},
            text=_capture_app_shell(),
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    marketing_capture_driver.verify_frontend_checkpoint_routes(
        "http://127.0.0.1:3100",
        EXPECTED_CAPTURE_BUILD,
        planner_token="seeded-planner-jwt",
        couple_token="seeded-couple-jwt",
    )

    members_call = next(item for item in calls if item[0].endswith("/team/members"))
    assert members_call[1]["headers"] == {"Authorization": "Bearer seeded-planner-jwt"}
    assert members_call[1]["params"] == {"skip": 0, "limit": 50}
    seats_call = next(item for item in calls if item[0].endswith("/team/seats"))
    assert seats_call[1]["headers"] == {"Authorization": "Bearer seeded-planner-jwt"}
    route_call = next(item for item in calls if item[0].endswith("/admin/planner/team"))
    assert route_call[1]["cookies"] == {"admin_token": "seeded-planner-jwt"}


@pytest.mark.parametrize(
    ("corrupt_endpoint", "expected_error"),
    [
        ("/team/members", "wrong seeded member"),
        ("/team/seats", "wrong seeded usage"),
    ],
)
def test_marketing_capture_team_checkpoint_rejects_wrong_seeded_state(
    monkeypatch,
    corrupt_endpoint,
    expected_error,
):
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_team_scene(),),
    )

    def _get(url, **_kwargs):
        if "/api/proxy/" in url:
            payload = _capture_readiness_payload(url)
            if url.endswith(corrupt_endpoint):
                if corrupt_endpoint == "/team/members":
                    payload["members"][0]["owner_id"] = "another-tenant"
                else:
                    payload["used_seats"] = 2
            return SimpleNamespace(
                status_code=200,
                headers={},
                text="capture readiness payload",
                json=lambda: payload,
            )
        return SimpleNamespace(
            status_code=200,
            headers={},
            text=_capture_app_shell(),
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    with pytest.raises(RuntimeError, match=expected_error):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://127.0.0.1:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="seeded-planner-jwt",
            couple_token="seeded-couple-jwt",
        )


def test_marketing_capture_couple_checkpoint_proves_exact_cookie_session(
    monkeypatch,
):
    route = "/couple/dashboard"
    profile_url = "http://127.0.0.1:3100/api/proxy/couple/profile"
    dashboard_url = "http://127.0.0.1:3100/api/proxy/couple/portal/dashboard"
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (
            {
                "featureId": "couple-portal",
                "session": "couple",
                "route": route,
                "title": "Couple portal",
                "expectation": "The seeded couple dashboard is populated.",
                "expectedVisibleText": "24 guests added so far",
                "safeInteraction": None,
            },
        ),
    )

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        if url == f"http://127.0.0.1:3100{route}":
            return SimpleNamespace(
                status_code=200,
                headers={},
                text=_capture_app_shell(),
            )
        if url == profile_url:
            return SimpleNamespace(
                status_code=200,
                headers={},
                text="couple profile",
                json=lambda: {
                    "id": marketing_capture_driver.COUPLE_ID,
                    "email": marketing_capture_driver.COUPLE_EMAIL,
                    "partner1_name": "Sofia",
                    "partner2_name": "Daniel",
                    "wedding_id": marketing_capture_driver.PRIMARY_WEDDING_ID,
                },
            )
        if url == dashboard_url:
            return SimpleNamespace(
                status_code=200,
                headers={},
                text="couple dashboard",
                json=lambda: {
                    "wedding": {
                        "id": marketing_capture_driver.PRIMARY_WEDDING_ID,
                        "couple_names": "Sofia & Daniel",
                    },
                    "guest_stats": {"guest_list_total": 24},
                },
            )
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    marketing_capture_driver.verify_frontend_checkpoint_routes(
        "http://127.0.0.1:3100",
        EXPECTED_CAPTURE_BUILD,
        planner_token="seeded-planner-jwt",
        couple_token="seeded-couple-jwt",
    )

    assert [url for url, _kwargs in calls] == [
        profile_url,
        dashboard_url,
        f"http://127.0.0.1:3100{route}",
    ]
    for _url, kwargs in calls:
        assert kwargs["cookies"] == {"couple_token": "seeded-couple-jwt"}
        assert "headers" not in kwargs
        assert kwargs["allow_redirects"] is False


def test_marketing_capture_couple_checkpoint_rejects_wrong_session_identity(
    monkeypatch,
):
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (
            {
                "featureId": "couple-portal",
                "session": "couple",
                "route": "/couple/dashboard",
                "title": "Couple portal",
                "expectation": "The seeded couple dashboard is populated.",
                "expectedVisibleText": "24 guests added so far",
                "safeInteraction": None,
            },
        ),
    )

    def _get(url, **_kwargs):
        if url.endswith("/api/proxy/couple/profile"):
            return SimpleNamespace(
                status_code=200,
                headers={},
                text="wrong couple profile",
                json=lambda: {
                    "id": "couple_from_another_wedding",
                    "email": "other@couples.thespecialwedding.io",
                    "wedding_id": "wedding_from_another_tenant",
                },
            )
        return SimpleNamespace(
            status_code=200,
            headers={},
            text=_capture_app_shell(),
            json=lambda: {},
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    with pytest.raises(RuntimeError, match="wrong seeded couple session"):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://127.0.0.1:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="seeded-planner-jwt",
            couple_token="wrong-couple-jwt",
        )


def test_marketing_capture_admin_checkpoint_reproduces_307_without_cookie(
    monkeypatch,
):
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_static_scene(),),
    )

    def _proxy_like_response(url, **kwargs):
        if "/admin/" in url and "admin_token" not in kwargs.get("cookies", {}):
            return SimpleNamespace(
                status_code=307,
                headers={"location": "/admin/login"},
                text="redirect",
            )
        return SimpleNamespace(
            status_code=200,
            headers={},
            text=(
                f'<meta name="tsw-app-build-commit" content="{EXPECTED_CAPTURE_BUILD}">'  # noqa: E501
                "Vendor Management"
            ),
        )

    assert (
        _proxy_like_response(
            "http://127.0.0.1:3100/admin/vendors",
            allow_redirects=False,
        ).status_code
        == 307
    )
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        _proxy_like_response,
    )
    marketing_capture_driver.verify_frontend_checkpoint_routes(
        "http://127.0.0.1:3100",
        EXPECTED_CAPTURE_BUILD,
        planner_token="real-seeded-planner-token",
        couple_token="real-seeded-couple-token",
    )


def test_marketing_capture_frontend_preflight_rejects_a_404(monkeypatch):
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_static_scene(),),
    )
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=404,
            headers={},
            text="not found",
        ),
    )

    with pytest.raises(RuntimeError, match="Frontend checkpoint returned HTTP 404"):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://127.0.0.1:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="seeded-planner-jwt",
            couple_token="seeded-couple-jwt",
        )


def test_marketing_capture_frontend_preflight_rejects_redirects(monkeypatch):
    observed_kwargs: dict = {}
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_static_scene(),),
    )

    def _redirect(_url, **kwargs):
        observed_kwargs.update(kwargs)
        return SimpleNamespace(
            status_code=307,
            headers={"Location": "/login"},
            text="redirect",
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _redirect)

    with pytest.raises(RuntimeError, match="Frontend checkpoint returned HTTP 307"):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://127.0.0.1:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="seeded-planner-jwt",
            couple_token="seeded-couple-jwt",
        )

    assert observed_kwargs["allow_redirects"] is False


def test_marketing_capture_frontend_preflight_rejects_location_on_200(monkeypatch):
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_static_scene(),),
    )
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            headers={"location": "/login"},
            text=(
                f'<meta name="tsw-app-build-commit" content="{EXPECTED_CAPTURE_BUILD}">'
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="unexpectedly redirected to /login"):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://127.0.0.1:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="seeded-planner-jwt",
            couple_token="seeded-couple-jwt",
        )


def test_marketing_capture_frontend_preflight_rejects_stale_build(monkeypatch):
    stale_build = "b" * 40
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (_planner_static_scene(),),
    )
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            headers={},
            text=(f'<meta name="tsw-app-build-commit" content="{stale_build}">'),
        ),
    )

    with pytest.raises(RuntimeError, match="served the wrong app build"):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://127.0.0.1:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="seeded-planner-jwt",
            couple_token="seeded-couple-jwt",
        )


@pytest.mark.parametrize(
    ("origin", "port"),
    [
        ("https://127.0.0.1:3100", 3100),
        ("http://example.com:3100", 3100),
        ("http://localhost:3100", 3100),
        ("http://127.0.0.2:3100", 3100),
        ("http://[::1]:3100", 3100),
        ("http://user:secret@127.0.0.1:3100", 3100),
        ("http://127.0.0.1:3100/admin", 3100),
        ("http://127.0.0.1:3100?next=evil", 3100),
        ("http://127.0.0.1:3100#capture", 3100),
        ("http://127.0.0.1:8000", 3100),
        ("http://127.0.0.1:8000/api", 8000),
    ],
)
def test_marketing_capture_rejects_non_exact_local_origins(origin, port):
    with pytest.raises(RuntimeError, match=r"exact HTTP 127\.0\.0\.1 origin"):
        marketing_capture_driver.require_local_capture_origin(
            origin,
            expected_port=port,
            label="Capture service",
        )


def test_marketing_capture_rejects_unsafe_origins_before_any_request(monkeypatch):
    request_attempts: list[str] = []

    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        lambda url, **_kwargs: request_attempts.append(url),
    )
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "post",
        lambda url, **_kwargs: request_attempts.append(url),
    )

    with pytest.raises(RuntimeError, match=r"exact HTTP 127\.0\.0\.1 origin"):
        marketing_capture_driver.verify_frontend_checkpoint_routes(
            "http://attacker.example:3100",
            EXPECTED_CAPTURE_BUILD,
            planner_token="planner-secret",
            couple_token="couple-secret",
        )
    with pytest.raises(RuntimeError, match=r"exact HTTP 127\.0\.0\.1 origin"):
        marketing_capture_driver._login(
            "http://127.0.0.1:8000/api",
            "/admin/token",
            marketing_capture_driver.PLANNER_EMAIL,
            marketing_capture_driver.PLANNER_PASSWORD,
        )

    assert request_attempts == []


def test_marketing_capture_route_preflight_can_resolve_real_seed_tokens(
    monkeypatch,
):
    login_calls: list[tuple[str, dict]] = []
    route_calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        marketing_capture_driver,
        "MARKETING_CAPTURE_E2E_CHECKPOINTS",
        (
            _planner_team_scene(),
            {
                "featureId": "guest-memories",
                "session": "couple",
                "route": "/couple/dashboard",
                "title": "Guest memories",
                "expectation": "The seeded review queue is visible.",
                "expectedVisibleText": "Review queue",
                "safeInteraction": "Open Memories.",
            },
        ),
    )

    def _post(url, **kwargs):
        login_calls.append((url, kwargs))
        token = "planner-token" if url.endswith("/admin/token") else "couple-token"
        return SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {"access_token": token},
        )

    def _get(url, **kwargs):
        route_calls.append((url, kwargs))
        if "/api/proxy/" in url:
            payload = _capture_readiness_payload(url)
            return SimpleNamespace(
                status_code=200,
                headers={},
                text="capture readiness payload",
                json=lambda: payload,
            )
        visible_text = (
            "Team Management" if url.endswith("/admin/planner/team") else "Review queue"
        )
        return SimpleNamespace(
            status_code=200,
            headers={},
            text=(
                f'<meta name="tsw-app-build-commit" content="{EXPECTED_CAPTURE_BUILD}">'  # noqa: E501
                f"{visible_text}"
            ),
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "post", _post)
    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    marketing_capture_driver.verify_frontend_checkpoint_routes(
        "http://127.0.0.1:3100",
        EXPECTED_CAPTURE_BUILD,
        backend_url="http://127.0.0.1:8000",
    )

    assert [url for url, _kwargs in login_calls] == [
        "http://127.0.0.1:8000/admin/token",
        "http://127.0.0.1:8000/couple/login",
    ]
    assert all(
        kwargs["allow_redirects"] is False and kwargs["timeout"] == 15
        for _url, kwargs in login_calls
    )
    planner_request = next(
        kwargs
        for url, kwargs in route_calls
        if url == "http://127.0.0.1:3100/admin/planner/team"
    )
    assert planner_request["cookies"] == {"admin_token": "planner-token"}
    couple_request = next(
        kwargs
        for url, kwargs in route_calls
        if url == "http://127.0.0.1:3100/couple/dashboard"
    )
    assert couple_request["cookies"] == {"couple_token": "couple-token"}
    assert "headers" not in couple_request


@pytest.mark.parametrize("status_code", [200, 307])
def test_marketing_capture_login_rejects_redirects_without_forwarding_credentials(
    monkeypatch,
    status_code,
):
    observed_kwargs: dict = {}

    def _redirect(_url, **kwargs):
        observed_kwargs.update(kwargs)
        return SimpleNamespace(
            status_code=status_code,
            headers={"Location": "https://attacker.example/collect"},
            text="redirect",
            json=lambda: {"access_token": "attacker-controlled"},
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "post", _redirect)

    with pytest.raises(RuntimeError, match="unexpectedly redirected"):
        marketing_capture_driver._login(
            "http://127.0.0.1:8000",
            "/admin/token",
            marketing_capture_driver.PLANNER_EMAIL,
            marketing_capture_driver.PLANNER_PASSWORD,
        )

    assert observed_kwargs["allow_redirects"] is False
    assert observed_kwargs["timeout"] == 15


@pytest.mark.parametrize("status_code", [200, 307])
def test_marketing_capture_json_readiness_rejects_any_location_header(
    monkeypatch,
    status_code,
):
    readiness_get = getattr(
        marketing_capture_driver,
        "_get_json_readiness",
        None,
    )
    assert callable(readiness_get), "capture JSON probes need one fail-closed helper"
    observed_kwargs: dict = {}

    def _redirect(_url, **kwargs):
        observed_kwargs.update(kwargs)
        return SimpleNamespace(
            status_code=status_code,
            headers={"Location": "https://attacker.example/collect"},
            text="redirect",
            json=lambda: {"slug": marketing_capture_driver.PRIMARY_SLUG},
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _redirect)

    with pytest.raises(RuntimeError, match="unexpectedly redirected"):
        readiness_get(
            "http://127.0.0.1:8000/weddings/slug/sofia-and-daniel",
            label="Public showcase wedding",
        )

    assert observed_kwargs["allow_redirects"] is False
    assert observed_kwargs["timeout"] == 15


def test_marketing_capture_json_readiness_rejects_redirect_status_without_location(
    monkeypatch,
):
    readiness_get = getattr(
        marketing_capture_driver,
        "_get_json_readiness",
        None,
    )
    assert callable(readiness_get), "capture JSON probes need one fail-closed helper"
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=307,
            headers={},
            text="redirect without location",
            json=lambda: {},
        ),
    )

    with pytest.raises(RuntimeError, match="returned HTTP 307"):
        readiness_get(
            "http://127.0.0.1:8000/public/kb/articles/slug/"
            "planner-command-center-first-steps",
            label="Published showcase Knowledge Base article",
        )


def test_marketing_capture_preflights_public_gallery_payload_and_assets(monkeypatch):
    origin = "http://127.0.0.1:3100"
    gallery_url = f"{origin}/api/proxy/gallery?wedding_slug=sofia-and-daniel&limit=12"
    requested: list[tuple[str, dict]] = []

    class FakeResponse:
        def __init__(
            self,
            *,
            status_code=200,
            payload=None,
            content_type=None,
            content=b"",
        ):
            self.status_code = status_code
            self._payload = payload
            self.headers = {"content-type": content_type} if content_type else {}
            self.content = content

        def json(self):
            return self._payload

    def _get(url, **kwargs):
        requested.append((url, kwargs))
        if url == gallery_url:
            return FakeResponse(
                payload={
                    "items": marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ITEMS,
                    "next_cursor": None,
                    "has_more": False,
                }
            )
        path = url.removeprefix(origin)
        return FakeResponse(
            content_type="image/webp",
            content=_gallery_fixture_bytes(path),
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    marketing_capture_driver.verify_frontend_gallery_assets(origin)

    assert [url for url, _kwargs in requested] == [
        gallery_url,
        *[
            f"{origin}{item['url']}"
            for item in marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ITEMS
        ],
    ]
    assert all(
        kwargs["allow_redirects"] is False and kwargs["timeout"] == 15
        for _url, kwargs in requested
    )


def test_marketing_capture_preflights_all_admin_gallery_prefixes_through_frontend_proxy(
    monkeypatch,
):
    verifier = getattr(
        marketing_capture_driver,
        "verify_frontend_admin_gallery_prefixes",
        None,
    )
    assert callable(verifier), "marketing capture must preflight admin gallery prefixes"

    frontend_origin = "http://127.0.0.1:3100"
    backend_origin = "http://127.0.0.1:8000"
    login_url = f"{backend_origin}/admin/token"
    list_url = f"{frontend_origin}/api/proxy/admin/gallery/list"
    calls: list[tuple[str, str, dict]] = []

    def _post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return SimpleNamespace(
            status_code=200,
            headers={},
            text="planner login",
            json=lambda: {"access_token": "seeded-planner-jwt"},
        )

    def _get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        prefix = kwargs["params"]["prefix"]
        payload = (
            marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ITEMS
            if prefix.startswith("gallery/")
            else []
        )
        return SimpleNamespace(
            status_code=200,
            headers={},
            text="gallery list",
            json=lambda: payload,
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "post", _post)
    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    verifier(frontend_origin, backend_origin)

    assert [(method, url) for method, url, _kwargs in calls] == [
        ("POST", login_url),
        ("GET", list_url),
        ("GET", list_url),
        ("GET", list_url),
    ]
    assert [
        kwargs["params"]["prefix"] for method, _url, kwargs in calls if method == "GET"
    ] == [
        "gallery/sofia-and-daniel/",
        "our-story/sofia-and-daniel/",
        "wedding-party/sofia-and-daniel/",
    ]
    assert all(
        kwargs["headers"] == {"Authorization": "Bearer seeded-planner-jwt"}
        and kwargs["allow_redirects"] is False
        and kwargs["timeout"] == 15
        for method, _url, kwargs in calls
        if method == "GET"
    )


def test_marketing_capture_admin_gallery_preflight_rejects_optional_prefix_503(
    monkeypatch,
):
    verifier = getattr(
        marketing_capture_driver,
        "verify_frontend_admin_gallery_prefixes",
        None,
    )
    assert callable(verifier), "marketing capture must preflight admin gallery prefixes"

    def _post(_url, **_kwargs):
        return SimpleNamespace(
            status_code=200,
            headers={},
            text="planner login",
            json=lambda: {"access_token": "seeded-planner-jwt"},
        )

    def _get(_url, **kwargs):
        prefix = kwargs["params"]["prefix"]
        return SimpleNamespace(
            status_code=503 if prefix.startswith("our-story/") else 200,
            headers={},
            text="storage unavailable",
            json=lambda: (
                marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ITEMS
                if prefix.startswith("gallery/")
                else []
            ),
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "post", _post)
    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    with pytest.raises(RuntimeError, match="our-story.*HTTP 503"):
        verifier("http://127.0.0.1:3100", "http://127.0.0.1:8000")


def test_marketing_capture_gallery_asset_rejects_invalid_webp_bytes():
    path = "/demo-gallery/sofia-daniel-terrace.webp"
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "image/webp"},
        content=b"not-a-webp",
    )

    with pytest.raises(RuntimeError, match="not a decodable WebP"):
        marketing_capture_driver._validate_gallery_asset_response(
            response,
            asset_url=f"http://127.0.0.1:3100{path}",
            asset_contract=(
                marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ASSET_CONTRACT[path]
            ),
        )


def test_marketing_capture_gallery_asset_rejects_wrong_dimensions():
    path = "/demo-gallery/sofia-daniel-terrace.webp"
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "image/webp"},
        content=_resized_webp_bytes(path, (800, 500)),
    )

    with pytest.raises(RuntimeError, match="wrong dimensions"):
        marketing_capture_driver._validate_gallery_asset_response(
            response,
            asset_url=f"http://127.0.0.1:3100{path}",
            asset_contract=(
                marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ASSET_CONTRACT[path]
            ),
        )


def test_marketing_capture_gallery_asset_rejects_wrong_hash():
    expected_path = "/demo-gallery/sofia-daniel-terrace.webp"
    different_path = "/demo-gallery/sofia-daniel-ceremony.webp"
    different_bytes = _gallery_fixture_bytes(different_path)
    assert (
        hashlib.sha256(different_bytes).hexdigest()
        != (
            marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ASSET_CONTRACT[
                expected_path
            ]["sha256"]
        )
    )
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "image/webp"},
        content=different_bytes,
    )

    with pytest.raises(RuntimeError, match="wrong SHA-256"):
        marketing_capture_driver._validate_gallery_asset_response(
            response,
            asset_url=f"http://127.0.0.1:3100{expected_path}",
            asset_contract=(
                marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ASSET_CONTRACT[
                    expected_path
                ]
            ),
        )


def test_marketing_capture_preflights_authenticated_couple_memory_preview(
    monkeypatch,
):
    frontend_origin = "http://127.0.0.1:3100"
    backend_origin = "http://127.0.0.1:8000"
    login_url = f"{backend_origin}/couple/login"
    memories_url = (
        f"{frontend_origin}/api/proxy/couple/portal/memories?media_type=image&limit=24"
    )
    preview_path = "/couple/portal/memories/memory-1/preview"
    preview_url = f"{frontend_origin}/api/proxy{preview_path}"
    asset_url = (
        f"{frontend_origin}"
        f"{marketing_capture_driver.MARKETING_CAPTURE_GALLERY_ITEMS[0]['url']}"
    )
    calls: list[tuple[str, str, dict]] = []

    class FakeResponse:
        def __init__(
            self,
            *,
            status_code=200,
            payload=None,
            headers=None,
            content=b"",
        ):
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}
            self.content = content
            self.text = ""

        def json(self):
            return self._payload

    def _post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return FakeResponse(payload={"access_token": "seeded-couple-jwt"})

    def _get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        if url == memories_url:
            return FakeResponse(
                payload={
                    "items": [
                        {
                            "id": "memory-1",
                            "media_type": "image",
                            "preview_path": preview_path,
                        }
                    ]
                }
            )
        if url == preview_url:
            return FakeResponse(status_code=307, headers={"location": asset_url})
        if url == asset_url:
            asset_path = url.removeprefix(frontend_origin)
            return FakeResponse(
                headers={"content-type": "image/webp; charset=binary"},
                content=_gallery_fixture_bytes(asset_path),
            )
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(marketing_capture_driver.requests, "post", _post)
    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    marketing_capture_driver.verify_frontend_couple_memory_preview(
        frontend_origin,
        backend_origin,
    )

    assert [(method, url) for method, url, _kwargs in calls] == [
        ("POST", login_url),
        ("GET", memories_url),
        ("GET", preview_url),
        ("GET", asset_url),
    ]
    assert calls[0][2]["json"] == {
        "email": marketing_capture_driver.COUPLE_EMAIL,
        "password": marketing_capture_driver.COUPLE_PASSWORD,
    }
    assert calls[0][2]["allow_redirects"] is False
    assert calls[1][2]["headers"] == {"Authorization": "Bearer seeded-couple-jwt"}
    assert calls[1][2]["allow_redirects"] is False
    assert calls[2][2]["headers"] == {"Authorization": "Bearer seeded-couple-jwt"}
    assert calls[2][2]["allow_redirects"] is False


def test_marketing_capture_couple_memory_preflight_rejects_wrong_redirect_origin(
    monkeypatch,
):
    frontend_origin = "http://127.0.0.1:3100"
    backend_origin = "http://127.0.0.1:8000"
    preview_path = "/couple/portal/memories/memory-1/preview"

    class FakeResponse:
        text = ""
        content = b""

        def __init__(self, *, status_code=200, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}

        def json(self):
            return self._payload

    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "post",
        lambda *_args, **_kwargs: FakeResponse(
            payload={"access_token": "seeded-couple-jwt"}
        ),
    )

    def _get(url, **_kwargs):
        if url.endswith("?media_type=image&limit=24"):
            return FakeResponse(
                payload={
                    "items": [
                        {
                            "id": "memory-1",
                            "media_type": "image",
                            "preview_path": preview_path,
                        }
                    ]
                }
            )
        return FakeResponse(
            status_code=307,
            headers={
                "location": "http://127.0.0.1:3000/demo-gallery/"
                "sofia-daniel-terrace.webp"
            },
        )

    monkeypatch.setattr(marketing_capture_driver.requests, "get", _get)

    with pytest.raises(RuntimeError, match="canonical frontend origin"):
        marketing_capture_driver.verify_frontend_couple_memory_preview(
            frontend_origin,
            backend_origin,
        )


@pytest.mark.parametrize("process_name", ["node", "npm", "next-server"])
def test_testbed_frontend_liveness_accepts_supported_runtime_names(
    monkeypatch, process_name
):
    monkeypatch.setattr(
        testbed_cli,
        "pane_process_names",
        lambda _session, _window: {process_name},
    )

    assert testbed_cli._service_process_is_live(
        "capture-testbed", testbed_cli.FRONTEND_WINDOW
    )


def test_testbed_status_fails_when_a_required_service_window_is_missing(monkeypatch):
    cfg = SimpleNamespace(
        session_name="capture-testbed",
        with_frontend=False,
        enabled_windows=lambda: [
            testbed_cli.BACKEND_WINDOW,
            testbed_cli.STRIPE_WINDOW,
        ],
    )
    monkeypatch.setattr(testbed_cli, "session_exists", lambda _session: True)
    monkeypatch.setattr(
        testbed_cli,
        "list_windows",
        lambda _session: [testbed_cli.BACKEND_WINDOW],
    )
    monkeypatch.setattr(
        testbed_cli,
        "service_is_ready",
        lambda _cfg, window: window == testbed_cli.BACKEND_WINDOW,
    )

    assert testbed_cli.cmd_status(cfg, SimpleNamespace()) == 1


def test_local_media_fallbacks_accept_the_canonical_marketing_capture_seed():
    constants_source = _required_text(SEED_SOURCES)
    media_source = _required_text(MARKETING_CAPTURE_MEDIA)
    gallery_source = _required_text(GALLERY_API)
    gallery_admin_source = _required_text(GALLERY_ADMIN_API)
    guest_media_source = _required_text(GUEST_MEDIA_SERVICE)

    assert (
        'MARKETING_CAPTURE_SEED_SOURCE = "system:marketing_capture_seed"'
        in constants_source
    )
    assert "is_exact_marketing_capture_seed" in media_source
    assert "allow_local_demo_gallery_fallback" in gallery_source
    assert "allow_local_demo_gallery_fallback" in gallery_admin_source
    assert "is_exact_marketing_capture_seed" in guest_media_source
    assert "MARKETING_CAPTURE_SEED_SCOPE" in constants_source
    assert "/demo-gallery/sofia-daniel-terrace.webp" in media_source


def test_marketing_gallery_assets_are_repository_owned_and_present():
    seeder = _load_seeder_module()
    asset_names = (
        "sofia-daniel-terrace.webp",
        "sofia-daniel-ceremony.webp",
        "sofia-daniel-reception.webp",
    )

    assert [
        Path(item["url"]).name for item in seeder.MARKETING_CAPTURE_GALLERY_ASSETS
    ] == list(asset_names)
    for name in asset_names:
        path = ROOT / "public" / "demo-gallery" / name
        assert path.is_file()
        with Image.open(path) as image:
            assert image.format == "WEBP"
            assert image.size == (1600, 1000)
    assert all(
        item["content_type"] == "image/webp"
        for item in seeder.MARKETING_CAPTURE_GALLERY_ASSETS
    )


def test_marketing_wedding_party_does_not_reuse_venue_gallery_photos_as_portraits():
    source = _required_text(SEEDER)
    party_start = source.index('"wedding_party": (')
    party_end = source.index('"registries":', party_start)
    party_source = source[party_start:party_end]

    assert "MARKETING_CAPTURE_GALLERY_ASSETS" not in party_source
    assert party_source.count('"image_url": None') == 2


def test_marketing_capture_clean_checkout_gate_returns_full_head(monkeypatch):
    calls: list[tuple[list[str], dict]] = []

    def _run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1] == "status":
            return SimpleNamespace(stdout="")
        if command[1] == "rev-parse":
            return SimpleNamespace(stdout=f"{EXPECTED_CAPTURE_BUILD}\n")
        raise AssertionError(f"unexpected git command: {command}")

    monkeypatch.setattr(marketing_capture_driver.subprocess, "run", _run)

    assert (
        marketing_capture_driver.require_clean_capture_checkout()
        == EXPECTED_CAPTURE_BUILD
    )
    assert [command for command, _kwargs in calls] == [
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        ["git", "rev-parse", "--verify", "HEAD"],
    ]
    assert all(
        kwargs
        == {
            "cwd": ROOT,
            "check": True,
            "capture_output": True,
            "text": True,
        }
        for _command, kwargs in calls
    )


def test_marketing_capture_clean_checkout_gate_rejects_dirty_state(monkeypatch):
    calls: list[list[str]] = []

    def _run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=" M app/page.tsx\n?? capture.png\n")

    monkeypatch.setattr(marketing_capture_driver.subprocess, "run", _run)

    with pytest.raises(RuntimeError, match="requires a clean checkout"):
        marketing_capture_driver.require_clean_capture_checkout()

    assert calls == [["git", "status", "--porcelain", "--untracked-files=normal"]]


def test_testbed_driver_resets_then_seeds_then_verifies_before_browser_checkpoints():
    source = _required_text(DRIVER)
    main_source = source.split("def main() -> int:", 1)[1]

    reset_index = main_source.find(
        "cleanup_marketing_capture_workspace_state(database)"
    )
    plan_index = main_source.find("_run_python(SUBSCRIPTION_PLAN_SEEDER")
    identity_index = main_source.find("_run_python(SETUP_SMOKE_ACCOUNTS")
    workspace_index = main_source.find(
        "_run_python(\n            RICH_WORKSPACE_SEEDER"
    )
    verification_index = main_source.find("verify_seeded_workspace(")

    assert -1 not in {
        reset_index,
        plan_index,
        identity_index,
        workspace_index,
        verification_index,
    }
    assert (
        reset_index < plan_index < identity_index < workspace_index < verification_index
    )
    assert '"STRIPE_ENABLED": "false"' in source
    assert "verify_public_subscription_plan_truth" in source
    assert "TESTBED_NON_INTERACTIVE" in source
    assert "America/Chicago" in source
    assert "MARKETING_CAPTURE_FRONTEND_URL" in source
    assert '"http://127.0.0.1:3100"' in source

    initial_clean_gate_index = main_source.find(
        "capture_build = require_clean_capture_checkout()"
    )
    database_open_index = main_source.find("client, database = _load_database()")
    backend_origin_index = main_source.find(
        "backend_url = require_local_capture_origin("
    )
    frontend_origin_index = main_source.find(
        "frontend_url = require_local_capture_origin("
    )
    runtime_gate_index = main_source.find(
        "verify_frontend_capture_runtime(frontend_url)"
    )
    capture_clean_gate_index = main_source.find(
        "capture_ready_build = require_clean_capture_checkout()"
    )
    route_preflight_index = main_source.find("verify_frontend_checkpoint_routes(")
    assert (
        -1
        < backend_origin_index
        < frontend_origin_index
        < runtime_gate_index
        < initial_clean_gate_index
        < database_open_index
    )
    assert -1 < capture_clean_gate_index < route_preflight_index
    public_plan_preflight_index = main_source.find(
        "verify_frontend_public_subscription_plans("
    )
    gallery_preflight_index = main_source.find(
        "verify_frontend_gallery_assets(frontend_url)"
    )
    admin_gallery_preflight_index = main_source.find(
        "verify_frontend_admin_gallery_prefixes(frontend_url, backend_url)"
    )
    memory_preflight_index = main_source.find(
        "verify_frontend_couple_memory_preview(frontend_url, backend_url)"
    )
    checkpoint_output_index = main_source.find(
        "for scene in MARKETING_CAPTURE_E2E_CHECKPOINTS"
    )
    assert (
        -1
        < route_preflight_index
        < public_plan_preflight_index
        < gallery_preflight_index
        < admin_gallery_preflight_index
        < memory_preflight_index
        < checkpoint_output_index
    )


def test_testbed_driver_preserves_operator_plan_visibility_during_capture_seed():
    source = _required_text(DRIVER)
    main_source = source.split("def main() -> int:", 1)[1]

    assert "canonical_plan_ids = [" in main_source
    assert '"_id": {"$in": canonical_plan_ids}' in main_source
    assert "require_active=False" in main_source
    assert "active_public_plan_names = {" in main_source
    assert "expected_plan_names=active_public_plan_names" in main_source
    assert 'find({"is_active": True})' not in main_source


def test_marketing_capture_plan_truth_rejects_retired_runtime_copy():
    stale_plans = [
        {
            "name": "Solo",
            "description": "stale",
            "features": {"vendor_collaboration": False},
            "features_list": [],
        },
        {
            "name": "Boutique",
            "description": "stale",
            "features": {"vendor_collaboration": False},
            "features_list": [],
        },
        {
            "name": "Signature",
            "description": "For agencies plus agency-grade reporting.",
            "features": {"vendor_collaboration": True},
            "features_list": [
                "Vendor-collaboration workspaces",
                "Cross-wedding analytics & revenue tracking",
            ],
        },
        {
            "name": "Enterprise",
            "description": "stale",
            "features": {"vendor_collaboration": True},
            "features_list": [],
        },
    ]

    with pytest.raises(RuntimeError, match="public subscription plan"):
        marketing_capture_driver.verify_public_subscription_plan_truth(
            stale_plans,
            label="test plans",
        )


def _canonical_public_capture_plans() -> list[dict]:
    return [
        {
            "name": plan_name,
            **expected,
            "features": {"vendor_collaboration": False},
        }
        for plan_name, expected in (
            marketing_capture_driver.EXPECTED_PUBLIC_PLAN_COPY.items()
        )
    ]


def test_marketing_capture_plan_truth_accepts_only_the_exact_catalog():
    canonical = _canonical_public_capture_plans()
    marketing_capture_driver.verify_public_subscription_plan_truth(
        canonical,
        label="test plans",
    )

    duplicate = [*canonical, dict(canonical[0])]
    with pytest.raises(RuntimeError, match="duplicate or extra"):
        marketing_capture_driver.verify_public_subscription_plan_truth(
            duplicate,
            label="test plans",
        )

    wrong_price = [dict(plan) for plan in canonical]
    wrong_price[2]["price_monthly"] = 99
    with pytest.raises(RuntimeError, match="stale price_monthly"):
        marketing_capture_driver.verify_public_subscription_plan_truth(
            wrong_price,
            label="test plans",
        )


def test_marketing_capture_plan_truth_preserves_hidden_canonical_plan():
    canonical = _canonical_public_capture_plans()
    canonical[-1]["is_active"] = False

    marketing_capture_driver.verify_public_subscription_plan_truth(
        canonical,
        label="seeded database",
        require_active=False,
    )


def test_marketing_capture_plan_truth_accepts_exact_active_subset():
    active_plans = _canonical_public_capture_plans()[:3]

    marketing_capture_driver.verify_public_subscription_plan_truth(
        active_plans,
        label="frontend plans",
        expected_plan_names={"Solo", "Boutique", "Signature"},
    )


def test_marketing_capture_verifies_the_frontend_plan_payload_without_cache(
    monkeypatch,
):
    observed: dict[str, object] = {}

    def _get_json(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return _canonical_public_capture_plans()

    monkeypatch.setattr(marketing_capture_driver, "_get_json_readiness", _get_json)

    marketing_capture_driver.verify_frontend_public_subscription_plans(
        "http://127.0.0.1:3100"
    )

    assert observed == {
        "url": "http://127.0.0.1:3100/api/proxy/public/subscription-plans",
        "label": "Marketing capture public subscription plans",
        "headers": {"Cache-Control": "no-cache"},
        "expected_cache_control": "no-cache, no-store, must-revalidate",
    }


def test_marketing_capture_requires_no_store_on_the_frontend_plan_response(
    monkeypatch,
):
    response = SimpleNamespace(
        status_code=200,
        headers={"Cache-Control": "public, max-age=300"},
        json=lambda: _canonical_public_capture_plans(),
    )
    monkeypatch.setattr(
        marketing_capture_driver.requests,
        "get",
        lambda *_args, **_kwargs: response,
    )

    with pytest.raises(RuntimeError, match="returned Cache-Control"):
        marketing_capture_driver._get_json_readiness(
            "http://127.0.0.1:3100/api/proxy/public/subscription-plans",
            label="Marketing capture public subscription plans",
            expected_cache_control="no-cache, no-store, must-revalidate",
        )


def test_marketing_seed_is_isolated_and_does_not_rebrand_an_arbitrary_planner():
    source = _required_text(SEEDER)

    assert "MARKETING_CAPTURE_SEED_SOURCE" in source
    assert "Marigold & Co. Weddings" in source
    assert "Amina" in source and "Cole" in source
    assert "www.thespecialwedding.io" in source
    assert "marketing-capture@" not in source
    assert "MCW-SHOWCASE" not in source
    assert "--anchor-at" in source

    forbidden_visible_fixture_copy = (
        "JoshLoveWeds",
        "Josh Akinwole",
        "CON-DEMO-VIDEO",
        "peace.emmanuel",
        "test_planner",
    )
    for forbidden in forbidden_visible_fixture_copy:
        assert forbidden not in source

    assert "seed_source" in source
    assert "seed_scope" in source
    assert "existing owner" in source.lower()


def test_marketing_vendor_contract_activity_seed_uses_the_api_response_shape():
    source = _required_text(SEEDER)
    activity_seed = source.split(
        'mongo.get_collection("vendor_contract_activities")', 2
    )[-1].split("remaining_amount =", 1)[0]

    assert "VendorContractActivityType" in source
    assert '"root_contract_id": str(contract_object_id)' in activity_seed
    assert '"activity_type": activity_type.value' in activity_seed
    assert '"title": activity_title' in activity_seed
    assert '"type": actor_type' in activity_seed
    assert '"identifier": actor_identifier' in activity_seed
    assert '"display_name": actor_display_name' in activity_seed
    for legacy_key in ('"role":', '"email":', '"name":'):
        assert legacy_key not in activity_seed


def test_marketing_contract_activity_validator_rejects_legacy_seed_shape():
    validator = getattr(
        marketing_capture_driver, "_validate_vendor_contract_activity_api_shape", None
    )
    assert validator is not None

    with pytest.raises(RuntimeError, match="contract activity is not API-compatible"):
        validator(
            {
                "_id": ObjectId("67ce00000000000000000001"),
                "contract_id": "67c100000000000000000001",
                "activity_type": "sent",
                "actor": {
                    "role": "planner",
                    "email": "amina@studio.thespecialwedding.io",
                },
                "created_at": "2026-07-12T10:00:00+00:00",
            }
        )


def test_marketing_contract_activity_validator_accepts_canonical_seed_shape():
    validator = getattr(
        marketing_capture_driver, "_validate_vendor_contract_activity_api_shape", None
    )
    assert validator is not None

    validator(
        {
            "_id": ObjectId("67ce00000000000000000001"),
            "contract_id": "67c100000000000000000001",
            "root_contract_id": "67c100000000000000000001",
            "activity_type": "contract_sent",
            "title": "Contract sent",
            "description": "Sent to Luna & Co. Photography for review.",
            "actor": {
                "type": "planner",
                "identifier": "amina@studio.thespecialwedding.io",
                "display_name": "Amina Cole",
            },
            "metadata": {"contract_number": "MCW-2027-001"},
            "created_at": "2026-07-12T10:00:00+00:00",
        }
    )


def test_seed_reset_filters_do_not_delete_unowned_global_communications():
    source = _required_text(SEEDER)

    assert '"system:setup_smoke_accounts"' not in source
    assert '"phone": "+13195296088"' not in source
    assert '"recipient": "+13195296088"' not in source
    assert '"to": {"$regex": "^(demo|test)' not in source


def test_every_marketing_seed_deletion_requires_exact_source_and_scope():
    source = _required_text(SEEDER)
    module = ast.parse(source)
    checked = 0

    for function in (
        node for node in module.body if isinstance(node, ast.AsyncFunctionDef)
    ):
        assigned_dicts = _assigned_dicts(function)
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if not (
                isinstance(call.func, ast.Attribute)
                and call.func.attr in {"delete_many", "delete_one"}
                and call.args
            ):
                continue
            filter_node = call.args[0]
            if isinstance(filter_node, ast.Name):
                filter_node = assigned_dicts.get(filter_node.id, filter_node)
            assert isinstance(filter_node, ast.Dict), (
                f"{function.name} must expose an auditable literal deletion filter"
            )
            assert _dict_keys(filter_node) >= {"seed_source", "seed_scope"}, (
                f"{function.name} deletion is not constrained to the exact capture "
                "source and scope"
            )
            filter_source = ast.unparse(filter_node)
            assert "MARKETING_CAPTURE_SEED_SOURCE" in filter_source
            assert "MARKETING_CAPTURE_SEED_SCOPE" in filter_source
            checked += 1

    assert checked >= 10, (
        "expected the contract to inspect the full fixture reset graph"
    )


def test_marketing_seed_replacements_are_exact_scope_or_fixed_legacy_migrations():
    source = _required_text(SEEDER)
    module = ast.parse(source)
    checked = 0

    for function in (
        node for node in module.body if isinstance(node, ast.AsyncFunctionDef)
    ):
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if not (
                isinstance(call.func, ast.Attribute)
                and call.func.attr in {"replace_one", "update_one", "update_many"}
                and call.args
            ):
                continue
            filter_node = call.args[0]
            assert isinstance(filter_node, ast.Dict), (
                f"{function.name} must expose an auditable literal mutation filter"
            )
            filter_keys = _dict_keys(filter_node)
            filter_source = ast.unparse(filter_node)
            assert filter_keys >= {"_id", "seed_source", "seed_scope"}
            if function.name == "_migrate_legacy_smoke_workspace":
                assert "SMOKE_ACCOUNT_SEED_SOURCE" in filter_source
                assert "LEGACY_SMOKE_SEED_SCOPE" in filter_source
                assert filter_keys & {"email", "slug", "wedding_id"}
            else:
                assert "MARKETING_CAPTURE_SEED_SOURCE" in filter_source
                assert "MARKETING_CAPTURE_SEED_SCOPE" in filter_source
            checked += 1

    assert checked >= 4, "expected canonical updates plus fixed legacy migrations"


@pytest.mark.asyncio
async def test_seeded_document_reset_uses_the_exact_capture_scope():
    seeder = _load_seeder_module()

    class RecordingCollection:
        def __init__(self):
            self.deleted_with = None
            self.inserted = None

        async def delete_many(self, query):
            self.deleted_with = query

        async def insert_many(self, docs):
            self.inserted = docs

    collection = RecordingCollection()
    documents = [
        {
            "_id": "fixture-1",
            "wedding_id": "wedding-1",
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
        }
    ]

    await seeder._replace_seeded_docs(collection, ["wedding-1"], documents)

    assert collection.deleted_with == {
        "wedding_id": {"$in": ["wedding-1"]},
        "seed_source": SEED_SOURCE,
        "seed_scope": SEED_SCOPE,
    }
    assert collection.inserted == documents


def test_seeded_identity_validator_accepts_only_reserved_or_controlled_contacts():
    validator = getattr(
        marketing_capture_driver, "_validate_seeded_identity_document", None
    )
    assert validator is not None

    validator(
        {
            "phone": "+1 (312) 555-0100",
            "phone_numbers": ["(405) 555-0199"],
            "email": "planner@studio.thespecialwedding.io",
            "website": "https://vendors.thespecialwedding.io/luna-lane",
            "nested": {
                "email": "host@example.com",
                "url": "https://florist.example/portfolio",
            },
        },
        path="vendor_profiles/example",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("phone", "+1 (312) 555-0200", "reserved fictional"),
        ("phone", "(555) 014-1188", "reserved fictional"),
        ("email", "routes@atlascoach.co", "controlled or reserved"),
        ("website", "https://atlascoach.co", "controlled or reserved"),
    ],
)
def test_seeded_identity_validator_rejects_unsafe_contacts(field, value, message):
    validator = getattr(
        marketing_capture_driver, "_validate_seeded_identity_document", None
    )
    assert validator is not None

    with pytest.raises(RuntimeError, match=message):
        validator({field: value}, path="vendor_profiles/unsafe")


def test_workspace_verifier_scans_every_scoped_document_for_identity_safety():
    source = _required_text(DRIVER)

    assert "_validate_seeded_identity_document" in source
    assert "database.list_collection_names()" in source
    assert '"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE' in source


def test_seating_reset_is_scoped_to_the_marketing_capture_owner():
    source = _required_text(SEEDER)
    seating_source = source.split("async def _seed_seating_fixture", 1)[1].split(
        "async def ", 1
    )[0]

    assert '"seed_source": MARKETING_CAPTURE_SEED_SOURCE' in seating_source
    assert '"seed_scope": MARKETING_CAPTURE_SEED_SCOPE' in seating_source
    assert 'delete_many({"wedding_id": {"$in": wedding_ids}})' not in seating_source


def test_ai_cache_seed_replaces_only_exact_content_addressed_rows():
    source = _required_text(SEEDER)
    function = _async_function(source, "_seed_ai_cache")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    assert not any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "update_many"
        for call in calls
    ), "AI fixture seeding must never retag every cache row for a tenant/feature"
    assert any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "_generate_cache_key"
        for call in calls
    ), "AI fixtures must derive the canonical content-addressed cache _id"
    assert any(
        isinstance(call.func, ast.Name)
        and call.func.id == "_replace_marketing_capture_owned_document"
        for call in calls
    ), "showcase AI cache fixtures must replace only their exact seed-owned _ids"
    assert "dashboard_insights" in ast.unparse(function)
    assert "budget_insights" in ast.unparse(function)


def test_form_artifact_resets_require_scope_wedding_and_exact_form_id():
    source = _required_text(SEEDER)
    function = _async_function(source, "_seed_form_fixture")
    expected_form_ids = {
        "form_responses": "DEMO_PUBLIC_FORM_ID",
        "form_submissions": "DEMO_COUPLE_FORM_ID",
    }
    checked: set[str] = set()

    for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
        if not (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "delete_many"
            and call.args
        ):
            continue
        collection_expr = ast.unparse(call.func.value)
        collection_name = next(
            (name for name in expected_form_ids if name in collection_expr), None
        )
        if collection_name is None:
            continue

        filter_node = call.args[0]
        assert _dict_keys(filter_node) >= {
            "seed_source",
            "seed_scope",
            "wedding_id",
            "form_id",
        }
        assert expected_form_ids[collection_name] in ast.unparse(filter_node)
        checked.add(collection_name)

    assert checked == set(expected_form_ids)


def test_knowledge_base_fixture_is_published_owned_verified_and_cleaned():
    seeder_source = _required_text(SEEDER)
    driver_source = _required_text(DRIVER)
    cleanup_source = _required_text(CLEANUP)

    kb_function = _async_function(seeder_source, "_seed_knowledge_base_fixture")
    assert "_replace_marketing_capture_owned_document" in ast.unparse(kb_function)
    strict_replace = _async_function(
        seeder_source, "_replace_marketing_capture_owned_document"
    )
    strict_replace_source = ast.unparse(strict_replace)
    assert "MARKETING_CAPTURE_SEED_SOURCE" in strict_replace_source
    assert "MARKETING_CAPTURE_SEED_SCOPE" in strict_replace_source
    assert "DEMO_KB_ARTICLE_ID" in seeder_source
    assert "DEMO_KB_ARTICLE_SLUG" in seeder_source
    assert '"status": "published"' in seeder_source
    assert '"kb_articles"' in cleanup_source
    assert '"kb_articles": 1' in driver_source
    assert "DEMO_KB_ARTICLE_SLUG" in driver_source
    assert "kb_count_before + 1" in driver_source


class _CollisionCollection:
    def __init__(self, existing=None):
        self.existing = existing

    def find_one(self, _query, _projection=None):
        return self.existing


class _CollisionDatabase:
    def __init__(self, collision_collection: str | None = None):
        self.collision_collection = collision_collection

    def __getitem__(self, collection_name: str):
        existing = (
            {"_id": "customer-owned"}
            if collection_name == self.collision_collection
            else None
        )
        return _CollisionCollection(existing)


class _IdentityCollection:
    def __init__(self, records):
        self.records = records

    def find(self, _query, _projection=None):
        return iter(self.records)


class _IdentityDatabase:
    def __init__(self, records_by_collection=None):
        self.records_by_collection = records_by_collection or {}

    def __getitem__(self, collection_name: str):
        return _IdentityCollection(self.records_by_collection.get(collection_name, []))


class _AsyncScopedCollection:
    def __init__(self, existing=None, *, insert_error: Exception | None = None):
        self.existing = existing
        self.insert_error = insert_error
        self.inserted = None
        self.replaced = None

    async def find_one(self, _query, _projection=None):
        return self.existing

    async def replace_one(self, query, document, *, upsert):
        self.replaced = (query, document, upsert)
        return SimpleNamespace(matched_count=1)

    async def insert_one(self, document):
        if self.insert_error:
            raise self.insert_error
        self.inserted = document
        return SimpleNamespace(inserted_id=document["_id"])


def test_setup_namespace_preflight_refuses_colliding_local_identity_before_smoke_seed():
    assert_setup_namespace_available(_CollisionDatabase())  # type: ignore[arg-type]

    with pytest.raises(
        RuntimeError, match="refusing to let setup_smoke_accounts overwrite"
    ):
        assert_setup_namespace_available(  # type: ignore[arg-type]
            _CollisionDatabase("users")
        )

    with pytest.raises(
        RuntimeError, match="refusing to let setup_smoke_accounts overwrite"
    ):
        assert_setup_namespace_available(  # type: ignore[arg-type]
            _CollisionDatabase("kb_articles")
        )


def test_runtime_cleanup_requires_seed_owned_identity_evidence():
    assert not _capture_namespace_is_owned(_IdentityDatabase())  # type: ignore[arg-type]
    assert _capture_namespace_is_owned(  # type: ignore[arg-type]
        _IdentityDatabase(
            {"users": [{"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}]}
        )
    )
    assert not _capture_namespace_is_owned(  # type: ignore[arg-type]
        _IdentityDatabase(
            {"users": [{"seed_source": "customer", "seed_scope": SEED_SCOPE}]}
        )
    )
    assert not _capture_namespace_is_owned(  # type: ignore[arg-type]
        _IdentityDatabase(
            {"users": [{"seed_source": SEED_SOURCE, "seed_scope": "another-demo"}]}
        )
    )


def test_identity_cleanup_filter_preserves_same_identity_from_wrong_seed_scope():
    database = mongomock.MongoClient().db
    database.users.insert_many(
        [
            {
                "_id": "owned",
                "email": PLANNER_EMAIL,
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
            },
            {
                "_id": "wrong-scope",
                "email": PLANNER_EMAIL,
                "seed_source": SEED_SOURCE,
                "seed_scope": "another-demo",
            },
        ]
    )

    result = database.users.delete_many(
        _owned_identity_filter({"email": PLANNER_EMAIL})
    )

    assert result.deleted_count == 1
    assert database.users.find_one({"_id": "wrong-scope"}) is not None


@pytest.mark.asyncio
async def test_scoped_seed_replacement_never_mutates_an_unrelated_owner():
    from pymongo.errors import DuplicateKeyError

    from testbed._marketing_capture_seed_ownership import replace_scoped_document

    invalid_document_collection = _AsyncScopedCollection()
    with pytest.raises(RuntimeError, match="must carry exact seed ownership"):
        await replace_scoped_document(
            invalid_document_collection,
            {"_id": "cache-key", "seed_source": "customer"},
            seed_source=SEED_SOURCE,
            seed_scope=SEED_SCOPE,
        )
    assert invalid_document_collection.inserted is None

    unrelated = _AsyncScopedCollection(
        {"_id": "cache-key", "seed_source": "customer", "seed_scope": SEED_SCOPE}
    )
    with pytest.raises(RuntimeError, match="not owned"):
        await replace_scoped_document(
            unrelated,
            {
                "_id": "cache-key",
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
            },
            seed_source=SEED_SOURCE,
            seed_scope=SEED_SCOPE,
        )

    assert unrelated.replaced is None
    assert unrelated.inserted is None

    owned = _AsyncScopedCollection(
        {"_id": "cache-key", "seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
    )
    document = {
        "_id": "cache-key",
        "seed_source": SEED_SOURCE,
        "seed_scope": SEED_SCOPE,
    }
    await replace_scoped_document(
        owned,
        document,
        seed_source=SEED_SOURCE,
        seed_scope=SEED_SCOPE,
    )

    assert owned.replaced == (
        {
            "_id": "cache-key",
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
        },
        document,
        False,
    )

    new_row = _AsyncScopedCollection()
    await replace_scoped_document(
        new_row,
        document,
        seed_source=SEED_SOURCE,
        seed_scope=SEED_SCOPE,
    )
    assert new_row.inserted == document

    raced = _AsyncScopedCollection(insert_error=DuplicateKeyError("race"))
    with pytest.raises(RuntimeError, match="collided during insertion"):
        await replace_scoped_document(
            raced,
            document,
            seed_source=SEED_SOURCE,
            seed_scope=SEED_SCOPE,
        )
    assert raced.replaced is None


def test_marketing_seed_uses_a_distinct_deterministic_id_namespace():
    source = _required_text(SEEDER)

    assert '"64f' not in source


def test_marketing_guest_tokens_use_the_capture_scope_not_a_wedding_suffix():
    source = _required_text(SEEDER)

    assert 'f"{MARKETING_CAPTURE_SEED_SCOPE}:{wedding_id}:token"' in source


def test_marketing_capture_driver_pins_the_safe_guest_card_fixture():
    source = _required_text(DRIVER)

    for expected_contract in (
        '"attending": []',
        '"name": "Priya Shah"',
        '"group_id": "friends"',
        '"plus_one_allowed": True',
        '"number_of_plus_ones_allowed": 1',
        '"attending": ["traditional"]',
        '"dietary": "Vegetarian"',
        "Priya Shah card must have exactly one submitted plus-one",
    ):
        assert expected_contract in source


def test_marketing_seed_does_not_reuse_legacy_string_document_ids():
    source = _required_text(SEEDER)

    for forbidden in (
        '"guest_memory_pending_',
        '"guest_memory_kept_',
        '"guest_memory_rejected_',
        '"form_demo_couple_intake"',
    ):
        assert forbidden not in source
    assert '"marketing_capture_memory_' in source


def test_cleanup_targets_the_full_seeded_domain_graph_and_asserts_no_survivors():
    source = _required_text(CLEANUP)
    required_collections = {
        "users",
        "user_subscriptions",
        "team_members",
        "weddings",
        "couple_users",
        "couple_messages",
        "guests",
        "rsvps",
        "plus_ones",
        "tables",
        "seating_layouts",
        "planner_tasks",
        "inbound_emails",
        "email_logs",
        "support_tickets",
        "vendor_profiles",
        "vendor_assignments",
        "vendor_contracts",
        "vendor_contract_activities",
        "vendor_payment_milestones",
        "vendor_quotes",
        "budget_categories",
        "payment_records",
        "contracts",
        "scheduled_payments",
        "packages",
        "forms",
        "form_responses",
        "form_distributions",
        "form_submissions",
        "guest_media_assets",
        "guest_media_exports",
    }

    missing = sorted(name for name in required_collections if name not in source)
    assert missing == [], f"cleanup is missing seeded collections: {missing}"
    assert "assert_no_seeded_survivors" in source
    assert "seed_source" in source and "seed_scope" in source
    assert "fixture_is_owned" in source
