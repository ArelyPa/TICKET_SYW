"""Mapeo y clasificación de filas de importación de Teamwork (spec 041, Capa 1 — sin imports de
Flask/SQLAlchemy/`openpyxl`/`requests`). La resolución contra la base de datos (Cliente, Proyecto,
Recursos, Usuarios/cliente, `external_reference_id` ya existentes) la hace la Capa 3
(`backend/api/routes/ticket_imports.py`) fila por fila y se le pasa a este servicio ya resuelta —
mismo patrón que `AssignmentService.validate`, que tampoco consulta repositorios directamente.
"""
from dataclasses import dataclass, field

STATUS_READY = "ready"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_ERROR = "error"

# Issues que fuerzan needs_review/error; el resto (ej. parent_not_found_in_batch) son solo
# informativos y no bloquean la importación (FR-006/Edge Cases: la fila se importa igual como
# Tarea de primer nivel).
_BLOCKING_ISSUES = {
    "duplicate_external_id_in_file",
    "client_not_found",
    "project_not_found",
    "assignee_not_found",
    "creator_not_found",
}
_ERROR_ISSUES = {"duplicate_external_id_in_file"}


@dataclass
class ImportRow:
    source_row_number: int
    external_id: str | None
    status: str
    issues: list[str] = field(default_factory=list)
    resolved: dict = field(default_factory=dict)


def convert_minutes_to_hours(minutes: int | None) -> float:
    """FR-008: `Time estimate` (minutos) -> Tiempo Estimado (horas)."""
    return round((minutes or 0) / 60, 2)


def build_external_reference_url(domain: str, external_id: str) -> str:
    """FR-006 spec.md: enlace directo a la tarea original en Teamwork."""
    return f"https://{domain}.teamwork.com/app/tasks/{external_id}"


def find_duplicate_external_ids(raw_rows: list[dict]) -> set[str]:
    """`ID` de Teamwork repetido más de una vez dentro del mismo archivo/lote (Edge Cases)."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in raw_rows:
        eid = row.get("external_id")
        if not eid:
            continue
        if eid in seen:
            duplicates.add(eid)
        seen.add(eid)
    return duplicates


def resolve_parent_link(parent_external_id: str | None, is_resolvable: bool) -> str | None:
    """FR-007: el padre se busca primero en el propio lote y luego entre lo ya importado antes
    (ambos chequeos los hace la Capa 3, que sabe consultar el lote y la base de datos; aquí solo
    se aplica la regla). Devuelve `parent_external_id` si se pudo resolver, o `None` si queda
    huérfano (no bloquea — ver Edge Cases, es el caso dominante confirmado con datos reales de
    Teamwork: en el export real ninguna de las 71 filas con `Parent task ID` tenía a su padre
    incluido en el mismo archivo)."""
    if not parent_external_id or not is_resolvable:
        return None
    return parent_external_id


def classify_row(raw_row: dict, resolution: dict) -> ImportRow:
    """Combina la fila cruda (`teamwork_file_parser`/`teamwork_api_client`) con su resolución
    contra SYTIX (armada por la Capa 3) y decide `status`/`issues` finales."""
    issues: list[str] = []
    if resolution.get("duplicate_in_file"):
        issues.append("duplicate_external_id_in_file")
    if resolution.get("client_id") is None:
        issues.append("client_not_found")
    elif resolution.get("project_id") is None:
        issues.append("project_not_found")
    if resolution.get("assignee_resource_id") is None:
        issues.append("assignee_not_found")
    if not resolution.get("requester_created_by_user_id") and not resolution.get("requester_client_contact_id"):
        issues.append("creator_not_found")
    if raw_row.get("parent_external_id") and not resolution.get("parent_resolved_external_id"):
        issues.append("parent_not_found_in_batch")

    if any(i in _ERROR_ISSUES for i in issues):
        status = STATUS_ERROR
    elif any(i in _BLOCKING_ISSUES for i in issues):
        status = STATUS_NEEDS_REVIEW
    else:
        status = STATUS_READY

    return ImportRow(
        source_row_number=raw_row["row_number"],
        external_id=raw_row.get("external_id"),
        status=status,
        issues=issues,
        resolved={
            "title": raw_row.get("title"),
            "description": raw_row.get("description") or "",
            "start_date": raw_row.get("start_date"),
            "due_date": raw_row.get("due_date"),
            "estimated_minutes": raw_row.get("estimated_minutes") or 0,
            "estimated_hours": convert_minutes_to_hours(raw_row.get("estimated_minutes")),
            "company_name": raw_row.get("company_name"),
            "project_name": raw_row.get("project_name"),
            "list_name": raw_row.get("list_name"),
            "assignee_name": raw_row.get("assignee_name"),
            "requester_name": raw_row.get("requester_name"),
            "parent_external_id": resolution.get("parent_resolved_external_id"),
            **resolution,
        },
    )
