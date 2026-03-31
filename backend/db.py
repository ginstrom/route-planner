from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from backend.config import get_settings


def _sqlite_path(database_url: str) -> Path | None:
    absolute_prefix = "sqlite:////"
    relative_prefix = "sqlite:///"
    if database_url.startswith(absolute_prefix):
        return Path("/" + database_url.removeprefix(absolute_prefix))
    if database_url.startswith(relative_prefix):
        return Path(database_url.removeprefix(relative_prefix))
    return None


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    sqlite_path = _sqlite_path(settings.database_url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
