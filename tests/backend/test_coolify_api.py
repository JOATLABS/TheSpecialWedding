from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "deploy" / "coolify_api.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location("coolify_api", MODULE_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
coolify_api = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = coolify_api
MODULE_SPEC.loader.exec_module(coolify_api)


def test_build_merged_patch_payload_preserves_allowed_fields_and_overrides_image():
    current = {
        "name": "backend-staging",
        "project_uuid": "project-123",
        "ports_exposes": "8000",
        "docker_registry_image_name": "ghcr.io/lopewale/wedding-app-backend",
        "docker_registry_image_tag": "c08446",
        "status": "exited",
    }

    payload = coolify_api.build_merged_patch_payload(
        current,
        {
            "docker_registry_image_name": "ghcr.io/lopewale/wedding-app-backend",
            "docker_registry_image_tag": "6cce451",
        },
    )

    assert payload["name"] == "backend-staging"
    assert payload["project_uuid"] == "project-123"
    assert payload["ports_exposes"] == "8000"
    assert payload["docker_registry_image_tag"] == "6cce451"
    assert "status" not in payload


def test_update_application_image_retries_with_merged_payload_and_verifies_stored_tag(
    monkeypatch,
):
    client = coolify_api.CoolifyClient("https://coolify.example.com", "token")
    patch_bodies: list[dict[str, object]] = []
    patch_statuses = iter(
        [
            coolify_api.ApiResponse(
                422, '{"message":"validation failed"}', {"message": "validation failed"}
            ),
            coolify_api.ApiResponse(200, '{"ok":true}', {"ok": True}),
        ]
    )
    current_apps = iter(
        [
            {
                "name": "backend-staging",
                "project_uuid": "project-123",
                "ports_exposes": "8000",
                "docker_registry_image_name": "ghcr.io/lopewale/wedding-app-backend",
                "docker_registry_image_tag": "c08446",
            },
            {
                "name": "backend-staging",
                "project_uuid": "project-123",
                "ports_exposes": "8000",
                "docker_registry_image_name": "ghcr.io/lopewale/wedding-app-backend",
                "docker_registry_image_tag": "6cce451",
            },
        ]
    )

    def fake_request(method: str, path: str, body=None):
        assert method == "PATCH"
        assert path == "/api/v1/applications/backend-uuid"
        patch_bodies.append(body)
        return next(patch_statuses)

    def fake_get_application(uuid: str):
        assert uuid == "backend-uuid"
        return next(current_apps)

    monkeypatch.setattr(client, "request", fake_request)
    monkeypatch.setattr(client, "get_application", fake_get_application)

    client.update_application_image(
        "backend-uuid",
        "ghcr.io/lopewale/wedding-app-backend",
        "6cce451",
    )

    assert patch_bodies[0] == {
        "docker_registry_image_name": "ghcr.io/lopewale/wedding-app-backend",
        "docker_registry_image_tag": "6cce451",
    }
    assert patch_bodies[1]["name"] == "backend-staging"
    assert patch_bodies[1]["project_uuid"] == "project-123"
    assert patch_bodies[1]["docker_registry_image_tag"] == "6cce451"
