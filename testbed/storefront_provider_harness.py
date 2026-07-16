"""Uvicorn entry point for the deterministic storefront provider harness.

Run only against an explicitly isolated testbed environment, for example:

    uvicorn testbed.storefront_provider_harness:app --host 127.0.0.1 --port 8112

Import intentionally fails before loading the production application unless
the non-interactive loopback/database/token contract is satisfied.
"""

from __future__ import annotations

import os

from testbed.storefront_testbed_safety import (
    assert_storefront_provider_harness_environment,
    normalize_disabled_provider_settings,
)


environment = assert_storefront_provider_harness_environment(os.environ)
if not environment.frontend_ca_certificate:
    raise RuntimeError(
        "The HTTPS provider harness requires a run-scoped frontend CA certificate"
    )

# Safety validation must happen before these imports. They initialize the
# repository's shared settings and Mongo connector from the current process.
from app.core.settings import settings  # noqa: E402

normalize_disabled_provider_settings(settings)

from app.core.database import mongo  # noqa: E402
from app.main import app as production_app  # noqa: E402
from app.services.storefront_entitlement_service import (  # noqa: E402
    storefront_entitlement_service,
)
from testbed.storefront_provider_harness_core import (  # noqa: E402
    create_storefront_provider_harness,
)


bundle = create_storefront_provider_harness(
    environment=environment,
    mongo_client=mongo,
    entitlement_service=storefront_entitlement_service,
    production_app=production_app,
)
app = bundle.app
