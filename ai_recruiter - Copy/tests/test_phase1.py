"""
Tests for Phase 1.
Run with:  pytest tests/test_phase1.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.utils.security import create_access_token, decode_access_token, hash_password, verify_password

TEST_DB_URL = "sqlite:///./test_recruiter.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


client = TestClient(app)


def test_password_hash_is_not_plain_text():
    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert hashed.startswith("$2b$")


def test_password_verify_correct():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_password_verify_wrong():
    hashed = hash_password("mysecret")
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_encode_decode():
    token = create_access_token({"sub": "test@example.com", "role": "recruiter"})
    payload = decode_access_token(token)
    assert payload["sub"] == "test@example.com"
    assert payload["role"] == "recruiter"


def test_jwt_tampered_token_returns_none():
    token = create_access_token({"sub": "test@example.com"})
    bad_token = token + "tampered"
    assert decode_access_token(bad_token) is None


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_new_user():
    response = client.post("/api/auth/register", json={
        "email": "recruiter@test.com",
        "password": "testpass123",
        "full_name": "Test Recruiter",
        "role": "recruiter",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "recruiter@test.com"
    assert data["role"] == "recruiter"
    assert "password_hash" not in data


def test_register_duplicate_email_fails():
    client.post("/api/auth/register", json={
        "email": "dup@test.com", "password": "pass123"
    })
    response = client.post("/api/auth/register", json={
        "email": "dup@test.com", "password": "pass456"
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login_success():
    client.post("/api/auth/register", json={
        "email": "login@test.com", "password": "mypassword"
    })
    response = client.post("/api/auth/login", json={
        "email": "login@test.com", "password": "mypassword"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    client.post("/api/auth/register", json={
        "email": "wrong@test.com", "password": "correct"
    })
    response = client.post("/api/auth/login", json={
        "email": "wrong@test.com", "password": "incorrect"
    })
    assert response.status_code == 401


def test_get_me_with_valid_token():
    client.post("/api/auth/register", json={
        "email": "me@test.com", "password": "pass123", "full_name": "Ali Khan"
    })
    login_resp = client.post("/api/auth/login", json={
        "email": "me@test.com", "password": "pass123"
    })
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "me@test.com"
    assert me_resp.json()["full_name"] == "Ali Khan"


def test_get_me_without_token():
    response = client.get("/api/auth/me")
    assert response.status_code == 401
