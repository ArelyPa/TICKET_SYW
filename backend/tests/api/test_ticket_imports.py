"""POST /api/ticket-imports/preview + /confirm (spec 041, US1).

Ultra-limitado (Principio VII): usa el fixture real de 8 filas
specs/041-importacion-tareas-teamwork/ejemplo-teamwork-tasks.xlsx. Ejecutado contra Docker real
(sywork_backend/sywork_db): la mayoría de las filas terminan `needs_review` incluso las de
Andes/Aris — ninguno de los `Assigned to`/`Created by` reales del export ("Jairo Jimenez",
"Ferdy Rentería Moreno", etc.) existe como Recurso/Usuario en el entorno de desarrollo, y Aris
(cliente ya sembrado, spec 026) resuelve Cliente pero no Proyecto porque "SOPORTE ARIS" no
coincide con los proyectos sembrados ("Soporte"/"Evolutivo y Preventa") — exactamente el
comportamiento documentado en spec.md § "Ejemplo de datos de referencia".
"""
import datetime
import io
import os

import pytest

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "specs", "041-importacion-tareas-teamwork", "ejemplo-teamwork-tasks.xlsx",
)


def _find_or_create_client(client, name: str) -> dict:
    existing = client.get("/api/clients", query_string={"search": name}).get_json()
    match = next((c for c in existing["items"] if c["name"] == name), None)
    if match:
        return match
    response = client.post("/api/clients", json={"name": name})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _find_or_create_project(client, client_id: str, name: str) -> dict:
    existing = client.get("/api/projects", query_string={"client_id": client_id}).get_json()
    match = next((p for p in existing["items"] if p["name"] == name), None)
    if match:
        return match
    response = client.post("/api/projects", json={
        "name": name, "client_id": client_id, "start_date": datetime.date.today().isoformat(),
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


@pytest.fixture()
def andes_client_and_project(client):
    """Cliente/Proyecto con el mismo nombre exacto que 3 de las 8 filas del fixture real
    (Andes Petroleum Company / Andes - Migración a 9.2) — para que esas filas resuelvan
    Cliente+Proyecto. `find_or_create` porque este entorno de Docker no aísla datos entre
    corridas de test (mismo patrón que el resto de la suite, sin rollback transaccional)."""
    c = _find_or_create_client(client, "Andes Petroleum Company")
    p = _find_or_create_project(client, c["id"], "Andes - Migración a 9.2")
    return c, p


def _upload(client):
    with open(FIXTURE_PATH, "rb") as f:
        content = f.read()
    return client.post(
        "/api/ticket-imports/preview",
        data={"file": (io.BytesIO(content), "ejemplo-teamwork-tasks.xlsx")},
        content_type="multipart/form-data",
    )


def _rows_by_company(body: dict, company: str) -> list[dict]:
    return [r for r in body["rows"] if r["resolved"]["company_name"] == company]


def test_preview_maps_8_rows_without_inserting_anything(client, andes_client_and_project):
    response = _upload(client)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["summary"]["total"] == 8
    assert body["summary"]["error"] == 0  # sin IDs de Teamwork duplicados en el fixture

    andes_rows = _rows_by_company(body, "Andes Petroleum Company")
    assert len(andes_rows) == 3
    for row in andes_rows:
        assert row["resolved"]["client_id"] is not None
        assert row["resolved"]["project_id"] is not None

    # Aris ya existe como Cliente sembrado (spec 026) pero "SOPORTE ARIS" no coincide con
    # ninguno de sus Proyectos sembrados ("Soporte"/"Evolutivo y Preventa") — resuelve Cliente,
    # no Proyecto.
    aris_rows = _rows_by_company(body, "Aris")
    assert len(aris_rows) == 2
    for row in aris_rows:
        assert row["resolved"]["client_id"] is not None
        assert row["resolved"]["project_id"] is None
        assert "project_not_found" in row["issues"]

    unknown_rows = [r for r in body["rows"]
                    if r["resolved"]["company_name"] not in ("Andes Petroleum Company", "Aris")]
    assert len(unknown_rows) == 3  # Cargill, Congrupo, Consorcio Shushufindi S.A.
    for row in unknown_rows:
        assert row["resolved"]["client_id"] is None
        assert "client_not_found" in row["issues"]


def test_confirm_creates_tasks_for_rows_with_client_resolved(client, andes_client_and_project):
    preview = _upload(client).get_json()

    response = client.post("/api/ticket-imports/confirm", json={"rows": preview["rows"]})
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    # Cliente resuelto en 5 de 8 filas (3 Andes + 2 Aris); las otras 3 no tienen client_id.
    # created+updated (no un `created` fijo) porque el `external_reference_id` es el mismo en
    # cada corrida de test contra el mismo Postgres de Docker (sin rollback entre tests) — una
    # corrida anterior de esta misma suite puede haber creado ya estos Tickets/Tareas, y esta
    # corrida los actualiza en vez de duplicarlos (FR-009), que es justamente lo esperado.
    assert result["created"] + result["updated"] == 5
    assert len(result["errors"]) == 3
    assert {e["reason"] for e in result["errors"]} == {"client_not_found"}

    listing = client.get("/api/tickets", query_string={"search": "Ajustar en las aplicaciones"})
    assert listing.status_code == 200
    items = listing.get_json()["items"]
    assert len(items) == 1
    child_ticket_id = items[0]["id"]
    detail = client.get(f"/api/tickets/{child_ticket_id}").get_json()
    assert detail["external_reference_id"] == "43340224"
    assert detail["parent"] is not None  # vinculado a su padre sintético (42106353)


def test_reimporting_same_file_updates_instead_of_duplicating(client, andes_client_and_project):
    preview = _upload(client).get_json()
    first = client.post("/api/ticket-imports/confirm", json={"rows": preview["rows"]}).get_json()
    assert first["created"] + first["updated"] == 5

    preview2 = _upload(client).get_json()
    second = client.post("/api/ticket-imports/confirm", json={"rows": preview2["rows"]}).get_json()
    assert second["created"] == 0  # ya existen todas por la corrida anterior (misma línea arriba)
    assert second["updated"] == 5

    listing = client.get("/api/tickets", query_string={"search": "Seguimientos"})
    assert len(listing.get_json()["items"]) == 1
