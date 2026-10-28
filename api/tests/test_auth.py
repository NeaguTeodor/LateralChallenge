from app.core.config import settings
from app.models import UserRole
from tests.conftest import API, _make_user


def test_register_login_and_me(client):
    payload = {"email": "New@Test.dev", "full_name": "New User", "password": "password123"}
    res = client.post(f"{API}/auth/register", json=payload)
    assert res.status_code == 201
    assert res.json()["email"] == "new@test.dev"
    assert res.json()["role"] == "customer"

    res = client.post(
        f"{API}/auth/login", data={"username": "new@test.dev", "password": "password123"}
    )
    assert res.status_code == 200
    token = res.json()["access_token"]

    res = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["full_name"] == "New User"


def test_register_duplicate_email(client):
    payload = {"email": "dup@test.dev", "full_name": "Dup", "password": "password123"}
    client.post(f"{API}/auth/register", json=payload)
    assert client.post(f"{API}/auth/register", json=payload).status_code == 409


def test_login_wrong_password(client, customer_headers):
    res = client.post(
        f"{API}/auth/login", data={"username": "customer@test.dev", "password": "nope"}
    )
    assert res.status_code == 401


def test_invalid_token_rejected(client):
    res = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage"})
    assert res.status_code == 401


def test_password_limit_is_in_bytes(client):
    # 72 characters but 144 bytes: bcrypt would reject it, so validation must catch it first.
    payload = {"email": "multi@test.dev", "full_name": "M", "password": "é" * 72}
    assert client.post(f"{API}/auth/register", json=payload).status_code == 422


def test_demo_switcher_lists_every_account_and_logs_in_as_any(client, db):
    _make_user(db, "boss@test.dev", UserRole.ADMIN)
    _make_user(db, "first@test.dev", UserRole.CUSTOMER)
    client.post(
        f"{API}/auth/register",
        json={"email": "new@test.dev", "full_name": "New", "password": "password123"},
    )
    accounts = client.get(f"{API}/auth/demo-accounts").json()
    # Customers first (including the one who just signed up), then admins.
    assert [a["email"] for a in accounts] == ["first@test.dev", "new@test.dev", "boss@test.dev"]

    for account in accounts:
        token = client.post(f"{API}/auth/demo-login/{account['id']}").json()["access_token"]
        me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["email"] == account["email"]


def test_demo_login_disabled_in_production(client, db, monkeypatch):
    admin = _make_user(db, "boss@test.dev", UserRole.ADMIN)
    monkeypatch.setattr(settings, "environment", "production")
    assert client.get(f"{API}/auth/demo-accounts").status_code == 404
    assert client.post(f"{API}/auth/demo-login/{admin.id}").status_code == 404
