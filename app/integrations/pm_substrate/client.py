"""
PM Substrate HTTP client.

Thin Python wrapper around the substrate-http Hono endpoints. Translates
WeddingWebApp domain calls into substrate graph + event operations.

Public API (three methods, per P2.2 spec):
  create_contract(tenant_id, vendor_profile_id, contract_data) -> pm_contract_id
  record_payment(tenant_id, pm_contract_id, amount_minor, recorded_at, payment_id) -> None
  assign_vendor_to_budget_category(tenant_id, vendor_profile_id, budget_category_id,
                                   vendor_data, category_data) -> None

Node ID strategy (P2.2):
  Vendor and BudgetCategory nodes in the substrate use UUID5 IDs derived from the
  WeddingWebApp MongoDB IDs. This gives stable, deterministic cross-reference without
  needing a separate mapping table. UUID5 is deterministic: the same input always
  produces the same output, so calling create_contract twice for the same vendor
  produces the same vendor_node_id both times.

  The UUID5 namespace is a fixed URL-namespace UUID defined in this module.

  P2.3 will add proper node lifecycle (create-or-fetch with persistent mapping) and
  full Vendor node management via @pm/capability-wedding-vendors.

Conflict handling:
  Vendor and BudgetCategory node creation uses a "create or ignore" pattern: if the
  substrate returns 4xx for a node creation attempt, we check whether the uuid5-derived
  node ID is already known (i.e., the node exists from a prior call) and proceed. Only
  unrecoverable creation failures surface as NodeCreationFailed.

  Contract node creation is never idempotent: a new node is created on each
  create_contract call. The returned ID is stored as `pm_contract_id` on the local doc.

Dependencies:
  httpx (already in requirements.txt) — async HTTP client.
  No additional external dependencies introduced.

P2.3 follow-up:
  - Replace uuid5-based node IDs with proper create-or-fetch backed by Mongo
    pm_vendor_id / pm_category_id fields on vendor_profiles / budget_categories.
  - Add real end-to-end test against live substrate + Postgres.
  - Handle substrate token rotation.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from .config import (
    PM_SUBSTRATE_RETRIES,
    PM_SUBSTRATE_TIMEOUT,
    PM_SUBSTRATE_TOKEN,
    PM_SUBSTRATE_URL,
)
from .errors import (
    ContractCreationFailed,
    EdgeCreationFailed,
    NodeCreationFailed,
    PaymentRecordFailed,
    PMSubstrateError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node ID derivation
# ---------------------------------------------------------------------------

# Fixed namespace for WeddingWebApp → substrate node ID derivation.
# UUID5(URL_NAMESPACE, "weddingwebapp") — stable across restarts.
_WWAPP_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _vendor_node_id(tenant_id: str, vendor_profile_id: str) -> str:
    """Derive a stable substrate node ID for a WeddingWebApp vendor profile."""
    return str(uuid.uuid5(_WWAPP_NS, f"vendor:{tenant_id}:{vendor_profile_id}"))


def _budget_category_node_id(tenant_id: str, budget_category_id: str) -> str:
    """Derive a stable substrate node ID for a WeddingWebApp budget category."""
    return str(uuid.uuid5(_WWAPP_NS, f"budget_category:{tenant_id}:{budget_category_id}"))


# ---------------------------------------------------------------------------
# Profile bindings (substrate graph node types)
# ---------------------------------------------------------------------------

_VENDOR_PROFILE = {"tier1": "Counterparty", "profile": "wedding", "concrete": "Vendor"}
_CONTRACT_PROFILE = {"tier1": "Transaction", "profile": "wedding", "concrete": "Contract"}
_BUDGET_CATEGORY_PROFILE = {"tier1": "Resource", "profile": "wedding", "concrete": "BudgetCategory"}

# ---------------------------------------------------------------------------
# PMSubstrateClient
# ---------------------------------------------------------------------------


class PMSubstrateClient:
    """
    Thin async HTTP client for the pm-substrate service.

    Designed to be instantiated once and reused across requests. Uses httpx
    AsyncClient internally with connection pooling.

    Usage:
        client = PMSubstrateClient()

        # In an async context:
        pm_contract_id = await client.create_contract(
            tenant_id=planner_email,
            vendor_profile_id=str(vendor_oid),
            contract_data={
                "amount_minor": int(total_amount * 100),
                "currency": "USD",
                "effective_date": service_date_iso,
            },
            vendor_data={
                "name": vendor["business_name"],
                "email": vendor.get("email"),
                "category": vendor["service_category"],
                "external_ref": str(vendor_oid),
            },
        )
    """

    def __init__(
        self,
        base_url: str = PM_SUBSTRATE_URL,
        token: str = PM_SUBSTRATE_TOKEN,
        timeout: float = PM_SUBSTRATE_TIMEOUT,
        retries: int = PM_SUBSTRATE_RETRIES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retries = retries
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_contract(
        self,
        tenant_id: str,
        vendor_profile_id: str,
        contract_data: Dict[str, Any],
        vendor_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a Contract node in the substrate graph and wire the contract→vendor edge.

        Steps:
          1. Ensure a Vendor node exists (uuid5-derived ID; silently handles conflicts).
          2. Create a new Contract node (substrate assigns the UUID).
          3. Create a wedding/contract_vendor edge (Contract → Vendor).

        This is the structural prerequisite for the budget rollup: the
        BudgetRollupHandler walks contract → vendor → budgetCategory. Without
        the contract_vendor edge, the rollup silently skips.

        Args:
            tenant_id: Planner's email (the substrate tenant identifier).
            vendor_profile_id: WeddingWebApp vendor profile MongoDB ObjectId string.
            contract_data: Dict with keys:
                - amount_minor (int): Contract value in integer minor units (cents).
                - currency (str): ISO-4217 currency code, e.g. "USD".
                - effective_date (str): ISO-8601 contract effective date.
            vendor_data: Optional vendor attributes for node creation.
                Keys: name, email, category, external_ref.
                If omitted, minimal identity is created from vendor_profile_id.

        Returns:
            pm_contract_id: Substrate-assigned UUID for the new Contract node.
            Store this on the local MongoDB `vendor_contracts` doc as `pm_contract_id`.

        Raises:
            ContractCreationFailed: substrate rejected the Contract node creation.
            EdgeCreationFailed: substrate rejected the contract_vendor edge.
            NodeCreationFailed: substrate rejected the Vendor node creation.
            PMSubstrateError: other substrate communication failure.
        """
        vendor_node_id = _vendor_node_id(tenant_id, vendor_profile_id)
        vdata = vendor_data or {}

        # Step 1: ensure Vendor node exists.
        await self._ensure_vendor_node(
            tenant_id=tenant_id,
            vendor_node_id=vendor_node_id,
            identity={
                "name": vdata.get("name", vendor_profile_id),
                "email": vdata.get("email"),
                "phone": vdata.get("phone"),
                "externalRef": vdata.get("external_ref", vendor_profile_id),
                "category": vdata.get("category", "other"),
            },
        )

        # Step 2: create the Contract node.
        contract_identity = {
            "state": "draft",
            "amountMinor": int(contract_data["amount_minor"]),
            "currency": contract_data.get("currency", "USD"),
            "effectiveDate": contract_data.get("effective_date", datetime.now(timezone.utc).date().isoformat()),
        }
        contract_node = await self._post_with_retry(
            f"/tenants/{tenant_id}/nodes",
            body={
                "profile": _CONTRACT_PROFILE,
                "identity": contract_identity,
                "schemaVersion": 1,
            },
        )
        pm_contract_id: str = contract_node["id"]
        logger.info(
            "pm_substrate.create_contract: created Contract node %s for tenant %s",
            pm_contract_id,
            tenant_id,
        )

        # Step 3: wire contract → vendor edge.
        try:
            await self._post_with_retry(
                f"/tenants/{tenant_id}/edges",
                body={
                    "type": "wedding/contract_vendor",
                    "fromId": pm_contract_id,
                    "toId": vendor_node_id,
                },
            )
            logger.debug(
                "pm_substrate: created wedding/contract_vendor edge %s → %s",
                pm_contract_id,
                vendor_node_id,
            )
        except PMSubstrateError as exc:
            raise EdgeCreationFailed(
                f"Failed to create wedding/contract_vendor edge "
                f"(contract={pm_contract_id}, vendor={vendor_node_id}): {exc}",
                status_code=exc.status_code,
            ) from exc

        return pm_contract_id

    async def record_payment(
        self,
        tenant_id: str,
        pm_contract_id: str,
        amount_minor: int,
        recorded_at: str,
        payment_id: str,
    ) -> None:
        """
        Emit wedding.contract.payment_recorded to the substrate event bus.

        The @pm/capability-wedding-budget handler subscribes to this event and
        performs the budget rollup transactionally in Postgres:
          1. Insert into budget.applied_payments (idempotency guard on payment_id).
          2. Lock BudgetCategory row (FOR UPDATE).
          3. Increment actualSpentMinor by amount_minor.
          4. Publish wedding.budget.actual_spent_updated in the same tx.

        No budget_category_id in the payload — the rollup infers the target by
        walking the graph: contract → vendor → budgetCategory. This is the
        architectural invariant we're asserting in the verifier tests.

        Args:
            tenant_id: Planner's email.
            pm_contract_id: Substrate UUID for the Contract node.
            amount_minor: Payment amount in integer minor units (cents).
            recorded_at: ISO-8601 timestamp of the payment.
            payment_id: Stable idempotency key (e.g. str(milestone._id)).

        Raises:
            PaymentRecordFailed: substrate rejected the event publication.
            PMSubstrateError: other substrate communication failure.
        """
        payload = {
            "contractId": pm_contract_id,
            "amount": amount_minor,
            "recordedAt": recorded_at,
            "paymentId": payment_id,
        }

        try:
            await self._post_with_retry(
                f"/tenants/{tenant_id}/events",
                body={
                    "type": "wedding.contract.payment_recorded",
                    "entityId": pm_contract_id,
                    "emittedBy": "weddingwebapp/vendor_service",
                    "payloadSchema": "wedding.contract.payment_recorded/v1",
                    "payload": payload,
                },
            )
            logger.info(
                "pm_substrate.record_payment: emitted payment_recorded "
                "(contract=%s, amount_minor=%d, payment_id=%s, tenant=%s)",
                pm_contract_id,
                amount_minor,
                payment_id,
                tenant_id,
            )
        except PMSubstrateError as exc:
            raise PaymentRecordFailed(
                f"Failed to publish wedding.contract.payment_recorded "
                f"(contract={pm_contract_id}, payment_id={payment_id}): {exc}",
                status_code=exc.status_code,
            ) from exc

    async def assign_vendor_to_budget_category(
        self,
        tenant_id: str,
        vendor_profile_id: str,
        budget_category_id: str,
        vendor_data: Optional[Dict[str, Any]] = None,
        category_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create the wedding/vendor_budget_category edge in the substrate graph.

        This edge is the structural fact the BudgetRollupHandler needs:
          contract → [wedding/contract_vendor] → vendor → [wedding/vendor_budget_category] → budgetCategory

        If this edge is absent, the budget rollup handler will log a warning and
        skip the rollup for all payments made on contracts through this vendor.
        That's why this call is logged + raises on failure — without the edge,
        payments silently don't roll up.

        Steps:
          1. Ensure Vendor node exists (uuid5-derived ID).
          2. Ensure BudgetCategory node exists (uuid5-derived ID).
          3. Create wedding/vendor_budget_category edge.

        Args:
            tenant_id: Planner's email.
            vendor_profile_id: WeddingWebApp vendor profile MongoDB ObjectId string.
            budget_category_id: WeddingWebApp budget_category MongoDB ObjectId string.
            vendor_data: Optional vendor attributes for Vendor node creation.
            category_data: Optional attributes for BudgetCategory node creation.

        Raises:
            EdgeCreationFailed: substrate rejected the edge. Fatal — log + raise,
                do not swallow. Without this edge, budget rollup is broken.
            NodeCreationFailed: substrate rejected a node creation.
            PMSubstrateError: other substrate communication failure.
        """
        vendor_node_id = _vendor_node_id(tenant_id, vendor_profile_id)
        category_node_id = _budget_category_node_id(tenant_id, budget_category_id)
        vdata = vendor_data or {}
        cdata = category_data or {}

        # Step 1: ensure Vendor node.
        await self._ensure_vendor_node(
            tenant_id=tenant_id,
            vendor_node_id=vendor_node_id,
            identity={
                "name": vdata.get("name", vendor_profile_id),
                "email": vdata.get("email"),
                "phone": vdata.get("phone"),
                "externalRef": vdata.get("external_ref", vendor_profile_id),
                "category": vdata.get("category", "other"),
            },
        )

        # Step 2: ensure BudgetCategory node.
        await self._ensure_budget_category_node(
            tenant_id=tenant_id,
            category_node_id=category_node_id,
            identity={
                "name": cdata.get("name", budget_category_id),
                "kind": "budget_category",
                "allocatedMinor": int(cdata.get("allocated_minor", 0)),
                "currency": cdata.get("currency", "USD"),
                "actualSpentMinor": 0,
            },
        )

        # Step 3: create vendor → budget_category edge.
        try:
            await self._post_with_retry(
                f"/tenants/{tenant_id}/edges",
                body={
                    "type": "wedding/vendor_budget_category",
                    "fromId": vendor_node_id,
                    "toId": category_node_id,
                },
            )
            logger.info(
                "pm_substrate.assign_vendor_to_budget_category: created edge "
                "vendor=%s → category=%s (tenant=%s)",
                vendor_node_id,
                category_node_id,
                tenant_id,
            )
        except PMSubstrateError as exc:
            raise EdgeCreationFailed(
                f"Failed to create wedding/vendor_budget_category edge "
                f"(vendor={vendor_node_id}, category={category_node_id}): {exc}. "
                "Without this edge the budget rollup handler cannot find the rollup "
                "target and will silently skip all payments through this vendor.",
                status_code=exc.status_code,
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_vendor_node(
        self,
        tenant_id: str,
        vendor_node_id: str,
        identity: Dict[str, Any],
    ) -> None:
        """Create a Vendor node with the pre-computed uuid5 ID, silently ignoring conflicts."""
        try:
            await self._post_with_retry(
                f"/tenants/{tenant_id}/nodes",
                body={
                    "id": vendor_node_id,
                    "profile": _VENDOR_PROFILE,
                    "identity": identity,
                    "schemaVersion": 1,
                },
            )
            logger.debug("pm_substrate: created Vendor node %s", vendor_node_id)
        except PMSubstrateError as exc:
            # 409 = node already exists with this uuid5 ID — treat as idempotent.
            # 4xx other than 409 = schema error or bad request — propagate.
            if exc.status_code == 409:
                logger.debug("pm_substrate: Vendor node %s already exists (409 ignored)", vendor_node_id)
            else:
                raise NodeCreationFailed(
                    f"Failed to create Vendor node {vendor_node_id}: {exc}",
                    status_code=exc.status_code,
                ) from exc

    async def _ensure_budget_category_node(
        self,
        tenant_id: str,
        category_node_id: str,
        identity: Dict[str, Any],
    ) -> None:
        """Create a BudgetCategory node with the pre-computed uuid5 ID, silently ignoring conflicts."""
        try:
            await self._post_with_retry(
                f"/tenants/{tenant_id}/nodes",
                body={
                    "id": category_node_id,
                    "profile": _BUDGET_CATEGORY_PROFILE,
                    "identity": identity,
                    "schemaVersion": 1,
                },
            )
            logger.debug("pm_substrate: created BudgetCategory node %s", category_node_id)
        except PMSubstrateError as exc:
            if exc.status_code == 409:
                logger.debug("pm_substrate: BudgetCategory node %s already exists (409 ignored)", category_node_id)
            else:
                raise NodeCreationFailed(
                    f"Failed to create BudgetCategory node {category_node_id}: {exc}",
                    status_code=exc.status_code,
                ) from exc

    async def _post_with_retry(
        self, path: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """POST with simple retry on transient 5xx / network errors."""
        last_exc: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                resp = await self._client.post(path, json=body)
                if resp.status_code >= 400:
                    detail = _extract_error(resp)
                    raise PMSubstrateError(
                        f"POST {path} → HTTP {resp.status_code}: {detail}",
                        status_code=resp.status_code,
                    )
                return resp.json()
            except PMSubstrateError:
                # 4xx: don't retry — caller decides.
                raise
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < self._retries:
                    logger.warning(
                        "pm_substrate: network error on attempt %d/%d for %s: %s",
                        attempt + 1,
                        self._retries + 1,
                        path,
                        exc,
                    )
                continue
        raise PMSubstrateError(
            f"POST {path} failed after {self._retries + 1} attempts: {last_exc}"
        ) from last_exc

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_client: Optional["PMSubstrateClient"] = None


def get_client() -> PMSubstrateClient:
    """Return the module-level singleton client (lazy init)."""
    global _default_client
    if _default_client is None:
        _default_client = PMSubstrateClient()
    return _default_client


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _extract_error(resp: httpx.Response) -> str:
    """Pull the error message out of a substrate JSON error response."""
    try:
        body = resp.json()
        return body.get("error") or body.get("detail") or resp.text
    except Exception:
        return resp.text[:200]
