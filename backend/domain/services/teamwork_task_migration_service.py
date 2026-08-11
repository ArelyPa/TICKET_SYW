"""Clasificación de Tareas/Subtareas de Teamwork para migración masiva (spec 044, Capa 1 — sin
imports de Flask/SQLAlchemy/`requests`). La resolución contra `teamwork_entity_mappings`/
Proyecto/Lista/Recurso ya homologados la hace la Capa 3 (`backend/api/routes/teamwork_integration.py`)
fila por fila y se le pasa a este servicio ya resuelta — mismo patrón que
`teamwork_import_service.classify_row` (spec 041), sin reutilizar ni modificar ese módulo
(research.md Decisión 8)."""
from dataclasses import dataclass, field

STATUS_READY = "ready"
STATUS_SKIPPED = "skipped"

SKIP_PROJECT_NOT_MAPPED = "project_not_mapped"
SKIP_TASKLIST_NOT_MAPPED = "tasklist_not_mapped"


@dataclass
class TeamworkTaskRow:
    teamwork_id: str
    name: str
    description: str | None
    project_teamwork_id: str | None
    tasklist_teamwork_id: str | None
    parent_task_teamwork_id: str | None
    assignee_teamwork_id: str | None
    status: str
    skip_reason: str | None
    resolved: dict = field(default_factory=dict)


def classify_task(raw: dict, resolution: dict) -> TeamworkTaskRow:
    """`raw`: fila cruda de `fetch_tasks` (Capa 2) — `{id, name, description, project_id,
    tasklist_id, parent_task_id, assignee_id}`. `resolution`:
    `{client_id, project_id, list_id, assignee_resource_id}` ya resuelto por la Capa 3 contra
    `teamwork_entity_mappings`. FR-016: sin Proyecto o sin Lista resueltos, la fila se omite —
    nunca se crea un Ticket huérfano. Un `assignee` sin resolver no bloquea (mismo criterio ya
    validado en spec 041 — la Tarea se crea sin asignar)."""
    skip_reason = None
    if resolution.get("project_id") is None:
        skip_reason = SKIP_PROJECT_NOT_MAPPED
    elif resolution.get("list_id") is None:
        skip_reason = SKIP_TASKLIST_NOT_MAPPED
    status = STATUS_SKIPPED if skip_reason else STATUS_READY

    return TeamworkTaskRow(
        teamwork_id=raw["id"],
        name=raw.get("name") or "(sin título)",
        description=raw.get("description"),
        project_teamwork_id=raw.get("project_id"),
        tasklist_teamwork_id=raw.get("tasklist_id"),
        parent_task_teamwork_id=raw.get("parent_task_id"),
        assignee_teamwork_id=raw.get("assignee_id"),
        status=status,
        skip_reason=skip_reason,
        resolved=resolution,
    )
