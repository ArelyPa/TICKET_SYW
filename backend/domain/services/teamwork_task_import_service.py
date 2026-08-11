"""Filtro por fecha y clasificación estricta ready/blocked para el Centro Independiente de
Importación de Tareas (spec 045, US4, Capa 1 — sin imports de Flask/SQLAlchemy/`requests`).
Reutiliza (importa, no modifica) `classify_task`/`TeamworkTaskRow` de
`teamwork_task_migration_service.py` (spec 044) para el chequeo base de Proyecto/Lista y agrega el
motivo `assignee_not_mapped` — este módulo es deliberadamente más estricto que `/sync/tasks`, que
crea la Tarea sin asignar cuando el asignado no resuelve (research.md Decisión 7)."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from backend.domain.services.teamwork_task_migration_service import (
    classify_task, SKIP_PROJECT_NOT_MAPPED, SKIP_TASKLIST_NOT_MAPPED,
)

STATUS_READY = "ready"
STATUS_BLOCKED = "blocked"

BLOCK_ASSIGNEE_NOT_MAPPED = "assignee_not_mapped"

_BLOCK_REASON_LABELS = {
    SKIP_PROJECT_NOT_MAPPED: "Proyecto sin homologar en SYTIX",
    SKIP_TASKLIST_NOT_MAPPED: "Lista de Tareas sin homologar en SYTIX",
    BLOCK_ASSIGNEE_NOT_MAPPED: "Usuario asignado sin homologar en SYTIX",
}

_RESOLVE_LINK_ENTITY_TYPE = {
    SKIP_PROJECT_NOT_MAPPED: "project",
    SKIP_TASKLIST_NOT_MAPPED: "tasklist",
    BLOCK_ASSIGNEE_NOT_MAPPED: "person",
}

_RESOLVE_LINK_RAW_KEY = {
    SKIP_PROJECT_NOT_MAPPED: "project_id",
    SKIP_TASKLIST_NOT_MAPPED: "tasklist_id",
    BLOCK_ASSIGNEE_NOT_MAPPED: "assignee_id",
}


@dataclass
class TaskImportDiagnosticRow:
    teamwork_id: str
    name: str
    is_subtask: bool
    status: str
    block_reason: Optional[str]
    block_reason_label: Optional[str]
    resolve_link: Optional[dict]
    resolved: dict


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def filter_tasks_by_date(raw_tasks: list[dict], date_from: Optional[date],
                         date_to: Optional[date]) -> list[dict]:
    """FR-018: filtra por `due_date` cuando está presente (más confiable para tareas con
    vencimiento definido); si no, por `created_at`. Una tarea sin ninguna de las dos fechas se
    excluye si hay rango pedido (no hay forma de saber si cae dentro). Sin rango, no filtra."""
    if not date_from and not date_to:
        return raw_tasks
    result = []
    for raw in raw_tasks:
        task_date = _parse_date(raw.get("due_date")) or _parse_date(raw.get("created_at"))
        if task_date is None:
            continue
        if date_from and task_date < date_from:
            continue
        if date_to and task_date > date_to:
            continue
        result.append(raw)
    return result


def classify_task_for_import(raw: dict, resolution: dict) -> TaskImportDiagnosticRow:
    """FR-020/021 (spec.md US4, AC3): a diferencia de `classify_task` (usada sin cambios por
    `/sync/tasks`, que no bloquea por asignado sin homologar), acá un Usuario asignado sin
    homologar SÍ bloquea la fila — el propio spec de esta feature exige tratarlo como advertencia
    bloqueante con enlace de resolución, no como Tarea creada sin asignar."""
    base = classify_task(raw, resolution)
    reason = base.skip_reason
    if (reason is None and raw.get("assignee_id") is not None
            and resolution.get("assignee_resource_id") is None):
        reason = BLOCK_ASSIGNEE_NOT_MAPPED

    status = STATUS_BLOCKED if reason else STATUS_READY
    resolve_link = None
    if reason:
        resolve_link = {
            "entity_type": _RESOLVE_LINK_ENTITY_TYPE[reason],
            "teamwork_id": raw.get(_RESOLVE_LINK_RAW_KEY[reason]),
        }

    return TaskImportDiagnosticRow(
        teamwork_id=base.teamwork_id,
        name=base.name,
        is_subtask=base.parent_task_teamwork_id is not None,
        status=status,
        block_reason=reason,
        block_reason_label=_BLOCK_REASON_LABELS.get(reason) if reason else None,
        resolve_link=resolve_link,
        resolved=base.resolved,
    )
