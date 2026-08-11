"""Cliente de conexión configurable de la integración Teamwork v3 (spec 042) — `requests`
mockeado con `unittest.mock` (sin dependencia nueva de testing). Principio VII: ≤10 registros."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.infra.importers.teamwork_connection_client import (
    test_connection as check_connection, fetch_companies, fetch_projects, fetch_people,
    fetch_tasklists, STATUS_SUCCESS, STATUS_AUTH_ERROR, STATUS_CONNECTION_ERROR,
    TeamworkConnectionError,
)

_SITE_URL = "https://empresa.teamwork.com"
_TOKEN = "tk_test"


def _mock_response(json_data=None, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    resp.raise_for_status.side_effect = (
        None if status < 400 else requests.HTTPError(f"{status}"))
    return resp


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_connection_success(mock_get):
    mock_get.return_value = _mock_response({"projects": []}, status=200)
    result = check_connection(_SITE_URL, _TOKEN)
    assert result["status"] == STATUS_SUCCESS


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_connection_auth_error(mock_get):
    mock_get.return_value = _mock_response(status=401)
    result = check_connection(_SITE_URL, "invalid")
    assert result["status"] == STATUS_AUTH_ERROR


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_connection_network_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("DNS failure")
    result = check_connection(_SITE_URL, _TOKEN)
    assert result["status"] == STATUS_CONNECTION_ERROR


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_fetch_companies_homologates_id_and_name(mock_get):
    mock_get.return_value = _mock_response(
        {"companies": [{"id": 12, "name": "Aris Ming"}, {"id": 13, "name": "Vaxthera"}]})
    rows = fetch_companies(_SITE_URL, _TOKEN)
    assert rows == [{"id": "12", "name": "Aris Ming"}, {"id": "13", "name": "Vaxthera"}]


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_fetch_people_uses_first_last_name_and_captures_email(mock_get):
    mock_get.return_value = _mock_response(
        {"people": [{"id": 556, "firstName": "Juan", "lastName": "Pérez",
                    "email": "juan.perez@aris.com"}]})
    rows = fetch_people(_SITE_URL, _TOKEN)
    assert rows == [{"id": "556", "name": "Juan Pérez", "email": "juan.perez@aris.com"}]


@patch("backend.infra.importers.teamwork_connection_client.requests.get")
def test_fetch_projects_and_tasklists_raise_on_http_error(mock_get):
    mock_get.return_value = _mock_response(status=500)
    with pytest.raises(TeamworkConnectionError):
        fetch_projects(_SITE_URL, _TOKEN)
    with pytest.raises(TeamworkConnectionError):
        fetch_tasklists(_SITE_URL, _TOKEN)
