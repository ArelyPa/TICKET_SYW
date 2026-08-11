"""POST /api/time-imports/preview + /confirm (spec 042, US2/US3).

Ultra-limitado (Principio VII): usa el fixture real de 9 filas
specs/042-integracion-teamwork-tiempos/ejemplo-reporte-tiempos.xlsx, con datos "QA42 *" propios
de este archivo de prueba (find-or-create, mismo criterio que test_ticket_imports.py — este
entorno de Docker no aísla datos entre corridas de test).
"""
import io
import os

import pytest

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "specs", "042-integracion-teamwork-tiempos", "ejemplo-reporte-tiempos.xlsx",
)

_TASK_EXTERNAL_ID = "TWTIME-9001"


def _find_or_create_client(client, name: str) -> dict:
    existing = client.get("/api/clients", query_string={"search": name}).get_json()
    match = next((c for c in existing["items"] if c["name"] == name), None)
    if match:
        return match
    response = client.post("/api/clients", json={"name": name})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _find_or_create_project(client, client_id: str, name: str) -> dict:
    import datetime
    existing = client.get("/api/projects", query_string={"client_id": client_id}).get_json()
    match = next((p for p in existing["items"] if p["name"] == name), None)
    if match:
        return match
    response = client.post("/api/projects", json={
        "name": name, "client_id": client_id, "start_date": datetime.date.today().isoformat(),
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _find_or_create_resource(client, full_name: str, email: str) -> dict:
    existing = client.get("/api/resources", query_string={"search": full_name}).get_json()
    match = next((r for r in existing["items"] if r["full_name"] == full_name), None)
    if match:
        return match
    response = client.post("/api/resources", json={"full_name": full_name, "email": email})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _find_or_create_ticket_with_external_id(app, client, client_id: str, project_id: str,
                                            external_id: str) -> dict:
    from backend.infra.database import get_db
    from backend.infra.repositories.ticket_repo import TicketRepository
    import uuid as _uuid
    with app.app_context():
        existing = TicketRepository(get_db()).get_by_external_reference_id(external_id)
        if existing:
            return {"id": str(existing.id)}
    response = client.post("/api/tickets", json={
        "title": f"Tarea de prueba {external_id}", "description": "Fixture spec 042",
        "client_id": client_id, "project_id": project_id,
        "ticket_type": "incident", "priority": "medium", "severity": "s3",
    })
    assert response.status_code == 201, response.get_json()
    ticket = response.get_json()
    with app.app_context():
        TicketRepository(get_db()).update_fields(
            _uuid.UUID(ticket["id"]), external_reference_id=external_id)
    return ticket


@pytest.fixture()
def qa42_fixtures(app, client):
    c = _find_or_create_client(client, "QA42 Company")
    p = _find_or_create_project(client, c["id"], "QA42 Project")
    r = _find_or_create_resource(client, "QA42 Resolutor", "qa42.resolutor@sywork.net")
    t = _find_or_create_ticket_with_external_id(app, client, c["id"], p["id"], _TASK_EXTERNAL_ID)
    return {"client": c, "project": p, "resource": r, "ticket": t}


def _upload(client, path=FIXTURE_PATH):
    with open(path, "rb") as f:
        content = f.read()
    return client.post(
        "/api/time-imports/preview",
        data={"file": (io.BytesIO(content), "ejemplo-reporte-tiempos.xlsx")},
        content_type="multipart/form-data",
    )


def _row(body, external_time_id, source_row_number=None):
    matches = [r for r in body["rows"] if r["external_time_id"] == external_time_id]
    if source_row_number is not None:
        matches = [r for r in matches if r["source_row_number"] == source_row_number]
    return matches[0]


def test_preview_classifies_9_rows_without_inserting_anything(client, qa42_fixtures):
    response = _upload(client)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["summary"]["total"] == 9
    assert body["summary"]["valid"] == 2
    assert body["summary"]["conflict"] == 3
    assert body["summary"]["error"] == 4


def test_preview_valid_rows_resolve_resource_project_ticket(client, qa42_fixtures):
    body = _upload(client).get_json()
    row = _row(body, "9011", source_row_number=2)
    assert row["status"] == "valid"
    assert row["resolved"]["resource_id"] == qa42_fixtures["resource"]["id"]
    assert row["resolved"]["project_id"] == qa42_fixtures["project"]["id"]
    assert row["resolved"]["ticket_id"] == qa42_fixtures["ticket"]["id"]
    assert row["resolved"]["duration_minutes"] == 90


def test_preview_who_not_found_is_conflict(client, qa42_fixtures):
    body = _upload(client).get_json()
    row = _row(body, "9013")
    assert row["status"] == "conflict"
    assert "who_not_found" in row["issues"]


def test_preview_project_not_found_is_conflict(client, qa42_fixtures):
    body = _upload(client).get_json()
    row = _row(body, "9014")
    assert row["status"] == "conflict"
    assert "project_not_found" in row["issues"]


def test_preview_task_not_found_is_conflict(client, qa42_fixtures):
    body = _upload(client).get_json()
    row = _row(body, "9015")
    assert row["status"] == "conflict"
    assert "task_not_found" in row["issues"]


def test_preview_duplicate_id_in_file_marks_both_rows_as_error(client, qa42_fixtures):
    body = _upload(client).get_json()
    dup_rows = [r for r in body["rows"] if r["external_time_id"] == "9017"]
    assert len(dup_rows) == 2
    assert all(r["status"] == "error" for r in dup_rows)
    assert all("duplicate_external_id_in_file" in r["issues"] for r in dup_rows)


def test_preview_rejects_missing_file(client, qa42_fixtures):
    response = client.post("/api/time-imports/preview", data={}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_confirm_resolves_creates_and_omits_conflicts(client, qa42_fixtures, unique_name):
    body = _upload(client).get_json()
    valid_row = _row(body, "9011", source_row_number=2)
    who_conflict_row = _row(body, "9013")
    project_conflict_row = _row(body, "9014")
    task_conflict_row = _row(body, "9015")

    # Nombre único por corrida: crear el Recurso acá no debe dejar "Colaborador Fantasma QA42"
    # resuelto para las próximas corridas de test_preview_who_not_found_is_conflict (este
    # entorno de Docker no aísla datos entre corridas, mismo criterio que spec 041).
    who_conflict_row["resolved"]["who_name"] = f"Colaborador Fantasma {unique_name}"
    who_conflict_row["action"] = "create"
    who_conflict_row["create_entity_type"] = "resource"
    project_conflict_row["action"] = "omit"
    task_conflict_row["action"] = "create"
    task_conflict_row["create_entity_type"] = "ticket"  # inválido: Tarea nunca se auto-crea

    response = client.post("/api/time-imports/confirm", json={"rows": [
        valid_row, who_conflict_row, project_conflict_row, task_conflict_row,
    ]})
    assert response.status_code == 200, response.get_json()
    result = response.get_json()

    assert result["created_time_entries"] + result["updated_time_entries"] == 2  # valid + who_conflict
    assert result["created_resources"] == 1
    assert result["skipped"] == 1  # project_conflict
    assert len(result["errors"]) == 1  # task_conflict: create_entity_type inválido
    assert result["errors"][0]["source_row_number"] == task_conflict_row["source_row_number"]


def test_confirm_reimporting_same_external_time_id_updates_not_duplicates(client, qa42_fixtures):
    body = _upload(client).get_json()
    row = _row(body, "9012", source_row_number=3)

    first = client.post("/api/time-imports/confirm", json={"rows": [row]}).get_json()
    second = client.post("/api/time-imports/confirm", json={"rows": [row]}).get_json()

    assert first["created_time_entries"] + first["updated_time_entries"] == 1
    assert second["created_time_entries"] == 0
    assert second["updated_time_entries"] == 1


def test_preview_forbidden_for_resolver(client, resolver_auth):
    response = client.post("/api/time-imports/preview", data={}, content_type="multipart/form-data",
                           headers=resolver_auth)
    assert response.status_code == 403
