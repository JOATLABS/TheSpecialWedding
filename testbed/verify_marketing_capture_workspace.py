#!/usr/bin/env python3
"""Reset, seed, verify, and expose browser checks for Phase 1 captures."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import requests
from bson import ObjectId
from PIL import Image, UnidentifiedImageError
from pymongo.database import Database
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testbed.cleanup_marketing_capture_workspace_state import (  # noqa: E402
    SEED_SCOPE,
    SEED_SOURCE,
    _load_database,
    cleanup_marketing_capture_workspace_state,
)
from testbed import testbed as testbed_cli  # noqa: E402
from app.models.vendor_contracts import (  # noqa: E402
    VendorContractActivityItem,
    VendorContractActivityType,
)
from app.constants.marketing_capture_media import (  # noqa: E402
    MARKETING_CAPTURE_GALLERY_ITEMS,
    MARKETING_CAPTURE_GALLERY_URLS,
)

SETUP_SMOKE_ACCOUNTS = ROOT / "scripts" / "setup_smoke_accounts.py"
RICH_WORKSPACE_SEEDER = (
    ROOT / "scripts" / "demo-videos" / "seed-demo-video-workspace.py"
)
DEFAULT_ANCHOR_AT = "2026-07-12T10:00:00"
PLANNER_EMAIL = "amina@studio.thespecialwedding.io"
PLANNER_PASSWORD = "CapturePlanner2026!"  # pragma: allowlist secret
PLANNER_USER_ID = "user_marketing_capture_amina_cole"
TEAM_EMAIL = "maya@studio.thespecialwedding.io"
TEAM_PASSWORD = "CaptureTeam2026!"  # pragma: allowlist secret
TEAM_MEMBER_ID = "67c700000000000000000001"
TEAM_USER_ID = "67c700000000000000000002"
COUPLE_EMAIL = "sofia.daniel@couples.thespecialwedding.io"
COUPLE_PASSWORD = "CaptureCouple2026!"  # pragma: allowlist secret
COUPLE_ID = "couple_marketing_capture_sofia_daniel"
PRIMARY_WEDDING_ID = "wedding_marketing_capture_sofia_daniel"
PRIMARY_SLUG = "sofia-and-daniel"
SECONDARY_WEDDING_ID = "wedding_marketing_capture_avery_morgan"
SECONDARY_SLUG = "avery-and-morgan"
DEMO_KB_ARTICLE_ID = ObjectId("67c900000000000000000001")
DEMO_KB_ARTICLE_SLUG = "planner-command-center-first-steps"
CONTROLLED_IDENTITY_DOMAIN = "thespecialwedding.io"
RESERVED_IDENTITY_DOMAINS = frozenset({"example.com", "example.net", "example.org"})
RESERVED_IDENTITY_SUFFIXES = (".example", ".invalid", ".test")
RESERVED_FICTIONAL_PHONE_PATTERN = re.compile(r"^1?[2-9]\d{2}55501\d{2}$")
FULL_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
MARKETING_CAPTURE_SCENES_PATH = ROOT / "app" / "data" / "marketingCaptureScenes.json"
MARKETING_CAPTURE_SESSIONS = frozenset({"planner", "couple", "public"})
MARKETING_CAPTURE_API_TEXT_FEATURES = frozenset(
    {
        "dashboard",
        "real-time",
        "couple-portal",
        "gallery-management",
        "inbox",
        "budget",
        "forms",
        "team",
    }
)


class _BuildCommitMetaParser(HTMLParser):
    """Collect explicit runtime build identities from a rendered app shell."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.commits: list[str] = []
        self.script_sources: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized_tag = tag.lower()
        attributes = {key.lower(): value for key, value in attrs}
        if normalized_tag == "script":
            source = attributes.get("src")
            if source:
                self.script_sources.append(source)
            return
        if normalized_tag != "meta":
            return
        if attributes.get("name") != "tsw-app-build-commit":
            return
        content = attributes.get("content")
        if content:
            self.commits.append(content)


def assert_setup_namespace_available(database: Database) -> None:
    """Fail before the smoke-account bootstrap can retag a real local record."""

    collision_queries = {
        "users": {
            "$or": [
                {"_id": PLANNER_USER_ID},
                {"_id": ObjectId("67c700000000000000000002")},
                {"email": {"$in": [PLANNER_EMAIL, TEAM_EMAIL]}},
            ]
        },
        "couple_users": {"$or": [{"_id": COUPLE_ID}, {"email": COUPLE_EMAIL}]},
        "team_members": {
            "$or": [
                {"_id": ObjectId("67c700000000000000000001")},
                {"email": TEAM_EMAIL},
            ]
        },
        "user_subscriptions": {"_id": "marketing_capture_signature_subscription"},
        "weddings": {
            "$or": [
                {"_id": {"$in": [PRIMARY_WEDDING_ID, SECONDARY_WEDDING_ID]}},
                {"slug": {"$in": [PRIMARY_SLUG, SECONDARY_SLUG]}},
            ]
        },
        "kb_articles": {
            "$or": [
                {"_id": DEMO_KB_ARTICLE_ID},
                {"slug": DEMO_KB_ARTICLE_SLUG},
            ]
        },
    }
    for collection_name, query in collision_queries.items():
        existing = database[collection_name].find_one(query, {"_id": 1})
        if existing:
            raise RuntimeError(
                f"Dedicated marketing-capture namespace collides in {collection_name}; "
                "refusing to let setup_smoke_accounts overwrite local data."
            )


def _run_python(
    script: Path, *, env: dict[str, str], args: list[str] | None = None
) -> None:
    command = [sys.executable, str(script), *(args or [])]
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _response_redirect_location(response: Any) -> str | None:
    headers = getattr(response, "headers", {}) or {}
    if not hasattr(headers, "items"):
        return None
    return next(
        (
            str(value)
            for key, value in headers.items()
            if str(key).lower() == "location" and value
        ),
        None,
    )


def _require_no_redirect(response: Any, label: str) -> None:
    redirect_location = _response_redirect_location(response)
    _require(
        redirect_location is None,
        f"{label} unexpectedly redirected to {redirect_location}",
    )


def _get_json_readiness(
    url: str,
    *,
    label: str,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> Any:
    """Fetch one readiness payload without allowing redirects or HTML shells."""

    request_kwargs: dict[str, Any] = {
        "timeout": 15,
        "allow_redirects": False,
    }
    if headers is not None:
        request_kwargs["headers"] = headers
    if cookies is not None:
        request_kwargs["cookies"] = cookies
    if params is not None:
        request_kwargs["params"] = params
    try:
        response = requests.get(url, **request_kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f"{label} is unreachable: {exc}") from exc
    _require_no_redirect(response, label)
    _require(
        response.status_code == 200,
        f"{label} returned HTTP {response.status_code}",
    )
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{label} returned invalid JSON") from exc


def require_local_capture_origin(
    value: str,
    *,
    expected_port: int,
    label: str,
) -> str:
    """Accept only the canonical 127.0.0.1 HTTP origin before sending credentials."""

    _require(isinstance(value, str) and bool(value), f"{label} origin is required")
    parsed = urlparse(value)
    try:
        port = parsed.port
        address = ipaddress.ip_address(parsed.hostname or "")
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            f"{label} must be the exact HTTP 127.0.0.1 origin on port {expected_port}"
        ) from exc

    _require(
        parsed.scheme == "http"
        and address == ipaddress.ip_address("127.0.0.1")
        and port == expected_port
        and parsed.username is None
        and parsed.password is None
        and parsed.path == ""
        and parsed.params == ""
        and parsed.query == ""
        and parsed.fragment == "",
        f"{label} must be the exact HTTP 127.0.0.1 origin on port {expected_port} "
        "with no credentials, path, query, or fragment",
    )
    return value


def verify_frontend_capture_runtime(frontend_url: str) -> None:
    """Require the canonical tmux frontend to be Next start running on Node 22."""

    frontend_origin = require_local_capture_origin(
        frontend_url,
        expected_port=3100,
        label="Marketing capture frontend",
    )
    capture_runtime = SimpleNamespace(
        session_name=testbed_cli.MARKETING_CAPTURE_SESSION_NAME,
        frontend_origin=frontend_origin,
        frontend_node_env=None,
    )
    _require(
        testbed_cli.service_is_ready(
            capture_runtime,
            testbed_cli.FRONTEND_WINDOW,
        ),
        "Marketing capture frontend must be the canonical tmux Next start under "
        "Node 22 before reset, seed, verification, or capture",
    )


def _load_marketing_capture_contract() -> tuple[
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
]:
    """Load the shared scene and immutable fixture-media capture contract."""

    try:
        payload = json.loads(MARKETING_CAPTURE_SCENES_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Unable to load app/data/marketingCaptureScenes.json"
        ) from exc

    _require(
        isinstance(payload, dict) and payload.get("schemaVersion") == 1,
        "Marketing capture scene contract must use schemaVersion 1",
    )
    scenes = payload.get("scenes")
    _require(
        isinstance(scenes, list) and len(scenes) == 17,
        "Marketing capture scene contract must contain exactly 17 scenes",
    )
    required_scene_fields = {
        "featureId",
        "session",
        "route",
        "title",
        "expectation",
        "expectedVisibleText",
        "safeInteraction",
    }
    feature_ids: set[str] = set()
    normalized_scenes: list[dict[str, Any]] = []
    for scene in scenes:
        _require(
            isinstance(scene, dict) and set(scene) == required_scene_fields,
            "Each marketing capture scene must declare the canonical scene fields",
        )
        for field in (
            "featureId",
            "route",
            "title",
            "expectation",
            "expectedVisibleText",
        ):
            _require(
                isinstance(scene[field], str) and bool(scene[field].strip()),
                f"Marketing capture scene field {field} must be non-empty",
            )
        _require(
            scene["session"] in MARKETING_CAPTURE_SESSIONS,
            f"Unknown marketing capture session: {scene['session']!r}",
        )
        _require(
            scene["route"].startswith("/") and not scene["route"].startswith("//"),
            f"Marketing capture route must be application-relative: {scene['route']!r}",
        )
        _require(
            scene["safeInteraction"] is None
            or (
                isinstance(scene["safeInteraction"], str)
                and bool(scene["safeInteraction"].strip())
            ),
            "Marketing capture safeInteraction must be null or non-empty text",
        )
        _require(
            scene["featureId"] not in feature_ids,
            f"Duplicate marketing capture featureId: {scene['featureId']}",
        )
        feature_ids.add(scene["featureId"])
        normalized_scenes.append(dict(scene))

    gallery_assets = payload.get("galleryAssets")
    _require(
        isinstance(gallery_assets, list) and bool(gallery_assets),
        "Marketing capture contract must declare galleryAssets",
    )
    normalized_gallery_assets: dict[str, dict[str, Any]] = {}
    for asset in gallery_assets:
        _require(
            isinstance(asset, dict)
            and set(asset) == {"path", "sha256", "width", "height"},
            "Each marketing capture gallery asset must declare path, hash, and size",
        )
        path = asset["path"]
        _require(
            isinstance(path, str)
            and path.startswith("/demo-gallery/")
            and path.endswith(".webp"),
            f"Marketing capture gallery path is invalid: {path!r}",
        )
        _require(
            isinstance(asset["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]) is not None,
            f"Marketing capture gallery hash is invalid: {path}",
        )
        _require(
            asset["width"] == 1600 and asset["height"] == 1000,
            f"Marketing capture gallery dimensions must be 1600x1000: {path}",
        )
        _require(
            path not in normalized_gallery_assets,
            f"Duplicate marketing capture gallery path: {path}",
        )
        normalized_gallery_assets[path] = dict(asset)

    _require(
        set(normalized_gallery_assets) == MARKETING_CAPTURE_GALLERY_URLS,
        "Canonical gallery hashes and seeded gallery URLs have drifted",
    )
    return tuple(normalized_scenes), normalized_gallery_assets


(
    MARKETING_CAPTURE_E2E_CHECKPOINTS,
    MARKETING_CAPTURE_GALLERY_ASSET_CONTRACT,
) = _load_marketing_capture_contract()


def require_clean_capture_checkout() -> str:
    """Fail before fixture mutation or capture unless HEAD is clean and exact."""

    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Unable to verify that the marketing-capture checkout is clean"
        ) from exc

    dirty_paths = status.stdout.strip()
    _require(
        not dirty_paths,
        "Marketing capture requires a clean checkout before reset, seed, or "
        f"capture; git reported:\n{dirty_paths}",
    )

    try:
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Unable to resolve the marketing-capture checkout HEAD"
        ) from exc

    _require(
        FULL_GIT_COMMIT_PATTERN.fullmatch(head) is not None,
        f"Marketing capture requires a full 40-character git HEAD; got {head!r}",
    )
    return head


def _identity_hostname_is_safe(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if not normalized:
        return False
    if normalized == CONTROLLED_IDENTITY_DOMAIN or normalized.endswith(
        f".{CONTROLLED_IDENTITY_DOMAIN}"
    ):
        return True
    if any(
        normalized == domain or normalized.endswith(f".{domain}")
        for domain in RESERVED_IDENTITY_DOMAINS
    ):
        return True
    return normalized.endswith(RESERVED_IDENTITY_SUFFIXES)


def _identity_field_kind(key: str) -> str | None:
    normalized = key.lower()
    if (
        normalized == "email"
        or normalized.endswith("_email")
        or normalized.endswith("_emails")
    ):
        return "email"
    if (
        normalized == "phone"
        or normalized.endswith("_phone")
        or normalized.endswith("_phone_number")
    ):
        return "phone"
    if normalized == "phone_numbers" or normalized.endswith("_phone_numbers"):
        return "phone"
    return None


def _validate_seeded_identity_document(document: Any, *, path: str) -> None:
    """Reject real-world contact identities anywhere in one scoped fixture."""

    def visit(value: Any, *, value_path: str, field_kind: str | None = None) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(
                    child,
                    value_path=f"{value_path}.{key}",
                    field_kind=_identity_field_kind(str(key)),
                )
            return
        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(
                    child,
                    value_path=f"{value_path}[{index}]",
                    field_kind=field_kind,
                )
            return
        if value is None or isinstance(value, (bool, int, float)):
            return
        if not isinstance(value, str):
            return

        normalized = value.strip()
        if not normalized:
            return
        if field_kind == "phone":
            digits = re.sub(r"\D", "", normalized)
            _require(
                RESERVED_FICTIONAL_PHONE_PATTERN.fullmatch(digits) is not None,
                f"{value_path} must use the NANP reserved fictional 555-0100 "
                f"through 555-0199 range; got {value!r}",
            )

        looks_like_email = field_kind == "email" or (
            normalized.count("@") == 1
            and " " not in normalized
            and not normalized.startswith(("http://", "https://"))
        )
        if looks_like_email:
            local_part, separator, domain = normalized.rpartition("@")
            _require(
                bool(local_part and separator and _identity_hostname_is_safe(domain)),
                f"{value_path} email must use a controlled or reserved fictional "
                f"domain; got {value!r}",
            )

        if normalized.startswith(("http://", "https://")):
            hostname = urlparse(normalized).hostname or ""
            _require(
                _identity_hostname_is_safe(hostname),
                f"{value_path} hostname must use a controlled or reserved fictional "
                f"domain; got {value!r}",
            )

    visit(document, value_path=path)


def _validate_vendor_contract_activity_api_shape(
    activity: dict[str, Any],
) -> VendorContractActivityItem:
    """Validate one stored activity through the endpoint response schema."""

    payload = {
        **activity,
        "id": str(activity.get("_id") or activity.get("id") or ""),
        "contract_id": str(activity.get("contract_id") or ""),
        "root_contract_id": str(activity.get("root_contract_id") or ""),
    }
    try:
        return VendorContractActivityItem.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError(
            f"Seeded contract activity is not API-compatible: {payload['id']}: {exc}"
        ) from exc


def _login(backend_url: str, endpoint: str, email: str, password: str) -> str:
    backend_origin = require_local_capture_origin(
        backend_url,
        expected_port=8000,
        label="Marketing capture backend",
    )
    try:
        response = requests.post(
            f"{backend_origin}{endpoint}",
            json={"email": email, "password": password},
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Dedicated showcase login endpoint is unreachable: {endpoint}: {exc}"
        ) from exc
    _require_no_redirect(response, f"Dedicated showcase login for {email}")
    if response.status_code != 200:
        raise RuntimeError(
            f"Dedicated showcase login failed for {email}: "
            f"HTTP {response.status_code} {response.text[:240]}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Dedicated showcase login returned invalid JSON for {email}"
        ) from exc
    access_token = payload.get("access_token") if isinstance(payload, dict) else None
    _require(
        isinstance(access_token, str) and bool(access_token.strip()),
        f"Dedicated showcase login returned no access token for {email}",
    )
    return access_token


def verify_seeded_workspace(
    database: Database,
    *,
    kb_count_before: int,
    backend_url: str,
) -> dict[str, int]:
    """Prove domain completeness, isolation, visible identity, and auth."""

    minimum_counts = {
        "users": 2,
        "user_subscriptions": 1,
        "team_members": 1,
        "weddings": 2,
        "couple_users": 1,
        "couple_messages": 3,
        "guests": 24,
        "rsvps": 12,
        "plus_ones": 1,
        "tables": 6,
        "seating_layouts": 1,
        "planner_tasks": 4,
        "inbound_emails": 1,
        "email_logs": 1,
        "support_tickets": 2,
        "vendor_profiles": 6,
        "vendor_assignments": 6,
        "vendor_contracts": 4,
        "vendor_contract_activities": 4,
        "vendor_payment_milestones": 4,
        "vendor_quotes": 3,
        "budget_categories": 4,
        "payment_records": 1,
        "contracts": 1,
        "scheduled_payments": 3,
        "packages": 3,
        "forms": 2,
        "form_responses": 1,
        "form_distributions": 1,
        "form_submissions": 1,
        "guest_media_assets": 7,
        "gallery": 3,
        "ai_cache": 2,
        "kb_articles": 1,
    }
    counts: dict[str, int] = {}
    for collection_name, minimum in minimum_counts.items():
        count = database[collection_name].count_documents(
            {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
        )
        counts[collection_name] = count
        _require(
            count >= minimum,
            f"{collection_name} has {count} capture fixtures; expected at least {minimum}",
        )

    for collection_name in database.list_collection_names():
        unscoped = database[collection_name].count_documents(
            {"seed_source": SEED_SOURCE, "seed_scope": {"$ne": SEED_SCOPE}},
            limit=1,
        )
        _require(
            unscoped == 0,
            f"{collection_name} contains marketing-capture fixtures without seed_scope",
        )

    capture_owner = {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
    for collection_name in database.list_collection_names():
        for document in database[collection_name].find(capture_owner):
            _validate_seeded_identity_document(
                document,
                path=f"{collection_name}/{document.get('_id', '<missing-id>')}",
            )

    contract_ids = {
        str(contract["_id"])
        for contract in database["vendor_contracts"].find(
            {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}, {"_id": 1}
        )
    }
    contract_activities = [
        _validate_vendor_contract_activity_api_shape(activity)
        for activity in database["vendor_contract_activities"].find(
            {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
        )
    ]
    _require(
        all(
            item.contract_id in contract_ids
            and item.root_contract_id == item.contract_id
            for item in contract_activities
        ),
        "Seeded contract activity ownership does not match an original seeded contract",
    )
    _require(
        {item.activity_type for item in contract_activities}
        == {
            VendorContractActivityType.CONTRACT_CREATED,
            VendorContractActivityType.CONTRACT_SENT,
            VendorContractActivityType.CONTRACT_VIEWED,
            VendorContractActivityType.CONTRACT_SIGNED,
        },
        "Seeded contract activities do not cover the production lifecycle states",
    )

    planner = database["users"].find_one({"email": PLANNER_EMAIL})
    _require(planner is not None, "Dedicated showcase planner is missing")
    _require(
        planner.get("first_name") == "Amina"
        and planner.get("last_name") == "Cole"
        and planner.get("company_name") == "Marigold & Co. Weddings",
        "Planner identity does not match the approved showcase world",
    )

    team = database["team_members"].find_one({"email": TEAM_EMAIL})
    _require(
        team is not None
        and team.get("status") == "active"
        and bool(team.get("user_id")),
        "Accepted team-member linkage is incomplete",
    )
    couple = database["couple_users"].find_one({"email": COUPLE_EMAIL})
    _require(
        couple is not None
        and couple.get("setup_completed") is True
        and couple.get("is_active") is True,
        "Sofia & Daniel couple login is incomplete",
    )

    wedding = database["weddings"].find_one({"_id": PRIMARY_WEDDING_ID})
    _require(wedding is not None, "Primary showcase wedding is missing")
    _require(
        wedding.get("couple_names") == "Sofia & Daniel"
        and wedding.get("our_story")
        and len(wedding.get("wedding_party") or []) >= 2
        and wedding.get("public_site_url")
        == "https://www.thespecialwedding.io/sofia-and-daniel",
        "Public microsite fixture is not capture-ready",
    )
    _require(
        (wedding.get("rsvp_config") or {}).get("phone_numbers")
        == ["(312) 555-0142", "(312) 555-0168"]
        and (wedding.get("rsvp_config") or {}).get("hide_phone_numbers") is True,
        "RSVP support contacts must use the approved fictional capture identity",
    )
    layout = database["seating_layouts"].find_one({"wedding_id": PRIMARY_WEDDING_ID})
    _require(
        layout is not None
        and str(layout.get("background_image_data_url") or "").startswith(
            "data:image/svg+xml;base64,"
        )
        and len(layout.get("fixtures") or []) >= 4,
        "Venue floorplan/background fixture is incomplete",
    )
    gallery_items = list(
        database["gallery"].find(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "approved_for_marketing": True,
                "is_public": True,
            }
        )
    )
    _require(
        len(gallery_items) >= 3
        and all(
            str(item.get("key") or "").startswith("gallery/sofia-and-daniel/20270125-")
            and "marketing-capture" not in str(item.get("key") or "")
            for item in gallery_items
        ),
        "Approved gallery metadata is incomplete",
    )
    for asset_name in (
        Path(item["url"]).name for item in MARKETING_CAPTURE_GALLERY_ITEMS
    ):
        _require(
            (ROOT / "public" / "demo-gallery" / asset_name).is_file(),
            f"Approved repository gallery asset is missing: {asset_name}",
        )
    guest_memory_previews = {
        str(item.get("demo_preview_url") or "")
        for item in database["guest_media_assets"].find(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
            },
            {"demo_preview_url": 1},
        )
    }
    _require(
        guest_memory_previews == MARKETING_CAPTURE_GALLERY_URLS,
        "Guest-memory previews do not use the complete approved gallery fixture set",
    )
    _require(
        database["guests"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "household_id": {"$exists": True, "$ne": ""},
            }
        )
        >= 12,
        "Guest household examples are incomplete",
    )
    _require(
        database["guests"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "accessibility_needs": {"$exists": True, "$ne": None},
            }
        )
        >= 1,
        "Guest accessibility examples are incomplete",
    )
    _require(
        database["rsvps"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "dietary": {"$exists": True, "$ne": None},
            }
        )
        >= 3,
        "Guest meal examples are incomplete",
    )
    _require(
        database["rsvps"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "attending": [],
            }
        )
        == 3,
        "Guest Management Declined filter fixture is not the expected three guests",
    )
    priya_guest = database["guests"].find_one(
        {
            "wedding_id": PRIMARY_WEDDING_ID,
            "name": "Priya Shah",
            "group_id": "friends",
            "plus_one_allowed": True,
            "number_of_plus_ones_allowed": 1,
        },
        {"_id": 1},
    )
    _require(
        priya_guest is not None,
        "Guest Management Priya Shah card fixture is missing or incomplete",
    )
    priya_guest_id = str(priya_guest["_id"])
    _require(
        database["rsvps"].find_one(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "guest_id": priya_guest_id,
                "guest_name": "Priya Shah",
                "attending": ["traditional"],
                "dietary": "Vegetarian",
            }
        )
        is not None,
        "Guest Management Priya Shah RSVP card fixture is missing or incomplete",
    )
    _require(
        database["plus_ones"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "guest_id": priya_guest_id,
            }
        )
        == 1,
        "Guest Management Priya Shah card must have exactly one submitted plus-one",
    )
    _require(
        database["scheduled_payments"].count_documents(
            {
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
                "status": "failed",
                "retry_count": {"$gte": 1},
            }
        )
        >= 1,
        "Payment failure/retry fixture is incomplete",
    )
    _require(
        database["budget_categories"].count_documents(
            {
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
                "$expr": {"$gt": ["$actual_spent", "$budgeted_amount"]},
            }
        )
        >= 1,
        "Budget overrun fixture is incomplete",
    )
    for category in database["budget_categories"].find(
        {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE},
        {"_id": 1, "actual_spent": 1},
    ):
        payment_total = sum(
            float(payment.get("amount") or 0)
            for payment in database["payment_records"].find(
                {
                    "seed_source": SEED_SOURCE,
                    "seed_scope": SEED_SCOPE,
                    "category_id": str(category["_id"]),
                },
                {"amount": 1},
            )
        )
        _require(
            abs(payment_total - float(category.get("actual_spent") or 0)) < 0.01,
            f"Budget category {category['_id']} does not reconcile to payment records",
        )
    budget_insight = database["ai_cache"].find_one(
        {
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
            "feature": "budget_insights",
        }
    )
    _require(
        budget_insight is not None
        and "$45,800"
        in str((budget_insight.get("response") or {}).get("summary") or ""),
        "Budget insight does not agree with the reconciled fixture totals",
    )
    kb_article = database["kb_articles"].find_one(
        {
            "_id": DEMO_KB_ARTICLE_ID,
            "slug": DEMO_KB_ARTICLE_SLUG,
            "status": "published",
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
        }
    )
    _require(
        kb_article is not None
        and kb_article.get("title") == "Planner Command Center: Your First 30 Minutes"
        and len(str(kb_article.get("content") or "")) >= 50,
        "Published showcase Knowledge Base article is incomplete",
    )
    _require(
        database["kb_articles"].count_documents({}) == kb_count_before + 1,
        "Marketing capture must add only its isolated Knowledge Base article",
    )

    _login(backend_url, "/admin/token", PLANNER_EMAIL, PLANNER_PASSWORD)
    _login(backend_url, "/admin/token", TEAM_EMAIL, TEAM_PASSWORD)
    _login(backend_url, "/couple/login", COUPLE_EMAIL, COUPLE_PASSWORD)
    public_payload = _get_json_readiness(
        f"{backend_url}/weddings/slug/{PRIMARY_SLUG}",
        label="Public showcase wedding",
    )
    public_venue = (
        public_payload.get("venue") if isinstance(public_payload, dict) else None
    )
    public_venue_name = (
        public_venue.get("name") if isinstance(public_venue, dict) else public_venue
    )
    _require(
        isinstance(public_payload, dict)
        and str(public_payload.get("id") or public_payload.get("_id") or "")
        == PRIMARY_WEDDING_ID
        and public_payload.get("couple_names") == "Sofia & Daniel"
        and public_payload.get("privacy_mode") == "public"
        and public_venue_name == "The Glasshouse at Riverbend",
        "Public showcase wedding returned the wrong seeded visible state",
    )
    kb_payload = _get_json_readiness(
        f"{backend_url}/public/kb/articles/slug/{DEMO_KB_ARTICLE_SLUG}",
        label="Published showcase Knowledge Base article",
    )
    _require(
        isinstance(kb_payload, dict)
        and kb_payload.get("slug") == DEMO_KB_ARTICLE_SLUG
        and kb_payload.get("title") == "Planner Command Center: Your First 30 Minutes",
        "Published showcase Knowledge Base article returned the wrong visible state",
    )
    return counts


def _verify_couple_capture_session(
    frontend_origin: str,
    couple_token: str,
) -> None:
    """Prove the cookie session resolves to the exact seeded couple and wedding."""

    profile = _get_json_readiness(
        f"{frontend_origin}/api/proxy/couple/profile",
        label="Marketing capture couple profile",
        cookies={"couple_token": couple_token},
    )
    _require(
        isinstance(profile, dict)
        and profile.get("id") == COUPLE_ID
        and profile.get("email") == COUPLE_EMAIL
        and profile.get("partner1_name") == "Sofia"
        and profile.get("partner2_name") == "Daniel"
        and profile.get("wedding_id") == PRIMARY_WEDDING_ID,
        "Marketing capture frontend resolved the wrong seeded couple session",
    )


def _find_primary_capture_wedding(payload: Any) -> dict[str, Any]:
    weddings = payload if isinstance(payload, list) else []
    wedding = next(
        (
            candidate
            for candidate in weddings
            if isinstance(candidate, dict)
            and str(candidate.get("id") or candidate.get("_id") or "")
            == PRIMARY_WEDDING_ID
        ),
        None,
    )
    _require(
        isinstance(wedding, dict)
        and wedding.get("slug") == PRIMARY_SLUG
        and wedding.get("couple_names") == "Sofia & Daniel",
        "Marketing capture planner wedding payload is missing Sofia & Daniel",
    )
    return wedding


def _api_backed_scene_text(
    feature_id: str,
    *,
    frontend_origin: str,
    planner_token: str,
    couple_token: str,
) -> str | None:
    """Resolve dynamic stable text through the same frontend proxy used by the UI."""

    planner_headers = {"Authorization": f"Bearer {planner_token}"}
    couple_cookies = {"couple_token": couple_token}

    if feature_id == "dashboard":
        profile = _get_json_readiness(
            f"{frontend_origin}/api/proxy/admin/profile",
            label="Marketing capture planner profile",
            headers=planner_headers,
        )
        company_name = (
            profile.get("company_name") if isinstance(profile, dict) else None
        )
        _require(
            isinstance(profile, dict)
            and profile.get("id") == PLANNER_USER_ID
            and profile.get("email") == PLANNER_EMAIL
            and company_name == "Marigold & Co. Weddings",
            "Marketing capture frontend resolved the wrong seeded planner profile",
        )
        return f"Welcome back, {company_name}!"

    if feature_id == "real-time":
        weddings = _get_json_readiness(
            f"{frontend_origin}/api/proxy/admin/planner/weddings",
            label="Marketing capture planner weddings",
            headers=planner_headers,
        )
        wedding = _find_primary_capture_wedding(weddings)
        venue = wedding.get("venue")
        venue_name = venue.get("name") if isinstance(venue, dict) else venue
        _require(
            venue_name == "The Glasshouse at Riverbend",
            "Marketing capture planner wedding returned the wrong venue",
        )
        return str(venue_name)

    if feature_id == "couple-portal":
        dashboard = _get_json_readiness(
            f"{frontend_origin}/api/proxy/couple/portal/dashboard",
            label="Marketing capture couple dashboard",
            cookies=couple_cookies,
        )
        wedding = dashboard.get("wedding") if isinstance(dashboard, dict) else None
        guest_stats = (
            dashboard.get("guest_stats") if isinstance(dashboard, dict) else None
        )
        guest_total = (
            guest_stats.get("guest_list_total")
            if isinstance(guest_stats, dict)
            else None
        )
        _require(
            isinstance(wedding, dict)
            and wedding.get("id") == PRIMARY_WEDDING_ID
            and wedding.get("couple_names") == "Sofia & Daniel"
            and guest_total == 24,
            "Marketing capture couple dashboard returned the wrong seeded state",
        )
        return f"{guest_total} guests added so far"

    if feature_id == "gallery-management":
        gallery = _get_json_readiness(
            f"{frontend_origin}/api/proxy/admin/gallery/list",
            label="Marketing capture admin gallery",
            headers=planner_headers,
            params={"prefix": f"gallery/{PRIMARY_SLUG}/"},
        )
        first_item = gallery[0] if isinstance(gallery, list) and gallery else None
        _require(
            isinstance(first_item, dict)
            and first_item.get("display_name") == "Garden terrace portrait"
            and first_item.get("url") == MARKETING_CAPTURE_GALLERY_ITEMS[0]["url"],
            "Marketing capture admin gallery returned the wrong seeded media",
        )
        return str(first_item["display_name"])

    if feature_id == "inbox":
        payload = _get_json_readiness(
            f"{frontend_origin}/api/proxy/couple-portal/conversations",
            label="Marketing capture couple conversations",
            headers=planner_headers,
        )
        conversations = (
            payload.get("conversations") if isinstance(payload, dict) else None
        )
        conversation = next(
            (
                item
                for item in (conversations or [])
                if isinstance(item, dict)
                and item.get("id") == COUPLE_ID
                and item.get("wedding_id") == PRIMARY_WEDDING_ID
            ),
            None,
        )
        _require(
            isinstance(conversation, dict)
            and conversation.get("partner1_name") == "Sofia"
            and conversation.get("partner2_name") == "Daniel",
            "Marketing capture inbox returned the wrong seeded couple conversation",
        )
        return f"{conversation['partner1_name']} & {conversation['partner2_name']}"

    if feature_id == "budget":
        payload = _get_json_readiness(
            f"{frontend_origin}/api/proxy/admin/weddings/{PRIMARY_WEDDING_ID}/budget",
            label="Marketing capture budget",
            headers=planner_headers,
        )
        summary = payload.get("summary") if isinstance(payload, dict) else None
        total_budget = (
            summary.get("total_budget") if isinstance(summary, dict) else None
        )
        _require(
            isinstance(total_budget, (int, float)) and total_budget == 82_500,
            "Marketing capture budget returned the wrong seeded total",
        )
        return f"${total_budget:,.0f}"

    if feature_id == "forms":
        form = _get_json_readiness(
            f"{frontend_origin}/api/proxy/admin/forms/"
            "form_marketing_capture_couple_intake",
            label="Marketing capture form builder",
            headers=planner_headers,
        )
        _require(
            isinstance(form, dict)
            and form.get("id") == "form_marketing_capture_couple_intake"
            and form.get("wedding_id") == PRIMARY_WEDDING_ID
            and form.get("name") == "Couple Intake Questionnaire",
            "Marketing capture form builder returned the wrong seeded form",
        )
        return str(form["name"])

    if feature_id == "team":
        members_payload = _get_json_readiness(
            f"{frontend_origin}/api/proxy/admin/team/members",
            label="Marketing capture team members",
            headers=planner_headers,
            params={"skip": 0, "limit": 50},
        )
        members = (
            members_payload.get("members")
            if isinstance(members_payload, dict)
            else None
        )
        member = members[0] if isinstance(members, list) and len(members) == 1 else None
        _require(
            isinstance(members_payload, dict)
            and members_payload.get("total") == 1
            and members_payload.get("skip") == 0
            and members_payload.get("limit") == 50
            and isinstance(member, dict)
            and member.get("id") == TEAM_MEMBER_ID
            and member.get("owner_id") == PLANNER_USER_ID
            and member.get("owner_email") == PLANNER_EMAIL
            and member.get("user_id") == TEAM_USER_ID
            and member.get("email") == TEAM_EMAIL
            and member.get("first_name") == "Maya"
            and member.get("last_name") == "Thompson"
            and member.get("status") == "active"
            and member.get("role") == "editor"
            and member.get("wedding_access") == "assigned"
            and member.get("assigned_wedding_ids") == [PRIMARY_WEDDING_ID],
            "Marketing capture team list returned the wrong seeded member",
        )

        seats = _get_json_readiness(
            f"{frontend_origin}/api/proxy/admin/team/seats",
            label="Marketing capture team seats",
            headers=planner_headers,
        )
        _require(
            isinstance(seats, dict)
            and seats.get("total_seats") == 5
            and seats.get("used_seats") == 1
            and seats.get("available_seats") == 4
            and seats.get("members_by_status") == {"active": 1},
            "Marketing capture team seats returned the wrong seeded usage",
        )
        return "Team Management"

    return None


def _load_served_checkpoint_scripts(
    frontend_origin: str,
    script_sources: list[str],
    cache: dict[str, str],
) -> str:
    """Load only same-origin Next.js route bundles referenced by the app shell."""

    script_text: list[str] = []
    for source in script_sources:
        parsed = urlparse(source)
        if not (
            parsed.scheme == ""
            and parsed.netloc == ""
            and parsed.path.startswith("/_next/static/")
            and parsed.path.endswith(".js")
            and parsed.params == ""
            and parsed.query == ""
            and parsed.fragment == ""
        ):
            continue
        if source not in cache:
            script_url = f"{frontend_origin}{source}"
            try:
                response = requests.get(
                    script_url,
                    timeout=15,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Frontend checkpoint bundle is unreachable: {script_url}: {exc}"
                ) from exc
            _require_no_redirect(response, f"Frontend checkpoint bundle {script_url}")
            _require(
                response.status_code == 200 and bool(response.text.strip()),
                "Frontend checkpoint bundle returned an invalid response: "
                f"{script_url}; HTTP {response.status_code}",
            )
            cache[source] = response.text
        script_text.append(cache[source])
    return "\n".join(script_text)


def verify_frontend_checkpoint_routes(
    frontend_url: str,
    expected_build: str,
    *,
    backend_url: str | None = None,
    planner_token: str | None = None,
    couple_token: str | None = None,
) -> None:
    origin = require_local_capture_origin(
        frontend_url,
        expected_port=3100,
        label="Marketing capture frontend",
    )
    backend_origin = None
    if backend_url is not None:
        backend_origin = require_local_capture_origin(
            backend_url,
            expected_port=8000,
            label="Marketing capture backend",
        )
    _require(
        FULL_GIT_COMMIT_PATTERN.fullmatch(expected_build) is not None,
        "Frontend checkpoint preflight requires the full expected git commit",
    )
    if not planner_token:
        _require(
            backend_origin is not None,
            "Frontend checkpoint preflight requires a planner token or local backend origin",
        )
        planner_token = _login(
            backend_origin,
            "/admin/token",
            PLANNER_EMAIL,
            PLANNER_PASSWORD,
        )
    if not couple_token:
        _require(
            backend_origin is not None,
            "Frontend checkpoint preflight requires a couple token or local backend origin",
        )
        couple_token = _login(
            backend_origin,
            "/couple/login",
            COUPLE_EMAIL,
            COUPLE_PASSWORD,
        )
    _require(
        isinstance(planner_token, str) and bool(planner_token.strip()),
        "Frontend checkpoint preflight received an empty planner token",
    )
    _require(
        isinstance(couple_token, str) and bool(couple_token.strip()),
        "Frontend checkpoint preflight received an empty couple token",
    )

    if any(scene["session"] == "couple" for scene in MARKETING_CAPTURE_E2E_CHECKPOINTS):
        _verify_couple_capture_session(origin, couple_token)

    script_cache: dict[str, str] = {}
    for scene in MARKETING_CAPTURE_E2E_CHECKPOINTS:
        title = scene["title"]
        route = scene["route"]
        url = f"{origin}{route}"
        api_backed_text = _api_backed_scene_text(
            scene["featureId"],
            frontend_origin=origin,
            planner_token=planner_token,
            couple_token=couple_token,
        )
        request_kwargs: dict[str, Any] = {
            "timeout": 15,
            "allow_redirects": False,
        }
        if scene["session"] == "planner":
            request_kwargs["cookies"] = {"admin_token": planner_token}
        elif scene["session"] == "couple":
            request_kwargs["cookies"] = {"couple_token": couple_token}
        try:
            response = requests.get(url, **request_kwargs)
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Frontend checkpoint is unreachable ({title}): {exc}"
            ) from exc
        _require(
            response.status_code == 200,
            f"Frontend checkpoint returned HTTP {response.status_code}: {url}",
        )
        _require_no_redirect(response, f"Frontend checkpoint {url}")
        document = response.text.strip()
        _require(document, f"Frontend checkpoint returned an empty app shell: {url}")

        parser = _BuildCommitMetaParser()
        parser.feed(document)
        _require(
            expected_build in parser.commits,
            "Frontend checkpoint served the wrong app build: "
            f"{url}; expected {expected_build}, observed "
            f"{parser.commits or ['missing meta[name=tsw-app-build-commit]']}",
        )

        expected_visible_text = scene["expectedVisibleText"]
        if scene["featureId"] in MARKETING_CAPTURE_API_TEXT_FEATURES:
            _require(
                api_backed_text == expected_visible_text,
                "Frontend checkpoint API returned the wrong stable visible text: "
                f"{url}; expected {expected_visible_text!r}, "
                f"observed {api_backed_text!r}",
            )
            continue

        served_text = document
        if expected_visible_text not in served_text:
            served_text += _load_served_checkpoint_scripts(
                origin,
                parser.script_sources,
                script_cache,
            )
        _require(
            expected_visible_text in served_text,
            "Frontend checkpoint is missing stable visible text "
            f"{expected_visible_text!r}: {url}",
        )


def _validate_gallery_asset_response(
    response: requests.Response,
    *,
    asset_url: str,
    asset_contract: dict[str, Any],
) -> None:
    """Fail closed unless a response is the exact reviewed gallery WebP."""

    redirect_location = _response_redirect_location(response)
    content_type = response.headers.get("content-type", "").split(";", 1)[0]
    _require(
        response.status_code == 200
        and redirect_location is None
        and content_type == "image/webp",
        f"Approved public gallery asset is not a direct HTTP 200 WebP: {asset_url}",
    )
    content = response.content
    _require(
        isinstance(content, bytes) and bool(content),
        f"Approved public gallery asset returned empty bytes: {asset_url}",
    )
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            image_format = image.format
            image_size = image.size
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(
            f"Approved public gallery asset is not a decodable WebP: {asset_url}"
        ) from exc
    _require(
        image_format == "WEBP",
        f"Approved public gallery asset decoded as {image_format}, not WebP: {asset_url}",
    )
    expected_size = (asset_contract["width"], asset_contract["height"])
    _require(
        image_size == expected_size,
        "Approved public gallery asset has the wrong dimensions: "
        f"{asset_url}; expected {expected_size[0]}x{expected_size[1]}, "
        f"observed {image_size[0]}x{image_size[1]}",
    )
    observed_hash = hashlib.sha256(content).hexdigest()
    _require(
        observed_hash == asset_contract["sha256"],
        "Approved public gallery asset has the wrong SHA-256: "
        f"{asset_url}; expected {asset_contract['sha256']}, observed {observed_hash}",
    )


def verify_frontend_gallery_assets(frontend_url: str) -> None:
    origin = require_local_capture_origin(
        frontend_url,
        expected_port=3100,
        label="Marketing capture frontend",
    )
    gallery_url = f"{origin}/api/proxy/gallery?wedding_slug={PRIMARY_SLUG}&limit=12"
    try:
        gallery_response = requests.get(
            gallery_url,
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Public showcase gallery is unreachable: {exc}") from exc
    _require(
        gallery_response.status_code == 200
        and not any(key.lower() == "location" for key in gallery_response.headers),
        f"Public showcase gallery returned HTTP {gallery_response.status_code}",
    )
    try:
        payload = gallery_response.json()
    except ValueError as exc:
        raise RuntimeError("Public showcase gallery returned invalid JSON") from exc

    items = payload.get("items") if isinstance(payload, dict) else None
    actual_urls = {
        str(item.get("url") or "") for item in (items or []) if isinstance(item, dict)
    }
    _require(
        actual_urls == MARKETING_CAPTURE_GALLERY_URLS,
        "Public showcase gallery did not return the complete approved fixture set",
    )

    for item in MARKETING_CAPTURE_GALLERY_ITEMS:
        asset_url = f"{origin}{item['url']}"
        try:
            asset_response = requests.get(
                asset_url,
                timeout=15,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Approved public gallery asset is unreachable: {exc}"
            ) from exc
        _validate_gallery_asset_response(
            asset_response,
            asset_url=asset_url,
            asset_contract=MARKETING_CAPTURE_GALLERY_ASSET_CONTRACT[item["url"]],
        )


def verify_frontend_admin_gallery_prefixes(
    frontend_url: str,
    backend_url: str,
) -> None:
    """Require the seeded planner gallery view to load without failed prefixes."""

    frontend_origin = require_local_capture_origin(
        frontend_url,
        expected_port=3100,
        label="Marketing capture frontend",
    )
    backend_origin = require_local_capture_origin(
        backend_url,
        expected_port=8000,
        label="Marketing capture backend",
    )
    planner_token = _login(
        backend_origin,
        "/admin/token",
        PLANNER_EMAIL,
        PLANNER_PASSWORD,
    )
    list_url = f"{frontend_origin}/api/proxy/admin/gallery/list"
    expected_payloads = {
        "gallery": MARKETING_CAPTURE_GALLERY_ITEMS,
        "our-story": [],
        "wedding-party": [],
    }

    for folder, expected_payload in expected_payloads.items():
        prefix = f"{folder}/{PRIMARY_SLUG}/"
        try:
            response = requests.get(
                list_url,
                params={"prefix": prefix},
                headers={"Authorization": f"Bearer {planner_token}"},
                timeout=15,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Marketing capture admin gallery prefix {folder} is unreachable: {exc}"
            ) from exc
        _require_no_redirect(
            response,
            f"Marketing capture admin gallery prefix {folder}",
        )
        _require(
            response.status_code == 200,
            "Marketing capture admin gallery prefix "
            f"{folder} returned HTTP {response.status_code}",
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Marketing capture admin gallery prefix {folder} returned invalid JSON"
            ) from exc
        _require(
            payload == expected_payload,
            "Marketing capture admin gallery prefix "
            f"{folder} returned unexpected media",
        )


def verify_frontend_couple_memory_preview(
    frontend_url: str,
    backend_url: str,
) -> None:
    """Prove the authenticated Memories path reaches canonical frontend media."""

    frontend_origin = require_local_capture_origin(
        frontend_url,
        expected_port=3100,
        label="Marketing capture frontend",
    )
    backend_origin = require_local_capture_origin(
        backend_url,
        expected_port=8000,
        label="Marketing capture backend",
    )
    access_token = _login(
        backend_origin,
        "/couple/login",
        COUPLE_EMAIL,
        COUPLE_PASSWORD,
    )
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    memories_url = (
        f"{frontend_origin}/api/proxy/couple/portal/memories?media_type=image&limit=24"
    )
    try:
        memories_response = requests.get(
            memories_url,
            headers=auth_headers,
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Authenticated Couple Memories list is unreachable: {exc}"
        ) from exc
    _require_no_redirect(memories_response, "Authenticated Couple Memories list")
    _require(
        memories_response.status_code == 200,
        "Authenticated Couple Memories list returned "
        f"HTTP {memories_response.status_code}",
    )
    try:
        memories_payload = memories_response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Authenticated Couple Memories list returned invalid JSON"
        ) from exc

    items = (
        memories_payload.get("items") if isinstance(memories_payload, dict) else None
    )
    preview_path = next(
        (
            item.get("preview_path")
            for item in (items or [])
            if isinstance(item, dict)
            and item.get("media_type") == "image"
            and isinstance(item.get("preview_path"), str)
        ),
        None,
    )
    _require(
        isinstance(preview_path, str)
        and preview_path.startswith("/couple/portal/memories/")
        and preview_path.endswith("/preview"),
        "Authenticated Couple Memories list returned no image preview path",
    )

    preview_url = f"{frontend_origin}/api/proxy{preview_path}"
    try:
        preview_response = requests.get(
            preview_url,
            headers=auth_headers,
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Authenticated Couple Memories preview is unreachable: {exc}"
        ) from exc
    _require(
        preview_response.status_code == 307,
        "Authenticated Couple Memories preview did not preserve the backend 307; "
        f"received HTTP {preview_response.status_code}",
    )

    redirect_url = preview_response.headers.get("location", "")
    approved_preview_urls = {
        f"{frontend_origin}{item['url']}" for item in MARKETING_CAPTURE_GALLERY_ITEMS
    }
    _require(
        redirect_url in approved_preview_urls,
        "Authenticated Couple Memories preview did not redirect to the exact "
        "canonical frontend origin and approved fixture path",
    )

    try:
        asset_response = requests.get(
            redirect_url,
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Redirected Couple Memories preview asset is unreachable: {exc}"
        ) from exc
    asset_path = urlparse(redirect_url).path
    _validate_gallery_asset_response(
        asset_response,
        asset_url=redirect_url,
        asset_contract=MARKETING_CAPTURE_GALLERY_ASSET_CONTRACT[asset_path],
    )


def _non_interactive() -> bool:
    return os.getenv("TESTBED_NON_INTERACTIVE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _seed_environment(anchor_at: str) -> dict[str, str]:
    primary_date = "2027-01-25"

    env = dict(os.environ)
    env.update(
        {
            "ENVIRONMENT": "development",
            "MARKETING_CAPTURE_ANCHOR_AT": anchor_at,
            "MARKETING_CAPTURE_PLANNER_EMAIL": PLANNER_EMAIL,
            "MARKETING_CAPTURE_TEAM_PASSWORD": TEAM_PASSWORD,
            "SMOKE_PLANNER_EMAIL": PLANNER_EMAIL,
            "SMOKE_PLANNER_PASSWORD": PLANNER_PASSWORD,
            "SMOKE_PLANNER_COMPANY_NAME": "Marigold & Co. Weddings",
            "SMOKE_PLANNER_FIRST_NAME": "Amina",
            "SMOKE_PLANNER_LAST_NAME": "Cole",
            "SMOKE_PLANNER_USER_ID": PLANNER_USER_ID,
            "SMOKE_PLANNER_PLAN_ID": "plan_signature",
            "SMOKE_WEDDING_ID": PRIMARY_WEDDING_ID,
            "SMOKE_PUBLIC_WEDDING_SLUG": PRIMARY_SLUG,
            "SMOKE_WEDDING_COUPLE_NAMES": "Sofia & Daniel",
            "SMOKE_WEDDING_DATE": primary_date,
            "DEMO_VIDEO_PRIMARY_DATE": primary_date,
            "DEMO_VIDEO_SECONDARY_DATE": "2027-07-06",
            "SMOKE_COUPLE_EMAIL": COUPLE_EMAIL,
            "SMOKE_COUPLE_PASSWORD": COUPLE_PASSWORD,
            "SMOKE_COUPLE_PARTNER1_NAME": "Sofia",
            "SMOKE_COUPLE_PARTNER2_NAME": "Daniel",
            "SMOKE_COUPLE_ID": COUPLE_ID,
        }
    )
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the isolated Phase 1 marketing-capture workspace"
    )
    parser.add_argument(
        "--anchor-at",
        default=os.getenv("MARKETING_CAPTURE_ANCHOR_AT", DEFAULT_ANCHOR_AT),
        help="ISO-8601 capture anchor; naive values use America/Chicago.",
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv(
            "MARKETING_CAPTURE_BACKEND_URL",
            os.getenv("BACKEND_URL", "http://127.0.0.1:8000"),
        ),
        help="Backend origin used for dedicated planner, team, couple, and public-route checks.",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("MARKETING_CAPTURE_FRONTEND_URL", "http://127.0.0.1:3100"),
        help="Production-like frontend origin used for the manual browser checkpoints.",
    )
    args = parser.parse_args()

    backend_url = require_local_capture_origin(
        args.backend_url,
        expected_port=8000,
        label="Marketing capture backend",
    )
    frontend_url = require_local_capture_origin(
        args.frontend_url,
        expected_port=3100,
        label="Marketing capture frontend",
    )
    verify_frontend_capture_runtime(frontend_url)
    capture_build = require_clean_capture_checkout()
    print(f"[BUILD] Clean marketing-capture checkout at {capture_build}")

    client, database = _load_database()
    try:
        print("[RESET] Removing the prior isolated capture workspace")
        cleanup_marketing_capture_workspace_state(database)
        kb_count_before = database["kb_articles"].count_documents({})
        assert_setup_namespace_available(database)

        env = _seed_environment(args.anchor_at)
        print("[SEED] Creating the dedicated planner and couple identities")
        _run_python(SETUP_SMOKE_ACCOUNTS, env=env)
        print("[SEED] Enriching the production-shaped fictional workspace")
        _run_python(
            RICH_WORKSPACE_SEEDER,
            env=env,
            args=[
                "--planner-email",
                PLANNER_EMAIL,
                "--anchor-at",
                args.anchor_at,
            ],
        )

        counts = verify_seeded_workspace(
            database,
            kb_count_before=kb_count_before,
            backend_url=backend_url,
        )
        print(
            "[OK] Marketing capture workspace verified: "
            + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        )
    finally:
        client.close()

    capture_ready_build = require_clean_capture_checkout()
    _require(
        capture_ready_build == capture_build,
        "Marketing-capture HEAD changed while the workspace was being seeded; "
        f"started at {capture_build}, now at {capture_ready_build}",
    )

    verify_frontend_checkpoint_routes(
        frontend_url,
        capture_build,
        backend_url=backend_url,
    )
    verify_frontend_gallery_assets(frontend_url)
    verify_frontend_admin_gallery_prefixes(frontend_url, backend_url)
    verify_frontend_couple_memory_preview(frontend_url, backend_url)
    for scene in MARKETING_CAPTURE_E2E_CHECKPOINTS:
        print(
            f"\nCHECKPOINT — {scene['title']}"
            f"\n  Feature: {scene['featureId']}"
            f"\n  Session: {scene['session']}"
            f"\n  URL: {frontend_url}{scene['route']}"
            f"\n  Expect: {scene['expectation']}"
            f"\n  Stable text: {scene['expectedVisibleText']}"
            f"\n  Safe interaction: {scene['safeInteraction'] or 'None'}"
        )
        if not _non_interactive():
            input("Press ENTER after verifying this checkpoint in the browser… ")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n[FAIL] Marketing capture verification aborted: {exc}\n")
        raise SystemExit(1)
