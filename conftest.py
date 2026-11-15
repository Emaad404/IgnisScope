import pytest
from fastapi.testclient import TestClient

from app import config, database


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "SYNTHETIC_DIR", tmp_path / "syn")
    database.init_db()
    yield tmp_path


@pytest.fixture()
def db(env):
    s = database.SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client(env):
    from app.main import app
    with TestClient(app) as c:
        yield c
