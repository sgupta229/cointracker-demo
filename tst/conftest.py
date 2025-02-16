import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from src.app import app

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, echo=False)

def get_test_session() -> Session:
    with Session(engine) as session:
        yield session

@pytest.fixture(scope="session", autouse=True)
def create_db_and_tables():
    """Create the in-memory database and tables before any test runs."""
    SQLModel.metadata.create_all(engine)
    yield
    # (No teardown needed for :memory: DB, it disappears after tst finish.)

@pytest.fixture
def client():
    """
    A TestClient that uses the test database session.
    """
    app.dependency_overrides = {}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}

@pytest.fixture
def session():
    """
    Returns a new Session instance connected to the test DB.
    Useful for direct DB operations in tst.
    """
    with Session(engine) as s:
        yield s
