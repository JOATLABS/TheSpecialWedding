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

    domain_planner = by_name["idx_storefront_domains_planner_unique"]
    domain_hostname = by_name["idx_storefront_domains_hostname_unique"]
    assert domain_planner[0] == [("planner_id", 1)]
    assert domain_planner[1]["unique"] is True
    assert domain_hostname[0] == [("hostname", 1)]
    assert domain_hostname[1]["unique"] is True

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
    assert by_name["idx_storefront_inquiries_owner_created"][0] == [
        ("planner_id", 1),
        ("created_at", -1),
    ]
    assert by_name["idx_storefront_inquiries_slug_created"][0] == [
        ("storefront_slug", 1),
        ("created_at", -1),
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
