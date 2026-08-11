"""Mapeo/clasificación puro de importación de Teamwork (spec 041) — sin DB. Usa las 8 filas
reales de specs/041-importacion-tareas-teamwork/ejemplo-teamwork-tasks.csv (Principio VII)."""
import os

from backend.infra.importers.teamwork_file_parser import parse_file
from backend.domain.services import teamwork_import_service as svc

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "specs", "041-importacion-tareas-teamwork", "ejemplo-teamwork-tasks.csv",
)


def _load_fixture_rows() -> list[dict]:
    with open(FIXTURE_PATH, "rb") as f:
        content = f.read()
    return parse_file("ejemplo-teamwork-tasks.csv", content)


def test_fixture_has_8_rows_with_expected_ids():
    rows = _load_fixture_rows()
    assert len(rows) == 8
    ids = {r["external_id"] for r in rows}
    assert ids == {"42106353", "43340224", "43266714", "41972833",
                    "42846282", "43012023", "43294455", "43220227"}


def test_convert_minutes_to_hours():
    assert svc.convert_minutes_to_hours(180) == 3.0
    assert svc.convert_minutes_to_hours(0) == 0.0
    assert svc.convert_minutes_to_hours(None) == 0.0


def test_build_external_reference_url():
    assert svc.build_external_reference_url("sywork", "41972833") == (
        "https://sywork.teamwork.com/app/tasks/41972833")


def test_no_duplicate_ids_in_fixture():
    rows = _load_fixture_rows()
    assert svc.find_duplicate_external_ids(rows) == set()


def test_duplicate_external_id_detected_and_marked_error():
    rows = [
        {"row_number": 2, "external_id": "1", "title": "a", "description": "",
         "parent_external_id": None},
        {"row_number": 3, "external_id": "1", "title": "b", "description": "",
         "parent_external_id": None},
    ]
    duplicates = svc.find_duplicate_external_ids(rows)
    assert duplicates == {"1"}
    row = svc.classify_row(rows[0], {
        "client_id": None, "project_id": None, "assignee_resource_id": None,
        "requester_created_by_user_id": None, "requester_client_contact_id": None,
        "duplicate_in_file": True, "parent_resolved_external_id": None,
        "existing_ticket_id": None,
    })
    assert row.status == svc.STATUS_ERROR
    assert "duplicate_external_id_in_file" in row.issues


def test_resolve_parent_link_within_batch():
    """El par 42106353 (padre sintético) -> 43340224 (hijo real) convive en el mismo lote."""
    rows = _load_fixture_rows()
    by_id = {r["external_id"]: r for r in rows}
    child = by_id["43340224"]
    assert child["parent_external_id"] == "42106353"
    resolved = svc.resolve_parent_link(child["parent_external_id"], is_resolvable=True)
    assert resolved == "42106353"


def test_resolve_parent_link_orphan_not_blocking():
    """43266714 referencia a 43266697, ausente del lote — caso dominante confirmado con datos
    reales (ver research.md Decisión sobre el export de Teamwork)."""
    rows = _load_fixture_rows()
    by_id = {r["external_id"]: r for r in rows}
    orphan = by_id["43266714"]
    assert orphan["parent_external_id"] == "43266697"
    resolved = svc.resolve_parent_link(orphan["parent_external_id"], is_resolvable=False)
    assert resolved is None
    row = svc.classify_row(orphan, {
        "client_id": "aris-id", "project_id": None, "assignee_resource_id": None,
        "requester_created_by_user_id": None, "requester_client_contact_id": None,
        "duplicate_in_file": False, "parent_resolved_external_id": None,
        "existing_ticket_id": None,
    })
    # huérfano de padre no es bloqueante por sí solo (solo informativo)
    assert "parent_not_found_in_batch" in row.issues
    # pero sigue needs_review por project_not_found (Aris con Proyecto que no calza)
    assert row.status == svc.STATUS_NEEDS_REVIEW


def test_classify_row_ready_when_fully_resolved():
    rows = _load_fixture_rows()
    raw = next(r for r in rows if r["external_id"] == "41972833")
    row = svc.classify_row(raw, {
        "client_id": "c1", "project_id": "p1", "assignee_resource_id": "r1",
        "requester_created_by_user_id": "u1", "requester_client_contact_id": None,
        "duplicate_in_file": False, "parent_resolved_external_id": None,
        "existing_ticket_id": None,
    })
    assert row.status == svc.STATUS_READY
    assert row.issues == []
    assert row.resolved["estimated_hours"] == 0.0  # esta fila real trae Time estimate=0
