"""Centro Independiente de Importación de Tareas y Subtareas (spec 045, US4) — namespace nuevo,
hermano de `teamwork_integration` (mismo permiso `teamwork_integration:operate`, sin permiso
nuevo). A diferencia de `POST /teamwork-integration/sync/tasks` (spec 044, sin filtros ni
prevalidación, migra el universo completo de tareas del sitio), este módulo acota la consulta a
Teamwork por Cliente/Proyecto(s)/fecha/Lista de Tareas y expone un paso de prevalidación
diagnóstica (`preview`) antes de ejecutar la importación por lotes (`confirm`) — no reemplaza ni
modifica `/sync/tasks` (research.md Decisión 7). Reutiliza sin modificar
`teamwork_task_migration_service.classify_task` (spec 044) y `TicketRepository.upsert_from_import`
(spec 041)."""
import uuid
from datetime import date, datetime, timedelta

from flask import request, g
from flask_restx import Namespace, Resource, fields

from backend.api.middleware.rbac import require_permission
from backend.api.routes._shared import error_model, server_error, parse_uuid
from backend.infra.database import get_db
from backend.infra.importers import teamwork_connection_client as twc
from backend.infra.importers.teamwork_connection_client import TeamworkConnectionError
from backend.infra.repositories.teamwork_integration_repo import (
    TeamworkIntegrationConfigRepository, EntityMappingRepository,
)
from backend.infra.repositories.project_repo import ProjectRepository
from backend.infra.repositories.ticket_repo import TicketRepository
from backend.infra.repositories.catalog_repo import CatalogRepository
from backend.domain.services import teamwork_task_import_service as task_import_svc

ns = Namespace("teamwork_task_imports",
               description="Importador de Tareas y Subtareas por filtros (Teamwork API v3)",
               path="/api/teamwork-integration/task-imports")

_error = error_model(ns, "TeamworkTaskImportError")

_filter_input = ns.model("TeamworkTaskImportFilter", {
    "client_id": fields.String(required=True),
    "project_ids": fields.List(fields.String(), required=True),
    "date_from": fields.String(allow_null=True, description="YYYY-MM-DD, default: primer día del mes en curso"),
    "date_to": fields.String(allow_null=True, description="YYYY-MM-DD, default: último día del mes en curso"),
    "task_list_teamwork_id": fields.String(allow_null=True),
})

_diagnostic_row_out = ns.model("TeamworkTaskImportDiagnosticRow", {
    "teamwork_id": fields.String(),
    "name": fields.String(),
    "is_subtask": fields.Boolean(),
    "block_reason": fields.String(allow_null=True),
    "block_reason_label": fields.String(allow_null=True),
    "resolve_link": fields.Raw(allow_null=True),
})

_preview_out = ns.model("TeamworkTaskImportPreview", {
    "summary": fields.Raw(),
    "ready": fields.List(fields.Nested(_diagnostic_row_out)),
    "blocked": fields.List(fields.Nested(_diagnostic_row_out)),
})

_confirm_skipped_out = ns.model("TeamworkTaskImportConfirmSkipped", {
    "teamwork_id": fields.String(),
    "block_reason": fields.String(),
})

_confirm_out = ns.model("TeamworkTaskImportConfirmResult", {
    "summary": fields.Raw(),
    "skipped": fields.List(fields.Nested(_confirm_skipped_out)),
})


def _parse_filter_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _default_month_range() -> tuple[date, date]:
    today = date.today()
    start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    return start, next_month - timedelta(days=1)


def _validate_filter(data: dict):
    """Devuelve `(parsed, None)` con `parsed = (project_ids, date_from, date_to,
    task_list_teamwork_id)`, o `(None, error_response)` — `client_id` en sí solo se valida por
    formato (FR-018), no se re-usa para la resolución (los Proyectos ya la implican)."""
    client_id = parse_uuid(data.get("client_id") or "")
    project_ids_raw = data.get("project_ids") or []
    if not client_id or not project_ids_raw:
        return None, ({"error": "validation_error",
                       "message": "'client_id' y al menos un 'project_ids' son requeridos"}, 400)
    project_ids = []
    for raw_id in project_ids_raw:
        parsed_id = parse_uuid(raw_id)
        if not parsed_id:
            return None, ({"error": "validation_error", "message": f"project_id inválido: {raw_id}"}, 400)
        project_ids.append(parsed_id)
    default_from, default_to = _default_month_range()
    date_from = _parse_filter_date(data.get("date_from")) or default_from
    date_to = _parse_filter_date(data.get("date_to")) or default_to
    task_list_teamwork_id = data.get("task_list_teamwork_id") or None
    return (project_ids, date_from, date_to, task_list_teamwork_id), None


def _diagnose(db, config, project_ids: list[uuid.UUID], date_from: date, date_to: date,
             task_list_teamwork_id: str | None) -> list[tuple[dict, "task_import_svc.TaskImportDiagnosticRow"]]:
    """Resuelve el filtro contra Teamwork y clasifica cada fila (Capa 3, glue de resolución —
    reutiliza `classify_task_for_import`, Capa 1, sin duplicar su lógica de negocio)."""
    mapping_repo = EntityMappingRepository(db)
    project_repo = ProjectRepository(db)

    project_teamwork_ids = set(mapping_repo.get_teamwork_ids_for_sytix("project", project_ids).values())

    raw_tasks = twc.fetch_tasks(config.site_url, config.api_token)
    raw_tasks = [t for t in raw_tasks if t.get("project_id") in project_teamwork_ids]
    if task_list_teamwork_id:
        raw_tasks = [t for t in raw_tasks if t.get("tasklist_id") == task_list_teamwork_id]
    raw_tasks = task_import_svc.filter_tasks_by_date(raw_tasks, date_from, date_to)

    rows = []
    for raw in raw_tasks:
        project_mapping = (mapping_repo.get_by_teamwork_key("project", raw["project_id"])
                           if raw.get("project_id") else None)
        project_sytix_id = (project_mapping.sytix_id
                            if project_mapping and project_mapping.sytix_id else None)
        client_id = None
        if project_sytix_id:
            project = project_repo.get_by_id(project_sytix_id)
            client_id = project.client_id if project else None
        tasklist_mapping = (mapping_repo.get_by_teamwork_key("tasklist", raw["tasklist_id"])
                            if raw.get("tasklist_id") else None)
        list_sytix_id = (tasklist_mapping.sytix_id
                         if tasklist_mapping and tasklist_mapping.sytix_id else None)
        assignee_mapping = (mapping_repo.get_by_teamwork_key("person", raw["assignee_id"])
                            if raw.get("assignee_id") else None)
        assignee_resource_id = (assignee_mapping.sytix_id
                                if assignee_mapping and assignee_mapping.sytix_id else None)
        resolution = {"client_id": client_id, "project_id": project_sytix_id,
                     "list_id": list_sytix_id, "assignee_resource_id": assignee_resource_id}
        rows.append((raw, task_import_svc.classify_task_for_import(raw, resolution)))
    return rows


def _row_out(row) -> dict:
    return {
        "teamwork_id": row.teamwork_id, "name": row.name, "is_subtask": row.is_subtask,
        "block_reason": row.block_reason, "block_reason_label": row.block_reason_label,
        "resolve_link": row.resolve_link,
    }


@ns.route("/preview")
class TeamworkTaskImportPreview(Resource):
    @ns.doc("teamwork_task_import_preview")
    @ns.expect(_filter_input, validate=False)
    @ns.response(200, "Diagnóstico de la importación (sin escritura)", _preview_out)
    @ns.response(400, "client_id/project_ids faltante o inválido", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(409, "La conexión no ha sido probada con éxito", _error)
    @ns.response(502, "La API v3 de Teamwork no respondió", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        data = request.get_json(silent=True) or {}
        parsed, error = _validate_filter(data)
        if error:
            return error
        project_ids, date_from, date_to, task_list_teamwork_id = parsed
        try:
            db = get_db()
            config = TeamworkIntegrationConfigRepository(db).get(include_token=True)
            if not config or config.last_test_status != twc.STATUS_SUCCESS:
                return {"error": "connection_not_tested",
                        "message": "Probá la conexión con éxito antes de importar"}, 409
            try:
                rows = _diagnose(db, config, project_ids, date_from, date_to, task_list_teamwork_id)
            except TeamworkConnectionError as e:
                return {"error": "teamwork_api_error", "message": str(e)}, 502
            ready = [r for _raw, r in rows if r.status == task_import_svc.STATUS_READY]
            blocked = [r for _raw, r in rows if r.status == task_import_svc.STATUS_BLOCKED]
            return {
                "summary": {"total": len(rows), "ready": len(ready), "blocked": len(blocked)},
                "ready": [_row_out(r) for r in ready],
                "blocked": [_row_out(r) for r in blocked],
            }, 200
        except Exception:
            return server_error()


@ns.route("/confirm")
class TeamworkTaskImportConfirm(Resource):
    @ns.doc("teamwork_task_import_confirm")
    @ns.expect(_filter_input, validate=False)
    @ns.response(200, "Tareas/Subtareas importadas por lotes", _confirm_out)
    @ns.response(400, "client_id/project_ids faltante o inválido", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(409, "La conexión no ha sido probada con éxito", _error)
    @ns.response(502, "La API v3 de Teamwork no respondió", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        data = request.get_json(silent=True) or {}
        parsed, error = _validate_filter(data)
        if error:
            return error
        project_ids, date_from, date_to, task_list_teamwork_id = parsed
        try:
            db = get_db()
            config = TeamworkIntegrationConfigRepository(db).get(include_token=True)
            if not config or config.last_test_status != twc.STATUS_SUCCESS:
                return {"error": "connection_not_tested",
                        "message": "Probá la conexión con éxito antes de importar"}, 409

            record_type = CatalogRepository(db, "record-types").get_by_name("Tarea")
            if not record_type:
                return {"error": "server_error",
                        "message": "El catálogo de tipo de registro no tiene sembrado 'Tarea'"}, 500
            record_type_id = uuid.UUID(record_type["id"])

            try:
                # research.md Decisión 7: re-clasifica en el momento de confirmar en vez de
                # confiar en la lista ya devuelta por `preview` — evita importar contra un lote
                # desactualizado si el usuario homologó algo entre ambos pasos.
                rows = _diagnose(db, config, project_ids, date_from, date_to, task_list_teamwork_id)
            except TeamworkConnectionError as e:
                return {"error": "teamwork_api_error", "message": str(e)}, 502

            ticket_repo = TicketRepository(db)
            site_url = config.site_url.rstrip("/")
            created_count = updated_count = 0
            skipped: list[dict] = []
            ready_raws: list[dict] = []
            for raw, row in rows:
                if row.status != task_import_svc.STATUS_READY:
                    skipped.append({"teamwork_id": row.teamwork_id, "block_reason": row.block_reason})
                    continue
                url = f"{site_url}/app/tasks/{row.teamwork_id}"
                _ticket, was_created = ticket_repo.upsert_from_import(
                    external_reference_id=row.teamwork_id, external_reference_url=url,
                    record_type_id=record_type_id, title=row.name, description=raw.get("description") or "",
                    client_id=row.resolved.get("client_id"), project_id=row.resolved.get("project_id"),
                    list_id=row.resolved.get("list_id"), parent_task_id=None,
                    assignee_id=row.resolved.get("assignee_resource_id"), client_contact_id=None,
                    created_by=g.current_user.id, estimated_resolution_minutes=0,
                )
                ready_raws.append(raw)
                if was_created:
                    created_count += 1
                else:
                    updated_count += 1

            # Segunda pasada: resuelve parent_task_id de Subtareas (mismo patrón ya usado por
            # ticket_imports.py / POST /sync/tasks, spec 041/044).
            for raw in ready_raws:
                parent_teamwork_id = raw.get("parent_task_id")
                if not parent_teamwork_id:
                    continue
                child = ticket_repo.get_by_external_reference_id(raw["id"])
                parent = ticket_repo.get_by_external_reference_id(parent_teamwork_id)
                if child and parent and child.parent_task_id != parent.id:
                    ticket_repo.update_fields(child.id, parent_task_id=parent.id, list_id=parent.list_id)

            return {
                "summary": {"created": created_count, "updated": updated_count, "skipped": len(skipped)},
                "skipped": skipped,
            }, 200
        except Exception:
            return server_error()
