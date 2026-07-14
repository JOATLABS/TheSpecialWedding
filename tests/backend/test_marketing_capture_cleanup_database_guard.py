"""Fail-closed database targeting for the destructive marketing-capture reset."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testbed import cleanup_marketing_capture_workspace_state as cleanup_driver  # noqa: E402


class _FakeMongoClient:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.selected_database: str | None = None
        self.admin = SimpleNamespace(command=lambda _command: {"ok": 1})

    def __getitem__(self, database_name: str) -> object:
        self.selected_database = database_name
        return object()


def _install_fake_mongo(monkeypatch: pytest.MonkeyPatch) -> list[_FakeMongoClient]:
    clients: list[_FakeMongoClient] = []

    def create_client(uri: str) -> _FakeMongoClient:
        client = _FakeMongoClient(uri)
        clients.append(client)
        return client

    monkeypatch.setattr(cleanup_driver, "MongoClient", create_client)
    return clients


def _use_empty_env_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    root = tmp_path / "repo"
    (root / "testbed").mkdir(parents=True)
    monkeypatch.setattr(cleanup_driver, "ROOT", root)
    return root


def test_cleanup_preserves_explicit_shell_database_target_over_dotenv_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _use_empty_env_directory(monkeypatch, tmp_path)
    (root / ".env").write_text(
        "ENVIRONMENT=development\n"
        "MONGO_URI=mongodb://127.0.0.1:27018/root\n"
        "MONGO_DB=root_capture\n",
        encoding="utf-8",
    )
    (root / "testbed" / ".env").write_text(
        "ENVIRONMENT=development\n"
        "MONGO_URI=mongodb://mongo:27017/overlay\n"
        "MONGO_DB=overlay_capture\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("MONGO_URI", "mongodb://127.0.0.1:27019/shell")
    monkeypatch.setenv("MONGO_DB", "shell_capture")
    clients = _install_fake_mongo(monkeypatch)

    _client, _database = cleanup_driver._load_database()

    assert len(clients) == 1
    assert clients[0].uri == "mongodb://127.0.0.1:27019/shell"
    assert clients[0].selected_database == "shell_capture"
    assert cleanup_driver.os.environ["ENVIRONMENT"] == "local"


def test_cleanup_preserves_explicit_shell_aliases_over_dotenv_canonical_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _use_empty_env_directory(monkeypatch, tmp_path)
    (root / "testbed" / ".env").write_text(
        "ENVIRONMENT=production\n"
        "MONGO_URI=mongodb://mongo:27017/overlay\n"
        "MONGO_DB=overlay_capture\n",
        encoding="utf-8",
    )
    for key in ("ENVIRONMENT", "MONGO_URI", "MONGO_DB"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NODE_ENV", "local")
    monkeypatch.setenv("MONGODB_URI", "mongodb://127.0.0.1:27019/shell")
    monkeypatch.setenv("MONGO_NAME", "shell_capture")
    clients = _install_fake_mongo(monkeypatch)

    _client, _database = cleanup_driver._load_database()

    assert len(clients) == 1
    assert clients[0].uri == "mongodb://127.0.0.1:27019/shell"
    assert clients[0].selected_database == "shell_capture"


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://mongo:27017/wedding",
        "mongodb://mongodb:27017/wedding",
        "mongodb://localhost.:27017/wedding",
        "mongodb://db.internal.example:27017/wedding",
        "mongodb://127.0.0.1:27017,db.internal.example:27017/wedding",
        "mongodb+srv://capture.example.test/wedding",
    ],
)
def test_cleanup_rejects_every_non_loopback_mongo_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    uri: str,
) -> None:
    _use_empty_env_directory(monkeypatch, tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("MONGO_URI", uri)
    clients = _install_fake_mongo(monkeypatch)

    with pytest.raises(RuntimeError, match="refuses non-local Mongo"):
        cleanup_driver._load_database()

    assert clients == []


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://127.0.0.1:27017/wedding",
        "mongodb://[::1]:27017/wedding",
        "mongodb://localhost:27017/wedding",
    ],
)
def test_cleanup_accepts_only_canonical_loopback_mongo_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    uri: str,
) -> None:
    _use_empty_env_directory(monkeypatch, tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("MONGO_URI", uri)
    monkeypatch.setenv("MONGO_DB", "capture")
    clients = _install_fake_mongo(monkeypatch)

    _client, _database = cleanup_driver._load_database()

    assert len(clients) == 1
    assert clients[0].uri == uri
    assert clients[0].selected_database == "capture"


def test_cleanup_rejects_an_explicitly_blank_database_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_empty_env_directory(monkeypatch, tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("MONGO_URI", "mongodb://127.0.0.1:27017/wedding")
    monkeypatch.setenv("MONGO_DB", "")
    clients = _install_fake_mongo(monkeypatch)

    with pytest.raises(RuntimeError, match="MONGO_DB is required"):
        cleanup_driver._load_database()

    assert clients == []
