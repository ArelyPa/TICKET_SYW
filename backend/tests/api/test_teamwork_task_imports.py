"""Centro Independiente de Importación de Tareas y Subtareas (spec 045, US4).

Principio VII: lote de prueba de 5-10 filas dummy, `requests` mockeado — sin cuenta real de
Teamwork ni suite completa de `pytest`.
"""
from datetime import date
from unittest.mock import patch, MagicMock

from backend.infra.importers import teamwork_connection_client as twc


def _connect_and_test(client):
    client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "test", "api_token": "tk_ok",
    })
    with patch("backend.api.routes.teamwork_integration.check_connection") as mock:
        mock.return_value = {"status": twc.STATUS_SUCCESS, "message": None}
        client.post("/api/teamwork-integration/test-connection")


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


def _build_hierarchy(client, db_session, unique_name: str) -> dict:
    """Empresa→Proyecto→Lista ya migrados a SYTIX, más una Persona migrada (mismo patrón que
    test_sync_tasks_creates_hierarchy_and_skips_unmapped_project de spec 044)."""
    company_tw_id, project_tw_id, tasklist_tw_id, person_tw_id = (
        f"tico-{unique_name}", f"tipr-{unique_name}", f"titl-{unique_name}", f"tipe-{unique_name}")

    _sync_with_payload(client, "company", {"companies": [
        {"id": company_tw_id, "name": f"QA48 Empresa {unique_name}"}]})
    company_mapping = _mapping_row(client, "company", company_tw_id)
    company_created = client.post(
        f"/api/teamwork-integration/entity-mappings/{company_mapping['id']}/create-new").get_json()

    _sync_with_payload(client, "project", {"projects": [
        {"id": project_tw_id, "name": f"QA48 Proyecto {unique_name}", "company": {"id": company_tw_id}}]})
    project_mapping = _mapping_row(client, "project", project_tw_id)
    project_created = client.post(
        f"/api/teamwork-integration/entity-mappings/{project_mapping['id']}/create-new").get_json()

    _sync_with_payload(client, "tasklist", {"tasklists": [
        {"id": tasklist_tw_id, "name": f"QA48 Lista {unique_name}", "project": {"id": project_tw_id}}]})
    tasklist_mapping = _mapping_row(client, "tasklist", tasklist_tw_id)
    client.post(f"/api/teamwork-integration/entity-mappings/{tasklist_mapping['id']}/create-new")

    _sync_with_payload(client, "person", {"people": [
        {"id": person_tw_id, "firstName": "QA48", "lastName": unique_name,
         "email": f"qa48.{unique_name}@sywork.net"}]})
    person_mapping = _mapping_row(client, "person", person_tw_id)
    from backend.infra.repositories.role_repo import RoleRepository
    resolutor_role = RoleRepository(db_session).get_by_name("Resolutor")
    client.post(f"/api/teamwork-integration/entity-mappings/{person_mapping['id']}/create-new",
               json={"role_id": str(resolutor_role.id)})

    return {
        "company_tw_id": company_tw_id, "project_tw_id": project_tw_id,
        "tasklist_tw_id": tasklist_tw_id, "person_tw_id": person_tw_id,
        "client_sytix_id": company_created["created"]["id"],
        "project_sytix_id": project_created["created"]["id"],
    }


def test_preview_and_confirm_requires_client_and_project_ids(client):
    _connect_and_test(client)
    response = client.post("/api/teamwork-integration/task-imports/preview", json={})
    assert response.status_code == 400

    response2 = client.post("/api/teamwork-integration/task-imports/confirm",
                            json={"client_id": "not-a-uuid"})
    assert response2.status_code == 400


def test_preview_blocked_when_connection_not_tested(client):
    client.put("/api/teamwork-integration/config", json={
        "site_url": "https://sytix.teamwork.com", "environment": "test", "api_token": "tk_ok",
    })
    response = client.post("/api/teamwork-integration/task-imports/preview", json={
        "client_id": "11111111-1111-1111-1111-111111111111",
        "project_ids": ["11111111-1111-1111-1111-111111111111"],
    })
    assert response.status_code == 409


def test_preview_classifies_ready_and_blocked_stricter_than_sync_tasks(client, db_session, unique_name):
    _connect_and_test(client)
    ctx = _build_hierarchy(client, db_session, unique_name)
    today = date.today().isoformat()

    task_ready_tw, task_blocked_assignee_tw, task_blocked_tasklist_tw, task_outside_range_tw = (
        f"tk1-{unique_name}", f"tk2-{unique_name}", f"tk3-{unique_name}", f"tk4-{unique_name}")

    def _tasks_response(*_args, **_kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status.side_effect = None
        resp.json.return_value = {
            "tasks": [
                {"id": task_ready_tw, "name": f"QA48 Lista {unique_name}", "createdAt": today,
                 "tasklistId": ctx["tasklist_tw_id"],
                 "assignees": {"userIds": [ctx["person_tw_id"]]}},
                {"id": task_blocked_assignee_tw, "name": f"QA48 Sin Asignado {unique_name}", "createdAt": today,
                 "tasklistId": ctx["tasklist_tw_id"],
                 "assignees": {"userIds": [f"unmapped-person-{unique_name}"]}},
                {"id": task_blocked_tasklist_tw, "name": f"QA48 Sin Lista {unique_name}", "createdAt": today,
                 "tasklistId": f"unmapped-tasklist-{unique_name}"},
                {"id": task_outside_range_tw, "name": f"QA48 Fuera de Rango {unique_name}",
                 "createdAt": "2020-01-01", "tasklistId": ctx["tasklist_tw_id"]},
            ],
            # El Proyecto de una Tarea real nunca viene en la Tarea misma — se deriva vía
            # `include=tasklists` sidecargado (ver fetch_tasks, corrección post-implementación).
            "included": {"tasklists": {
                ctx["tasklist_tw_id"]: {"projectId": ctx["project_tw_id"]},
                f"unmapped-tasklist-{unique_name}": {"projectId": ctx["project_tw_id"]},
            }},
        }
        return resp

    with patch("backend.infra.importers.teamwork_connection_client.requests.get") as mock_get:
        mock_get.side_effect = _tasks_response
        response = client.post("/api/teamwork-integration/task-imports/preview", json={
            "client_id": ctx["client_sytix_id"],
            "project_ids": [ctx["project_sytix_id"]],
        })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()

    # La tarea fuera del rango de fechas (mes en curso por defecto) queda excluida del todo.
    assert body["summary"]["total"] == 3
    assert body["summary"]["ready"] == 1
    assert body["summary"]["blocked"] == 2

    ready_ids = {r["teamwork_id"] for r in body["ready"]}
    assert ready_ids == {task_ready_tw}

    blocked_by_id = {r["teamwork_id"]: r for r in body["blocked"]}
    assert blocked_by_id[task_blocked_assignee_tw]["block_reason"] == "assignee_not_mapped"
    assert blocked_by_id[task_blocked_assignee_tw]["resolve_link"]["entity_type"] == "person"
    assert blocked_by_id[task_blocked_tasklist_tw]["block_reason"] == "tasklist_not_mapped"
    assert blocked_by_id[task_blocked_tasklist_tw]["resolve_link"]["entity_type"] == "tasklist"


def test_confirm_creates_only_ready_rows_and_is_idempotent(client, db_session, unique_name):
    _connect_and_test(client)
    ctx = _build_hierarchy(client, db_session, unique_name)
    today = date.today().isoformat()

    task_ready_tw, task_subtask_tw, task_blocked_tw = (
        f"tc1-{unique_name}", f"tc2-{unique_name}", f"tc3-{unique_name}")
    parent_title = f"QA48 Confirm Padre {unique_name}"
    child_title = f"QA48 Confirm Hija {unique_name}"

    def _tasks_response(*_args, **_kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status.side_effect = None
        resp.json.return_value = {
            "tasks": [
                {"id": task_ready_tw, "name": parent_title, "createdAt": today,
                 "tasklistId": ctx["tasklist_tw_id"]},
                {"id": task_subtask_tw, "name": child_title, "createdAt": today,
                 "tasklistId": ctx["tasklist_tw_id"], "parentTaskId": task_ready_tw},
                {"id": task_blocked_tw, "name": f"QA48 Bloqueada {unique_name}", "createdAt": today,
                 "tasklistId": f"unmapped-{unique_name}"},
            ],
            # El Proyecto de una Tarea real nunca viene en la Tarea misma — se deriva vía
            # `include=tasklists` sidecargado (ver fetch_tasks, corrección post-implementación).
            "included": {"tasklists": {
                ctx["tasklist_tw_id"]: {"projectId": ctx["project_tw_id"]},
                f"unmapped-{unique_name}": {"projectId": ctx["project_tw_id"]},
            }},
        }
        return resp

    filter_body = {"client_id": ctx["client_sytix_id"], "project_ids": [ctx["project_sytix_id"]]}

    with patch("backend.infra.importers.teamwork_connection_client.requests.get") as mock_get:
        mock_get.side_effect = _tasks_response
        response = client.post("/api/teamwork-integration/task-imports/confirm", json=filter_body)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["summary"]["created"] == 2
    assert body["summary"]["updated"] == 0
    assert body["summary"]["skipped"] == 1
    assert body["skipped"][0]["teamwork_id"] == task_blocked_tw

    child_items = client.get("/api/tickets", query_string={"search": child_title}).get_json()["items"]
    assert len(child_items) == 1
    child_detail = client.get(f"/api/tickets/{child_items[0]['id']}").get_json()
    assert child_detail["external_reference_id"] == task_subtask_tw
    assert child_detail["external_reference_url"].endswith(f"/app/tasks/{task_subtask_tw}")
    assert child_detail["parent"] is not None

    # Re-confirmar el mismo filtro actualiza en vez de duplicar (FR-024).
    with patch("backend.infra.importers.teamwork_connection_client.requests.get") as mock_get2:
        mock_get2.side_effect = _tasks_response
        response2 = client.post("/api/teamwork-integration/task-imports/confirm", json=filter_body)
    assert response2.status_code == 200, response2.get_json()
    body2 = response2.get_json()
    assert body2["summary"]["created"] == 0
    assert body2["summary"]["updated"] == 2
