import pytest

from scripts import reset_test_user_data


def test_reset_guard_blocks_production_environment(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")

    with pytest.raises(RuntimeError, match="production"):
        reset_test_user_data.assert_reset_allowed()


def test_reset_guard_blocks_remote_mongo_without_explicit_bypass(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    monkeypatch.setenv("MONGO_URI", "mongodb+srv://example.invalid/prod")
    monkeypatch.delenv(reset_test_user_data.REMOTE_RESET_BYPASS_ENV, raising=False)

    with pytest.raises(RuntimeError, match="non-local MongoDB"):
        reset_test_user_data.assert_reset_allowed()


def test_reset_guard_allows_local_mongo(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/wedding_test")

    reset_test_user_data.assert_reset_allowed()
