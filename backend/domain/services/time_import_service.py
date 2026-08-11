"""Clasificación pura de filas del reporte mensual de tiempos de Teamwork (spec 042, Capa 1 —
sin imports de Flask/SQLAlchemy/`openpyxl`/`requests`). Mismo patrón que
`teamwork_import_service.classify_row` de spec 041: la Capa 3 resuelve cada campo contra la base
de datos y le pasa a este servicio un `dict` de resolución ya armado; aquí solo se decide
`status`/`issues`. Ver data-model.md § "Clasificación de una fila del reporte de tiempos"."""
from dataclasses import dataclass, field

STATUS_VALID = "valid"
STATUS_CONFLICT = "conflict"
STATUS_ERROR = "error"

_ERROR_ISSUES = {"duplicate_external_id_in_file", "duration_inconsistent", "description_missing"}
_CONFLICT_ISSUES = {"who_not_found", "project_not_found", "task_not_found"}

CREATABLE_ENTITY_TYPES = {"resource", "client"}


@dataclass
class TimeImportRow:
    source_row_number: int
    external_time_id: str | None
    status: str
    issues: list[str] = field(default_factory=list)
    resolved: dict = field(default_factory=dict)


def find_duplicate_external_time_ids(raw_rows: list[dict]) -> set[str]:
    """`ID` de Teamwork repetido más de una vez dentro del mismo archivo (Edge Cases)."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in raw_rows:
        eid = row.get("external_time_id")
        if not eid:
            continue
        if eid in seen:
            duplicates.add(eid)
        seen.add(eid)
    return duplicates


def classify_row(raw_row: dict, resolution: dict) -> TimeImportRow:
    """`resolution` trae `resource_id`/`project_id`/`ticket_id` (None si no se resolvió) y
    `duplicate_in_file` (bool), armados por la Capa 3."""
    issues: list[str] = []
    if resolution.get("duplicate_in_file"):
        issues.append("duplicate_external_id_in_file")
    if raw_row.get("duration_minutes") is None:
        issues.append("duration_inconsistent")
    if not (raw_row.get("description") or "").strip():
        issues.append("description_missing")
    if resolution.get("resource_id") is None:
        issues.append("who_not_found")
    if resolution.get("project_id") is None:
        issues.append("project_not_found")
    if resolution.get("ticket_id") is None:
        issues.append("task_not_found")

    if any(i in _ERROR_ISSUES for i in issues):
        status = STATUS_ERROR
    elif any(i in _CONFLICT_ISSUES for i in issues):
        status = STATUS_CONFLICT
    else:
        status = STATUS_VALID

    return TimeImportRow(
        source_row_number=raw_row["row_number"],
        external_time_id=raw_row.get("external_time_id"),
        status=status,
        issues=issues,
        resolved={
            "who_name": raw_row.get("who_name"),
            "company_name": raw_row.get("company_name"),
            "project_name": raw_row.get("project_name"),
            "task_reference": raw_row.get("task_reference"),
            "description": raw_row.get("description") or "",
            "started_at": raw_row.get("started_at"),
            "ended_at": raw_row.get("ended_at"),
            "duration_minutes": raw_row.get("duration_minutes"),
            **resolution,
        },
    )


def validate_resolution_action(action: str | None, create_entity_type: str | None) -> str | None:
    """FR-011/data-model.md: `action="create"` solo admite Recurso/Cliente — Proyecto y
    Tarea/Ticket nunca se crean automáticamente (research.md Decisión 4). Devuelve un mensaje de
    error si la acción es inválida, o `None` si es válida."""
    if action == "create" and create_entity_type not in CREATABLE_ENTITY_TYPES:
        return ("create_entity_type debe ser 'resource' o 'client' — Proyecto y Tarea/Ticket "
               "nunca se crean automáticamente")
    if action not in {None, "resolve", "create", "omit"}:
        return f"action inválida: {action}"
    return None
