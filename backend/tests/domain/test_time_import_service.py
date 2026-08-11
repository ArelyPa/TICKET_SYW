"""Clasificación pura de filas del reporte de tiempos (spec 042, US2/US3) — sin DB, usa las
mismas 8 filas de ejemplo-reporte-tiempos.csv (Principio VII)."""
from backend.domain.services.time_import_service import (
    classify_row, find_duplicate_external_time_ids, validate_resolution_action,
    STATUS_VALID, STATUS_CONFLICT, STATUS_ERROR,
)

_RESOLVED_OK = {"resource_id": "res-1", "project_id": "proj-1", "ticket_id": "tk-1",
               "duplicate_in_file": False}


def _row(row_number, external_time_id, duration_minutes, description="Trabajo realizado"):
    return {
        "row_number": row_number, "external_time_id": external_time_id,
        "duration_minutes": duration_minutes, "description": description,
        "who_name": "QA42 Resolutor", "company_name": "QA42 Company",
        "project_name": "QA42 Project", "task_reference": "TWTIME-9001",
    }


def test_valid_row_when_everything_resolves():
    row = classify_row(_row(2, "9001", 90), _RESOLVED_OK)
    assert row.status == STATUS_VALID
    assert row.issues == []


def test_who_not_found_is_conflict():
    resolution = {**_RESOLVED_OK, "resource_id": None}
    row = classify_row(_row(3, "9003", 60), resolution)
    assert row.status == STATUS_CONFLICT
    assert row.issues == ["who_not_found"]


def test_project_not_found_is_conflict():
    resolution = {**_RESOLVED_OK, "project_id": None}
    row = classify_row(_row(4, "9004", 60), resolution)
    assert row.status == STATUS_CONFLICT
    assert row.issues == ["project_not_found"]


def test_task_not_found_is_conflict():
    resolution = {**_RESOLVED_OK, "ticket_id": None}
    row = classify_row(_row(5, "9005", 60), resolution)
    assert row.status == STATUS_CONFLICT
    assert row.issues == ["task_not_found"]


def test_description_missing_is_error_even_if_rest_resolves():
    row = classify_row(_row(6, "9006", 60, description=""), _RESOLVED_OK)
    assert row.status == STATUS_ERROR
    assert "description_missing" in row.issues


def test_duplicate_external_id_in_file_is_error():
    resolution = {**_RESOLVED_OK, "duplicate_in_file": True}
    row = classify_row(_row(7, "9001", 60), resolution)
    assert row.status == STATUS_ERROR
    assert "duplicate_external_id_in_file" in row.issues


def test_missing_duration_is_error():
    row = classify_row(_row(8, "9008", None), _RESOLVED_OK)
    assert row.status == STATUS_ERROR
    assert "duration_inconsistent" in row.issues


def test_find_duplicate_external_time_ids_detects_repeated_id():
    raw_rows = [_row(2, "9001", 90), _row(7, "9001", 60), _row(3, "9003", 60)]
    assert find_duplicate_external_time_ids(raw_rows) == {"9001"}


def test_validate_resolution_action_rejects_create_project_or_task():
    assert validate_resolution_action("create", "project") is not None
    assert validate_resolution_action("create", "ticket") is not None


def test_validate_resolution_action_accepts_create_resource_or_client():
    assert validate_resolution_action("create", "resource") is None
    assert validate_resolution_action("create", "client") is None


def test_validate_resolution_action_accepts_resolve_and_omit():
    assert validate_resolution_action("resolve", None) is None
    assert validate_resolution_action("omit", None) is None
