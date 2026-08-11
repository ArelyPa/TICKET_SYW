import uuid

import pytest

from backend.app import create_app
from backend.domain.entities.user import User
from backend.infra.database import get_db
from backend.infra.repositories.user_repo import UserRepository


@pytest.fixture(scope="session")
def app():
    return create_app()


def _token_for_email(app, email: str) -> str:
    """JWT real para un usuario semilla, sin necesitar su contraseña."""
    from flask_jwt_extended import create_access_token
    with app.app_context():
        user = UserRepository(get_db()).get_by_email(email)
        assert user is not None, f"Usuario semilla {email} no existe (correr migraciones)"
        return create_access_token(identity=str(user.id))


@pytest.fixture(scope="session")
def admin_token(app):
    return _token_for_email(app, "admin@sywork.net")


@pytest.fixture(scope="session")
def coordinator_token(app):
    return _token_for_email(app, "coordinador@sywork.net")


@pytest.fixture(scope="session")
def qm_token(app):
    return _token_for_email(app, "qm@sywork.net")


@pytest.fixture(scope="session")
def resolver_token(app):
    return _token_for_email(app, "resolutor@sywork.net")


@pytest.fixture()
def client(app, admin_token):
    """Test client autenticado como Admin por defecto (FR-022: la API exige JWT).

    Los tests de enforcement usan `anon_client` o tokens de otros roles.
    """
    test_client = app.test_client()
    original_open = test_client.open

    def open_with_auth(*args, **kwargs):
        headers = kwargs.pop("headers", None) or {}
        if "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {admin_token}"
        kwargs["headers"] = headers
        return original_open(*args, **kwargs)

    test_client.open = open_with_auth
    return test_client


@pytest.fixture()
def anon_client(app):
    """Test client SIN autenticación, para validar 401."""
    return app.test_client()


@pytest.fixture()
def unique_name():
    """Short random suffix so repeated test runs never collide on unique constraints."""
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def db_session():
    session = get_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def resolver_user(db_session, unique_name):
    """A throwaway non-admin user for exercising /api/users mutation endpoints
    without touching real accounts or the last-admin business rule."""
    from backend.infra.repositories.role_repo import RoleRepository
    resolutor_role = RoleRepository(db_session).get_by_name("Resolutor")
    user = User(
        id=uuid.uuid4(), email=f"test.{unique_name}@sywork.net", username=f"test_{unique_name}",
        role=resolutor_role, active=True,
    )
    return UserRepository(db_session).create(user)


@pytest.fixture()
def qm_user(db_session, unique_name):
    """OBS-0052/0053: usuario QM de prueba sin perfil de recurso propio — los candidatos para
    "Pre-Análisis" se listan/asignan por rol, no por la tabla `resources`."""
    from backend.infra.repositories.role_repo import RoleRepository
    qm_role = RoleRepository(db_session).get_by_name("QM")
    user = User(
        id=uuid.uuid4(), email=f"test.qm.{unique_name}@sywork.net", username=f"test_qm_{unique_name}",
        role=qm_role, active=True,
    )
    return UserRepository(db_session).create(user)


@pytest.fixture()
def coordinador_user(db_session, unique_name):
    """spec 041 (FR-013): usuario Coordinador de prueba sin perfil de recurso propio — mismo
    patrón que `qm_user` (candidatos listados/asignados por rol, no por `resources`)."""
    from backend.infra.repositories.role_repo import RoleRepository
    coordinador_role = RoleRepository(db_session).get_by_name("Coordinador")
    user = User(
        id=uuid.uuid4(), email=f"test.coord.{unique_name}@sywork.net",
        username=f"test_coord_{unique_name}", role=coordinador_role, active=True,
    )
    return UserRepository(db_session).create(user)


# ── Fixtures compartidos de tickets (usados por tests/api y tests/infra) ────────

@pytest.fixture()
def ticket_client(client, unique_name):
    """Cliente (maestro) activo de prueba."""
    response = client.post("/api/clients", json={"name": f"Cliente Tickets {unique_name}"})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


@pytest.fixture()
def ticket_resource(client, unique_name, resolver_user):
    """Recurso activo vinculado al usuario resolutor de prueba."""
    response = client.post("/api/resources", json={
        "full_name": f"Resolutor Tickets {unique_name}",
        "email": f"resolutor.tk.{unique_name}@sywork.net",
        "user_id": str(resolver_user.id),
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


@pytest.fixture()
def ticket_project(client, ticket_client, unique_name):
    """Proyecto activo de prueba, vinculado a `ticket_client` — OBS-0045: Proyecto pasa a ser
    obligatorio al crear un Ticket (no Tarea) desde perfil interno."""
    import datetime
    response = client.post("/api/projects", json={
        "name": f"Proyecto Tickets {unique_name}",
        "client_id": ticket_client["id"],
        "start_date": datetime.date.today().isoformat(),
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


@pytest.fixture()
def make_ticket(client, ticket_client, ticket_project):
    """Factory de tickets en estado NUEVO."""
    def _make(**overrides):
        payload = {
            "title": "Error contabilizando en GL",
            "description": "El batch de contabilización falla con error 105",
            "ticket_type": "incident",
            "priority": "high",
            "severity": "s2",
            "client_id": ticket_client["id"],
            "project_id": ticket_project["id"],
            **overrides,
        }
        response = client.post("/api/tickets", json=payload)
        assert response.status_code == 201, response.get_json()
        return response.get_json()
    return _make


@pytest.fixture()
def resolver_auth(app, resolver_user):
    """Header Authorization del usuario resolutor de prueba."""
    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity=str(resolver_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def coordinator_auth(coordinator_token):
    """Header Authorization del Coordinador semilla (rol interno con tickets:manage_skills,
    OBS-0047/0048 spec 033 — permiso ampliado a todo rol interno en spec 035)."""
    return {"Authorization": f"Bearer {coordinator_token}"}


@pytest.fixture()
def encargado_user(db_session, unique_name, ticket_client):
    """Usuario de rol Usuario/cliente (antes Encargado, spec 010) vinculado a `ticket_client` vía client_contacts (Fase 2.1)."""
    from backend.domain.entities.client_contact import ClientContact
    from backend.infra.repositories.client_contact_repo import ClientContactRepository
    from backend.infra.repositories.role_repo import RoleRepository
    encargado_role = RoleRepository(db_session).get_by_name("Usuario/cliente")
    user = User(
        id=uuid.uuid4(), email=f"encargado.{unique_name}@clienteexterno.com",
        username=f"encargado_{unique_name}", role=encargado_role,
    )
    created = UserRepository(db_session).create(user)
    ClientContactRepository(db_session).create(
        ClientContact(id=uuid.uuid4(), user_id=created.id, client_id=uuid.UUID(ticket_client["id"]))
    )
    return created


@pytest.fixture()
def encargado_auth(app, encargado_user):
    """Header Authorization del usuario de rol Usuario/cliente de prueba."""
    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity=str(encargado_user.id))
    return {"Authorization": f"Bearer {token}"}
