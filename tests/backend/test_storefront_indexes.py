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

    def __getitem__(self, name: str):
        assert name == "storefront_settings"
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
