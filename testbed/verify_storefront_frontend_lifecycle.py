#!/usr/bin/env python3
"""Run-scoped Chromium acceptance driver for the planner storefront.

Python is deliberately limited to target safety, fixture seeding, runtime
attestation, post-browser persistence assertions, and cleanup orchestration.
Every customer interaction is performed by Playwright in
``storefront_frontend_lifecycle.spec.ts``.

Pair: cleanup_storefront_frontend_lifecycle_state.py
"""

from __future__ import annotations

import base64
import bcrypt
import binascii
from collections.abc import Mapping
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import time
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from PIL import Image
from pymongo import MongoClient
import requests

try:
    from testbed.storefront_build_evidence import (
        frontend_source_evidence,
        storefront_evidence_source_evidence,
    )
    from testbed.storefront_testbed_safety import (
        PROVIDER_DISABLED_ENVIRONMENT_KEYS,
        assert_safe_storefront_target,
        parse_exact_hostname_allowlist,
    )
except ModuleNotFoundError:  # Direct ``python testbed/<driver>.py`` execution.
    from storefront_build_evidence import (  # type: ignore[no-redef]
        frontend_source_evidence,
        storefront_evidence_source_evidence,
    )
    from storefront_testbed_safety import (  # type: ignore[no-redef]
        PROVIDER_DISABLED_ENVIRONMENT_KEYS,
        assert_safe_storefront_target,
        parse_exact_hostname_allowlist,
    )


REPO_ROOT = Path(__file__).resolve().parent.parent
SHELL_ENVIRONMENT = dict(os.environ)
load_dotenv(REPO_ROOT / ".env", override=False)
testbed_env = REPO_ROOT / "testbed" / ".env"
if testbed_env.exists():
    load_dotenv(testbed_env, override=True)
os.environ.update(SHELL_ENVIRONMENT)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("verify_storefront_frontend_lifecycle")

BACKEND_URL = os.getenv(
    "TESTBED_STOREFRONT_BACKEND_URL", "https://127.0.0.1:8122"
).rstrip("/")
FRONTEND_URL = os.getenv(
    "TESTBED_STOREFRONT_FRONTEND_URL", "https://127.0.0.1:3122"
).rstrip("/")
FRONTEND_UPSTREAM_URL = os.getenv(
    "TESTBED_STOREFRONT_FRONTEND_UPSTREAM_URL", "http://127.0.0.1:3123"
).rstrip("/")
MONGO_URI = os.getenv("TESTBED_STOREFRONT_MONGO_URI", "mongodb://127.0.0.1:28127")
MONGO_DB = os.getenv("TESTBED_STOREFRONT_MONGO_DB", "wedding_storefront_e2e")
EXTERNAL_MODE = (
    os.getenv("TESTBED_STOREFRONT_EXTERNAL_MODE", "deterministic").strip().lower()
)
INQUIRY_DELIVERY_MODE = (
    os.getenv("TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE", "disabled").strip().lower()
)
ARTIFACT_ROOT = Path(
    os.getenv(
        "TESTBED_STOREFRONT_ARTIFACT_DIR",
        str(REPO_ROOT / "testbed" / ".testbed" / "artifacts" / "storefront"),
    )
).expanduser()
REQUEST_TIMEOUT = 30
SEED_SOURCE = "testbed:storefront_frontend_lifecycle"
INQUIRY_RESPONSE_MESSAGE = "Thanks — your inquiry was received by the wedding planner."
PROVIDER_CONTROL_PREFIX = "/__testbed/storefront-provider"
PROVIDER_CUSTOMER_ZONE = "customer.test"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _ensure_isolated_runtime_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a writable runtime receipt even when startup failed mid-flight."""

    runtime_state = manifest.get("isolated_runtime")
    if isinstance(runtime_state, dict):
        return runtime_state

    runtime_state = {"status": "START_FAILED"}
    manifest["isolated_runtime"] = runtime_state
    return runtime_state


def _record_isolated_runtime_shutdown(
    manifest: dict[str, Any], shutdown: dict[str, Any]
) -> dict[str, Any]:
    """Record the terminal runtime state without sealing a RUNNING contradiction."""

    runtime_state = _ensure_isolated_runtime_manifest(manifest)
    runtime_state["shutdown"] = shutdown
    runtime_state["status"] = (
        "STOPPED" if shutdown.get("status") == "STOPPED" else "STOP_FAILED"
    )
    return runtime_state


def _port(origin: str) -> int:
    parsed = urlparse(origin)
    if parsed.port:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def _host(origin: str) -> str:
    return urlparse(origin).hostname or ""


def _wait_for_http(
    url: str,
    *,
    process: subprocess.Popen[str],
    verify: str | bool,
    timeout_seconds: float = 45,
) -> requests.Response:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Isolated process exited before {url} became ready: {process.returncode}"
            )
        try:
            response = requests.get(
                url,
                timeout=2,
                allow_redirects=False,
                verify=verify,
            )
            if response.status_code < 500:
                return response
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _require_free_port(origin: str, label: str) -> None:
    parsed = urlparse(origin)
    host = parsed.hostname or ""
    port = _port(origin)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex((host, port)) == 0:
            raise RuntimeError(
                f"Isolated storefront {label} port {host}:{port} is already in use"
            )


def _node_22() -> str:
    candidates = [
        os.getenv("TESTBED_STOREFRONT_NODE", "").strip(),
        "/opt/homebrew/opt/node@22/bin/node",
        shutil.which("node") or "",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        version = subprocess.check_output([candidate, "--version"], text=True).strip()
        if version.startswith("v22."):
            return candidate
    raise RuntimeError(
        "The isolated storefront production runtime requires Node 22. "
        "Set TESTBED_STOREFRONT_NODE to the Node 22 executable."
    )


def _write_loopback_certificate(artifact_dir: Path) -> tuple[Path, Path, str]:
    """Create one run-scoped CA certificate trusted only by this testbed run."""

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "WeddingWebApp storefront testbed")]
    )
    now = _now()
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=4))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_path = artifact_dir / "loopback-provider-ca.pem"
    private_key_path = artifact_dir / "loopback-provider-key.pem"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    private_key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    private_key_path.chmod(0o600)
    return (
        certificate_path,
        private_key_path,
        hashlib.sha256(certificate_path.read_bytes()).hexdigest(),
    )


class IsolatedStorefrontRuntime:
    """Own Mongo, HTTPS FastAPI harness, and the receipt-bound Next server."""

    def __init__(
        self,
        *,
        run_id: str,
        root_admin_email: str,
        control_token: str,
        artifact_dir: Path,
        runtime_revision: str,
    ) -> None:
        self.run_id = run_id
        self.root_admin_email = root_admin_email
        self.control_token = control_token
        self.probe_ingress_secret = hashlib.sha256(
            f"{control_token}\nstorefront-probe-ingress-v1".encode("utf-8")
        ).hexdigest()
        self.artifact_dir = artifact_dir
        self.runtime_revision = runtime_revision
        self.certificate_path, self.private_key_path, self.certificate_sha256 = (
            _write_loopback_certificate(artifact_dir)
        )
        self.processes: list[tuple[str, subprocess.Popen[str], Any]] = []
        self.started_at = _now()

    @staticmethod
    def _mongo_coordinates() -> tuple[str, int]:
        parsed = urlparse(str(MONGO_URI))
        if (
            parsed.scheme != "mongodb"
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.hostname not in {"127.0.0.1", "localhost"}
        ):
            raise RuntimeError(
                "The isolated storefront runtime requires a credential-free single-host "
                "loopback Mongo URI without a database path"
            )
        return parsed.hostname, parsed.port or 27017

    def _spawn(
        self,
        label: str,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> subprocess.Popen[str]:
        log_path = self.artifact_dir / f"runtime-{label}.log"
        log_file = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=environment,
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            # Keep runtime children out of the parent's terminal process group.
            # The visible playback contract uses Ctrl-C to ask the parent to
            # perform authenticated fixture cleanup first; propagating SIGINT
            # directly to Mongo would tear down the database before cleanup.
            start_new_session=True,
        )
        self.processes.append((label, process, log_file))
        return process

    def start(self) -> dict[str, Any]:
        if urlparse(BACKEND_URL).scheme != "https":
            raise RuntimeError(
                "Deterministic storefront provider proof requires an HTTPS loopback backend"
            )
        if urlparse(FRONTEND_URL).scheme != "https":
            raise RuntimeError(
                "The isolated storefront frontend must use an HTTPS loopback origin"
            )
        if urlparse(FRONTEND_UPSTREAM_URL).scheme != "http":
            raise RuntimeError("The private Next upstream must use loopback HTTP")
        _require_free_port(BACKEND_URL, "backend")
        _require_free_port(FRONTEND_URL, "frontend")
        _require_free_port(FRONTEND_UPSTREAM_URL, "private Next upstream")
        mongo_host, mongo_port = self._mongo_coordinates()
        _require_free_port(f"http://{mongo_host}:{mongo_port}", "Mongo")

        mongod = shutil.which("mongod")
        if not mongod:
            raise RuntimeError(
                "mongod is required for isolated storefront browser proof"
            )
        mongo_dir = self.artifact_dir / "mongo-data"
        mongo_dir.mkdir()
        mongo_process = self._spawn(
            "mongo",
            [
                mongod,
                "--dbpath",
                str(mongo_dir),
                "--bind_ip",
                mongo_host,
                "--port",
                str(mongo_port),
                "--nounixsocket",
                "--quiet",
            ],
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if mongo_process.poll() is not None:
                raise RuntimeError("Isolated Mongo exited during startup")
            try:
                probe = MongoClient(MONGO_URI, serverSelectionTimeoutMS=500)
                probe.admin.command("ping")
                probe.close()
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Timed out waiting for isolated Mongo")

        python = REPO_ROOT / ".venv.nosync" / "bin" / "python"
        if not python.is_file():
            raise RuntimeError(
                ".venv.nosync Python is required for the storefront harness"
            )
        backend_environment = _disabled_provider_child_environment(os.environ)
        backend_environment.update(
            {
                "TESTBED_NON_INTERACTIVE": "1",
                "STOREFRONT_PROVIDER_HARNESS_RUN_ID": self.run_id,
                "STOREFRONT_PROVIDER_HARNESS_TOKEN": self.control_token,
                "STOREFRONT_PROVIDER_HARNESS_CUSTOMER_ZONE": PROVIDER_CUSTOMER_ZONE,
                "STOREFRONT_PROVIDER_HARNESS_FRONTEND_CA_CERT": str(
                    self.certificate_path
                ),
                "BACKEND_URL": BACKEND_URL,
                "FRONTEND_URL": FRONTEND_URL,
                "MONGO_URI": str(MONGO_URI),
                "MONGODB_URI": str(MONGO_URI),
                "MONGO_DB": MONGO_DB,
                "MONGO_NAME": MONGO_DB,
                # Keep raw-env and typed settings consumers on a supported
                # non-production value; TESTING below selects test semantics.
                "ENVIRONMENT": "development",
                "TESTING": "true",
                "WEB_CONCURRENCY": "1",
                "REDIS_ENABLED": "false",
                "AUDIT_LOG_TO_DB": "false",
                "RESEND_API_KEY": "",
                "ROOT_ADMIN_EMAIL": self.root_admin_email,
                "STRIPE_ENABLED": "false",
                "STRIPE_SECRET_KEY": "",
                "STOREFRONT_RUNTIME_REVISION": self.runtime_revision,
                "STOREFRONT_PROBE_INGRESS_SECRET": self.probe_ingress_secret,
            }
        )
        _assert_disabled_provider_fence(backend_environment)
        backend_process = self._spawn(
            "backend",
            [
                str(python),
                "-m",
                "uvicorn",
                "testbed.storefront_provider_harness:app",
                "--host",
                _host(BACKEND_URL),
                "--port",
                str(_port(BACKEND_URL)),
                "--ssl-certfile",
                str(self.certificate_path),
                "--ssl-keyfile",
                str(self.private_key_path),
                "--no-access-log",
                "--workers",
                "1",
            ],
            environment=backend_environment,
        )
        backend_health = _wait_for_http(
            f"{BACKEND_URL}/health/livez",
            process=backend_process,
            verify=str(self.certificate_path),
        )
        if backend_health.status_code != 200:
            raise RuntimeError(
                f"Isolated harness backend health returned {backend_health.status_code}"
            )

        node = _node_22()
        frontend_environment = dict(os.environ)
        frontend_environment.update(
            {
                "NODE_ENV": "production",
                "NODE_EXTRA_CA_CERTS": str(self.certificate_path),
                "FRONTEND_URL": FRONTEND_URL,
                "BACKEND_SERVICE_URL": BACKEND_URL,
                "INTERNAL_API_BASE_URL": BACKEND_URL,
                "NEXT_PUBLIC_API_BASE_URL": BACKEND_URL,
                "PORT": str(_port(FRONTEND_UPSTREAM_URL)),
                "STOREFRONT_CNAME_TARGET": "domains.thespecialwedding.com",
                "STOREFRONT_PLATFORM_DOMAINS": json.dumps(
                    ["thespecialwedding.io", "thespecialwedding.com"]
                ),
                "STOREFRONT_PROBE_INGRESS_SECRET": self.probe_ingress_secret,
            }
        )
        next_process = self._spawn(
            "frontend-next",
            [
                node,
                str(REPO_ROOT / "node_modules" / "next" / "dist" / "bin" / "next"),
                "start",
                "--hostname",
                _host(FRONTEND_UPSTREAM_URL),
                "--port",
                str(_port(FRONTEND_UPSTREAM_URL)),
            ],
            environment=frontend_environment,
        )
        _wait_for_http(
            f"{FRONTEND_UPSTREAM_URL}/admin/login",
            process=next_process,
            verify=False,
        )
        tls_proxy_environment = dict(os.environ)
        tls_proxy_environment.update(
            {
                "STOREFRONT_HTTPS_PROXY_HOST": _host(FRONTEND_URL),
                "STOREFRONT_HTTPS_PROXY_PORT": str(_port(FRONTEND_URL)),
                "STOREFRONT_HTTPS_PROXY_UPSTREAM": FRONTEND_UPSTREAM_URL,
                "STOREFRONT_HTTPS_PROXY_CERT": str(self.certificate_path),
                "STOREFRONT_HTTPS_PROXY_KEY": str(self.private_key_path),
            }
        )
        proxy_process = self._spawn(
            "frontend-tls",
            [node, str(REPO_ROOT / "testbed" / "storefront_https_proxy.mjs")],
            environment=tls_proxy_environment,
        )
        frontend_login = _wait_for_http(
            f"{FRONTEND_URL}/admin/login",
            process=proxy_process,
            verify=str(self.certificate_path),
        )
        if frontend_login.status_code != 200:
            raise RuntimeError(
                f"Isolated production frontend returned {frontend_login.status_code}"
            )

        return {
            "status": "RUNNING",
            "started_at": self.started_at.isoformat(),
            "backend_pid": backend_process.pid,
            "frontend_pid": proxy_process.pid,
            "frontend_next_pid": next_process.pid,
            "mongo_pid": mongo_process.pid,
            "backend_app": "testbed.storefront_provider_harness:app",
            "backend_url": BACKEND_URL,
            "frontend_url": FRONTEND_URL,
            "frontend_upstream_url": FRONTEND_UPSTREAM_URL,
            "mongo_uri_sha256": hashlib.sha256(str(MONGO_URI).encode()).hexdigest(),
            "database": MONGO_DB,
            "certificate": str(self.certificate_path),
            "certificate_sha256": self.certificate_sha256,
            "probe_ingress_secret_sha256": hashlib.sha256(
                self.probe_ingress_secret.encode("utf-8")
            ).hexdigest(),
            "provider_disabled_environment": {
                "status": "PASSED",
                "blank_keys": list(PROVIDER_DISABLED_ENVIRONMENT_KEYS),
            },
            "logs": {
                label: str(self.artifact_dir / f"runtime-{label}.log")
                for label, _process, _handle in self.processes
            },
        }

    def stop(self) -> dict[str, Any]:
        stopped: list[dict[str, Any]] = []
        for label, process, log_file in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log_file.close()
            stopped.append(
                {"label": label, "pid": process.pid, "returncode": process.returncode}
            )
        return {
            "status": "STOPPED",
            "stopped_at": _now().isoformat(),
            "processes": stopped,
        }


@dataclass(frozen=True)
class Fixtures:
    run_id: str
    root_admin_id: str
    root_admin_email: str
    root_admin_password: str
    signature_id: str
    signature_email: str
    signature_password: str
    signature_subscription_id: str
    solo_id: str
    solo_email: str
    solo_password: str
    solo_subscription_id: str
    foreign_owner_id: str
    foreign_email: str
    foreign_password: str
    foreign_subscription_id: str
    slug: str
    title: str
    description: str
    contact_email: str
    contact_phone: str
    package_id: str
    package_name: str
    inactive_package_id: str
    inactive_package_name: str
    template_package_id: str
    template_package_name: str
    included_service_name: str
    excluded_service_name: str
    review_id: str
    review_text: str
    unpublished_review_id: str
    unpublished_review_text: str
    foreign_package_id: str
    foreign_package_name: str
    foreign_review_id: str
    foreign_review_text: str
    inquiry_name: str
    inquiry_email: str
    inquiry_message: str
    custom_domain: str
    image_path: str

    @classmethod
    def create(cls, run_id: str, artifact_dir: Path) -> "Fixtures":
        image_path = artifact_dir / f"storefront-{run_id}.png"
        Image.new("RGB", (64, 40), (89, 45, 72)).save(image_path, format="PNG")
        custom_domain = (
            (
                os.getenv("TESTBED_STOREFRONT_CUSTOM_DOMAIN", "")
                if EXTERNAL_MODE == "live"
                else f"events-{run_id}.{PROVIDER_CUSTOMER_ZONE}"
            )
            .strip()
            .lower()
        )
        return cls(
            run_id=run_id,
            root_admin_id=f"user_testbed_storefront_root_{run_id}",
            root_admin_email=f"test_root+storefront_{run_id}@thespecialwedding.io",
            root_admin_password=f"StorefrontRoot-{run_id}!",
            signature_id=f"user_testbed_storefront_signature_{run_id}",
            signature_email=(
                f"test_planner+storefront_signature_{run_id}@thespecialwedding.io"
            ),
            signature_password=f"StorefrontSignature-{run_id}!",
            signature_subscription_id=f"sub_testbed_storefront_signature_{run_id}",
            solo_id=f"user_testbed_storefront_solo_{run_id}",
            solo_email=f"test_planner+storefront_solo_{run_id}@thespecialwedding.io",
            solo_password=f"StorefrontSolo-{run_id}!",
            solo_subscription_id=f"sub_testbed_storefront_solo_{run_id}",
            foreign_owner_id=f"user_testbed_storefront_foreign_{run_id}",
            foreign_email=f"test_planner+storefront_foreign_{run_id}@thespecialwedding.io",
            foreign_password=f"StorefrontForeign-{run_id}!",
            foreign_subscription_id=f"sub_testbed_storefront_foreign_{run_id}",
            slug=f"testbed-storefront-{run_id}",
            title=f"North Star Storefront {run_id}",
            description=f"Production storefront browser proof run {run_id}.",
            contact_email=f"storefront+{run_id}@thespecialwedding.io",
            contact_phone="+1 312 555 0148",
            package_id=f"package_testbed_storefront_{run_id}",
            package_name=f"Signature Planning Experience {run_id}",
            inactive_package_id=f"package_testbed_storefront_inactive_{run_id}",
            inactive_package_name=f"Inactive Package Must Not Render {run_id}",
            template_package_id=f"package_testbed_storefront_template_{run_id}",
            template_package_name=f"Template Package Must Not Render {run_id}",
            included_service_name=f"Wedding Day Production {run_id}",
            excluded_service_name=f"Excluded Service Must Not Render {run_id}",
            review_id=f"review_testbed_storefront_{run_id}",
            review_text=f"Calm, precise, and thoughtful — {run_id}.",
            unpublished_review_id=f"review_testbed_storefront_unpublished_{run_id}",
            unpublished_review_text=f"Unpublished Review Must Not Render {run_id}",
            foreign_package_id=f"package_testbed_storefront_foreign_{run_id}",
            foreign_package_name=f"Foreign Planner Package Must Not Render {run_id}",
            foreign_review_id=f"review_testbed_storefront_foreign_{run_id}",
            foreign_review_text=f"Foreign planner review must not render {run_id}",
            inquiry_name=f"Jordan Testbed {run_id}",
            inquiry_email=f"test_couple+storefront_{run_id}@thespecialwedding.io",
            inquiry_message=f"Storefront inquiry persistence proof {run_id}.",
            custom_domain=custom_domain,
            image_path=str(image_path),
        )

    def manifest_dict(self) -> dict[str, str]:
        return {
            "root_admin_id": self.root_admin_id,
            "root_admin_email": self.root_admin_email,
            "signature_id": self.signature_id,
            "signature_email": self.signature_email,
            "signature_subscription_id": self.signature_subscription_id,
            "solo_id": self.solo_id,
            "solo_email": self.solo_email,
            "solo_subscription_id": self.solo_subscription_id,
            "foreign_owner_id": self.foreign_owner_id,
            "foreign_email": self.foreign_email,
            "foreign_subscription_id": self.foreign_subscription_id,
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "package_id": self.package_id,
            "package_name": self.package_name,
            "inactive_package_id": self.inactive_package_id,
            "inactive_package_name": self.inactive_package_name,
            "template_package_id": self.template_package_id,
            "template_package_name": self.template_package_name,
            "included_service_name": self.included_service_name,
            "excluded_service_name": self.excluded_service_name,
            "review_id": self.review_id,
            "review_text": self.review_text,
            "unpublished_review_id": self.unpublished_review_id,
            "unpublished_review_text": self.unpublished_review_text,
            "foreign_package_id": self.foreign_package_id,
            "foreign_package_name": self.foreign_package_name,
            "foreign_review_id": self.foreign_review_id,
            "foreign_review_text": self.foreign_review_text,
            "inquiry_name": self.inquiry_name,
            "inquiry_email": self.inquiry_email,
            "inquiry_message": self.inquiry_message,
            "custom_domain": self.custom_domain,
            "image_path": self.image_path,
        }


def assert_safe_target() -> None:
    assert_safe_storefront_target(
        backend_url=BACKEND_URL,
        frontend_url=FRONTEND_URL,
        mongo_uri=MONGO_URI,
        mongo_db=MONGO_DB,
    )


def _workspace_evidence() -> dict[str, Any]:
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    git_status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    ).splitlines()
    tracked_diff = subprocess.check_output(
        ["git", "diff", "--binary", "HEAD", "--"], cwd=REPO_ROOT
    )
    source_paths = sorted(
        {
            *REPO_ROOT.glob("app/admin/packages/*.tsx"),
            *REPO_ROOT.glob("app/storefront/**/*.tsx"),
            REPO_ROOT / "app/api/storefront.py",
            REPO_ROOT / "app/models/storefront.py",
            *REPO_ROOT.glob("app/services/storefront_*.py"),
        }
    )
    source_sha256 = {
        str(source.relative_to(REPO_ROOT)): hashlib.sha256(
            source.read_bytes()
        ).hexdigest()
        for source in source_paths
        if source.is_file()
    }
    frontend = frontend_source_evidence(REPO_ROOT)
    storefront_evidence = storefront_evidence_source_evidence(REPO_ROOT)
    fingerprint_payload = json.dumps(
        {
            "git_head": git_head,
            "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
            "source_sha256": source_sha256,
            "frontend_source_sha256": frontend["frontend_source_sha256"],
            "storefront_evidence_source_sha256": storefront_evidence[
                "storefront_evidence_source_sha256"
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "git_head": git_head,
        "git_dirty": bool(git_status),
        "git_status": git_status,
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "source_sha256": source_sha256,
        "frontend_source_sha256": frontend["frontend_source_sha256"],
        "frontend_source_file_count": frontend["frontend_source_file_count"],
        "frontend_source_files": frontend["frontend_source_files"],
        "storefront_evidence_source_sha256": storefront_evidence[
            "storefront_evidence_source_sha256"
        ],
        "storefront_evidence_source_file_count": storefront_evidence[
            "storefront_evidence_source_file_count"
        ],
        "storefront_evidence_source_files": storefront_evidence[
            "storefront_evidence_source_files"
        ],
        "runtime_revision": f"storefront-e2e:{hashlib.sha256(fingerprint_payload).hexdigest()}",
    }


def _attest_frontend(expected_source_sha256: str, artifact_dir: Path) -> dict[str, Any]:
    build_id_path = REPO_ROOT / ".next" / "BUILD_ID"
    if not build_id_path.is_file():
        raise RuntimeError(
            "Storefront E2E consumes an existing production frontend; .next/BUILD_ID "
            "is missing. Build and start the loopback frontend before this driver."
        )
    build_id = build_id_path.read_text(encoding="utf-8").strip()
    if not build_id:
        raise RuntimeError("The local Next BUILD_ID is empty")
    receipt_path = REPO_ROOT / ".next" / "storefront-testbed-build-receipt.json"
    if not receipt_path.is_file():
        raise RuntimeError(
            "The production frontend has no source-bound storefront build receipt. "
            "Run `python testbed/build_storefront_frontend.py` before starting it."
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("The storefront build receipt is unreadable") from exc
    if not isinstance(receipt, dict):
        raise RuntimeError("The storefront build receipt is not an object")
    if receipt.get("build_id") != build_id:
        raise RuntimeError(
            "The served Next build does not match its storefront receipt"
        )
    if receipt.get("frontend_source_sha256") != expected_source_sha256:
        raise RuntimeError(
            "The production frontend build is stale relative to the current source tree"
        )
    response = requests.get(
        f"{FRONTEND_URL}/_next/static/{build_id}/_buildManifest.js",
        timeout=REQUEST_TIMEOUT,
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise RuntimeError(
            "The loopback frontend is not serving this checkout's production build "
            f"{build_id!r}: HTTP {response.status_code}"
        )
    retained_receipt = artifact_dir / "frontend-build-receipt.json"
    shutil.copy2(receipt_path, retained_receipt)
    return {
        "build_id": build_id,
        "build_id_sha256": hashlib.sha256(build_id_path.read_bytes()).hexdigest(),
        "served_build_manifest_sha256": hashlib.sha256(response.content).hexdigest(),
        "source_sha256": expected_source_sha256,
        "build_receipt": str(retained_receipt),
        "build_receipt_sha256": hashlib.sha256(
            retained_receipt.read_bytes()
        ).hexdigest(),
        "node_version": receipt.get("node_version"),
    }


def _password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _require_plan(db: Any, plan_id: str, expected: dict[str, bool]) -> None:
    plan = db["subscription_plans"].find_one({"_id": plan_id})
    if not plan:
        raise RuntimeError(
            f"Canonical {plan_id} is missing; run `python testbed/testbed.py seed`."
        )
    features = plan.get("features")
    if not isinstance(features, dict) or any(
        features.get(name) is not enabled for name, enabled in expected.items()
    ):
        raise RuntimeError(f"Canonical {plan_id} storefront entitlements drifted")


def _seed_canonical_plans(db: Any, run_id: str) -> None:
    """Seed only the two capability fixtures required by the isolated run."""

    plans = (
        (
            "plan_signature",
            "Signature",
            {"planner_storefront": True, "custom_domain": True},
        ),
        (
            "plan_solo",
            "Solo",
            {"planner_storefront": False, "custom_domain": False},
        ),
    )
    now = _now()
    for plan_id, name, features in plans:
        db["subscription_plans"].insert_one(
            {
                "_id": plan_id,
                "name": name,
                "description": "",
                "price_monthly": 0,
                "price_yearly": 0,
                "billing_model": "flat_rate",
                "is_metered": False,
                "meter_event_name": None,
                "meter_id": None,
                "max_weddings": 1,
                "max_guests_per_wedding": 100,
                "ai_credits_monthly": 10,
                "storage_gb": 1,
                "staff_seats": 0,
                "features": features,
                "features_list": [],
                "is_featured": False,
                "is_active": True,
                "display_order": 0,
                "sort_order": 0,
                "trial_days": 0,
                "created_by": "testbed",
                "seed_source": SEED_SOURCE,
                "testbed_run_id": run_id,
                "created_at": now,
                "updated_at": now,
            }
        )


def _seed(db: Any, fixtures: Fixtures) -> None:
    _require_plan(
        db, "plan_signature", {"planner_storefront": True, "custom_domain": True}
    )
    _require_plan(
        db, "plan_solo", {"planner_storefront": False, "custom_domain": False}
    )
    now = _now()
    db["users"].insert_one(
        {
            "_id": fixtures.root_admin_id,
            "email": fixtures.root_admin_email,
            "password_hash": _password_hash(fixtures.root_admin_password),
            "role": "ROOT_ADMIN",
            "first_name": "Storefront",
            "last_name": "Root Testbed",
            "is_active": True,
            "email_verified": True,
            "registration_source": "testbed",
            "seed_source": SEED_SOURCE,
            "testbed_run_id": fixtures.run_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    users = (
        (
            fixtures.signature_id,
            fixtures.signature_email,
            fixtures.signature_password,
            "plan_solo",  # stale profile value intentionally contradicts canonical subscription
            f"North Star Testbed {fixtures.run_id}",
        ),
        (
            fixtures.solo_id,
            fixtures.solo_email,
            fixtures.solo_password,
            "plan_signature",
            f"Solo Testbed {fixtures.run_id}",
        ),
        (
            fixtures.foreign_owner_id,
            fixtures.foreign_email,
            fixtures.foreign_password,
            "plan_solo",  # capability proof must come from the active subscription
            f"Conflict Owner Testbed {fixtures.run_id}",
        ),
    )
    for user_id, email, password, stale_plan_id, company in users:
        db["users"].insert_one(
            {
                "_id": user_id,
                "email": email,
                "password_hash": _password_hash(password),
                "role": "wedding_planner",
                "first_name": f"Storefront {fixtures.run_id}",
                "last_name": "Testbed",
                "company_name": company,
                "plan_id": stale_plan_id,
                "subscription_status": "active",
                "is_active": True,
                "email_verified": True,
                "registration_source": "testbed",
                "seed_source": SEED_SOURCE,
                "testbed_run_id": fixtures.run_id,
                "created_at": now,
                "updated_at": now,
            }
        )
    db["user_subscriptions"].insert_many(
        [
            {
                "_id": fixtures.signature_subscription_id,
                "user_id": fixtures.signature_id,
                "email": fixtures.signature_email,
                "plan_id": "plan_signature",
                "status": "active",
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
                "seed_source": SEED_SOURCE,
                "testbed_run_id": fixtures.run_id,
                "created_at": now,
                "updated_at": now,
            },
            {
                "_id": fixtures.solo_subscription_id,
                "user_id": fixtures.solo_id,
                "email": fixtures.solo_email,
                "plan_id": "plan_solo",
                "status": "active",
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
                "seed_source": SEED_SOURCE,
                "testbed_run_id": fixtures.run_id,
                "created_at": now,
                "updated_at": now,
            },
            {
                "_id": fixtures.foreign_subscription_id,
                "user_id": fixtures.foreign_owner_id,
                "email": fixtures.foreign_email,
                "plan_id": "plan_signature",
                "status": "active",
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
                "seed_source": SEED_SOURCE,
                "testbed_run_id": fixtures.run_id,
                "created_at": now,
                "updated_at": now,
            },
        ]
    )
    common_package = {
        "planner_id": fixtures.signature_id,
        "description": f"Storefront package fixture {fixtures.run_id}",
        "total_amount": 12500,
        "currency": "USD",
        "seed_source": SEED_SOURCE,
        "testbed_run_id": fixtures.run_id,
        "created_at": now,
        "updated_at": now,
    }
    db["packages"].insert_many(
        [
            {
                **common_package,
                "_id": fixtures.package_id,
                "name": fixtures.package_name,
                "status": "active",
                "is_template": False,
                "services": [
                    {
                        "name": fixtures.included_service_name,
                        "description": f"Included service {fixtures.run_id}",
                        "included": True,
                    },
                    {
                        "name": fixtures.excluded_service_name,
                        "description": f"Excluded service {fixtures.run_id}",
                        "included": False,
                    },
                ],
            },
            {
                **common_package,
                "_id": fixtures.inactive_package_id,
                "name": fixtures.inactive_package_name,
                "status": "archived",
                "is_template": False,
                "services": [],
            },
            {
                **common_package,
                "_id": fixtures.template_package_id,
                "name": fixtures.template_package_name,
                "status": "active",
                "is_template": True,
                "services": [],
            },
            {
                **common_package,
                "_id": fixtures.foreign_package_id,
                "planner_id": fixtures.foreign_owner_id,
                "name": fixtures.foreign_package_name,
                "status": "active",
                "is_template": False,
                "services": [],
            },
        ]
    )
    common_review = {
        "planner_id": fixtures.signature_id,
        "author_name": f"Testbed Couple {fixtures.run_id}",
        "rating": 5,
        "source": "testbed",
        "date": now.date().isoformat(),
        "seed_source": SEED_SOURCE,
        "testbed_run_id": fixtures.run_id,
        "created_at": now,
        "updated_at": now,
    }
    db["planner_reviews"].insert_many(
        [
            {
                **common_review,
                "_id": fixtures.review_id,
                "text": fixtures.review_text,
                "is_published": True,
            },
            {
                **common_review,
                "_id": fixtures.unpublished_review_id,
                "text": fixtures.unpublished_review_text,
                "is_published": False,
            },
            {
                **common_review,
                "_id": fixtures.foreign_review_id,
                "planner_id": fixtures.foreign_owner_id,
                "text": fixtures.foreign_review_text,
                "is_published": True,
            },
        ]
    )
    logger.info(
        "Seeded isolated run %s with positive and negative fixtures", fixtures.run_id
    )


def _login(email: str, password: str) -> str:
    response = requests.post(
        f"{BACKEND_URL}/admin/token",
        json={"email": email, "password": password},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Fixture login failed for {email}: {response.status_code} {response.text[:500]}"
        )
    token = response.json().get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Fixture login did not return an access token")
    return token


def _attest_backend(token: str, expected_revision: str) -> dict[str, Any]:
    response = requests.get(
        f"{BACKEND_URL}/admin/storefront/provider-readiness",
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(
            "Backend storefront readiness failed: "
            f"{response.status_code} {response.text[:500]}"
        )
    readiness = response.json()
    if readiness.get("runtime_revision") != expected_revision:
        raise RuntimeError(
            "The running backend is not attested to the current storefront source. "
            f"Restart it with STOREFRONT_RUNTIME_REVISION={expected_revision!r}; "
            f"received {readiness.get('runtime_revision')!r}."
        )
    return readiness


def _disabled_provider_child_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Create a child environment that cannot reach configured providers."""

    environment = dict(source if source is not None else os.environ)
    for name in PROVIDER_DISABLED_ENVIRONMENT_KEYS:
        environment[name] = ""
    return environment


def _assert_disabled_provider_fence(
    environment: Mapping[str, str] | None = None,
) -> None:
    values = environment if environment is not None else os.environ
    configured = {
        name: str(values.get(name, "")).strip()
        for name in PROVIDER_DISABLED_ENVIRONMENT_KEYS
        if str(values.get(name, "")).strip()
    }
    if configured:
        raise RuntimeError(
            "Provider-disabled proof requires provider credentials/configuration to be "
            f"blank in the verifier and running backend: {sorted(configured)}"
        )


def _live_provider_doctor(fixtures: Fixtures) -> dict[str, str]:
    """Validate exact live-provider fences without treating them as proof."""

    required = (
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_ZONE_ID",
        "CLOUDFLARE_SAAS_API_TOKEN",
        "CLOUDFLARE_API_TOKEN",
        "STOREFRONT_CNAME_TARGET",
        "S3_STOREFRONT_STAGING_BUCKET_NAME",
        "S3_BLOG_BUCKET_NAME",
        "TESTBED_STOREFRONT_CUSTOM_DOMAIN",
        "TESTBED_STOREFRONT_EXPECTED_PROVIDER_HOSTNAME_ID",
    )
    values = {name: os.getenv(name, "").strip() for name in required}
    missing = [name for name, value in values.items() if not value]
    allowed_domains = parse_exact_hostname_allowlist(
        os.getenv("TESTBED_STOREFRONT_ALLOWED_CUSTOM_DOMAINS")
    )
    allowed_cname_targets = parse_exact_hostname_allowlist(
        os.getenv("TESTBED_STOREFRONT_ALLOWED_CNAME_TARGETS")
    )
    exact_allowlists = {
        "CLOUDFLARE_ACCOUNT_ID": {
            value.strip()
            for value in os.getenv(
                "TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ACCOUNT_IDS", ""
            ).split(",")
            if value.strip()
        },
        "CLOUDFLARE_ZONE_ID": {
            value.strip()
            for value in os.getenv(
                "TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ZONE_IDS", ""
            ).split(",")
            if value.strip()
        },
        "S3_STOREFRONT_STAGING_BUCKET_NAME": {
            value.strip()
            for value in os.getenv(
                "TESTBED_STOREFRONT_ALLOWED_STAGING_BUCKETS", ""
            ).split(",")
            if value.strip()
        },
        "S3_BLOG_BUCKET_NAME": {
            value.strip()
            for value in os.getenv(
                "TESTBED_STOREFRONT_ALLOWED_PUBLIC_BUCKETS", ""
            ).split(",")
            if value.strip()
        },
    }
    # Provider IDs are opaque, so their explicit allowlist is parsed separately.
    raw_provider_ids = {
        value.strip()
        for value in os.getenv(
            "TESTBED_STOREFRONT_ALLOWED_PROVIDER_HOSTNAME_IDS", ""
        ).split(",")
        if value.strip()
    }
    if missing:
        raise RuntimeError(f"Live-provider doctor is missing exact fences: {missing}")
    if fixtures.custom_domain not in allowed_domains:
        raise RuntimeError(
            "Live custom hostname is not in the exact hostname allowlist"
        )
    if values["STOREFRONT_CNAME_TARGET"].lower() not in allowed_cname_targets:
        raise RuntimeError("Live CNAME target is not in the exact hostname allowlist")
    for field, allowlist in exact_allowlists.items():
        if values[field] not in allowlist:
            raise RuntimeError(f"Live {field} is not in its exact allowlist")
    if (
        values["TESTBED_STOREFRONT_EXPECTED_PROVIDER_HOSTNAME_ID"]
        not in raw_provider_ids
    ):
        raise RuntimeError("Live provider hostname ID is not in its exact allowlist")
    if values["S3_STOREFRONT_STAGING_BUCKET_NAME"] == values["S3_BLOG_BUCKET_NAME"]:
        raise RuntimeError("Storefront staging and public buckets must be distinct")
    return {
        name: value
        for name, value in values.items()
        if name not in {"CLOUDFLARE_API_TOKEN", "CLOUDFLARE_SAAS_API_TOKEN"}
    }


_LIFECYCLE_TEST_TITLE = (
    "gates Solo and completes the real Signature slug, publication, content, and "
    "inquiry lifecycle"
)
_PLAN_CAPABILITY_TEST_TITLE = (
    "lets root admin configure storefront plan access and proves the planner gate"
)
_MODAL_TEST_TITLE = (
    "keeps every modal tab readable, bounded, accessible, and keyboard-operable"
)
_DETERMINISTIC_PROVIDER_TEST_TITLE = (
    "drives deterministic provider state through real FastAPI Mongo routes without "
    "external-provider claims"
)
_LIVE_PROVIDER_FENCE_TEST_TITLE = (
    "runs a real provider lifecycle only after exact provider fencing succeeds"
)
_MODAL_PROJECTS = (
    "chromium-desktop-light",
    "chromium-desktop-dark",
    "chromium-mobile-320-light",
    "chromium-mobile-320-dark",
    "chromium-mobile-375-light",
    "chromium-mobile-375-dark",
    "chromium-mobile-390-light",
    "chromium-mobile-390-dark",
)

_PLAYWRIGHT_BASE_REQUIRED_RESULTS = {
    (
        _LIFECYCLE_TEST_TITLE,
        "chromium-desktop-light",
    ): "expected",
    (
        _PLAN_CAPABILITY_TEST_TITLE,
        "chromium-desktop-light",
    ): "expected",
}
_PLAYWRIGHT_BASE_REQUIRED_RESULTS.update(
    {(_MODAL_TEST_TITLE, project): "expected" for project in _MODAL_PROJECTS}
)
_PLAYWRIGHT_DETERMINISTIC_REQUIRED_RESULTS = {
    (
        _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "chromium-desktop-dark",
    ): "deterministic_provider_lifecycle",
}
_PLAYWRIGHT_LIVE_FENCE_RESULTS = {
    (
        _LIVE_PROVIDER_FENCE_TEST_TITLE,
        "chromium-desktop-dark",
    ): "configuration_fence_only",
}

_BASE_SCENARIO_RECEIPTS = (
    {
        "scenario_id": "21_root_admin_plan_capability_round_trip",
        "component": "root-plan-to-planner-gate",
        "test_title": _PLAN_CAPABILITY_TEST_TITLE,
        "project": "chromium-desktop-light",
    },
    {
        "scenario_id": "01_restricted_upgrade_gate",
        "component": "gate",
        "test_title": _LIFECYCLE_TEST_TITLE,
        "project": "chromium-desktop-light",
    },
    {
        "scenario_id": "05_draft_publish_filter_unpublish",
        "component": "publication-lifecycle",
        "test_title": _LIFECYCLE_TEST_TITLE,
        "project": "chromium-desktop-light",
    },
    {
        "scenario_id": "04_design_media_internal_preview",
        "component": "design-media-preview",
        "test_title": _LIFECYCLE_TEST_TITLE,
        "project": "chromium-desktop-light",
    },
    {
        "scenario_id": "06_inquiry_validation_rate_limit_delivery",
        "component": "inquiry-lifecycle",
        "test_title": _LIFECYCLE_TEST_TITLE,
        "project": "chromium-desktop-light",
    },
    {
        "scenario_id": "20_negative_content_filtering",
        "component": "content-filtering",
        "test_title": _LIFECYCLE_TEST_TITLE,
        "project": "chromium-desktop-light",
    },
    {
        "scenario_id": "03_keyboard_focus_and_copy",
        "component": "keyboard",
        "test_title": _MODAL_TEST_TITLE,
        "project": "chromium-desktop-light",
    },
    *(
        {
            "scenario_id": "02_modal_responsive_contrast",
            "component": f"layout-{project}",
            "test_title": _MODAL_TEST_TITLE,
            "project": project,
        }
        for project in _MODAL_PROJECTS
    ),
)
_DETERMINISTIC_SCENARIO_RECEIPTS = (
    {
        "scenario_id": "03_keyboard_focus_and_copy",
        "component": "copy",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "07_hostname_validation_provider_detection",
        "component": "preflight",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "11_fresh_claim_conflict_privacy",
        "component": "conflict-proof",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "12_hostname_active_ssl_pending",
        "component": "ssl-pending",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "13_ssl_active_https_failed",
        "component": "https-failed",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "08_domain_connect_resume_without_dns",
        "component": "authorization-resume",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "09_manual_and_emailed_instructions",
        "component": "instructions-lifecycle",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "10_dns_expected_vs_observed",
        "component": "dns-observations",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "15_missing_config_friendly_error",
        "component": "configuration-failure",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "16_existing_site_prevalidation",
        "component": "migration-prevalidation",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "17_activation_state_immutability",
        "component": "account-publication-immutability",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "18_disconnect_retry_receipt",
        "component": "deterministic-disconnect-recovery",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
    {
        "scenario_id": "19_platform_slug_survives_domain_lifecycle",
        "component": "slug-continuity",
        "test_title": _DETERMINISTIC_PROVIDER_TEST_TITLE,
        "project": "chromium-desktop-dark",
    },
)


def _required_playwright_results(provider_mode: str) -> dict[tuple[str, str], str]:
    """Return exact browser receipts appropriate to the selected provider mode.

    The live-mode spec currently proves only that the exact allowlist/credential
    fences were supplied.  Requiring that result keeps the suite honest about
    which branch ran, but its category deliberately prevents it from being
    interpreted as an external provider lifecycle receipt.
    """

    required = dict(_PLAYWRIGHT_BASE_REQUIRED_RESULTS)
    if provider_mode == "deterministic":
        required.update(_PLAYWRIGHT_DETERMINISTIC_REQUIRED_RESULTS)
    elif provider_mode == "live":
        required.update(_PLAYWRIGHT_LIVE_FENCE_RESULTS)
    else:
        raise ValueError(f"Unsupported storefront provider mode: {provider_mode!r}")
    return required


def _required_scenario_receipts(provider_mode: str) -> tuple[dict[str, str], ...]:
    if provider_mode == "deterministic":
        return (*_BASE_SCENARIO_RECEIPTS, *_DETERMINISTIC_SCENARIO_RECEIPTS)
    if provider_mode == "live":
        return _BASE_SCENARIO_RECEIPTS
    raise ValueError(f"Unsupported storefront provider mode: {provider_mode!r}")


# Backward-compatible deterministic default for focused receipt tests and tools.
_PLAYWRIGHT_REQUIRED_RESULTS = _required_playwright_results("deterministic")


def _playwright_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the JSON reporter without trusting aggregate counters.

    Playwright's JSON reporter nests suites recursively.  A production receipt
    must bind the exact test title and project to a terminal result; an
    unrelated passing test is not evidence for a storefront scenario.
    """

    flattened: list[dict[str, Any]] = []

    def visit(suite: object) -> None:
        if not isinstance(suite, dict):
            return
        for spec in suite.get("specs") or []:
            if not isinstance(spec, dict):
                continue
            title = str(spec.get("title") or "")
            for test in spec.get("tests") or []:
                if not isinstance(test, dict):
                    continue
                project = str(test.get("projectName") or test.get("projectId") or "")
                results = test.get("results") or []
                terminal = (
                    results[-1] if results and isinstance(results[-1], dict) else {}
                )
                flattened.append(
                    {
                        "title": title,
                        "project": project,
                        "status": str(terminal.get("status") or "missing"),
                        "expected_status": str(test.get("expectedStatus") or ""),
                        "attachments": [
                            attachment
                            for attachment in terminal.get("attachments") or []
                            if isinstance(attachment, dict)
                        ],
                    }
                )
        for child in suite.get("suites") or []:
            visit(child)

    for suite in payload.get("suites") or []:
        visit(suite)
    return flattened


def _decode_receipt_attachment(
    attachment: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    encoded = attachment.get("body")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("scenario receipt attachment has no inline body")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            "scenario receipt attachment body is not valid base64"
        ) from exc
    try:
        receipt = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("scenario receipt attachment is not valid JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("scenario receipt attachment root is not an object")
    return receipt, raw


def _validate_scenario_receipt(
    receipt: dict[str, Any],
    raw: bytes,
    *,
    requirement: Mapping[str, str],
    run_id: str,
    attachment_names: set[str],
) -> dict[str, Any]:
    expected = {
        "schema_version": 1,
        "scenario_id": requirement["scenario_id"],
        "component": requirement["component"],
        "run_id": run_id,
        "test_title": requirement["test_title"],
        "project": requirement["project"],
    }
    mismatches = {
        key: {"expected": value, "observed": receipt.get(key)}
        for key, value in expected.items()
        if receipt.get(key) != value
    }
    if mismatches:
        raise ValueError(f"scenario receipt identity mismatch: {mismatches}")
    captured_at = receipt.get("captured_at")
    if not isinstance(captured_at, str):
        raise ValueError("scenario receipt captured_at is missing")
    try:
        parsed_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("scenario receipt captured_at is invalid") from exc
    if parsed_at.tzinfo is None:
        raise ValueError("scenario receipt captured_at must include a timezone")
    routes = receipt.get("routes")
    if (
        not isinstance(routes, list)
        or not routes
        or any(
            not isinstance(route, str) or not route.startswith("/") for route in routes
        )
    ):
        raise ValueError("scenario receipt routes must be non-empty application paths")
    checks = receipt.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(
            not isinstance(name, str) or value is not True
            for name, value in checks.items()
        )
    ):
        raise ValueError("scenario receipt checks must be a non-empty all-true object")
    referenced = receipt.get("attachment_names")
    if (
        not isinstance(referenced, list)
        or not referenced
        or any(
            not isinstance(name, str) or name not in attachment_names
            for name in referenced
        )
    ):
        raise ValueError(
            "scenario receipt attachment_names must resolve inside its terminal test result"
        )
    return {
        **expected,
        "captured_at": captured_at,
        "routes": sorted(set(routes)),
        "checks": dict(sorted(checks.items())),
        "attachment_names": sorted(set(referenced)),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _parse_playwright_results(
    path: Path,
    *,
    run_id: str,
    provider_mode: str = "deterministic",
) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "FAILED", "error": "Playwright JSON report is missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAILED", "error": f"Unreadable Playwright JSON: {exc}"}
    if not isinstance(payload, dict):
        return {"status": "FAILED", "error": "Playwright JSON root is not an object"}
    stats = payload.get("stats")
    counts = {
        "expected": int((stats or {}).get("expected", 0)),
        "unexpected": int((stats or {}).get("unexpected", 0)),
        "flaky": int((stats or {}).get("flaky", 0)),
        "skipped": int((stats or {}).get("skipped", 0)),
    }
    results = _playwright_results(payload)
    indexed = {(result["title"], result["project"]): result for result in results}
    missing: list[dict[str, str]] = []
    wrong_status: list[dict[str, str]] = []
    required_results = _required_playwright_results(provider_mode)
    for (title, project), _category in required_results.items():
        result = indexed.get((title, project))
        if result is None:
            missing.append({"title": title, "project": project})
        elif result["status"] != "passed":
            wrong_status.append(result)
    scenario_receipts: list[dict[str, Any]] = []
    missing_scenario_receipts: list[dict[str, str]] = []
    invalid_scenario_receipts: list[dict[str, str]] = []
    for requirement in _required_scenario_receipts(provider_mode):
        result = indexed.get((requirement["test_title"], requirement["project"]))
        if result is None or result["status"] != "passed":
            continue
        attachment_name = (
            f"scenario-receipt-{requirement['scenario_id']}-{requirement['component']}"
        )
        attachments = result.get("attachments") or []
        matches = [
            attachment
            for attachment in attachments
            if attachment.get("name") == attachment_name
        ]
        identity = dict(requirement)
        if len(matches) != 1:
            missing_scenario_receipts.append(identity)
            continue
        try:
            receipt, raw = _decode_receipt_attachment(matches[0])
            scenario_receipts.append(
                _validate_scenario_receipt(
                    receipt,
                    raw,
                    requirement=requirement,
                    run_id=run_id,
                    attachment_names={
                        str(attachment.get("name") or "") for attachment in attachments
                    },
                )
            )
        except ValueError as exc:
            invalid_scenario_receipts.append({**identity, "error": str(exc)})
    exact_receipts_pass = (
        not missing
        and not wrong_status
        and not missing_scenario_receipts
        and not invalid_scenario_receipts
    )
    return {
        "status": (
            "PASSED"
            if counts["unexpected"] == 0
            and counts["flaky"] == 0
            and exact_receipts_pass
            else "FAILED"
        ),
        "counts": counts,
        "provider_mode": provider_mode,
        "provider_receipt_scope": (
            "deterministic_provider_lifecycle"
            if provider_mode == "deterministic"
            else "configuration_fence_only_not_external_lifecycle"
        ),
        "required_result_count": len(required_results),
        "observed_result_count": len(results),
        "missing_required_results": missing,
        "wrong_required_results": wrong_status,
        "required_scenario_receipt_count": len(
            _required_scenario_receipts(provider_mode)
        ),
        "scenario_receipts": scenario_receipts,
        "missing_scenario_receipts": missing_scenario_receipts,
        "invalid_scenario_receipts": invalid_scenario_receipts,
        "report": str(path),
    }


def _run_playwright(
    manifest_path: Path,
    artifact_dir: Path,
    fixtures: Fixtures,
    *,
    provider_control_token: str,
) -> dict[str, Any]:
    executable = REPO_ROOT / "node_modules" / ".bin" / "playwright"
    if not executable.is_file():
        raise RuntimeError(
            "Playwright is missing; run `npm ci` before the storefront E2E"
        )
    environment = dict(os.environ)
    environment.update(
        {
            "STOREFRONT_TESTBED_RUN_MANIFEST": str(manifest_path),
            "STOREFRONT_TESTBED_SIGNATURE_PASSWORD": fixtures.signature_password,
            "STOREFRONT_TESTBED_SOLO_PASSWORD": fixtures.solo_password,
            "STOREFRONT_TESTBED_FOREIGN_PASSWORD": fixtures.foreign_password,
            "STOREFRONT_TESTBED_ROOT_ADMIN_PASSWORD": fixtures.root_admin_password,
            "STOREFRONT_PROVIDER_HARNESS_RUN_ID": fixtures.run_id,
            "STOREFRONT_PROVIDER_HARNESS_TOKEN": provider_control_token,
        }
    )
    command = [
        str(executable),
        "test",
        "--config",
        "testbed/playwright.storefront.config.ts",
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    (artifact_dir / "playwright.stdout.log").write_text(result.stdout, encoding="utf-8")
    (artifact_dir / "playwright.stderr.log").write_text(result.stderr, encoding="utf-8")
    parsed = _parse_playwright_results(
        artifact_dir / "playwright" / "results.json",
        run_id=fixtures.run_id,
        provider_mode=EXTERNAL_MODE,
    )
    parsed.update(
        {
            "returncode": result.returncode,
            "command": command,
            "stdout": str(artifact_dir / "playwright.stdout.log"),
            "stderr": str(artifact_dir / "playwright.stderr.log"),
        }
    )
    if result.returncode != 0:
        parsed["status"] = "FAILED"
    return parsed


def _retain_playwright_artifact_manifest(
    artifact_dir: Path,
    *,
    run_id: str,
    workspace: dict[str, Any],
    frontend_runtime: dict[str, Any],
    provider_mode: str,
) -> dict[str, Any]:
    """Hash the generated evidence and require each promised artifact family."""

    root = artifact_dir / "playwright"
    required_files = (
        root / "results.json",
        root / "results.xml",
        root / "html" / "index.html",
    )
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise AssertionError(f"Required Playwright artifacts are missing: {missing}")
    files = sorted(path for path in root.rglob("*") if path.is_file())
    trace_files = [path for path in files if path.name == "trace.zip"]
    video_files = [path for path in files if path.suffix.lower() == ".webm"]
    screenshot_files = [path for path in files if path.suffix.lower() == ".png"]
    minimum = len(_required_playwright_results(provider_mode))
    if len(trace_files) < minimum:
        raise AssertionError(
            f"Playwright produced {len(trace_files)} traces for {minimum} required results"
        )
    if len(video_files) < minimum:
        raise AssertionError(
            f"Playwright produced {len(video_files)} videos for {minimum} required results"
        )
    if len(screenshot_files) < minimum:
        raise AssertionError(
            "Playwright did not retain a screenshot for every required browser result"
        )
    entries = [
        {
            "path": str(path.relative_to(artifact_dir)),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in files
    ]
    return {
        "schema_version": 1,
        "run_id": run_id,
        "generated_at": _now().isoformat(),
        "git_head": workspace["git_head"],
        "tracked_diff_sha256": workspace["tracked_diff_sha256"],
        "frontend_source_sha256": workspace["frontend_source_sha256"],
        "storefront_evidence_source_sha256": workspace[
            "storefront_evidence_source_sha256"
        ],
        "storefront_evidence_source_files": workspace[
            "storefront_evidence_source_files"
        ],
        "frontend_build_id": frontend_runtime["build_id"],
        "backend_runtime_revision": workspace["runtime_revision"],
        "file_count": len(entries),
        "trace_count": len(trace_files),
        "video_count": len(video_files),
        "screenshot_count": len(screenshot_files),
        "files": entries,
    }


def _write_final_artifact_seal(
    artifact_dir: Path,
    *,
    manifest: dict[str, Any],
    workspace: Mapping[str, Any],
    frontend_runtime: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal the immutable run artifacts after cleanup and process shutdown.

    The seal intentionally excludes Mongo's mutable storage directory and the
    seal file itself. The final run manifest must already be persisted, so its
    bytes are included without introducing a circular self-hash.
    """

    if manifest.get("cleanup", {}).get("status") != "PASSED":
        raise AssertionError("Final artifact sealing requires successful cleanup")
    shutdown_status = (
        manifest.get("isolated_runtime", {}).get("shutdown", {}).get("status")
    )
    if shutdown_status not in {"STOPPED", "NOT_STARTED"}:
        raise AssertionError("Final artifact sealing requires runtime shutdown")
    if not manifest.get("completed_at"):
        raise AssertionError("Final artifact sealing requires completed_at")
    manifest_path = artifact_dir / "run-manifest.json"
    if not manifest_path.is_file():
        raise AssertionError("Final run manifest is missing before artifact sealing")
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(persisted, dict)
        or persisted.get("run_id") != manifest.get("run_id")
        or persisted.get("completed_at") != manifest.get("completed_at")
        or persisted.get("artifact_manifest") != manifest.get("artifact_manifest")
    ):
        raise AssertionError("Persisted final manifest does not match the seal input")

    routes: set[str] = set()
    scenarios: dict[str, Any] = {}
    for scenario, status in sorted(manifest.get("browser_scenarios", {}).items()):
        evidence = manifest.get("browser_scenario_evidence", {}).get(scenario)
        if status == "PASSED":
            evidence_error = _scenario_evidence_error(manifest, scenario, evidence)
            if evidence_error:
                raise AssertionError(
                    f"Cannot seal invalid PASSED scenario {scenario}: {evidence_error}"
                )
            scenario_routes = sorted(set(evidence["routes"]))
            receipt_sha256 = sorted(
                str(receipt["sha256"]) for receipt in evidence["receipts"]
            )
            routes.update(scenario_routes)
        else:
            scenario_routes = []
            receipt_sha256 = []
        scenarios[scenario] = {
            "status": status,
            "routes": scenario_routes,
            "receipt_sha256": receipt_sha256,
        }

    files: list[dict[str, Any]] = []
    for path in sorted(
        candidate for candidate in artifact_dir.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(artifact_dir)
        if relative == Path("artifact-seal.json") or relative.parts[0] == "mongo-data":
            continue
        files.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if "run-manifest.json" not in {entry["path"] for entry in files}:
        raise AssertionError("Final artifact index does not include the run manifest")

    seal = {
        "schema_version": 2,
        "run_id": manifest["run_id"],
        "generated_at": _now().isoformat(),
        "sealed_after": {
            "cleanup": manifest["cleanup"]["status"],
            "runtime_shutdown": shutdown_status,
            "completed_at": manifest["completed_at"],
        },
        "git_head": workspace["git_head"],
        "tracked_diff_sha256": workspace["tracked_diff_sha256"],
        "frontend_source_sha256": workspace["frontend_source_sha256"],
        "storefront_evidence_source_sha256": workspace[
            "storefront_evidence_source_sha256"
        ],
        "storefront_evidence_source_files": workspace.get(
            "storefront_evidence_source_files", {}
        ),
        "frontend_build_id": frontend_runtime.get("build_id"),
        "backend_runtime_revision": workspace["runtime_revision"],
        "routes": sorted(routes),
        "scenarios": scenarios,
        "file_count": len(files),
        "files": files,
        "excluded_mutable_paths": ["mongo-data/**", "artifact-seal.json"],
    }
    _write_json(artifact_dir / "artifact-seal.json", seal)
    return seal


def _assert_authenticated_settings(fixtures: Fixtures, token: str) -> dict[str, Any]:
    response = requests.get(
        f"{BACKEND_URL}/admin/storefront/settings",
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise AssertionError(
            f"Authenticated settings read failed: {response.status_code} {response.text[:500]}"
        )
    settings = response.json().get("settings")
    required = {
        "slug": fixtures.slug,
        "title": fixtures.title,
        "description": fixtures.description,
        "contact_email": fixtures.contact_email,
        "contact_phone": fixtures.contact_phone,
        "is_published": True,
        "packages_enabled": True,
        "reviews_enabled": True,
    }
    if not isinstance(settings, dict) or any(
        settings.get(name) != value for name, value in required.items()
    ):
        raise AssertionError(
            f"Authenticated settings do not match browser intent: {settings!r}"
        )
    if fixtures.run_id not in json.dumps(settings, default=str):
        raise AssertionError("Authenticated settings response lost the run identity")
    return settings


def _account_state_fingerprint(db: Any, fixtures: Fixtures) -> str:
    """Bind acceptance to unchanged account/subscription business state.

    Authentication itself updates ``users.last_login``. That single telemetry
    field is excluded explicitly; every other user field and the complete
    subscription documents remain protected by the hash.
    """

    users = list(
        db["users"]
        .find(
            {
                "_id": {
                    "$in": [
                        fixtures.signature_id,
                        fixtures.solo_id,
                        fixtures.foreign_owner_id,
                        fixtures.root_admin_id,
                    ]
                }
            }
        )
        .sort("_id", 1)
    )
    protected_users = []
    for user in users:
        protected = dict(user)
        protected.pop("last_login", None)
        protected_users.append(protected)

    payload = {
        "users": protected_users,
        "subscriptions": list(
            db["user_subscriptions"]
            .find(
                {
                    "_id": {
                        "$in": [
                            fixtures.signature_subscription_id,
                            fixtures.solo_subscription_id,
                            fixtures.foreign_subscription_id,
                        ]
                    }
                }
            )
            .sort("_id", 1)
        ),
    }
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _assert_persistence(
    db: Any,
    fixtures: Fixtures,
    token: str,
    account_state_before: str,
) -> dict[str, Any]:
    settings_api = _assert_authenticated_settings(fixtures, token)
    settings = db["storefront_settings"].find_one({"planner_id": fixtures.signature_id})
    if (
        not settings
        or settings.get("slug") != fixtures.slug
        or settings.get("is_published") is not True
    ):
        raise AssertionError(
            "Browser publication did not persist for the Signature owner"
        )
    if db["storefront_settings"].count_documents({"planner_id": fixtures.solo_id}):
        raise AssertionError("Restricted Solo planner acquired storefront settings")
    inquiries = list(
        db["storefront_inquiries"].find(
            {
                "planner_id": fixtures.signature_id,
                "storefront_slug": fixtures.slug,
                "name": fixtures.inquiry_name,
                "email": fixtures.inquiry_email,
                "message": fixtures.inquiry_message,
            }
        )
    )
    if len(inquiries) != 1:
        raise AssertionError(f"Expected one run-scoped inquiry, found {len(inquiries)}")
    inquiry = inquiries[0]
    if fixtures.run_id not in json.dumps(inquiry, default=str):
        raise AssertionError("Persisted inquiry lost the run identity")
    notification = inquiry.get("notification")
    if not isinstance(notification, dict):
        raise AssertionError("Inquiry notification outcome was not persisted")
    if INQUIRY_DELIVERY_MODE == "disabled":
        if (
            notification.get("status") != "retry_pending"
            or notification.get("delivery_outcome") != "not_sent"
        ):
            raise AssertionError(
                f"Delivery-disabled inquiry did not fail closed: {notification!r}"
            )
        if notification.get("provider_id"):
            raise AssertionError(
                "Delivery-disabled inquiry has an external provider ID"
            )
        if int(notification.get("attempt_count") or 0) < 2:
            raise AssertionError(
                "Delivery-disabled inquiry did not retain the browser's idempotent retry attempt"
            )
    elif notification.get("status") != "sent" or not notification.get("provider_id"):
        raise AssertionError(
            f"Required inquiry delivery was not confirmed: {notification!r}"
        )
    seeded_counts = {
        "users": db["users"].count_documents({"testbed_run_id": fixtures.run_id}),
        "subscriptions": db["user_subscriptions"].count_documents(
            {"testbed_run_id": fixtures.run_id}
        ),
        "packages": db["packages"].count_documents({"testbed_run_id": fixtures.run_id}),
        "reviews": db["planner_reviews"].count_documents(
            {"testbed_run_id": fixtures.run_id}
        ),
    }
    if seeded_counts != {"users": 4, "subscriptions": 3, "packages": 4, "reviews": 3}:
        raise AssertionError(f"Run-scoped fixture identity drifted: {seeded_counts}")
    account_state_after = _account_state_fingerprint(db, fixtures)
    if account_state_after != account_state_before:
        raise AssertionError(
            "Storefront browser actions mutated protected account or subscription fields"
        )
    return {
        "status": "PASSED",
        "settings_revision": settings_api.get("revision"),
        "inquiry_id": str(inquiry["_id"]),
        "notification_status": notification.get("status"),
        "notification_delivery_outcome": notification.get("delivery_outcome"),
        "notification_attempt_count": notification.get("attempt_count"),
        "seeded_counts": seeded_counts,
        "account_state_sha256_before": account_state_before,
        "account_state_sha256_after": account_state_after,
        "excluded_auth_telemetry_fields": ["last_login"],
        "authenticated_fixture_count": db["users"].count_documents(
            {
                "_id": {
                    "$in": [
                        fixtures.signature_id,
                        fixtures.solo_id,
                        fixtures.foreign_owner_id,
                    ]
                },
                "last_login": {"$type": "date"},
            }
        ),
    }


def _assert_domain_connect_flow_receipts(
    flows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prove callback outcomes survived the required one-time flow consumption.

    The authenticated completion POST consumes every Domain Connect flow.  The
    durable cancellation/authorization evidence therefore lives in
    ``completion_outcome``; retaining a raw ``cancelled`` callback state would
    instead mean the one-time completion step never finished.
    """

    flow_states = {str(row.get("state")) for row in flows}
    consumed_outcomes = {
        str(row.get("completion_outcome"))
        for row in flows
        if row.get("state") == "consumed" and row.get("completion_outcome")
    }
    for required_outcome in ("cancelled", "authorized"):
        if required_outcome not in consumed_outcomes:
            raise AssertionError(
                "No consumed Domain Connect "
                f"{required_outcome} completion was retained: "
                f"states={sorted(flow_states)}, "
                f"outcomes={sorted(consumed_outcomes)}"
            )

    cancelled_flows = [
        row
        for row in flows
        if row.get("state") == "consumed"
        and row.get("completion_outcome") == "cancelled"
    ]
    if not any(
        row.get("consumed_at")
        and row.get("callback_recorded_at")
        and row.get("provider_callback_error") == "access_denied"
        and isinstance(row.get("last_error"), Mapping)
        and row["last_error"].get("code") == "domain_connect_authorization_cancelled"
        for row in cancelled_flows
    ):
        raise AssertionError(
            "The consumed Domain Connect cancelled completion is missing durable "
            "callback metadata"
        )

    authorized_flows = [
        row
        for row in flows
        if row.get("state") == "consumed"
        and row.get("completion_outcome") == "authorized"
    ]
    if not any(
        row.get("consumed_at")
        and row.get("callback_recorded_at")
        and row.get("last_error") is None
        for row in authorized_flows
    ):
        raise AssertionError(
            "The consumed Domain Connect authorized completion is missing durable "
            "callback metadata"
        )

    return {
        "flow_count": len(flows),
        "flow_states": sorted(flow_states),
        "completion_outcomes": sorted(consumed_outcomes),
    }


def _assert_domain_control_plane(db: Any, fixtures: Fixtures) -> dict[str, Any]:
    """Bind browser receipts to real owner-scoped lifecycle rows in Mongo."""

    planner_ids = [fixtures.signature_id, fixtures.foreign_owner_id]
    active = list(db["storefront_domains"].find({"planner_id": {"$in": planner_ids}}))
    if active:
        raise AssertionError(
            "The deterministic browser lifecycle left an active domain row: "
            f"{[(row.get('planner_id'), row.get('hostname')) for row in active]}"
        )

    flows = list(
        db["storefront_domain_flows"].find({"planner_id": {"$in": planner_ids}})
    )
    flow_receipt = _assert_domain_connect_flow_receipts(flows)

    operations = list(
        db["storefront_domain_operations"].find({"planner_id": fixtures.signature_id})
    )
    operation_kinds = {str(row.get("kind")) for row in operations}
    required_kinds = {"instruction_email", "provider_create", "provider_delete"}
    if not required_kinds.issubset(operation_kinds):
        raise AssertionError(
            f"Domain operation ledger is incomplete: {sorted(operation_kinds)}"
        )
    provider_delete_operations = {
        str(row.get("operation_id")): row
        for row in operations
        if row.get("kind") == "provider_delete" and row.get("operation_id")
    }
    if not provider_delete_operations or not all(
        row.get("request_fingerprint")
        and len(str(row["request_fingerprint"])) == 64
        and row.get("state") in {"completed", "failed"}
        for row in provider_delete_operations.values()
    ):
        raise AssertionError(
            "Provider deletion attempts have no bounded, durable operation receipts"
        )

    instruction_links = list(
        db["storefront_domain_instruction_links"].find(
            {"planner_id": fixtures.signature_id}
        )
    )
    if not instruction_links or not any(
        row.get("state") == "revoked" and row.get("revoked_token_digest")
        for row in instruction_links
    ):
        raise AssertionError(
            "The seven-day DNS instruction link was not revoked durably"
        )

    conflict_hostname = f"claimed-{fixtures.run_id}.{PROVIDER_CUSTOMER_ZONE}"
    conflict_claims = list(
        db["storefront_domain_conflict_claims"].find(
            {
                "claimant_planner_id": fixtures.signature_id,
                "hostname": conflict_hostname,
            }
        )
    )
    if len(conflict_claims) != 1:
        raise AssertionError(
            f"Expected one retained fresh conflict claim, found {len(conflict_claims)}"
        )
    conflict_claim = conflict_claims[0]
    if (
        conflict_claim.get("application_status") != "disconnected"
        or conflict_claim.get("status") != "cancelled"
        or not conflict_claim.get("ownership_verified_at")
        or "current_owner_key" in conflict_claim
        or conflict_claim.get("provider_hostname_id")
        or conflict_claim.get("reserved_owner")
    ):
        raise AssertionError(
            "The fresh conflict proof was not retained as a cancelled, verified, "
            "non-transferring claimant-owned receipt"
        )

    tombstones = list(
        db["storefront_domain_tombstones"].find(
            {
                "planner_id": {"$in": planner_ids},
                "hostname": {"$regex": rf"\.{re.escape(PROVIDER_CUSTOMER_ZONE)}$"},
            }
        )
    )
    signature_tombstones = [
        row for row in tombstones if row.get("planner_id") == fixtures.signature_id
    ]
    if not any(
        row.get("provider_hostname_id")
        and row.get("deletion_receipt_id")
        and row.get("hostname") == fixtures.custom_domain
        and row.get("provider_delete_operation_id") in provider_delete_operations
        and provider_delete_operations[row["provider_delete_operation_id"]].get("state")
        == "completed"
        and row.get("provider_delete_receipt")
        == provider_delete_operations[row["provider_delete_operation_id"]].get(
            "provider_receipt"
        )
        for row in signature_tombstones
    ):
        raise AssertionError(
            "The deterministic provider-adapter disconnect has no bound deletion "
            "operation and tombstone receipt"
        )

    return {
        "status": "PASSED",
        **flow_receipt,
        "operation_count": len(operations),
        "operation_kinds": sorted(operation_kinds),
        "provider_delete_operation_ids": sorted(provider_delete_operations),
        "instruction_link_count": len(instruction_links),
        "revoked_instruction_links": sum(
            row.get("state") == "revoked" for row in instruction_links
        ),
        "conflict_claim_count": len(conflict_claims),
        "conflict_claim_attempt_id": str(conflict_claim.get("attempt_id")),
        "conflict_claim_verified_at": str(conflict_claim.get("ownership_verified_at")),
        "tombstone_count": len(tombstones),
        "deterministic_provider_deletion_receipts": sorted(
            str(row["deletion_receipt_id"])
            for row in signature_tombstones
            if row.get("deletion_receipt_id")
        ),
        "external_provider_live": False,
    }


def _record_browser_scenario(
    manifest: dict[str, Any],
    scenario: str,
    status: str,
    *,
    blocker: str | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> None:
    """Update one scenario only when green evidence is structured and run-bound."""

    if scenario not in manifest["browser_scenarios"]:
        raise KeyError(f"Unknown storefront browser scenario: {scenario}")
    if status not in {"NOT RUN", "PASSED", "BLOCKED"}:
        raise ValueError(f"Unsupported storefront scenario status: {status!r}")
    if status == "PASSED":
        if blocker:
            raise ValueError(f"Passed scenario {scenario} cannot retain a blocker")
        evidence_error = _scenario_evidence_error(manifest, scenario, evidence)
        if evidence_error:
            raise ValueError(
                f"Passed scenario {scenario} requires structured run-bound evidence: "
                f"{evidence_error}"
            )
        manifest["browser_scenario_blockers"].pop(scenario, None)
    elif status == "BLOCKED":
        if not blocker:
            raise ValueError(f"Blocked scenario {scenario} requires a blocker")
        manifest["browser_scenario_blockers"][scenario] = blocker
    elif blocker:
        manifest["browser_scenario_blockers"][scenario] = blocker
    manifest["browser_scenarios"][scenario] = status
    if status == "PASSED" and evidence is not None:
        manifest["browser_scenario_evidence"][scenario] = dict(evidence)
    elif status != "PASSED":
        manifest["browser_scenario_evidence"].pop(scenario, None)


def _scenario_evidence_error(
    manifest: Mapping[str, Any],
    scenario: str,
    evidence: Mapping[str, Any] | None,
) -> str | None:
    if not isinstance(evidence, Mapping):
        return "evidence is missing or is not an object"
    run_id = manifest.get("run_id")
    if evidence.get("schema_version") != 1:
        return "schema_version is not 1"
    if evidence.get("scenario_id") != scenario:
        return "scenario_id does not match the ledger row"
    if not isinstance(run_id, str) or evidence.get("run_id") != run_id:
        return "run_id does not match this manifest"
    routes = evidence.get("routes")
    if (
        not isinstance(routes, list)
        or not routes
        or any(
            not isinstance(route, str) or not route.startswith("/") for route in routes
        )
    ):
        return "routes are missing or invalid"
    receipts = evidence.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        return "receipts are missing"
    observed_routes: set[str] = set()
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            return "a receipt is not an object"
        if receipt.get("scenario_id") != scenario or receipt.get("run_id") != run_id:
            return "a receipt is not bound to this scenario and run"
        sha256 = receipt.get("sha256")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            return "a receipt sha256 is invalid"
        receipt_routes = receipt.get("routes")
        if (
            not isinstance(receipt_routes, list)
            or not receipt_routes
            or any(
                not isinstance(route, str) or not route.startswith("/")
                for route in receipt_routes
            )
        ):
            return "a receipt has invalid routes"
        observed_routes.update(receipt_routes)
        checks = receipt.get("checks")
        if (
            not isinstance(checks, Mapping)
            or not checks
            or any(value is not True for value in checks.values())
        ):
            return "a receipt has missing or failed checks"
    if set(routes) != observed_routes:
        return "scenario routes do not equal the receipt route union"
    return None


def _scenario_evidence_from_playwright(
    playwright: Mapping[str, Any],
    *,
    scenario: str,
    run_id: str,
    provider_mode: str,
) -> dict[str, Any] | None:
    requirements = [
        requirement
        for requirement in _required_scenario_receipts(provider_mode)
        if requirement["scenario_id"] == scenario
    ]
    if not requirements:
        return None
    indexed = {
        (
            receipt.get("scenario_id"),
            receipt.get("component"),
            receipt.get("test_title"),
            receipt.get("project"),
        ): receipt
        for receipt in playwright.get("scenario_receipts") or []
        if isinstance(receipt, dict)
    }
    receipts: list[dict[str, Any]] = []
    for requirement in requirements:
        receipt = indexed.get(
            (
                requirement["scenario_id"],
                requirement["component"],
                requirement["test_title"],
                requirement["project"],
            )
        )
        if not isinstance(receipt, dict):
            return None
        receipts.append(receipt)
    routes = sorted(
        {
            route
            for receipt in receipts
            for route in receipt.get("routes") or []
            if isinstance(route, str)
        }
    )
    return {
        "schema_version": 1,
        "scenario_id": scenario,
        "run_id": run_id,
        "routes": routes,
        "receipts": receipts,
    }


def _enforce_browser_scenario_truth(manifest: dict[str, Any]) -> list[str]:
    """Fail closed if a future edit reintroduces contradictory ledger rows."""

    contradictions = sorted(
        scenario
        for scenario, status in manifest["browser_scenarios"].items()
        if status == "PASSED"
        and (
            scenario in manifest.get("browser_scenario_blockers", {})
            or _scenario_evidence_error(
                manifest,
                scenario,
                manifest.get("browser_scenario_evidence", {}).get(scenario),
            )
        )
    )
    for scenario in contradictions:
        manifest["browser_scenarios"][scenario] = "BLOCKED"
        manifest["browser_scenario_blockers"][scenario] = (
            "Evidence ledger contradiction: this scenario was marked passed without "
            "valid run-bound structured evidence or while a blocker remained. The "
            "driver failed closed."
        )
        manifest.get("browser_scenario_evidence", {}).pop(scenario, None)
    return contradictions


def _run_cleanup(
    manifest_path: Path, fixtures: Fixtures, artifact_dir: Path
) -> dict[str, Any]:
    environment = dict(os.environ)
    environment.update(
        {
            "STOREFRONT_TESTBED_RUN_MANIFEST": str(manifest_path),
            "STOREFRONT_TESTBED_SIGNATURE_PASSWORD": fixtures.signature_password,
            "STOREFRONT_TESTBED_SOLO_PASSWORD": fixtures.solo_password,
            "STOREFRONT_TESTBED_FOREIGN_PASSWORD": fixtures.foreign_password,
            "BACKEND_URL": BACKEND_URL,
            "FRONTEND_URL": FRONTEND_URL,
            "MONGO_URI": str(MONGO_URI),
            "MONGODB_URI": str(MONGO_URI),
            "MONGO_DB": MONGO_DB,
            "MONGO_NAME": MONGO_DB,
        }
    )
    command = [
        str(REPO_ROOT / ".venv.nosync" / "bin" / "python"),
        str(REPO_ROOT / "testbed" / "cleanup_storefront_frontend_lifecycle_state.py"),
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    (artifact_dir / "cleanup.stdout.log").write_text(result.stdout, encoding="utf-8")
    (artifact_dir / "cleanup.stderr.log").write_text(result.stderr, encoding="utf-8")
    return {
        "status": "PASSED" if result.returncode == 0 else "FAILED",
        "returncode": result.returncode,
        "command": command,
        "stdout": str(artifact_dir / "cleanup.stdout.log"),
        "stderr": str(artifact_dir / "cleanup.stderr.log"),
    }


def _base_manifest(
    run_id: str,
    artifact_dir: Path,
    manifest_path: Path,
    fixtures: Fixtures,
    workspace: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "driver": "verify_storefront_frontend_lifecycle",
        "run_id": run_id,
        "started_at": _now().isoformat(),
        "completed_at": None,
        "manifest_path": str(manifest_path),
        "artifact_dir": str(artifact_dir),
        "backend_url": BACKEND_URL,
        "frontend_url": FRONTEND_URL,
        "ports": {
            "backend": _port(BACKEND_URL),
            "frontend": _port(FRONTEND_URL),
            "frontend_upstream": _port(FRONTEND_UPSTREAM_URL),
        },
        "database": MONGO_DB,
        "provider_mode": "live" if EXTERNAL_MODE == "live" else "deterministic",
        "inquiry_delivery_mode": INQUIRY_DELIVERY_MODE,
        "workspace": workspace,
        "expected_backend_revision": workspace["runtime_revision"],
        "frontend_runtime": None,
        "backend_runtime": None,
        "isolated_runtime": None,
        "fixtures": fixtures.manifest_dict(),
        "acceptance": {
            "automated_chromium": "NOT RUN",
            "deterministic_provider_control_plane": "NOT RUN",
            "deterministic_disconnect_cleanup": "NOT RUN",
            "external_provider_deletion": "BLOCKED",
            "missing_configuration_readiness": "BLOCKED",
            "migration_prevalidation_mutation_snapshot": "BLOCKED",
            "inquiry_live_delivery": (
                "BLOCKED" if INQUIRY_DELIVERY_MODE == "disabled" else "NOT RUN"
            ),
            "media_provider_disabled": "NOT RUN",
            "media_live_lifecycle": "BLOCKED",
            "live_provider": "BLOCKED",
            "in_app_chrome_playback": "NOT RUN",
            "persistence": "NOT RUN",
            "account_and_subscription_immutability": "NOT RUN",
            "cleanup": "NOT RUN",
        },
        "browser_scenarios": {
            "01_restricted_upgrade_gate": "NOT RUN",
            "02_modal_responsive_contrast": "NOT RUN",
            "03_keyboard_focus_and_copy": "NOT RUN",
            "04_design_media_internal_preview": "NOT RUN",
            "05_draft_publish_filter_unpublish": "NOT RUN",
            "06_inquiry_validation_rate_limit_delivery": "NOT RUN",
            "07_hostname_validation_provider_detection": "NOT RUN",
            "08_domain_connect_resume_without_dns": "NOT RUN",
            "09_manual_and_emailed_instructions": "NOT RUN",
            "10_dns_expected_vs_observed": "NOT RUN",
            "11_fresh_claim_conflict_privacy": "NOT RUN",
            "12_hostname_active_ssl_pending": "NOT RUN",
            "13_ssl_active_https_failed": "NOT RUN",
            "14_real_custom_url": "BLOCKED",
            "15_missing_config_friendly_error": "NOT RUN",
            "16_existing_site_prevalidation": "NOT RUN",
            "17_activation_state_immutability": "NOT RUN",
            "18_disconnect_retry_receipt": "NOT RUN",
            "19_platform_slug_survives_domain_lifecycle": "NOT RUN",
            "20_negative_content_filtering": "NOT RUN",
            "21_root_admin_plan_capability_round_trip": "NOT RUN",
        },
        "browser_scenario_evidence": {},
        "browser_scenario_blockers": {
            "02_modal_responsive_contrast": (
                "No current retained production-build browser run covers every modal tab in "
                "the desktop/mobile light/dark matrix."
            ),
            "03_keyboard_focus_and_copy": (
                "No current retained production-build browser run proves focus cycling, "
                "keyboard copy, and status announcements together."
            ),
            "04_design_media_internal_preview": (
                "The deterministic browser receipt proves real local image bytes, safe "
                "disabled-provider handling, saved design state, and internal-slug preview, "
                "but it does not prove upload, finalize, persistence, and rendered-image "
                "round-trip through configured object storage. Live R2 remains blocked "
                "without authorized credentials."
            ),
            "06_inquiry_validation_rate_limit_delivery": (
                (
                    "No passing retained production-build run yet binds required-field "
                    "validation, an idempotent acknowledgement retry, the public rate-limit "
                    "state, and durable retry_pending delivery recovery. Live Resend delivery "
                    "is tracked separately and remains blocked in disabled mode."
                )
                if INQUIRY_DELIVERY_MODE == "disabled"
                else (
                    "No passing retained production-build run yet binds required-field "
                    "validation, an idempotent acknowledgement retry, the public rate-limit "
                    "state, and the required live delivery receipt."
                )
            ),
            "07_hostname_validation_provider_detection": (
                "No passing run-scoped real-route preflight and authoritative DNS receipt exists yet."
            ),
            "08_domain_connect_resume_without_dns": (
                "No passing run-scoped deterministic signed consent, cancellation, reload, "
                "callback-without-DNS, and connected-state withholding receipt exists yet."
            ),
            "09_manual_and_emailed_instructions": (
                "No passing run-scoped instruction email, bounded seven-day link, reload, "
                "public read-only view, and revocation receipt exists yet."
            ),
            "10_dns_expected_vs_observed": (
                "No passing run-scoped expected-versus-authoritative-observed browser receipt exists yet."
            ),
            "11_fresh_claim_conflict_privacy": (
                "Conflict privacy is exercised, but no browser receipt yet completes a fresh claimant TXT proof into operator_review without provider mutation."
            ),
            "12_hostname_active_ssl_pending": (
                "No passing persisted provider-active/SSL-pending receipt exists yet."
            ),
            "13_ssl_active_https_failed": (
                "No passing persisted SSL-active/HTTPS-failed receipt exists yet."
            ),
            "14_real_custom_url": (
                "No independently authoritative customer zone and scoped Cloudflare for SaaS "
                "credentials were authorized for this run."
            ),
            "15_missing_config_friendly_error": (
                "No passing browser receipt from the provider-credential-free isolated backend "
                "binds its exact readiness gaps to friendly slug-safe customer copy."
            ),
            "16_existing_site_prevalidation": (
                "No passing receipt yet binds the existing CNAME before and after ownership-only "
                "proof to zero provider creation before assisted cutover."
            ),
            "17_activation_state_immutability": (
                "No passing custom-domain lifecycle receipt is yet bound to unchanged account, "
                "plan, subscription, slug, publication, and storefront revision snapshots."
            ),
            "18_disconnect_retry_receipt": (
                "No passing deterministic receipt yet binds delete failure, focused customer "
                "feedback, background retry, durable operation/tombstone receipts, exact DNS "
                "cleanup, and zero retained provider records. External Cloudflare deletion is "
                "tracked separately and remains blocked without authorization."
            ),
            "19_platform_slug_survives_domain_lifecycle": (
                "No passing run-scoped slug-before/during/after persisted domain lifecycle receipt exists yet."
            ),
        },
        "live_provider_blocker": (
            "No independently authorized live provider run was performed. Deterministic "
            "FastAPI/Mongo/provider-adapter evidence is not external-provider proof."
        ),
        "playwright": None,
        "playwright_artifacts": None,
        "artifact_manifest": None,
        "persistence": None,
        "cleanup": None,
        "failure": None,
    }


def main() -> int:
    assert_safe_target()
    if EXTERNAL_MODE not in {"deterministic", "live"}:
        raise RuntimeError(
            "TESTBED_STOREFRONT_EXTERNAL_MODE must be deterministic or live"
        )
    if INQUIRY_DELIVERY_MODE not in {"disabled", "required"}:
        raise RuntimeError(
            "TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE must be disabled or required"
        )

    run_id = secrets.token_hex(6)
    provider_control_token = secrets.token_urlsafe(48)
    artifact_dir = ARTIFACT_ROOT / "runs" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = artifact_dir / "run-manifest.json"
    fixtures = Fixtures.create(run_id, artifact_dir)
    workspace = _workspace_evidence()
    manifest = _base_manifest(run_id, artifact_dir, manifest_path, fixtures, workspace)
    _write_json(manifest_path, manifest)

    client: MongoClient | None = None
    runtime: IsolatedStorefrontRuntime | None = None
    seeded = False
    exit_code = 1
    try:
        if manifest["provider_mode"] == "live":
            manifest["live_provider_doctor"] = {
                "status": "PASSED",
                "evidence_scope": "configuration_fence_only_not_lifecycle",
                "validated_fences": _live_provider_doctor(fixtures),
                "does_not_prove": [
                    "provider authorization",
                    "authoritative DNS mutation",
                    "custom hostname creation",
                    "certificate activation",
                    "HTTPS storefront routing",
                    "external provider deletion",
                ],
            }
            raise RuntimeError(
                "Live provider mode is BLOCKED: an independently authoritative customer "
                "zone and exact external-provider lifecycle were not authorized for this run."
            )

        runtime = IsolatedStorefrontRuntime(
            run_id=run_id,
            root_admin_email=fixtures.root_admin_email,
            control_token=provider_control_token,
            artifact_dir=artifact_dir,
            runtime_revision=workspace["runtime_revision"],
        )
        manifest["isolated_runtime"] = runtime.start()
        os.environ["REQUESTS_CA_BUNDLE"] = str(runtime.certificate_path)

        manifest["frontend_runtime"] = _attest_frontend(
            workspace["frontend_source_sha256"], artifact_dir
        )
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[MONGO_DB]
        _seed_canonical_plans(db, run_id)
        seeded = True
        _seed(db, fixtures)
        account_state_before = _account_state_fingerprint(db, fixtures)
        signature_token = _login(fixtures.signature_email, fixtures.signature_password)
        manifest["backend_runtime"] = _attest_backend(
            signature_token, workspace["runtime_revision"]
        )
        control_status = requests.get(
            f"{BACKEND_URL}{PROVIDER_CONTROL_PREFIX}/status",
            headers={
                "x-storefront-testbed-run-id": run_id,
                "x-storefront-testbed-control-token": provider_control_token,
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
        if (
            control_status.status_code != 200
            or control_status.headers.get("x-storefront-provider-mode")
            != "deterministic-testbed"
            or control_status.json().get("run_id") != run_id
            or control_status.json().get("external_provider_live") is not False
        ):
            raise AssertionError(
                "The HTTPS backend is not the exact deterministic provider harness for this run"
            )
        manifest["provider_harness"] = {
            **control_status.json(),
            "control_token_sha256": hashlib.sha256(
                provider_control_token.encode()
            ).hexdigest(),
            "certificate_sha256": runtime.certificate_sha256,
        }
        _write_json(manifest_path, manifest)

        playwright = _run_playwright(
            manifest_path,
            artifact_dir,
            fixtures,
            provider_control_token=provider_control_token,
        )
        manifest["playwright"] = playwright
        manifest["acceptance"]["automated_chromium"] = playwright["status"]
        if playwright["status"] != "PASSED":
            raise AssertionError(
                "Storefront Playwright acceptance failed; inspect retained JSON/JUnit/trace/video artifacts"
            )
        final_control_status = requests.get(
            f"{BACKEND_URL}{PROVIDER_CONTROL_PREFIX}/status",
            headers={
                "x-storefront-testbed-run-id": run_id,
                "x-storefront-testbed-control-token": provider_control_token,
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
        final_provider_receipt = final_control_status.json()
        latest_probe = final_provider_receipt.get("latest_explicit_https_probe")
        if (
            final_control_status.status_code != 200
            or final_provider_receipt.get("external_provider_live") is not False
            or int(final_provider_receipt.get("explicit_https_probe_count") or 0) < 2
            or not isinstance(latest_probe, dict)
            or latest_probe.get("hostname") != fixtures.custom_domain
            or latest_probe.get("path") != "/.well-known/tsw-storefront-verification"
            or latest_probe.get("status_code") != 404
            or latest_probe.get("verified") is not False
        ):
            raise AssertionError(
                "The disconnected deterministic domain lacks the expected HTTPS route-removal receipt"
            )
        manifest["provider_harness"]["final_status"] = final_provider_receipt
        manifest["playwright_artifacts"] = _retain_playwright_artifact_manifest(
            artifact_dir,
            run_id=run_id,
            workspace=workspace,
            frontend_runtime=manifest["frontend_runtime"],
            provider_mode=manifest["provider_mode"],
        )
        manifest["acceptance"]["deterministic_provider_control_plane"] = "PASSED"
        manifest["acceptance"]["media_provider_disabled"] = "PASSED"
        manifest["persistence"] = _assert_persistence(
            db, fixtures, signature_token, account_state_before
        )
        manifest["domain_control_plane"] = _assert_domain_control_plane(db, fixtures)
        for scenario in (
            "01_restricted_upgrade_gate",
            "02_modal_responsive_contrast",
            "03_keyboard_focus_and_copy",
            "05_draft_publish_filter_unpublish",
            "06_inquiry_validation_rate_limit_delivery",
            "07_hostname_validation_provider_detection",
            "08_domain_connect_resume_without_dns",
            "09_manual_and_emailed_instructions",
            "10_dns_expected_vs_observed",
            "11_fresh_claim_conflict_privacy",
            "12_hostname_active_ssl_pending",
            "13_ssl_active_https_failed",
            "15_missing_config_friendly_error",
            "16_existing_site_prevalidation",
            "17_activation_state_immutability",
            "18_disconnect_retry_receipt",
            "19_platform_slug_survives_domain_lifecycle",
            "20_negative_content_filtering",
            "21_root_admin_plan_capability_round_trip",
        ):
            evidence = _scenario_evidence_from_playwright(
                playwright,
                scenario=scenario,
                run_id=run_id,
                provider_mode=manifest["provider_mode"],
            )
            if evidence is None:
                raise AssertionError(
                    f"Playwright omitted the complete receipt set for scenario {scenario}"
                )
            _record_browser_scenario(
                manifest,
                scenario,
                "PASSED",
                evidence=evidence,
            )
        _record_browser_scenario(
            manifest,
            "04_design_media_internal_preview",
            "BLOCKED",
            blocker=(
                "Run-bound browser evidence proves real PNG selection, browser decoding, "
                "friendly disabled-provider handling, saved design state, and internal-slug "
                "preview. It does not prove that media bytes were uploaded, finalized, "
                "persisted, and rendered from configured object storage; reporting this row "
                "as passed would be a false positive."
            ),
        )
        manifest["acceptance"]["deterministic_disconnect_cleanup"] = "PASSED"
        manifest["acceptance"]["persistence"] = "PASSED"
        manifest["acceptance"]["account_and_subscription_immutability"] = "PASSED"
        exit_code = 0
    except Exception as exc:
        manifest["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        logger.error("Storefront browser acceptance failed: %s", exc)
    finally:
        ledger_contradictions = _enforce_browser_scenario_truth(manifest)
        incomplete_scenarios = sorted(
            scenario
            for scenario, status in manifest["browser_scenarios"].items()
            if status != "PASSED"
        )
        manifest["browser_scenario_ledger"] = {
            "status": (
                "FAILED"
                if ledger_contradictions
                else "BLOCKED"
                if incomplete_scenarios
                else "PASSED"
            ),
            "passed_rows_with_blockers": ledger_contradictions,
            "incomplete_scenarios": incomplete_scenarios,
        }
        if ledger_contradictions:
            manifest["failure"] = {
                "type": "EvidenceLedgerContradiction",
                "message": (
                    "Browser scenarios were marked PASSED while retaining blockers: "
                    + ", ".join(ledger_contradictions)
                ),
            }
            exit_code = 1
        elif incomplete_scenarios and exit_code == 0:
            manifest["failure"] = {
                "type": "EvidenceCoverageIncomplete",
                "message": (
                    "Required storefront browser scenarios remain BLOCKED or NOT RUN: "
                    + ", ".join(incomplete_scenarios)
                ),
            }
            exit_code = 1
        _write_json(manifest_path, manifest)
        if seeded:
            cleanup = _run_cleanup(manifest_path, fixtures, artifact_dir)
            manifest["cleanup"] = cleanup
            manifest["acceptance"]["cleanup"] = cleanup["status"]
            if cleanup["status"] != "PASSED":
                exit_code = 1
        else:
            manifest["cleanup"] = {
                "status": "PASSED",
                "reason": "No fixtures were seeded before the failure",
            }
            manifest["acceptance"]["cleanup"] = "PASSED"
        if client is not None:
            client.close()
        if runtime is not None:
            try:
                _record_isolated_runtime_shutdown(manifest, runtime.stop())
            except Exception as exc:
                _record_isolated_runtime_shutdown(
                    manifest,
                    {"status": "FAILED", "error": str(exc)},
                )
                manifest["failure"] = {
                    "type": type(exc).__name__,
                    "message": f"Isolated runtime shutdown failed: {exc}",
                }
                exit_code = 1
        else:
            manifest["isolated_runtime"] = {
                "status": "NOT_STARTED",
                "shutdown": {"status": "NOT_STARTED"},
            }
        manifest["completed_at"] = _now().isoformat()
        manifest["artifact_manifest"] = {
            "schema_version": 2,
            "path": "artifact-seal.json",
            "status": "SEALED_AFTER_FINAL_MANIFEST",
        }
        _write_json(manifest_path, manifest)
        try:
            _write_final_artifact_seal(
                artifact_dir,
                manifest=manifest,
                workspace=workspace,
                frontend_runtime=manifest.get("frontend_runtime") or {},
            )
        except Exception as exc:
            manifest["artifact_manifest"] = {
                "schema_version": 2,
                "path": "artifact-seal.json",
                "status": "FAILED",
                "error": str(exc),
            }
            manifest["failure"] = {
                "type": type(exc).__name__,
                "message": f"Final artifact sealing failed: {exc}",
            }
            exit_code = 1
            _write_json(manifest_path, manifest)

    logger.info("Run manifest: %s", manifest_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
