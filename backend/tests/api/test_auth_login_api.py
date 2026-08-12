import uuid

from backend.domain.entities.user import User
from backend.domain.services.auth_service import AuthService
from backend.infra.repositories.role_repo import RoleRepository
from backend.infra.repositories.user_repo import UserRepository

_auth_svc = AuthService()


def _make_login_user(db_session, unique_name, role_name="Resolutor", password="Sywork2026!"):
    role = RoleRepository(db_session).get_by_name(role_name)
    user = User(
        id=uuid.uuid4(),
        email=f"login.{unique_name}@sywork.net",
        username=f"login_{unique_name}",
        role=role,
        active=True,
        password_hash=_auth_svc.hash_password(password),
    )
    return UserRepository(db_session).create(user)


def test_login_with_email_succeeds(client, db_session, unique_name):
    user = _make_login_user(db_session, unique_name)
    resp = client.post("/api/auth/login", json={"username_or_email": user.email, "password": "Sywork2026!"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "access_token" in body
    assert body["user"]["email"] == user.email
    assert body["user"]["username"] == user.username
    assert body["user"]["role"]["name"] == "Resolutor"
    assert isinstance(body["user"]["permissions"], list)
    assert {"module": "clients", "action": "view"} in body["user"]["permissions"]


def test_login_with_username_succeeds(client, db_session, unique_name):
    user = _make_login_user(db_session, unique_name)
    resp = client.post("/api/auth/login", json={"username_or_email": user.username, "password": "Sywork2026!"})
    assert resp.status_code == 200


def test_login_with_wrong_password_returns_401(client, db_session, unique_name):
    user = _make_login_user(db_session, unique_name)
    resp = client.post("/api/auth/login", json={"username_or_email": user.email, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "unauthorized"


def test_login_with_unknown_identifier_returns_401(client):
    resp = client.post("/api/auth/login", json={"username_or_email": "nobody@sywork.net", "password": "x"})
    assert resp.status_code == 401


def test_login_missing_fields_returns_400(client):
    resp = client.post("/api/auth/login", json={"username_or_email": "a@sywork.net"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "validation_error"


def test_me_requires_a_valid_token(anon_client):
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_role_and_permissions_for_logged_in_user(client, db_session, unique_name):
    user = _make_login_user(db_session, unique_name)
    login = client.post("/api/auth/login", json={"username_or_email": user.email, "password": "Sywork2026!"}).get_json()
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user"]["email"] == user.email
    assert body["user"]["role"]["name"] == "Resolutor"


def test_forgot_password_existing_email_returns_generic_message(anon_client, db_session, unique_name):
    user = _make_login_user(db_session, unique_name)
    resp = anon_client.post("/api/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 200
    assert "message" in resp.get_json()


def test_forgot_password_unknown_email_returns_same_generic_message(anon_client):
    known = anon_client.post("/api/auth/forgot-password", json={"email": "nadie@sywork.net"})
    assert known.status_code == 200
    assert "message" in known.get_json()


def test_forgot_password_missing_email_returns_400(anon_client):
    resp = anon_client.post("/api/auth/forgot-password", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "validation_error"


def test_reset_password_with_valid_token_succeeds(anon_client, db_session, unique_name):
    user = _make_login_user(db_session, unique_name)
    token, expires_at = _auth_svc.generate_reset_token()
    UserRepository(db_session).set_reset_token(user.id, token, expires_at)

    resp = anon_client.post("/api/auth/reset-password", json={"token": token, "new_password": "NuevaClave2026!"})
    assert resp.status_code == 200

    login = anon_client.post("/api/auth/login", json={
        "username_or_email": user.username, "password": "NuevaClave2026!",
    })
    assert login.status_code == 200

    # El token es de un solo uso: reintentarlo debe fallar
    reuse = anon_client.post("/api/auth/reset-password", json={"token": token, "new_password": "OtraClave2026!"})
    assert reuse.status_code == 400


def test_reset_password_with_expired_token_returns_400(anon_client, db_session, unique_name):
    import datetime as dt
    user = _make_login_user(db_session, unique_name)
    token = "expired-token-" + unique_name
    UserRepository(db_session).set_reset_token(user.id, token, dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1))

    resp = anon_client.post("/api/auth/reset-password", json={"token": token, "new_password": "NuevaClave2026!"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_token"


def test_reset_password_with_unknown_token_returns_400(anon_client):
    resp = anon_client.post("/api/auth/reset-password", json={"token": "no-existe", "new_password": "NuevaClave2026!"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_token"


def test_login_mode_team_rejects_client_portal_role(client, db_session, unique_name):
    """spec 046 FR-003: una cuenta Usuario/cliente no puede loguear por la pestaña 'team'."""
    user = _make_login_user(db_session, unique_name, role_name="Usuario/cliente")
    resp = client.post("/api/auth/login", json={
        "username_or_email": user.email, "password": "Sywork2026!", "login_mode": "team",
    })
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "unauthorized"


def test_login_mode_client_portal_rejects_internal_role(client, db_session, unique_name):
    """spec 046 FR-003: una cuenta interna no puede loguear por la pestaña 'client_portal'."""
    user = _make_login_user(db_session, unique_name, role_name="Coordinador")
    resp = client.post("/api/auth/login", json={
        "username_or_email": user.email, "password": "Sywork2026!", "login_mode": "client_portal",
    })
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "unauthorized"


def test_login_mode_matching_role_succeeds(client, db_session, unique_name):
    """spec 046 FR-003: el rol correcto para la pestaña elegida sigue funcionando."""
    user = _make_login_user(db_session, unique_name, role_name="Usuario/cliente")
    resp = client.post("/api/auth/login", json={
        "username_or_email": user.email, "password": "Sywork2026!", "login_mode": "client_portal",
    })
    assert resp.status_code == 200


def test_reset_password_rejected_for_inactive_account(anon_client, db_session, unique_name):
    user = _make_login_user(db_session, unique_name)
    token, expires_at = _auth_svc.generate_reset_token()
    repo = UserRepository(db_session)
    repo.set_reset_token(user.id, token, expires_at)
    repo.set_active(user.id, False)

    resp = anon_client.post("/api/auth/reset-password", json={"token": token, "new_password": "NuevaClave2026!"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_token"
