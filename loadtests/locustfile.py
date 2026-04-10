"""
Read-only Locust scenarios for The Special Wedding.

This harness is intentionally scoped to safe, repeatable flows:
- Public wedding landing and gallery pages
- Planner authentication plus read-heavy dashboard APIs
- Couple authentication plus read-heavy portal APIs

It explicitly avoids write-heavy or side-effecting endpoints such as:
- OTP generation/verification that could hit Twilio or email providers
- RSVP submission
- Reminder sends
- Package sending / contract creation
- Contract signing or payment mutation
"""

from __future__ import annotations

import os
from typing import Any

from locust import HttpUser, between, task
from locust.exception import StopUser

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional helper for local use

    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


load_dotenv()


REQUEST_TIMEOUT_SECONDS = float(os.getenv("LOCUST_REQUEST_TIMEOUT_SECONDS", "15"))


def _env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


API_HOST = (
    _env_first(
        "LOCUST_API_HOST", "NEXT_PUBLIC_API_BASE_URL", default="http://localhost:8000"
    )
    or ""
).rstrip("/")
FRONTEND_HOST = (
    _env_first("LOCUST_FRONTEND_HOST", "FRONTEND_URL", default="http://localhost:3000")
    or ""
).rstrip("/")

WEDDING_SLUG = (
    _env_first("LOCUST_WEDDING_SLUG", default="james-and-mel") or "james-and-mel"
)
WEDDING_ID_OVERRIDE = _env_first("LOCUST_WEDDING_ID")

PLANNER_BEARER_TOKEN = _env_first("LOCUST_PLANNER_BEARER_TOKEN")
COUPLE_BEARER_TOKEN = _env_first("LOCUST_COUPLE_BEARER_TOKEN")

PLANNER_EMAIL = (
    _env_first("LOCUST_PLANNER_EMAIL", "TEST_PLANNER_WITH_PACKAGE_EMAIL", default="")
    or ""
)
PLANNER_PASSWORD = (
    _env_first(
        "LOCUST_PLANNER_PASSWORD", "TEST_PLANNER_WITH_PACKAGE_PASSWORD", default=""
    )
    or ""
)
COUPLE_EMAIL = _env_first("LOCUST_COUPLE_EMAIL", "TEST_COUPLE_EMAIL", default="") or ""
COUPLE_PASSWORD = (
    _env_first("LOCUST_COUPLE_PASSWORD", "TEST_COUPLE_PASSWORD", default="") or ""
)

if not PLANNER_BEARER_TOKEN:
    if not PLANNER_EMAIL or not PLANNER_PASSWORD:
        raise RuntimeError(
            "Planner credentials are required unless LOCUST_PLANNER_BEARER_TOKEN is set"
        )

if not COUPLE_BEARER_TOKEN:
    if not COUPLE_EMAIL or not COUPLE_PASSWORD:
        raise RuntimeError(
            "Couple credentials are required unless LOCUST_COUPLE_BEARER_TOKEN is set"
        )


class JsonApiUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        name: str,
        expected_statuses: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> Any:
        with self.client.request(
            method,
            path,
            name=name,
            timeout=REQUEST_TIMEOUT_SECONDS,
            catch_response=True,
            **kwargs,
        ) as response:
            if response.status_code not in expected_statuses:
                response.failure(f"{method} {path} returned {response.status_code}")
                return None
            try:
                return response.json()
            except ValueError:
                response.failure(f"{method} {path} did not return JSON")
                return None

    def _request_ok(
        self,
        method: str,
        path: str,
        *,
        name: str,
        expected_statuses: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> None:
        with self.client.request(
            method,
            path,
            name=name,
            timeout=REQUEST_TIMEOUT_SECONDS,
            catch_response=True,
            **kwargs,
        ) as response:
            if response.status_code not in expected_statuses:
                response.failure(f"{method} {path} returned {response.status_code}")


class PlannerApiUser(JsonApiUser):
    """
    Simulates a planner repeatedly reading the main operational surfaces.
    """

    host = API_HOST
    weight = 2

    def on_start(self) -> None:
        if PLANNER_BEARER_TOKEN:
            self.auth_headers = {"Authorization": f"Bearer {PLANNER_BEARER_TOKEN}"}
        else:
            login = self._request_json(
                "POST",
                "/admin/token",
                name="POST /admin/token",
                json={"email": PLANNER_EMAIL, "password": PLANNER_PASSWORD},
            )
            if not login or "access_token" not in login:
                raise StopUser("Planner login failed")

            self.auth_headers = {"Authorization": f"Bearer {login['access_token']}"}
        self.wedding_id = WEDDING_ID_OVERRIDE or self._discover_wedding_id()
        if not self.wedding_id:
            raise StopUser("Unable to discover a planner wedding id for load testing")

    def _discover_wedding_id(self) -> str | None:
        data = self._request_json(
            "GET",
            "/admin/planner/weddings?page=1&limit=200",
            name="GET /admin/planner/weddings",
            headers=self.auth_headers,
        )
        if not data:
            return None

        weddings = data if isinstance(data, list) else data.get("weddings", [])
        for wedding in weddings:
            if wedding.get("slug") == WEDDING_SLUG:
                return wedding.get("_id") or wedding.get("id")
        if weddings:
            return weddings[0].get("_id") or weddings[0].get("id")
        return None

    @task(2)
    def profile(self) -> None:
        profile = self._request_json(
            "GET",
            "/admin/profile",
            name="GET /admin/profile",
            headers=self.auth_headers,
        )
        if profile and profile.get("email") != PLANNER_EMAIL:
            raise StopUser(
                "Planner profile response does not match configured planner email"
            )

    @task(5)
    def weddings(self) -> None:
        self._request_ok(
            "GET",
            "/admin/planner/weddings?page=1&limit=50",
            name="GET /admin/planner/weddings",
            headers=self.auth_headers,
        )

    @task(4)
    def guests(self) -> None:
        self._request_ok(
            "GET",
            f"/admin/guests?wedding_id={self.wedding_id}&page=1&limit=50",
            name="GET /admin/guests",
            headers=self.auth_headers,
        )

    @task(1)
    def packages(self) -> None:
        self._request_ok(
            "GET",
            "/admin/packages?limit=20&skip=0",
            name="GET /admin/packages",
            headers=self.auth_headers,
        )

    @task(1)
    def contracts(self) -> None:
        self._request_ok(
            "GET",
            "/admin/contracts?limit=20&skip=0",
            name="GET /admin/contracts",
            headers=self.auth_headers,
        )


class CouplePortalApiUser(JsonApiUser):
    """
    Simulates a couple reading the authenticated portal.
    """

    host = API_HOST
    weight = 1

    def on_start(self) -> None:
        if COUPLE_BEARER_TOKEN:
            self.auth_headers = {"Authorization": f"Bearer {COUPLE_BEARER_TOKEN}"}
            return

        login = self._request_json(
            "POST",
            "/couple/login",
            name="POST /couple/login",
            json={"email": COUPLE_EMAIL, "password": COUPLE_PASSWORD},
        )
        if not login or "access_token" not in login:
            raise StopUser("Couple login failed")

        self.auth_headers = {"Authorization": f"Bearer {login['access_token']}"}

    @task(2)
    def profile(self) -> None:
        profile = self._request_json(
            "GET",
            "/couple/profile",
            name="GET /couple/profile",
            headers=self.auth_headers,
        )
        if profile and profile.get("email") != COUPLE_EMAIL:
            raise StopUser(
                "Couple profile response does not match configured couple email"
            )

    @task(4)
    def dashboard(self) -> None:
        self._request_ok(
            "GET",
            "/couple/portal/dashboard",
            name="GET /couple/portal/dashboard",
            headers=self.auth_headers,
        )

    @task(3)
    def events(self) -> None:
        self._request_ok(
            "GET",
            "/couple/portal/events",
            name="GET /couple/portal/events",
            headers=self.auth_headers,
        )


class PublicWeddingPageUser(HttpUser):
    """
    Simulates guest traffic on the public-facing wedding pages.
    """

    host = FRONTEND_HOST
    weight = 6
    wait_time = between(1, 4)

    @task(5)
    def wedding_landing_page(self) -> None:
        with self.client.get(
            f"/{WEDDING_SLUG}",
            name="GET /:slug",
            timeout=REQUEST_TIMEOUT_SECONDS,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"Wedding landing page returned {response.status_code}"
                )
                return
            if "text/html" not in response.headers.get("content-type", ""):
                response.failure("Wedding landing page did not return HTML")

    @task(2)
    def wedding_gallery_page(self) -> None:
        with self.client.get(
            f"/{WEDDING_SLUG}/gallery",
            name="GET /:slug/gallery",
            timeout=REQUEST_TIMEOUT_SECONDS,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"Wedding gallery page returned {response.status_code}"
                )
                return
            if "text/html" not in response.headers.get("content-type", ""):
                response.failure("Wedding gallery page did not return HTML")
