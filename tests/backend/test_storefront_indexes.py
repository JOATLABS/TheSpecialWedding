from __future__ import annotations

import inspect

import pytest

import app.core.database_indexes as index_module


class RecordingCollection:
    def __init__(self):
        self.calls: list[tuple[object, dict]] = []

    async def create_index(self, keys, **kwargs):
        self.calls.append((keys, kwargs))
        return kwargs.get("name")


class RecordingDatabase:
    def __init__(self, collection: RecordingCollection):
        self.collection = collection
        self.requested: list[str] = []

    def __getitem__(self, name: str):
        self.requested.append(name)
        return self.collection


@pytest.mark.asyncio
async def test_storefront_indexes_are_unique_named_and_slug_is_legacy_safe(
    monkeypatch,
):
    collection = RecordingCollection()
    monkeypatch.setattr(
        index_module,
        "mongo",
        type("FakeMongo", (), {"db": RecordingDatabase(collection)})(),
    )

    await index_module.create_storefront_indexes()

    by_name = {kwargs["name"]: (keys, kwargs) for keys, kwargs in collection.calls}
    planner_keys, planner_options = by_name["idx_storefront_settings_planner_unique"]
    slug_keys, slug_options = by_name["idx_storefront_settings_slug_unique"]

    assert planner_keys == [("planner_id", 1)]
    assert planner_options["unique"] is True
    assert slug_keys == [("slug", 1)]
    assert slug_options["unique"] is True
    assert slug_options["partialFilterExpression"] == {"slug": {"$type": "string"}}
    pending_recovery = by_name["idx_storefront_settings_pending_recovery_due_owner"]
    assert pending_recovery[0] == [
        ("pending_asset_recovery_status", 1),
        ("pending_asset_recovery_due_at", 1),
        ("pending_asset_recovery_lease_expires_at", 1),
        ("updated_at", 1),
        ("planner_id", 1),
    ]
    assert pending_recovery[1]["partialFilterExpression"] == {
        "pending_asset_group": {"$exists": True}
    }
    assert "expireAfterSeconds" not in pending_recovery[1]

    domain_planner = by_name["idx_storefront_domains_planner_unique"]
    domain_hostname = by_name["idx_storefront_domains_hostname_unique"]
    assert domain_planner[0] == [("planner_id", 1)]
    assert domain_planner[1]["unique"] is True
    assert domain_planner[1]["partialFilterExpression"] == {
        "planner_id": {"$type": "string"}
    }
    assert domain_hostname[0] == [("hostname", 1)]
    assert domain_hostname[1]["unique"] is True
    assert domain_hostname[1]["partialFilterExpression"] == {
        "hostname": {"$type": "string"}
    }
    assert by_name["idx_storefront_domains_lifecycle_retry_lease"][0] == [
        ("application_status", 1),
        ("retry_due_at", 1),
        ("lease_expires_at", 1),
    ]
    conflict_attempt = by_name["idx_storefront_domain_conflict_claims_attempt_unique"]
    assert conflict_attempt[0] == [("attempt_id", 1)]
    assert conflict_attempt[1]["unique"] is True
    conflict_digest = by_name["idx_storefront_domain_conflict_claims_digest_unique"]
    assert conflict_digest[0] == [("claim_token_digest", 1)]
    assert conflict_digest[1]["unique"] is True
    assert conflict_digest[1]["partialFilterExpression"] == {
        "claim_token_digest": {"$type": "string"}
    }
    conflict_current = by_name[
        "idx_storefront_domain_conflict_claims_current_owner_unique"
    ]
    assert conflict_current[0] == [("current_owner_key", 1)]
    assert conflict_current[1]["unique"] is True
    assert conflict_current[1]["partialFilterExpression"] == {
        "current_owner_key": {"$type": "string"}
    }
    conflict_ttl = by_name["idx_storefront_domain_conflict_claims_purge_ttl"]
    assert conflict_ttl[0] == [("purge_at", 1)]
    assert conflict_ttl[1]["expireAfterSeconds"] == 0
    operation_id = by_name["idx_storefront_domain_operations_operation_unique"]
    assert operation_id[0] == [("operation_id", 1)]
    assert operation_id[1]["unique"] is True
    operation_attempt = by_name[
        "idx_storefront_domain_operations_domain_attempt_unique"
    ]
    assert operation_attempt[0] == [
        ("domain_id", 1),
        ("attempt_id", 1),
        ("kind", 1),
    ]
    assert operation_attempt[1]["unique"] is True
    flow_id = by_name["idx_storefront_domain_flows_id_unique"]
    assert flow_id[0] == [("flow_id", 1)]
    assert flow_id[1]["unique"] is True
    flow_attempt = by_name["idx_storefront_domain_flows_domain_attempt_unique"]
    assert flow_attempt[0] == [("domain_id", 1), ("attempt_id", 1)]
    assert flow_attempt[1]["unique"] is True
    flow_digest = by_name["idx_storefront_domain_flows_digest_unique"]
    assert flow_digest[0] == [("flow_token_digest", 1)]
    assert flow_digest[1]["unique"] is True
    assert flow_digest[1]["partialFilterExpression"] == {
        "flow_token_digest": {"$type": "string"}
    }
    flow_ttl = by_name["idx_storefront_domain_flows_expiry_ttl"]
    assert flow_ttl[0] == [("expires_at", 1)]
    assert flow_ttl[1]["expireAfterSeconds"] == 0
    operation_ttl = by_name["idx_storefront_domain_operations_expiry_ttl"]
    assert operation_ttl[0] == [("expires_at", 1)]
    assert operation_ttl[1]["expireAfterSeconds"] == 0
    instruction_id = by_name["idx_storefront_domain_instruction_links_id_unique"]
    assert instruction_id[0] == [("link_id", 1)]
    assert instruction_id[1]["unique"] is True
    instruction_digest = by_name[
        "idx_storefront_domain_instruction_links_digest_unique"
    ]
    assert instruction_digest[0] == [("token_digest", 1)]
    assert instruction_digest[1]["unique"] is True
    instruction_recipient = by_name[
        "idx_storefront_domain_instruction_links_recipient_unique"
    ]
    assert instruction_recipient[0] == [
        ("domain_id", 1),
        ("claim_attempt_id", 1),
        ("recipient_hash", 1),
    ]
    assert instruction_recipient[1]["unique"] is True
    instruction_ttl = by_name["idx_storefront_domain_instruction_links_expiry_ttl"]
    assert instruction_ttl[0] == [("expires_at", 1)]
    assert instruction_ttl[1]["expireAfterSeconds"] == 0
    instruction_quota_key = by_name[
        "idx_storefront_domain_instruction_quotas_key_unique"
    ]
    assert instruction_quota_key[0] == [("quota_key", 1)]
    assert instruction_quota_key[1]["unique"] is True
    instruction_quota_ttl = by_name[
        "idx_storefront_domain_instruction_quotas_expiry_ttl"
    ]
    assert instruction_quota_ttl[0] == [("expires_at", 1)]
    assert instruction_quota_ttl[1]["expireAfterSeconds"] == 0
    tombstone_receipt = by_name["idx_storefront_domain_tombstones_receipt_unique"]
    assert tombstone_receipt[0] == [("deletion_receipt_id", 1)]
    assert tombstone_receipt[1]["unique"] is True
    tombstone_ttl = by_name["idx_storefront_domain_tombstones_expiry_ttl"]
    assert tombstone_ttl[0] == [("expires_at", 1)]
    assert tombstone_ttl[1]["expireAfterSeconds"] == 0

    reserved_asset = by_name["idx_storefront_assets_reserved_slot_unique"]
    assert reserved_asset[0] == [("owner_id", 1), ("slot", 1)]
    assert reserved_asset[1]["unique"] is True
    assert reserved_asset[1]["partialFilterExpression"] == {"state": "reserved"}

    assert by_name["idx_storefront_assets_owner_state_created"][0] == [
        ("owner_id", 1),
        ("state", 1),
        ("created_at", -1),
    ]
    reservation_ttl = by_name["idx_storefront_assets_reservation_ttl"]
    assert reservation_ttl[0] == [("reservation_expires_at", 1)]
    assert reservation_ttl[1]["expireAfterSeconds"] == 0
    assert reservation_ttl[1]["partialFilterExpression"] == {"state": "reserved"}
    owner_cleanup_due = by_name["idx_storefront_assets_owner_state_cleanup_due"]
    assert owner_cleanup_due[0] == [
        ("owner_id", 1),
        ("state", 1),
        ("cleanup_due_at", 1),
    ]
    assert "expireAfterSeconds" not in owner_cleanup_due[1]
    owner_reaping_lease = by_name["idx_storefront_assets_owner_state_reaping_lease"]
    assert owner_reaping_lease[0] == [
        ("owner_id", 1),
        ("state", 1),
        ("reaping_started_at", 1),
    ]
    assert "expireAfterSeconds" not in owner_reaping_lease[1]
    global_cleanup_due = by_name["idx_storefront_assets_state_cleanup_due_owner"]
    assert global_cleanup_due[0] == [
        ("state", 1),
        ("cleanup_due_at", 1),
        ("owner_id", 1),
    ]
    assert "expireAfterSeconds" not in global_cleanup_due[1]
    global_reaping_lease = by_name["idx_storefront_assets_state_reaping_lease_owner"]
    assert global_reaping_lease[0] == [
        ("state", 1),
        ("reaping_started_at", 1),
        ("owner_id", 1),
    ]
    assert "expireAfterSeconds" not in global_reaping_lease[1]
    global_attach_lease = by_name["idx_storefront_assets_state_attach_lease_owner"]
    assert global_attach_lease[0] == [
        ("state", 1),
        ("attach_claimed_at", 1),
        ("owner_id", 1),
    ]
    assert "expireAfterSeconds" not in global_attach_lease[1]
    global_claim_due = by_name["idx_storefront_assets_state_claim_due_owner"]
    assert global_claim_due[0] == [
        ("state", 1),
        ("claim_reconcile_due_at", 1),
        ("owner_id", 1),
    ]
    assert "expireAfterSeconds" not in global_claim_due[1]
    detached_candidate = by_name["idx_storefront_asset_cleanup_candidate_unique"]
    assert detached_candidate[0] == [("owner_id", 1), ("candidate_key", 1)]
    assert detached_candidate[1]["unique"] is True
    assert "expireAfterSeconds" not in detached_candidate[1]
    detached_due = by_name["idx_storefront_asset_cleanup_state_due"]
    assert detached_due[0] == [
        ("state", 1),
        ("cleanup_due_at", 1),
    ]
    detached_reaping = by_name["idx_storefront_asset_cleanup_state_reaping"]
    assert detached_reaping[0] == [
        ("state", 1),
        ("reaping_started_at", 1),
    ]
    assert "expireAfterSeconds" not in detached_due[1]
    assert "expireAfterSeconds" not in detached_reaping[1]
    assert by_name["idx_storefront_inquiries_owner_created"][0] == [
        ("planner_id", 1),
        ("created_at", -1),
    ]
    assert by_name["idx_storefront_inquiries_slug_created"][0] == [
        ("storefront_slug", 1),
        ("created_at", -1),
    ]
    inquiry_idempotency = by_name["idx_storefront_inquiries_owner_idempotency_unique"]
    assert inquiry_idempotency[0] == [("planner_id", 1), ("idempotency_key", 1)]
    assert inquiry_idempotency[1]["unique"] is True
    assert inquiry_idempotency[1]["partialFilterExpression"] == {
        "planner_id": {"$type": "string"},
        "idempotency_key": {"$type": "string"},
    }
    assert by_name["idx_storefront_inquiries_notification_retry_due"][0] == [
        ("notification.status", 1),
        ("notification.next_attempt_at", 1),
        ("created_at", 1),
    ]
    assert by_name["idx_storefront_inquiries_notification_lease_due"][0] == [
        ("notification.status", 1),
        ("notification.lease_expires_at", 1),
        ("created_at", 1),
    ]
    assert by_name["idx_storefront_inquiries_operator_alert_due"][0] == [
        ("notification.operator_alert.status", 1),
        ("notification.operator_alert.next_attempt_at", 1),
        ("created_at", 1),
    ]


def test_create_all_indexes_invokes_storefront_index_setup():
    source = inspect.getsource(index_module.create_all_indexes)
    assert "await create_storefront_indexes()" in source


@pytest.mark.asyncio
async def test_storefront_unique_index_failure_propagates_and_fails_startup(
    monkeypatch,
):
    class FailingCollection:
        async def create_index(self, *_args, **_kwargs):
            raise RuntimeError("duplicate legacy storefront rows")

    monkeypatch.setattr(
        index_module,
        "mongo",
        type("FakeMongo", (), {"db": RecordingDatabase(FailingCollection())})(),
    )

    with pytest.raises(RuntimeError, match="duplicate legacy storefront rows"):
        await index_module.create_storefront_indexes()
