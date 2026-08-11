"""Cliente de la API v3 de Teamwork (spec 041, US3) — `requests` mockeado con `unittest.mock`
(sin dependencia nueva de testing). Homologa la misma cantidad de filas que el fixture real de
US1 (2 filas mínimas, Principio VII)."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.infra.importers.teamwork_api_client import fetch_tasks, TeamworkApiError

_ENV = {"TEAMWORK_DOMAIN": "sywork", "TEAMWORK_API_TOKEN": "tk_test"}

_PAYLOAD = {
    "tasks": [
        {"id": 41972833, "name": "Seguimientos", "description": "", "startDate": "2026-08-03",
         "dueDate": "2026-08-31", "estimateMinutes": 0, "projectId": 100, "tasklistId": 200,
         "parentTaskId": None, "assignees": [{"id": 900}], "createdBy": {"id": 901}},
        {"id": 43340224, "name": "Ajustar visualización", "description": "detalle",
         "startDate": "2026-08-03", "dueDate": "2026-08-03", "estimateMinutes": 60,
         "projectId": 100, "tasklistId": 201, "parentTaskId": 42106353,
         "assignees": [{"id": 900}], "createdBy": {"id": 902}},
    ],
    "included": {
        "projects": {"100": {"name": "Andes - Migración a 9.2", "companyId": 50}},
        "companies": {"50": {"name": "Andes Petroleum Company"}},
        "tasklists": {"200": {"name": "Fase de Pruebas"}, "201": {"name": "Soporte CNC"}},
        "users": {"900": {"name": "Jairo Jimenez"}, "901": {"name": "Ferdy Rentería Moreno"},
                 "902": {"name": "Otro Usuario"}},
    },
}


def _mock_response(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status.side_effect = (
        None if status < 400 else requests.HTTPError(f"{status}"))
    return resp


@patch("backend.infra.importers.teamwork_api_client.requests.get")
def test_fetch_tasks_homologates_to_file_parser_shape(mock_get, monkeypatch):
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    mock_get.return_value = _mock_response(_PAYLOAD)

    rows = fetch_tasks()

    assert len(rows) == 2
    first = next(r for r in rows if r["external_id"] == "41972833")
    assert first["company_name"] == "Andes Petroleum Company"
    assert first["project_name"] == "Andes - Migración a 9.2"
    assert first["list_name"] == "Fase de Pruebas"
    assert first["assignee_name"] == "Jairo Jimenez"
    assert first["requester_name"] == "Ferdy Rentería Moreno"
    assert first["parent_external_id"] is None

    second = next(r for r in rows if r["external_id"] == "43340224")
    assert second["parent_external_id"] == "42106353"
    assert second["estimated_minutes"] == 60


@patch("backend.infra.importers.teamwork_api_client.requests.get")
def test_fetch_tasks_raises_teamwork_api_error_on_http_failure(mock_get, monkeypatch):
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    mock_get.return_value = _mock_response({}, status=500)

    with pytest.raises(TeamworkApiError):
        fetch_tasks()


def test_fetch_tasks_requires_configuration(monkeypatch):
    monkeypatch.delenv("TEAMWORK_DOMAIN", raising=False)
    monkeypatch.delenv("TEAMWORK_API_TOKEN", raising=False)
    with pytest.raises(TeamworkApiError):
        fetch_tasks()
