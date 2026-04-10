#!/usr/bin/env python3
"""Checked Coolify API helper for image-based deployments."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT = 30
VERIFY_ATTEMPTS = 5
VERIFY_DELAY_SECONDS = 2

# Based on the documented Coolify application update schema. We preserve the
# current values for these writable fields when a minimal image-only PATCH is
# rejected by the API, then override the image reference explicitly.
PATCH_FIELD_ALLOWLIST = {
    "project_uuid",
    "server_uuid",
    "environment_name",
    "github_app_uuid",
    "git_repository",
    "git_branch",
    "ports_exposes",
    "destination_uuid",
    "build_pack",
    "name",
    "description",
    "domains",
    "git_commit_sha",
    "docker_registry_image_name",
    "docker_registry_image_tag",
    "is_static",
    "is_spa",
    "is_auto_deploy_enabled",
    "is_force_https_enabled",
    "install_command",
    "build_command",
    "start_command",
    "ports_mappings",
    "base_directory",
    "publish_directory",
    "health_check_enabled",
    "health_check_path",
    "health_check_port",
    "health_check_host",
    "health_check_method",
    "health_check_return_code",
    "health_check_scheme",
    "health_check_response_text",
    "health_check_interval",
    "health_check_timeout",
    "health_check_retries",
    "health_check_start_period",
    "limits_memory",
    "limits_memory_swap",
    "limits_memory_swappiness",
    "limits_memory_reservation",
    "limits_cpus",
    "limits_cpuset",
    "limits_cpu_shares",
    "custom_labels",
    "custom_docker_run_options",
    "post_deployment_command",
    "post_deployment_command_container",
    "pre_deployment_command",
    "pre_deployment_command_container",
    "manual_webhook_secret_github",
    "manual_webhook_secret_gitlab",
    "manual_webhook_secret_bitbucket",
    "manual_webhook_secret_gitea",
    "redirect",
    "instant_deploy",
    "dockerfile",
    "dockerfile_location",
    "docker_compose_location",
    "docker_compose_custom_start_command",
    "docker_compose_custom_build_command",
    "docker_compose_domains",
    "docker_compose",
    "docker_compose_raw",
    "docker_compose_custom_url",
    "docker_compose_custom_build_command",
    "docker_compose_custom_start_command",
    "swarm_replicas",
    "swarm_placement_constraints",
    "swarm_labels",
    "swarm_command",
    "swarm_update_config",
    "swarm_rollback_config",
    "swarm_restart_policy",
    "swarm_resources_limits",
    "swarm_resources_reservations",
    "compose_parsing_version",
    "watch_paths",
}


def log(message: str) -> None:
    print(f"[coolify] {message}", flush=True)


def write_github_output(path: str, values: dict[str, str]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def append_summary(path: str | None, message: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"- {message}\n")


@dataclass
class ApiResponse:
    status: int
    text: str
    data: Any

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class CoolifyRequestError(RuntimeError):
    def __init__(self, action: str, response: ApiResponse) -> None:
        self.action = action
        self.response = response
        super().__init__(
            f"{action} failed with HTTP {response.status}: {format_error_body(response)}"
        )


def maybe_json_decode(payload: str) -> Any:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def normalize_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def flatten_messages(value: Any) -> list[str]:
    messages: list[str] = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            messages.append(stripped)
    elif isinstance(value, list):
        for item in value:
            messages.extend(flatten_messages(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            nested = flatten_messages(item)
            if nested:
                messages.append(f"{key}: {'; '.join(nested)}")
    return messages


def format_error_body(response: ApiResponse) -> str:
    if isinstance(response.data, dict):
        messages: list[str] = []
        for key in ("message", "error"):
            messages.extend(flatten_messages(response.data.get(key)))
        messages.extend(flatten_messages(response.data.get("errors")))
        messages.extend(flatten_messages(response.data.get("messages")))
        if messages:
            return " | ".join(messages)

    body = response.text.strip().replace("\n", " ")
    return body[:800] if body else "<empty response body>"


class CoolifyClient:
    def __init__(
        self, base_url: str, token: str, timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> ApiResponse:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
                return ApiResponse(response.status, text, maybe_json_decode(text))
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            return ApiResponse(exc.code, text, maybe_json_decode(text))

    def get_application(self, uuid: str) -> dict[str, Any]:
        response = self.request("GET", f"/api/v1/applications/{uuid}")
        if not response.ok:
            raise CoolifyRequestError(f"Read application {uuid}", response)
        if not isinstance(response.data, dict):
            raise RuntimeError(f"Read application {uuid} returned a non-JSON payload")
        return response.data

    def restart_application(self, uuid: str) -> None:
        response = self.request("GET", f"/api/v1/applications/{uuid}/restart")
        if not response.ok:
            raise CoolifyRequestError(f"Restart application {uuid}", response)
        log(f"Restart requested for application {uuid}")

    def update_application_image(
        self, uuid: str, image_name: str, image_tag: str
    ) -> None:
        minimal_payload = {
            "docker_registry_image_name": image_name,
            "docker_registry_image_tag": image_tag,
        }
        minimal_response = self.request(
            "PATCH", f"/api/v1/applications/{uuid}", body=minimal_payload
        )
        if minimal_response.ok:
            log(f"Updated application {uuid} image reference with minimal PATCH")
        else:
            log(
                "Minimal image-only PATCH was rejected; retrying with a merged payload "
                f"to satisfy Coolify validation ({minimal_response.status})."
            )
            current = self.get_application(uuid)
            merged_payload = build_merged_patch_payload(current, minimal_payload)
            merged_response = self.request(
                "PATCH", f"/api/v1/applications/{uuid}", body=merged_payload
            )
            if not merged_response.ok:
                raise CoolifyRequestError(
                    f"Update application {uuid} image reference", merged_response
                )
            log(
                f"Updated application {uuid} image reference with merged PATCH "
                f"({len(merged_payload)} fields)"
            )

        self.verify_image_reference(uuid, image_name, image_tag)

    def verify_image_reference(
        self, uuid: str, image_name: str, image_tag: str
    ) -> None:
        for attempt in range(1, VERIFY_ATTEMPTS + 1):
            app = self.get_application(uuid)
            stored_name, stored_tag = extract_image_reference(app)
            if stored_name == image_name and stored_tag == image_tag:
                log(
                    f"Verified stored image reference for application {uuid}: "
                    f"{stored_name}:{stored_tag} (attempt {attempt})"
                )
                return
            if attempt < VERIFY_ATTEMPTS:
                time.sleep(VERIFY_DELAY_SECONDS)

        raise RuntimeError(
            "Coolify stored image reference mismatch after update: "
            f"expected {image_name}:{image_tag}, got {stored_name}:{stored_tag}"
        )


def build_merged_patch_payload(
    current_application: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in PATCH_FIELD_ALLOWLIST:
        if key in current_application and current_application[key] is not None:
            payload[key] = current_application[key]
    payload.update(overrides)
    return payload


def extract_image_reference(application: dict[str, Any]) -> tuple[str, str]:
    image_name = normalize_string(application.get("docker_registry_image_name"))
    image_tag = normalize_string(application.get("docker_registry_image_tag"))
    return image_name, image_tag


def require_setting(value: str | None, label: str) -> str:
    if value:
        return value
    raise RuntimeError(f"{label} is required")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Checked Coolify API helper")
    parser.add_argument("--base-url", default=os.getenv("COOLIFY_BASE_URL"))
    parser.add_argument("--api-token", default=os.getenv("COOLIFY_API_TOKEN"))

    subparsers = parser.add_subparsers(dest="command", required=True)

    image_ref = subparsers.add_parser(
        "image-ref", help="Read the current image reference"
    )
    image_ref.add_argument("--uuid", required=True)
    image_ref.add_argument("--github-output")
    image_ref.add_argument("--summary-file")

    set_image = subparsers.add_parser(
        "set-image", help="Update and verify the image reference"
    )
    set_image.add_argument("--uuid", required=True)
    set_image.add_argument("--image-name", required=True)
    set_image.add_argument("--image-tag", required=True)
    set_image.add_argument("--summary-file")

    restart = subparsers.add_parser("restart", help="Restart an application")
    restart.add_argument("--uuid", required=True)
    restart.add_argument("--summary-file")

    return parser


def handle_image_ref(client: CoolifyClient, args: argparse.Namespace) -> int:
    application = client.get_application(args.uuid)
    image_name, image_tag = extract_image_reference(application)
    if not image_name:
        raise RuntimeError(
            f"Application {args.uuid} has an empty docker_registry_image_name"
        )
    if not image_tag:
        raise RuntimeError(
            f"Application {args.uuid} has an empty docker_registry_image_tag"
        )

    log(
        f"Current image reference for application {args.uuid}: {image_name}:{image_tag}"
    )
    append_summary(
        args.summary_file,
        f"Current Coolify image reference for `{args.uuid}` is `{image_name}:{image_tag}`.",
    )
    if args.github_output:
        write_github_output(args.github_output, {"name": image_name, "tag": image_tag})
    return 0


def handle_set_image(client: CoolifyClient, args: argparse.Namespace) -> int:
    client.update_application_image(args.uuid, args.image_name, args.image_tag)
    append_summary(
        args.summary_file,
        f"Updated Coolify application `{args.uuid}` to `{args.image_name}:{args.image_tag}` and verified the stored tag.",
    )
    return 0


def handle_restart(client: CoolifyClient, args: argparse.Namespace) -> int:
    client.restart_application(args.uuid)
    append_summary(
        args.summary_file, f"Restart requested for Coolify application `{args.uuid}`."
    )
    return 0


def main() -> int:
    args = build_parser().parse_args()
    base_url = require_setting(args.base_url, "COOLIFY_BASE_URL / --base-url")
    api_token = require_setting(args.api_token, "COOLIFY_API_TOKEN / --api-token")
    client = CoolifyClient(base_url=base_url, token=api_token)

    if args.command == "image-ref":
        return handle_image_ref(client, args)
    if args.command == "set-image":
        return handle_set_image(client, args)
    if args.command == "restart":
        return handle_restart(client, args)

    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure surface
        print(f"[coolify] ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
