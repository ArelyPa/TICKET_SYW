"""Parser de reporte de tiempos (spec 042, US2) — usa el fixture de 9 filas
specs/042-integracion-teamwork-tiempos/ejemplo-reporte-tiempos.csv/.xlsx (Principio VII)."""
import os

import pytest

from backend.infra.importers.teamwork_time_file_parser import (
    parse_file, TeamworkTimeFileParseError,
)

_FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "specs", "042-integracion-teamwork-tiempos")
_CSV_PATH = os.path.join(_FIXTURE_DIR, "ejemplo-reporte-tiempos.csv")
_XLSX_PATH = os.path.join(_FIXTURE_DIR, "ejemplo-reporte-tiempos.xlsx")


def _read(path):
    with open(path, "rb") as f:
        return f.read()


@pytest.mark.parametrize("path", [_CSV_PATH, _XLSX_PATH])
def test_parse_file_returns_9_rows(path):
    rows = parse_file(os.path.basename(path), _read(path))
    assert len(rows) == 9


def test_decimal_hours_takes_priority_over_hours_minutes():
    rows = parse_file("ejemplo-reporte-tiempos.csv", _read(_CSV_PATH))
    row1 = next(r for r in rows if r["external_time_id"] == "9011" and r["row_number"] == 2)
    assert row1["duration_minutes"] == 90  # 1.5h


def test_hours_and_minutes_used_when_no_decimal_hours():
    rows = parse_file("ejemplo-reporte-tiempos.csv", _read(_CSV_PATH))
    row2 = next(r for r in rows if r["row_number"] == 3)
    assert row2["duration_minutes"] == 45


def test_missing_duration_columns_resolve_to_none():
    rows = parse_file("ejemplo-reporte-tiempos.csv", _read(_CSV_PATH))
    last_row = next(r for r in rows if r["row_number"] == 10)
    assert last_row["duration_minutes"] is None


def test_description_and_who_and_task_reference_extracted():
    rows = parse_file("ejemplo-reporte-tiempos.csv", _read(_CSV_PATH))
    row1 = next(r for r in rows if r["row_number"] == 2)
    assert row1["who_name"] == "QA42 Resolutor"
    assert row1["company_name"] == "QA42 Company"
    assert row1["project_name"] == "QA42 Project"
    assert row1["task_reference"] == "TWTIME-9001"
    assert row1["description"] == "Ajuste de reporte mensual"


def test_blank_description_becomes_empty_string():
    rows = parse_file("ejemplo-reporte-tiempos.csv", _read(_CSV_PATH))
    row6 = next(r for r in rows if r["row_number"] == 7)
    assert row6["description"] == ""


def test_missing_required_columns_raises():
    content = b"ID,Description\n1,x\n"
    with pytest.raises(TeamworkTimeFileParseError):
        parse_file("bad.csv", content)


def test_unsupported_extension_raises():
    with pytest.raises(TeamworkTimeFileParseError):
        parse_file("report.txt", b"x")
