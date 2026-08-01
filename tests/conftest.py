from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.database import Base, create_database_engine, get_db_session
from app.main import app


@pytest.fixture
def test_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(test_engine: Engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    with session_factory() as database_session:
        yield database_session


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
