import os
os.environ.setdefault("DATABASE_URL","sqlite:///./test_business_agent.db")
os.environ.setdefault("JWT_SECRET","test-secret-0123456789-0123456789-abcdef")
os.environ["ENVIRONMENT"]="test"
os.environ["DEVELOPMENT_AUTH_EMAIL"]=""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base,engine
@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    from app.db.seed import init_database; init_database(); yield
@pytest.fixture
def client():
    with TestClient(app) as c: yield c
