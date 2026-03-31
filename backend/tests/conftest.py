from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.config import get_settings
from backend.db import get_engine, init_db
from backend.main import create_app


@pytest.fixture
def database_url(tmp_path) -> str:
    database_path = tmp_path / "test.db"
    return f"sqlite:////{database_path}"


@pytest.fixture
def configured_database(database_url, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    get_engine.cache_clear()
    init_db()
    yield
    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def client(configured_database) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def db_session(configured_database) -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
