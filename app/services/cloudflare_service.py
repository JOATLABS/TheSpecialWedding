"""Strict Cloudflare for SaaS custom-hostname client.

The client never fabricates provider success. Both the API token and zone ID
must be explicitly configured, and every provider/transport/response failure is
reported through a structured exception that callers can persist for retry.
"""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import quote

import httpx

from app.core.settings import settings


class CloudflareServiceError(RuntimeError):
    """A safe, structured Cloudflare operation failure."""

    def __init__(
        self,
        message: str = "Cloudflare operation failed",
        *,
        operation: str = "unknown",
        kind: str = "provider",
        provider_status_code: int | None = None,
        errors: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
    ) -> None:
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.kind = kind
        self.provider_status_code = provider_status_code
        self.errors = tuple(dict(error) for error in errors)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": "cloudflare",
            "operation": self.operation,
            "kind": self.kind,
            "provider_status_code": self.provider_status_code,
            "errors": [dict(error) for error in self.errors],
        }


class CloudflareService:
    """Small async client for Cloudflare custom-hostname lifecycle calls."""

    API_ROOT = "https://api.cloudflare.com/client/v4"

    def __init__(
        self,
        *,
        api_token: str | None = None,
        zone_id: str | None = None,
        http_client: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_token = (
            settings.cloudflare_api_token if api_token is None else api_token
        )
        self._zone_id = settings.cloudflare_zone_id if zone_id is None else zone_id
        self._http_client = http_client
        self._timeout_seconds = timeout_seconds

    def _require_configuration(self, operation: str) -> tuple[str, str]:
        token = (self._api_token or "").strip()
        zone_id = (self._zone_id or "").strip()
        if not token or not zone_id:
            raise CloudflareServiceError(
                "Cloudflare custom-hostname credentials are not configured",
                operation=operation,
                kind="configuration",
                errors=(
                    {
                        "code": "cloudflare_not_configured",
                        "message": "CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID are required",
                    },
                ),
            )
        if any(character.isspace() for character in zone_id) or "/" in zone_id:
            raise CloudflareServiceError(
                "Cloudflare zone configuration is invalid",
                operation=operation,
                kind="configuration",
                errors=(
                    {
                        "code": "invalid_cloudflare_zone",
                        "message": "CLOUDFLARE_ZONE_ID must be a zone identifier",
                    },
                ),
            )
        return token, zone_id

    @staticmethod
    def _provider_errors(payload: object) -> tuple[dict[str, Any], ...]:
        if not isinstance(payload, dict) or not isinstance(payload.get("errors"), list):
            return (
                {
                    "code": "invalid_provider_response",
                    "message": "Cloudflare returned an invalid response",
                },
            )

        normalized: list[dict[str, Any]] = []
        for error in payload["errors"]:
            if isinstance(error, dict):
                normalized.append(
                    {
                        "code": error.get("code", "cloudflare_error"),
                        "message": str(
                            error.get("message") or "Cloudflare request failed"
                        ),
                    }
                )
        return tuple(normalized) or (
            {"code": "cloudflare_error", "message": "Cloudflare request failed"},
        )

    async def _request(
        self,
        method: str,
        operation: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        expect_list: bool = False,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        token, zone_id = self._require_configuration(operation)
        url = f"{self.API_ROOT}/zones/{zone_id}/custom_hostnames{path}"
        request_kwargs: dict[str, Any] = {
            "headers": {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            "timeout": self._timeout_seconds,
        }
        if json is not None:
            request_kwargs["json"] = json
        if params is not None:
            request_kwargs["params"] = params

        try:
            if self._http_client is not None:
                response = await self._http_client.request(
                    method, url, **request_kwargs
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.request(method, url, **request_kwargs)
        except httpx.RequestError as exc:
            raise CloudflareServiceError(
                "Cloudflare request failed",
                operation=operation,
                kind="transport",
                errors=(
                    {
                        "code": "cloudflare_transport_error",
                        "message": "Cloudflare could not be reached",
                    },
                ),
            ) from exc

        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise CloudflareServiceError(
                "Cloudflare returned an unreadable response",
                operation=operation,
                kind="response",
                provider_status_code=response.status_code,
                errors=(
                    {
                        "code": "invalid_provider_response",
                        "message": "Cloudflare returned non-JSON content",
                    },
                ),
            ) from exc

        if (
            not response.is_success
            or not isinstance(payload, dict)
            or payload.get("success") is not True
        ):
            raise CloudflareServiceError(
                "Cloudflare rejected the custom-hostname operation",
                operation=operation,
                kind="provider",
                provider_status_code=response.status_code,
                errors=self._provider_errors(payload),
            )

        result = payload.get("result")
        if expect_list:
            if not isinstance(result, list) or any(
                not isinstance(item, dict) for item in result
            ):
                raise CloudflareServiceError(
                    "Cloudflare returned an invalid custom-hostname list",
                    operation=operation,
                    kind="response",
                    provider_status_code=response.status_code,
                    errors=(
                        {
                            "code": "invalid_provider_result",
                            "message": "Cloudflare response did not contain a list result",
                        },
                    ),
                )
            return cast(list[dict[str, Any]], result)
        if not isinstance(result, dict):
            raise CloudflareServiceError(
                "Cloudflare returned an invalid custom-hostname result",
                operation=operation,
                kind="response",
                provider_status_code=response.status_code,
                errors=(
                    {
                        "code": "invalid_provider_result",
                        "message": "Cloudflare response did not contain an object result",
                    },
                ),
            )
        return result

    async def create_custom_hostname(self, hostname: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request(
                "POST",
                "create_custom_hostname",
                "",
                json={
                    "hostname": hostname,
                    "ssl": {
                        "method": "txt",
                        "type": "dv",
                        "settings": {"min_tls_version": "1.2"},
                    },
                },
            ),
        )

    async def get_custom_hostname(self, hostname_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request(
                "GET",
                "get_custom_hostname",
                f"/{quote(hostname_id, safe='')}",
            ),
        )

    async def delete_custom_hostname(self, hostname_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request(
                "DELETE",
                "delete_custom_hostname",
                f"/{quote(hostname_id, safe='')}",
            ),
        )

    async def list_custom_hostnames(self, hostname: str) -> list[dict[str, Any]]:
        """List provider mappings filtered by an exact normalized hostname."""

        return cast(
            list[dict[str, Any]],
            await self._request(
                "GET",
                "list_custom_hostnames",
                "",
                params={"hostname": hostname},
                expect_list=True,
            ),
        )

    # Transitional aliases keep older internal callsites source-compatible
    # while preserving the strict failure contract above.
    async def add_custom_hostname(self, hostname: str) -> dict[str, Any]:
        return await self.create_custom_hostname(hostname)

    async def get_custom_hostname_status(self, hostname_id: str) -> dict[str, Any]:
        return await self.get_custom_hostname(hostname_id)
