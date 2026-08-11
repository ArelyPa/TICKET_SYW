"""GET/PUT /api/teamwork-integration/config + POST /test-connection (spec 042, US1).

Principio VII: solo la configuración singleton (1 fila) y `requests` mockeado — sin dependencia
real de una cuenta de Teamwork.
"""
from unittest.mock import patch, MagicMock

import pytest

from backend.infra.importers import teamwork_connection_client as twc

_QA42_RESOURCE_EMAIL = "qa42.entitymapping@sywork.net"


@pytest.fixture()
def qa42_resource(client):
    existing = client.get("/api/resources", query_string={"search": "QA42 EntityMapping"}).get_json()
    match = next((r for r in existing["items"] if r["email"] == _QA42_RESOURCE_EMAIL), None)
    if match:
        return match
    response = client.post("/api/resources", json={
        "full_name": "QA42 EntityMapping", "email": _QA42_RESOURCE_EMAIL,
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_get_config_without_saved_config_returns_has_token_false(client):
    response = client.get("/api/teamwork-integration/config")
    assert response.status_code == 200
    body = response.get_json()
    assert "api_token" not in body


def test_put_config_then_get_reflects_it_without_exposing_token(client):
    response = client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix-test.teamwork.com", "environment": "test",
        "api_token": "tk_super_secreto",
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["site_url"] == "https://sytix-test.teamwork.com"
    assert body["environment"] == "test"
    assert body["has_token"] is True
    assert "api_token" not in body

    get_response = client.get("/api/teamwork-integration/config")
    assert get_response.get_json()["has_token"] is True
    assert "api_token" not in get_response.get_json()


def test_put_config_omitting_token_keeps_previous_one(client):
    client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "production",
        "api_token": "tk_original",
    })
    response = client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "production",
    })
    assert response.status_code == 200
    assert response.get_json()["has_token"] is True


def test_put_config_rejects_invalid_site_url(client):
    response = client.put("/api/teamwork-integration/config", json={
        "site_url": "not-a-url", "environment": "test", "api_token": "x",
    })
    assert response.status_code == 400


def test_put_config_rejects_invalid_environment(client):
    response = client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "staging", "api_token": "x",
    })
    assert response.status_code == 400


@patch("backend.api.routes.teamwork_integration.check_connection")
def test_test_connection_success_updates_last_test_status(mock_test_connection, client):
    client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "test", "api_token": "tk_ok",
    })
    mock_test_connection.return_value = {"status": twc.STATUS_SUCCESS, "message": None}

    response = client.post("/api/teamwork-integration/test-connection")
    assert response.status_code == 200
    assert response.get_json()["status"] == "success"

    get_response = client.get("/api/teamwork-integration/config")
    assert get_response.get_json()["last_test_status"] == "success"


def test_config_forbidden_for_resolver(client, resolver_auth):
    response = client.get("/api/teamwork-integration/config", headers=resolver_auth)
    assert response.status_code == 403


def _connect_and_test(client):
    client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "test", "api_token": "tk_ok",
    })
    with patch("backend.api.routes.teamwork_integration.check_connection") as mock:
        mock.return_value = {"status": twc.STATUS_SUCCESS, "message": None}
        client.post("/api/teamwork-integration/test-connection")


def test_sync_blocked_when_connection_not_tested(client):
    client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "test", "api_token": "tk_ok",
    })
    response = client.post("/api/teamwork-integration/sync/company")
    assert response.status_code == 409


def test_sync_rejects_invalid_entity_type(client):
    _connect_and_test(client)
    response = client.post("/api/teamwork-integration/sync/invalid")
    assert response.status_code == 400


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_sync_companies_upserts_entity_mappings(mock_get, client, app):
    _connect_and_test(client)
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"companies": [{"id": 501, "name": "QA42 Sync Company"}]}
    resp.raise_for_status.side_effect = None
    mock_get.return_value = resp

    response = client.post("/api/teamwork-integration/sync/company")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["synced"] == 1

    # Re-sincronizar el mismo elemento actualiza, no duplica (idempotente incluso si la fila ya
    # existía de una corrida anterior — este entorno de Docker no aísla datos entre corridas).
    response2 = client.post("/api/teamwork-integration/sync/company")
    assert response2.get_json()["updated"] == 1
    assert response2.get_json()["new"] == 0

    from backend.infra.database import get_db
    from backend.infra.repositories.teamwork_integration_repo import EntityMappingRepository
    with app.app_context():
        mappings = EntityMappingRepository(get_db()).list(entity_type="company")
    assert any(m.teamwork_name == "QA42 Sync Company" for m in mappings)


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_sync_person_automaps_by_email(mock_get, client, qa42_resource):
    _connect_and_test(client)
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"people": [
        {"id": 777, "firstName": "QA42-B", "lastName": "Distinto",
         "email": qa42_resource["email"]},
    ]}
    resp.raise_for_status.side_effect = None
    mock_get.return_value = resp

    client.post("/api/teamwork-integration/sync/person")
    mappings = client.get("/api/teamwork-integration/entity-mappings",
                          query_string={"entity_type": "person"}).get_json()["rows"]
    row = next(m for m in mappings if m["teamwork_id"] == "777")
    assert row["match_method"] == "email"
    assert row["sytix_id"] == qa42_resource["id"]
    assert row["sytix_name"] == qa42_resource["full_name"]


def test_entity_mapping_manual_override(client, qa42_resource):
    _connect_and_test(client)
    with patch("backend.infra.importers.teamwork_connection_client.requests.get") as mock_get:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"people": [{"id": 778, "firstName": "Sin", "lastName": "Match"}]}
        resp.raise_for_status.side_effect = None
        mock_get.return_value = resp
        client.post("/api/teamwork-integration/sync/person")

    mappings = client.get("/api/teamwork-integration/entity-mappings",
                          query_string={"entity_type": "person"}).get_json()["rows"]
    mapping = next(m for m in mappings if m["teamwork_id"] == "778")
    assert mapping["match_method"] is None

    response = client.put(f"/api/teamwork-integration/entity-mappings/{mapping['id']}",
                          json={"sytix_id": qa42_resource["id"]})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["match_method"] == "manual"
    assert response.get_json()["sytix_id"] == qa42_resource["id"]

    cleared = client.put(f"/api/teamwork-integration/entity-mappings/{mapping['id']}",
                         json={"sytix_id": None})
    assert cleared.get_json()["sytix_id"] is None
    assert cleared.get_json()["match_method"] is None


def test_entity_mapping_update_not_found(client):
    import uuid
    response = client.put(f"/api/teamwork-integration/entity-mappings/{uuid.uuid4()}",
                          json={"sytix_id": None})
    assert response.status_code == 404


# ── "Migrar como Nuevo" (spec 043 US1-US4) ──────────────────────────────────────────────────
# Principio VII: acotado a los archivos de esta sesión, máximo ~10 registros dummy por test.

def _sync_with_payload(client, entity_type: str, payload: dict):
    with patch("backend.infra.importers.teamwork_connection_client.requests.get") as mock_get:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        resp.raise_for_status.side_effect = None
        mock_get.return_value = resp
        response = client.post(f"/api/teamwork-integration/sync/{entity_type}")
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _mapping_row(client, entity_type: str, teamwork_id: str) -> dict:
    rows = client.get("/api/teamwork-integration/entity-mappings",
                      query_string={"entity_type": entity_type}).get_json()["rows"]
    return next(m for m in rows if m["teamwork_id"] == teamwork_id)


def test_create_new_company_success_already_linked_and_duplicate(client, unique_name):
    # IDs de Teamwork derivados de `unique_name` (no literales fijos): esta suite corre contra
    # Postgres real sin rollback entre corridas (mismo caso ya documentado en
    # test_sync_companies_upserts_entity_mappings) — un `teamwork_id` fijo colisionaría con la
    # fila que dejó una corrida anterior de este mismo test.
    tw_id = f"c1-{unique_name}"
    tw_id_dup = f"c2-{unique_name}"
    name = f"QA43 Migrar Empresa {unique_name}"
    _sync_with_payload(client, "company", {"companies": [{"id": tw_id, "name": name}]})
    mapping = _mapping_row(client, "company", tw_id)
    assert mapping["migration_status"] == "pending"

    response = client.post(f"/api/teamwork-integration/entity-mappings/{mapping['id']}/create-new")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["mapping"]["migration_status"] == "created"
    assert body["mapping"]["match_method"] == "created_new"
    assert body["created"]["name"] == name

    client_response = client.get(f"/api/clients/{body['created']['id']}")
    assert client_response.status_code == 200
    assert client_response.get_json()["name"] == name

    # Ya vinculada: no se puede volver a migrar (FR-004)
    retry = client.post(f"/api/teamwork-integration/entity-mappings/{mapping['id']}/create-new")
    assert retry.status_code == 409
    assert retry.get_json()["error"] == "already_linked"

    # Nombre duplicado: otra fila sin vincular con el mismo nombre no puede migrarse (FR-002)
    _sync_with_payload(client, "company", {"companies": [{"id": tw_id_dup, "name": name}]})
    dup_mapping = _mapping_row(client, "company", tw_id_dup)
    # El nombre ya coincide exacto con el Cliente recién creado: el automapeo de la sincronización
    # ya lo dejó vinculado (match_method="name") — se limpia manualmente para forzar el caso real
    # de "intentar migrar sobre un nombre duplicado" (spec.md US1 escenario 4).
    client.put(f"/api/teamwork-integration/entity-mappings/{dup_mapping['id']}",
              json={"sytix_id": None})
    dup_response = client.post(f"/api/teamwork-integration/entity-mappings/{dup_mapping['id']}/create-new")
    assert dup_response.status_code == 409
    assert dup_response.get_json()["error"] == "name_duplicate"


def test_create_new_project_and_tasklist_blocked_until_parent_resolved(client, unique_name):
    company_tw_id, project_tw_id, tasklist_tw_id = f"co-{unique_name}", f"pr-{unique_name}", f"tl-{unique_name}"
    company_name = f"QA43 Empresa Cadena {unique_name}"
    project_name = f"QA43 Proyecto Cadena {unique_name}"
    tasklist_name = f"QA43 Lista Cadena {unique_name}"

    _sync_with_payload(client, "company", {"companies": [{"id": company_tw_id, "name": company_name}]})
    _sync_with_payload(client, "project", {"projects": [
        {"id": project_tw_id, "name": project_name, "company": {"id": company_tw_id}}]})
    _sync_with_payload(client, "tasklist", {"tasklists": [
        {"id": tasklist_tw_id, "name": tasklist_name, "project": {"id": project_tw_id}}]})

    project_mapping = _mapping_row(client, "project", project_tw_id)
    tasklist_mapping = _mapping_row(client, "tasklist", tasklist_tw_id)
    assert project_mapping["parent_context"]["status"] == "pending"
    # El Proyecto padre ya se sincronizó (existe su fila de homologación) pero aún no está
    # vinculado a un Cliente de SYTIX — "pending", no "unmapped" (que sería si ni siquiera se
    # hubiera sincronizado ese Proyecto todavía).
    assert tasklist_mapping["parent_context"]["status"] == "pending"

    blocked = client.post(f"/api/teamwork-integration/entity-mappings/{project_mapping['id']}/create-new")
    assert blocked.status_code == 409
    assert blocked.get_json()["error"] == "parent_not_resolved"

    company_mapping = _mapping_row(client, "company", company_tw_id)
    company_created = client.post(
        f"/api/teamwork-integration/entity-mappings/{company_mapping['id']}/create-new").get_json()

    project_mapping = _mapping_row(client, "project", project_tw_id)
    assert project_mapping["parent_context"]["status"] == "resolved"
    assert project_mapping["parent_context"]["client_label"] == company_name

    project_created = client.post(
        f"/api/teamwork-integration/entity-mappings/{project_mapping['id']}/create-new")
    assert project_created.status_code == 200, project_created.get_json()
    assert project_created.get_json()["created"]["name"] == project_name

    project_get = client.get(f"/api/projects/{project_created.get_json()['created']['id']}")
    assert project_get.get_json()["client_id"] == company_created["created"]["id"]

    tasklist_mapping = _mapping_row(client, "tasklist", tasklist_tw_id)
    assert tasklist_mapping["parent_context"]["status"] == "resolved"
    assert tasklist_mapping["parent_context"]["client_label"] == company_name
    assert tasklist_mapping["parent_context"]["project_label"] == project_name

    tasklist_created = client.post(
        f"/api/teamwork-integration/entity-mappings/{tasklist_mapping['id']}/create-new")
    assert tasklist_created.status_code == 200, tasklist_created.get_json()
    assert tasklist_created.get_json()["created"]["name"] == tasklist_name


def test_create_new_person_internal_role_creates_user_and_resource(client, db_session, unique_name):
    from backend.infra.repositories.role_repo import RoleRepository
    resolutor_role = RoleRepository(db_session).get_by_name("Resolutor")
    tw_id = f"p1-{unique_name}"
    email = f"qa43.person.{unique_name}@sywork.net"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id, "firstName": "QA43", "lastName": unique_name, "email": email}]})
    mapping = _mapping_row(client, "person", tw_id)
    assert mapping["teamwork_email"] == email
    assert mapping["migration_status"] == "pending"

    candidates = client.get(
        f"/api/teamwork-integration/entity-mappings/{mapping['id']}/create-new-candidates").get_json()
    assert any(r["id"] == str(resolutor_role.id) for r in candidates["roles"])

    response = client.post(f"/api/teamwork-integration/entity-mappings/{mapping['id']}/create-new",
                           json={"role_id": str(resolutor_role.id)})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["mapping"]["migration_status"] == "created"

    resource_id = response.get_json()["created"]["id"]
    resource_get = client.get(f"/api/resources/{resource_id}")
    assert resource_get.get_json()["email"] == email


def test_create_new_person_usuario_cliente_role_requires_and_uses_client(client, db_session, unique_name):
    from backend.infra.repositories.role_repo import RoleRepository
    contact_role = RoleRepository(db_session).get_by_name("Usuario/cliente")
    client_response = client.post("/api/clients", json={"name": f"QA43 Cliente Persona {unique_name}"})
    assert client_response.status_code == 201
    client_id = client_response.get_json()["id"]

    tw_id = f"p2-{unique_name}"
    email = f"qa43.cliente.{unique_name}@clienteexterno.com"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id, "firstName": "QA43C", "lastName": unique_name, "email": email}]})
    mapping = _mapping_row(client, "person", tw_id)

    missing_client = client.post(
        f"/api/teamwork-integration/entity-mappings/{mapping['id']}/create-new",
        json={"role_id": str(contact_role.id)})
    assert missing_client.status_code == 400

    response = client.post(
        f"/api/teamwork-integration/entity-mappings/{mapping['id']}/create-new",
        json={"role_id": str(contact_role.id), "client_id": client_id})
    assert response.status_code == 200, response.get_json()
    contacts = client.get("/api/client-contacts", query_string={"email": email}).get_json()["items"]
    assert any(c["client_id"] == client_id for c in contacts)


def test_create_new_person_missing_role_id_and_duplicate_email(client, db_session, resolver_user, unique_name):
    tw_id_no_role, tw_id_dup = f"p3-{unique_name}", f"p4-{unique_name}"
    fresh_email = f"qa43.norole.{unique_name}@sywork.net"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id_no_role, "firstName": "QA43-NoRole", "lastName": unique_name, "email": fresh_email}]})
    no_role_mapping = _mapping_row(client, "person", tw_id_no_role)
    no_role_response = client.post(
        f"/api/teamwork-integration/entity-mappings/{no_role_mapping['id']}/create-new")
    assert no_role_response.status_code == 400

    # resolver_user tiene User pero ningún Recurso con ese correo — la sincronización no lo
    # automapea (los candidatos de automapeo de "person" son Recursos, no Usuarios), así que
    # llega sin resolver hasta "Migrar como Nuevo", donde el chequeo de correo duplicado sí debe
    # bloquearlo (FR-011).
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id_dup, "firstName": "QA43-Dup", "lastName": unique_name, "email": resolver_user.email}]})
    dup_mapping = _mapping_row(client, "person", tw_id_dup)
    from backend.infra.repositories.role_repo import RoleRepository
    resolutor_role = RoleRepository(db_session).get_by_name("Resolutor")
    dup_response = client.post(
        f"/api/teamwork-integration/entity-mappings/{dup_mapping['id']}/create-new",
        json={"role_id": str(resolutor_role.id)})
    assert dup_response.status_code == 409
    assert dup_response.get_json()["error"] == "email_in_use"


def test_resync_does_not_regress_created_or_manual_mapping(client, qa42_resource, unique_name):
    tw_id = f"c3-{unique_name}"
    name = f"QA43 Empresa NoRegresion {unique_name}"
    _sync_with_payload(client, "company", {"companies": [{"id": tw_id, "name": name}]})
    mapping = _mapping_row(client, "company", tw_id)
    created = client.post(
        f"/api/teamwork-integration/entity-mappings/{mapping['id']}/create-new").get_json()

    # Re-sincronizar el mismo catálogo no debe tocar sytix_id/match_method de una fila ya
    # "Migrado" (FR-014) — el nombre puede repetirse tal cual, upsert_from_sync solo actualiza
    # teamwork_name/parent_teamwork_id/teamwork_email, nunca sytix_id de una fila ya resuelta.
    _sync_with_payload(client, "company", {"companies": [{"id": tw_id, "name": name}]})
    after_resync = _mapping_row(client, "company", tw_id)
    assert after_resync["sytix_id"] == created["mapping"]["sytix_id"]
    assert after_resync["match_method"] == "created_new"
    assert after_resync["migration_status"] == "created"


# ── US1 (spec 044): paginación completa + Compañía de origen en Personal ───────────────────

@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_fetch_all_pages_recorre_paginas_hasta_pagina_corta(mock_get):
    """research.md Decisión 1: una página con menos elementos que `pageSize` (o vacía) es la
    última — el helper debe devolver la unión de todas las páginas, no solo la primera."""
    from backend.infra.importers import teamwork_connection_client as twc

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = {"people": [{"id": 1}, {"id": 2}, {"id": 3}]}
    page1.raise_for_status.side_effect = None
    page2 = MagicMock()
    page2.status_code = 200
    page2.json.return_value = {"people": [{"id": 4}]}
    page2.raise_for_status.side_effect = None
    mock_get.side_effect = [page1, page2]

    items = twc._fetch_all_pages("https://x.teamwork.com/projects/api/v3/people.json",
                                 ("tok", "x"), {"pageSize": 3}, "people")
    assert [i["id"] for i in items] == [1, 2, 3, 4]
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].kwargs["params"]["page"] == 1
    assert mock_get.call_args_list[1].kwargs["params"]["page"] == 2


def test_sync_person_resolves_company_via_parent_context(client, unique_name):
    company_tw_id = f"pco-{unique_name}"
    company_name = f"QA44 Compania Personal {unique_name}"
    _sync_with_payload(client, "company", {"companies": [{"id": company_tw_id, "name": company_name}]})
    company_mapping = _mapping_row(client, "company", company_tw_id)
    create_response = client.post(
        f"/api/teamwork-integration/entity-mappings/{company_mapping['id']}/create-new")
    assert create_response.status_code == 200, create_response.get_json()

    person_tw_id = f"pp-{unique_name}"
    person_tw_id_no_company = f"pp2-{unique_name}"
    _sync_with_payload(client, "person", {"people": [
        {"id": person_tw_id, "firstName": "QA44", "lastName": unique_name,
         "email": f"qa44.{unique_name}@sywork.net", "companyId": company_tw_id},
        {"id": person_tw_id_no_company, "firstName": "QA44-Sin", "lastName": unique_name,
         "email": f"qa44b.{unique_name}@sywork.net"},
    ]})

    mapping_with_company = _mapping_row(client, "person", person_tw_id)
    mapping_without_company = _mapping_row(client, "person", person_tw_id_no_company)
    assert mapping_with_company["parent_context"]["status"] == "resolved"
    assert mapping_with_company["parent_context"]["client_label"] == company_name
    assert mapping_without_company["parent_context"]["status"] == "unmapped"
    assert mapping_without_company["parent_context"]["client_label"] is None


# ── US2 (spec 044): migración masiva de Personal ────────────────────────────────────────────

def test_bulk_create_new_person_success_and_already_linked_skip(client, db_session, unique_name):
    from backend.infra.repositories.role_repo import RoleRepository
    resolutor_role = RoleRepository(db_session).get_by_name("Resolutor")

    tw_id_new, tw_id_already = f"bp1-{unique_name}", f"bp2-{unique_name}"
    email_new = f"qa44.bulk1.{unique_name}@sywork.net"
    email_already = f"qa44.bulk2.{unique_name}@sywork.net"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id_new, "firstName": "QA44-Bulk1", "lastName": unique_name, "email": email_new},
        {"id": tw_id_already, "firstName": "QA44-Bulk2", "lastName": unique_name, "email": email_already},
    ]})
    mapping_new = _mapping_row(client, "person", tw_id_new)
    mapping_already = _mapping_row(client, "person", tw_id_already)
    already_response = client.post(
        f"/api/teamwork-integration/entity-mappings/{mapping_already['id']}/create-new",
        json={"role_id": str(resolutor_role.id)})
    assert already_response.status_code == 200, already_response.get_json()

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new", json={
        "mapping_ids": [mapping_new["id"], mapping_already["id"]],
        "role_id": str(resolutor_role.id),
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert len(body["created"]) == 1
    assert body["created"][0]["mapping_id"] == mapping_new["id"]
    assert any(s["mapping_id"] == mapping_already["id"] and s["reason"] == "already_linked"
              for s in body["skipped"])

    resource_get = client.get(f"/api/resources/{body['created'][0]['sytix_id']}")
    assert resource_get.get_json()["email"] == email_new


def test_bulk_create_new_usuario_cliente_role_uses_client(client, db_session, unique_name):
    from backend.infra.repositories.role_repo import RoleRepository
    contact_role = RoleRepository(db_session).get_by_name("Usuario/cliente")
    client_response = client.post("/api/clients", json={"name": f"QA44 Bulk Cliente {unique_name}"})
    assert client_response.status_code == 201
    client_id = client_response.get_json()["id"]

    tw_id = f"bp3-{unique_name}"
    email = f"qa44.bulk3.{unique_name}@clienteexterno.com"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id, "firstName": "QA44-Bulk3", "lastName": unique_name, "email": email}]})
    mapping = _mapping_row(client, "person", tw_id)

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new", json={
        "mapping_ids": [mapping["id"]], "role_id": str(contact_role.id), "client_id": client_id,
    })
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["created"][0]["mapping_id"] == mapping["id"]
    contacts = client.get("/api/client-contacts", query_string={"email": email}).get_json()["items"]
    assert any(c["client_id"] == client_id for c in contacts)


def test_bulk_create_new_usuario_cliente_missing_client_id_is_skipped_not_aborted(
        client, db_session, unique_name):
    from backend.infra.repositories.role_repo import RoleRepository
    contact_role = RoleRepository(db_session).get_by_name("Usuario/cliente")
    tw_id = f"bp4-{unique_name}"
    email = f"qa44.bulk4.{unique_name}@clienteexterno.com"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id, "firstName": "QA44-Bulk4", "lastName": unique_name, "email": email}]})
    mapping = _mapping_row(client, "person", tw_id)

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new", json={
        "mapping_ids": [mapping["id"]], "role_id": str(contact_role.id),
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["created"] == []
    assert body["skipped"][0]["mapping_id"] == mapping["id"]


def test_bulk_create_new_invalid_role_id_format_returns_400(client):
    # spec 045 US2 generaliza el endpoint a los 4 catálogos: `role_id` ya no es obligatorio en el
    # cuerpo (research.md Decisión 2) — solo se valida el *formato* si viene informado. Una fila
    # `person` sin `role_id` en absoluto se omite fila por fila (`role_id_required`, ver
    # test_bulk_create_new_generalized_person_without_role_id_is_skipped), en vez de rechazar todo
    # el request con 400 como hacía la versión de spec 044 exclusiva de Personal.
    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new",
                           json={"mapping_ids": ["not-a-uuid"], "role_id": "not-a-uuid-either"})
    assert response.status_code == 400


def test_bulk_create_new_empty_mapping_ids_returns_400(client, db_session):
    from backend.infra.repositories.role_repo import RoleRepository
    resolutor_role = RoleRepository(db_session).get_by_name("Resolutor")
    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new",
                           json={"mapping_ids": [], "role_id": str(resolutor_role.id)})
    assert response.status_code == 400


# ── US3 (spec 044): migración masiva de Tareas y Subtareas ──────────────────────────────────

def test_sync_tasks_blocked_when_connection_not_tested(client):
    client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "test", "api_token": "tk_ok",
    })
    response = client.post("/api/teamwork-integration/sync/tasks")
    assert response.status_code == 409


def test_sync_tasks_creates_hierarchy_and_skips_unmapped_project(client, unique_name):
    _connect_and_test(client)

    company_tw_id, project_tw_id, tasklist_tw_id = (
        f"tco-{unique_name}", f"tpr-{unique_name}", f"ttl-{unique_name}")
    company_name = f"QA45 Empresa Tareas {unique_name}"
    project_name = f"QA45 Proyecto Tareas {unique_name}"
    tasklist_name = f"QA45 Lista Tareas {unique_name}"

    _sync_with_payload(client, "company", {"companies": [{"id": company_tw_id, "name": company_name}]})
    company_mapping = _mapping_row(client, "company", company_tw_id)
    assert client.post(
        f"/api/teamwork-integration/entity-mappings/{company_mapping['id']}/create-new").status_code == 200

    _sync_with_payload(client, "project", {"projects": [
        {"id": project_tw_id, "name": project_name, "company": {"id": company_tw_id}}]})
    project_mapping = _mapping_row(client, "project", project_tw_id)
    assert client.post(
        f"/api/teamwork-integration/entity-mappings/{project_mapping['id']}/create-new").status_code == 200

    _sync_with_payload(client, "tasklist", {"tasklists": [
        {"id": tasklist_tw_id, "name": tasklist_name, "project": {"id": project_tw_id}}]})
    tasklist_mapping = _mapping_row(client, "tasklist", tasklist_tw_id)
    assert client.post(
        f"/api/teamwork-integration/entity-mappings/{tasklist_mapping['id']}/create-new").status_code == 200

    task_parent_tw_id, task_child_tw_id, task_unmapped_tw_id = (
        f"tk1-{unique_name}", f"tk2-{unique_name}", f"tk3-{unique_name}")
    parent_title = f"QA45 Tarea Padre {unique_name}"
    child_title = f"QA45 Subtarea {unique_name}"

    def _tasks_response(*_args, **_kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status.side_effect = None
        resp.json.return_value = {"tasks": [
            {"id": task_parent_tw_id, "name": parent_title, "description": "desc padre",
             "projectId": project_tw_id, "tasklistId": tasklist_tw_id},
            {"id": task_child_tw_id, "name": child_title, "description": "desc hija",
             "projectId": project_tw_id, "tasklistId": tasklist_tw_id,
             "parentTaskId": task_parent_tw_id},
            {"id": task_unmapped_tw_id, "name": f"QA45 Sin Proyecto {unique_name}",
             "projectId": f"unmapped-{unique_name}"},
        ]}
        return resp

    with patch("backend.infra.importers.teamwork_connection_client.requests.get") as mock_get:
        mock_get.side_effect = _tasks_response
        response = client.post("/api/teamwork-integration/sync/tasks")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["synced"] == 3
    assert body["created"] == 2
    assert body["updated"] == 0
    assert len(body["skipped"]) == 1
    assert body["skipped"][0] == {"teamwork_id": task_unmapped_tw_id, "reason": "project_not_mapped"}

    child_items = client.get("/api/tickets", query_string={"search": child_title}).get_json()["items"]
    assert len(child_items) == 1
    child_detail = client.get(f"/api/tickets/{child_items[0]['id']}").get_json()
    assert child_detail["external_reference_id"] == task_child_tw_id
    assert child_detail["external_reference_url"].endswith(f"/app/tasks/{task_child_tw_id}")
    assert child_detail["parent"] is not None

    parent_items = client.get("/api/tickets", query_string={"search": parent_title}).get_json()["items"]
    assert len(parent_items) == 1
    parent_detail = client.get(f"/api/tickets/{parent_items[0]['id']}").get_json()
    assert child_detail["parent"]["id"] == parent_detail["id"]

    # Re-ejecutar el mismo lote actualiza en vez de duplicar (mismo lote mockeado).
    with patch("backend.infra.importers.teamwork_connection_client.requests.get") as mock_get2:
        mock_get2.side_effect = _tasks_response
        response2 = client.post("/api/teamwork-integration/sync/tasks")
    assert response2.status_code == 200, response2.get_json()
    body2 = response2.get_json()
    assert body2["created"] == 0
    assert body2["updated"] == 2


# ── US5 (spec 044): distintivo de trazabilidad en pantallas principales de SYTIX ────────────

def test_migrated_refs_returns_only_migrated_of_requested_type(client, unique_name):
    tw_id_migrated, tw_id_pending = f"mr1-{unique_name}", f"mr2-{unique_name}"
    name_migrated = f"QA46 Cliente Migrado {unique_name}"
    name_pending = f"QA46 Cliente Pendiente {unique_name}"
    _sync_with_payload(client, "company", {"companies": [
        {"id": tw_id_migrated, "name": name_migrated},
        {"id": tw_id_pending, "name": name_pending},
    ]})
    mapping_migrated = _mapping_row(client, "company", tw_id_migrated)
    created = client.post(
        f"/api/teamwork-integration/entity-mappings/{mapping_migrated['id']}/create-new").get_json()

    response = client.get("/api/teamwork-integration/migrated-refs",
                          query_string={"sytix_entity_type": "client"})
    assert response.status_code == 200, response.get_json()
    sytix_ids = response.get_json()["sytix_ids"]
    assert created["created"]["id"] in sytix_ids

    other_type = client.get("/api/teamwork-integration/migrated-refs",
                            query_string={"sytix_entity_type": "project"})
    assert created["created"]["id"] not in other_type.get_json()["sytix_ids"]


def test_migrated_refs_rejects_invalid_entity_type(client):
    response = client.get("/api/teamwork-integration/migrated-refs",
                          query_string={"sytix_entity_type": "invalid"})
    assert response.status_code == 400


# ── US1 (spec 045): matriz de 4 estados ─────────────────────────────────────────────────────

def test_new_mapping_reports_pending_status_and_null_metadata(client, unique_name):
    tw_id = f"m1-{unique_name}"
    _sync_with_payload(client, "company", {"companies": [{"id": tw_id, "name": f"QA47 Estado {unique_name}"}]})
    mapping = _mapping_row(client, "company", tw_id)
    assert mapping["migration_status"] == "pending"
    assert mapping["teamwork_metadata"] is None


# ── US2 (spec 045): acciones masivas ampliadas (migrar/inactivar/reactivar) ────────────────

def test_bulk_create_new_generalized_creates_company_project_and_tasklist(client, unique_name):
    company_tw_id = f"bc1-{unique_name}"
    _sync_with_payload(client, "company", {"companies": [
        {"id": company_tw_id, "name": f"QA47 Bulk Empresa {unique_name}"}]})
    company_mapping = _mapping_row(client, "company", company_tw_id)

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new",
                           json={"mapping_ids": [company_mapping["id"]]})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["created"][0]["mapping_id"] == company_mapping["id"]

    client_get = client.get(f"/api/clients/{body['created'][0]['sytix_id']}")
    assert client_get.status_code == 200


def test_bulk_create_new_generalized_skips_already_linked_and_discarded(client, unique_name):
    tw_id_linked, tw_id_discarded = f"bc2-{unique_name}", f"bc3-{unique_name}"
    _sync_with_payload(client, "company", {"companies": [
        {"id": tw_id_linked, "name": f"QA47 Bulk Vinculada {unique_name}"},
        {"id": tw_id_discarded, "name": f"QA47 Bulk Descartada {unique_name}"},
    ]})
    mapping_linked = _mapping_row(client, "company", tw_id_linked)
    mapping_discarded = _mapping_row(client, "company", tw_id_discarded)
    client.post(f"/api/teamwork-integration/entity-mappings/{mapping_linked['id']}/create-new")
    client.post("/api/teamwork-integration/entity-mappings/bulk-discard",
               json={"mapping_ids": [mapping_discarded["id"]]})

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new",
                           json={"mapping_ids": [mapping_linked["id"], mapping_discarded["id"]]})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["created"] == []
    reasons = {s["mapping_id"]: s["reason"] for s in body["skipped"]}
    assert reasons[mapping_linked["id"]] == "already_linked"
    assert reasons[mapping_discarded["id"]] == "discarded"


def test_bulk_create_new_generalized_person_without_role_id_is_skipped(client, unique_name):
    tw_id = f"bc4-{unique_name}"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id, "firstName": "QA47-Bulk", "lastName": unique_name,
         "email": f"qa47.bulknorole.{unique_name}@sywork.net"}]})
    mapping = _mapping_row(client, "person", tw_id)

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-create-new",
                           json={"mapping_ids": [mapping["id"]]})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["created"] == []
    assert body["skipped"][0] == {"mapping_id": mapping["id"], "reason": "role_id_required"}


def test_bulk_discard_marks_inactive_and_skips_already_linked(client, unique_name):
    tw_id_pending, tw_id_linked = f"bd1-{unique_name}", f"bd2-{unique_name}"
    _sync_with_payload(client, "company", {"companies": [
        {"id": tw_id_pending, "name": f"QA47 Descarte Pendiente {unique_name}"},
        {"id": tw_id_linked, "name": f"QA47 Descarte Vinculada {unique_name}"},
    ]})
    mapping_pending = _mapping_row(client, "company", tw_id_pending)
    mapping_linked = _mapping_row(client, "company", tw_id_linked)
    client.post(f"/api/teamwork-integration/entity-mappings/{mapping_linked['id']}/create-new")

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-discard", json={
        "mapping_ids": [mapping_pending["id"], mapping_linked["id"]],
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["updated"] == [{"mapping_id": mapping_pending["id"]}]
    assert body["skipped"][0] == {"mapping_id": mapping_linked["id"], "reason": "already_linked"}

    refreshed = _mapping_row(client, "company", tw_id_pending)
    assert refreshed["migration_status"] == "inactive"


def test_bulk_reactivate_reverts_to_pending_and_skips_non_discarded(client, unique_name):
    tw_id_discarded, tw_id_pending = f"br1-{unique_name}", f"br2-{unique_name}"
    _sync_with_payload(client, "company", {"companies": [
        {"id": tw_id_discarded, "name": f"QA47 Reactivar {unique_name}"},
        {"id": tw_id_pending, "name": f"QA47 No Descartada {unique_name}"},
    ]})
    mapping_discarded = _mapping_row(client, "company", tw_id_discarded)
    mapping_pending = _mapping_row(client, "company", tw_id_pending)
    client.post("/api/teamwork-integration/entity-mappings/bulk-discard",
               json={"mapping_ids": [mapping_discarded["id"]]})

    response = client.post("/api/teamwork-integration/entity-mappings/bulk-reactivate", json={
        "mapping_ids": [mapping_discarded["id"], mapping_pending["id"]],
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["updated"] == [{"mapping_id": mapping_discarded["id"]}]
    assert body["skipped"][0] == {"mapping_id": mapping_pending["id"], "reason": "not_discarded"}

    refreshed = _mapping_row(client, "company", tw_id_discarded)
    assert refreshed["migration_status"] == "pending"


def test_resync_preserves_discarded_state(client, unique_name):
    tw_id = f"br3-{unique_name}"
    name = f"QA47 Descarte Persistente {unique_name}"
    _sync_with_payload(client, "company", {"companies": [{"id": tw_id, "name": name}]})
    mapping = _mapping_row(client, "company", tw_id)
    client.post("/api/teamwork-integration/entity-mappings/bulk-discard",
               json={"mapping_ids": [mapping["id"]]})

    # spec.md Edge Cases: resincronizar el mismo catálogo no reinicia una fila Inactiva a Pendiente.
    _sync_with_payload(client, "company", {"companies": [{"id": tw_id, "name": name}]})
    refreshed = _mapping_row(client, "company", tw_id)
    assert refreshed["migration_status"] == "inactive"


# ── US3 (spec 045): extracción ampliada de metadatos de la API v3 ──────────────────────────

def test_sync_company_extracts_expanded_metadata_and_omits_missing_fields(client, unique_name):
    tw_id_full, tw_id_empty = f"cm1-{unique_name}", f"cm2-{unique_name}"
    _sync_with_payload(client, "company", {"companies": [
        {"id": tw_id_full, "name": f"QA49 Empresa Completa {unique_name}",
         "country": "AR", "addressOne": "Av. Siempre Viva 742", "city": "Springfield",
         "companyDomain": "arcor.com.ar", "phone": "+54 11 5555-5555"},
        {"id": tw_id_empty, "name": f"QA49 Empresa Vacia {unique_name}"},
    ]})
    full = _mapping_row(client, "company", tw_id_full)
    assert full["teamwork_metadata"]["country"] == "AR"
    assert "Av. Siempre Viva 742" in full["teamwork_metadata"]["address"]
    assert full["teamwork_metadata"]["domain"] == "arcor.com.ar"
    assert full["teamwork_metadata"]["phone"] == "+54 11 5555-5555"

    # Sin ningún campo ampliado informado, el repo guarda `None` en vez de un dict vacío
    # (`metadata or None` en `upsert_from_sync`) — mismo criterio "ausente, no error" (FR-016).
    empty = _mapping_row(client, "company", tw_id_empty)
    assert empty["teamwork_metadata"] is None


def test_sync_person_extracts_job_title_and_timezone(client, unique_name):
    tw_id = f"pm1-{unique_name}"
    _sync_with_payload(client, "person", {"people": [
        {"id": tw_id, "firstName": "QA49", "lastName": unique_name,
         "email": f"qa49.{unique_name}@sywork.net", "jobTitle": "Analista Senior",
         "timezone": "America/Bogota"}]})
    mapping = _mapping_row(client, "person", tw_id)
    assert mapping["teamwork_metadata"]["job_title"] == "Analista Senior"
    assert mapping["teamwork_metadata"]["timezone"] == "America/Bogota"


def test_sync_project_extracts_description_and_archived_status(client, unique_name):
    tw_id_archived, tw_id_active = f"pr1-{unique_name}", f"pr2-{unique_name}"
    _sync_with_payload(client, "project", {"projects": [
        {"id": tw_id_archived, "name": f"QA49 Proyecto Archivado {unique_name}",
         "description": "Proyecto cerrado el año pasado", "status": "archived"},
        {"id": tw_id_active, "name": f"QA49 Proyecto Activo {unique_name}", "isArchived": False},
    ]})
    archived = _mapping_row(client, "project", tw_id_archived)
    assert archived["teamwork_metadata"]["description"] == "Proyecto cerrado el año pasado"
    assert archived["teamwork_metadata"]["status"] == "archived"

    active = _mapping_row(client, "project", tw_id_active)
    assert active["teamwork_metadata"]["status"] == "active"
    assert "description" not in active["teamwork_metadata"]


def test_resync_refreshes_metadata_like_teamwork_name(client, unique_name):
    tw_id = f"pr3-{unique_name}"
    _sync_with_payload(client, "project", {"projects": [
        {"id": tw_id, "name": f"QA49 Proyecto Cambia {unique_name}", "status": "active"}]})
    before = _mapping_row(client, "project", tw_id)
    assert before["teamwork_metadata"]["status"] == "active"

    _sync_with_payload(client, "project", {"projects": [
        {"id": tw_id, "name": f"QA49 Proyecto Cambia {unique_name}", "status": "archived"}]})
    after = _mapping_row(client, "project", tw_id)
    assert after["teamwork_metadata"]["status"] == "archived"


def test_bulk_discard_and_reactivate_empty_mapping_ids_returns_400(client):
    discard_response = client.post("/api/teamwork-integration/entity-mappings/bulk-discard",
                                   json={"mapping_ids": []})
    assert discard_response.status_code == 400
    reactivate_response = client.post("/api/teamwork-integration/entity-mappings/bulk-reactivate",
                                      json={"mapping_ids": []})
    assert reactivate_response.status_code == 400
