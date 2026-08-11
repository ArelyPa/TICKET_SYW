"""Importador de reportes mensuales de tiempos de Teamwork (spec 042) — preview/confirm sin
persistencia intermedia (mismo patrón que `ticket_imports.py` de spec 041). Namespace nuevo,
independiente del importador de tareas de spec 041."""
import re
import uuid
from datetime import date, datetime

from flask import request, g
from flask_restx import Namespace, Resource, fields

from backend.api.middleware.rbac import require_permission
from backend.api.routes._shared import error_model, server_error
from backend.infra.database import get_db
from backend.infra.importers.teamwork_time_file_parser import parse_file, TeamworkTimeFileParseError
from backend.infra.repositories.client_repo import ClientRepository
from backend.infra.repositories.project_repo import ProjectRepository
from backend.infra.repositories.resource_repo import ResourceRepository
from backend.infra.repositories.ticket_repo import TicketRepository
from backend.infra.repositories.teamwork_integration_repo import EntityMappingRepository
from backend.infra.repositories.work_session_repo import WorkSessionRepository
from backend.domain.entities.client import Client
from backend.domain.entities.resource import Resource as ResourceEntity
from backend.domain.entities.work_session import WorkSession
from backend.domain.services import time_import_service as svc

ns = Namespace("time_imports", description="Importación de reportes mensuales de tiempos",
              path="/api/time-imports")

_error = error_model(ns, "TimeImportError")

_time_import_row_out = ns.model("TimeImportRow", {
    "source_row_number": fields.Integer(),
    "external_time_id": fields.String(allow_null=True),
    "status": fields.String(description="valid | conflict | error"),
    "issues": fields.List(fields.String()),
    "resolved": fields.Raw(),
})

_preview_out = ns.model("TimeImportPreview", {
    "rows": fields.List(fields.Nested(_time_import_row_out)),
    "summary": fields.Raw(),
})


def _resolve_resource_id(db, raw: dict) -> uuid.UUID | None:
    mapping_repo = EntityMappingRepository(db)
    resource_repo = ResourceRepository(db)
    if raw.get("who_external_id"):
        mapping = mapping_repo.get_by_teamwork_key("person", raw["who_external_id"])
        if mapping and mapping.sytix_id:
            return mapping.sytix_id
    if not raw.get("who_name"):
        return None
    mapping = mapping_repo.get_by_name("person", raw["who_name"])
    if mapping and mapping.sytix_id:
        return mapping.sytix_id
    resource = (resource_repo.get_by_email(raw["who_name"]) if "@" in raw["who_name"]
               else resource_repo.get_by_full_name(raw["who_name"]))
    return resource.id if resource else None


def _resolve_client_id(db, raw: dict) -> uuid.UUID | None:
    if not raw.get("company_name"):
        return None
    mapping = EntityMappingRepository(db).get_by_name("company", raw["company_name"])
    if mapping and mapping.sytix_id:
        return mapping.sytix_id
    client = ClientRepository(db).get_by_name(raw["company_name"])
    return client.id if client else None


def _resolve_project_id(db, raw: dict, client_id: uuid.UUID | None) -> uuid.UUID | None:
    if not raw.get("project_name"):
        return None
    mapping = EntityMappingRepository(db).get_by_name("project", raw["project_name"])
    if mapping and mapping.sytix_id:
        return mapping.sytix_id
    if not client_id:
        return None
    project = ProjectRepository(db).get_by_client_and_name(client_id, raw["project_name"])
    return project.id if project else None


def _resolve_ticket_id(db, raw: dict) -> uuid.UUID | None:
    if not raw.get("task_reference"):
        return None
    ticket = TicketRepository(db).get_by_external_reference_id(raw["task_reference"])
    return ticket.id if ticket else None


def _resolve_row(db, raw: dict, duplicates: set[str]) -> svc.TimeImportRow:
    resource_id = _resolve_resource_id(db, raw)
    client_id = _resolve_client_id(db, raw)
    project_id = _resolve_project_id(db, raw, client_id)
    ticket_id = _resolve_ticket_id(db, raw)
    resolution = {
        "resource_id": resource_id,
        "client_id": client_id,
        "project_id": project_id,
        "ticket_id": ticket_id,
        "duplicate_in_file": raw.get("external_time_id") in duplicates,
    }
    return svc.classify_row(raw, resolution)


def build_preview(db, raw_rows: list[dict]) -> dict:
    duplicates = svc.find_duplicate_external_time_ids(raw_rows)
    rows = [_resolve_row(db, raw, duplicates) for raw in raw_rows]
    summary = {
        "total": len(rows),
        "valid": sum(1 for r in rows if r.status == svc.STATUS_VALID),
        "conflict": sum(1 for r in rows if r.status == svc.STATUS_CONFLICT),
        "error": sum(1 for r in rows if r.status == svc.STATUS_ERROR),
    }
    return {
        "rows": [{"source_row_number": r.source_row_number, "external_time_id": r.external_time_id,
                  "status": r.status, "issues": r.issues, "resolved": _jsonable(r.resolved)}
                 for r in rows],
        "summary": summary,
    }


def _jsonable(resolved: dict) -> dict:
    out = {}
    for k, v in resolved.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out


_confirm_input = ns.model("TimeImportConfirmInput", {
    "rows": fields.List(fields.Raw(), required=True,
                        description="Filas de la preview ya revisadas/editadas por el usuario"),
})

_confirm_row_error_out = ns.model("TimeImportConfirmRowError", {
    "source_row_number": fields.Integer(),
    "reason": fields.String(),
})

_confirm_out = ns.model("TimeImportConfirmResult", {
    "created_time_entries": fields.Integer(),
    "updated_time_entries": fields.Integer(),
    "created_resources": fields.Integer(),
    "created_clients": fields.Integer(),
    "skipped": fields.Integer(),
    "errors": fields.List(fields.Nested(_confirm_row_error_out)),
})


def _parse_uuid(value) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_datetime_field(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _placeholder_email(who_name: str) -> str:
    """Los reportes de tiempos de Teamwork solo traen el nombre (`Who`), sin correo — se genera
    un correo determinístico y único para el Recurso creado sin acceso de login (FR-014); si el
    mismo nombre vuelve a aparecer en una importación futura, `get_by_full_name` ya lo resuelve
    sin duplicar. `resources.email` exige el dominio `@sywork.net` a nivel de base de datos
    (`ck_resources_email_domain`, migración 004) — el placeholder respeta ese dominio, pero al no
    llevar `user_id` no otorga ninguna cuenta de acceso real (Principio IV)."""
    slug = re.sub(r"[^a-z0-9]+", ".", who_name.strip().lower()).strip(".") or "recurso"
    return f"{slug}.teamwork-import@sywork.net"


def _apply_confirm_action(db, row: dict) -> tuple[dict | None, str | None, dict]:
    """Aplica la acción de una fila de confirmación y devuelve
    `(campos_para_worksession | None, razon_de_error | None, contadores_de_creacion)`."""
    resolved = row.get("resolved") or {}
    status = row.get("status")
    action = row.get("action")
    created = {"resource": 0, "client": 0}

    if status == svc.STATUS_ERROR:
        return None, "row_has_error_status", created
    if status == svc.STATUS_CONFLICT and action == "omit":
        return None, "omitted", created

    if status == svc.STATUS_CONFLICT and action == "create":
        create_entity_type = row.get("create_entity_type")
        invalid = svc.validate_resolution_action(action, create_entity_type)
        if invalid:
            return None, invalid, created
        if create_entity_type == "resource" and not resolved.get("resource_id"):
            who_name = resolved.get("who_name") or "Recurso importado"
            resource_repo = ResourceRepository(db)
            existing_resource = resource_repo.get_by_full_name(who_name)
            if existing_resource:
                resolved["resource_id"] = str(existing_resource.id)
            else:
                resource = resource_repo.create(ResourceEntity.create(
                    full_name=who_name, email=_placeholder_email(who_name)))
                resolved["resource_id"] = str(resource.id)
                created["resource"] = 1
        elif create_entity_type == "client" and not resolved.get("client_id"):
            client_repo = ClientRepository(db)
            company_name = resolved.get("company_name") or "Cliente importado"
            existing_client = client_repo.get_by_name(company_name)
            if existing_client:
                resolved["client_id"] = str(existing_client.id)
            else:
                client = client_repo.create(Client.create(name=company_name))
                resolved["client_id"] = str(client.id)
                created["client"] = 1

    resource_id = _parse_uuid(resolved.get("resource_id"))
    project_id = _parse_uuid(resolved.get("project_id"))
    ticket_id = _parse_uuid(resolved.get("ticket_id"))
    duration_minutes = resolved.get("duration_minutes")
    started_at = _parse_datetime_field(resolved.get("started_at"))

    if status == svc.STATUS_CONFLICT and not action:
        return None, "unresolved_conflict", created
    if not resource_id or not ticket_id or not duration_minutes or not started_at:
        return None, "still_unresolved_after_action", created

    return {
        "resource_id": resource_id, "project_id": project_id, "ticket_id": ticket_id,
        "duration_minutes": duration_minutes, "started_at": started_at,
        "ended_at": _parse_datetime_field(resolved.get("ended_at")),
        "description": resolved.get("description") or "",
    }, None, created


@ns.route("/confirm")
class TimeImportConfirm(Resource):
    @ns.doc("time_import_confirm")
    @ns.expect(_confirm_input, validate=False)
    @ns.response(200, "Importación aplicada", _confirm_out)
    @ns.response(400, "'rows' faltante o vacío", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        """FR-012: nada se inserta hasta este paso. Cada fila `valid` se procesa tal cual; cada
        fila `conflict` requiere `action` ('resolve'/'create'/'omit'); las `error` se ignoran."""
        data = request.get_json(silent=True) or {}
        rows = data.get("rows")
        if not rows:
            return {"error": "validation_error", "message": "El campo 'rows' es requerido"}, 400
        try:
            db = get_db()
            work_session_repo = WorkSessionRepository(db)
            created_entries = updated_entries = skipped = 0
            created_resources = created_clients = 0
            valid_ok = resolved_ok = 0
            errors: list[dict] = []
            filename = data.get("filename") or "importación de tiempos"

            for row in rows:
                fields_out, reason, created = _apply_confirm_action(db, row)
                created_resources += created["resource"]
                created_clients += created["client"]
                if reason == "omitted":
                    skipped += 1
                    continue
                if fields_out is None:
                    errors.append({"source_row_number": row.get("source_row_number"), "reason": reason})
                    continue
                work_session = WorkSession.create(
                    resource_id=fields_out["resource_id"], ticket_id=fields_out["ticket_id"],
                    work_date=fields_out["started_at"].date(),
                    duration_minutes=int(fields_out["duration_minutes"]),
                    created_by=g.current_user.id, note=fields_out["description"],
                    started_at=fields_out["started_at"], ended_at=fields_out["ended_at"],
                    external_time_id=row.get("external_time_id"),
                )
                _, is_new = work_session_repo.upsert_from_import(work_session)
                if is_new:
                    created_entries += 1
                else:
                    updated_entries += 1
                if row.get("status") == svc.STATUS_VALID:
                    valid_ok += 1
                else:
                    resolved_ok += 1

            from backend.infra.repositories.teamwork_integration_repo import TimeImportBatchRepository
            TimeImportBatchRepository(db).create(
                filename=filename, imported_by=g.current_user.id, total_rows=len(rows),
                valid_rows=valid_ok, resolved_rows=resolved_ok,
                skipped_rows=skipped, error_rows=len(errors),
            )

            return {
                "created_time_entries": created_entries, "updated_time_entries": updated_entries,
                "created_resources": created_resources, "created_clients": created_clients,
                "skipped": skipped, "errors": errors,
            }, 200
        except Exception:
            return server_error()


@ns.route("/preview")
class TimeImportPreview(Resource):
    @ns.doc("time_import_preview")
    @ns.response(200, "Vista previa de la carga, nada insertado todavía", _preview_out)
    @ns.response(400, "Archivo inválido o columnas faltantes", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        """`multipart/form-data` con `file` (.xlsx/.csv del reporte mensual de tiempos)."""
        file = request.files.get("file")
        if not file or not file.filename:
            return {"error": "validation_error", "message": "El campo 'file' es requerido"}, 400
        try:
            raw_rows = parse_file(file.filename, file.read())
        except TeamworkTimeFileParseError as e:
            return {"error": "validation_error", "message": str(e)}, 400
        try:
            db = get_db()
            return build_preview(db, raw_rows), 200
        except Exception:
            return server_error()
