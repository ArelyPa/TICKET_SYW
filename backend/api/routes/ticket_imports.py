"""Importación de tareas de Teamwork (spec 041) — carga Excel/CSV (US1) y sincronización por
API v3 (US3), ambas con vista previa obligatoria antes de confirmar. Namespace nuevo, gateado
por `ticket_imports:run` (Admin, Coordinador)."""
import os
import uuid

from flask import request, g
from flask_restx import Namespace, Resource, fields

from backend.api.middleware.rbac import require_permission
from backend.api.routes._shared import error_model, server_error
from backend.infra.database import get_db
from backend.infra.importers.teamwork_file_parser import parse_file, TeamworkFileParseError
from backend.infra.repositories.client_repo import ClientRepository
from backend.infra.repositories.project_repo import ProjectRepository
from backend.infra.repositories.task_list_repo import TaskListRepository
from backend.infra.repositories.resource_repo import ResourceRepository
from backend.infra.repositories.client_contact_repo import ClientContactRepository
from backend.infra.repositories.ticket_repo import TicketRepository
from backend.infra.repositories.catalog_repo import CatalogRepository
from backend.domain.services import teamwork_import_service as svc

ns = Namespace("ticket_imports", description="Importación de tareas de Teamwork",
              path="/api/ticket-imports")

_error = error_model(ns, "TicketImportError")

_import_row_out = ns.model("ImportRow", {
    "source_row_number": fields.Integer(),
    "external_id": fields.String(allow_null=True),
    "status": fields.String(description="ready | needs_review | error"),
    "issues": fields.List(fields.String()),
    "resolved": fields.Raw(description="Campos ya mapeados a IDs de SYTIX cuando se pudieron "
                                       "resolver; ver data-model.md § ImportRow"),
})

_preview_out = ns.model("ImportPreview", {
    "rows": fields.List(fields.Nested(_import_row_out)),
    "summary": fields.Raw(),
})

_confirm_input = ns.model("ImportConfirmInput", {
    "rows": fields.List(fields.Raw(), required=True,
                        description="Filas de la preview ya revisadas/editadas por el usuario"),
})

_confirm_error_out = ns.model("ImportConfirmRowError", {
    "source_row_number": fields.Integer(),
    "reason": fields.String(),
})

_confirm_out = ns.model("ImportConfirmResult", {
    "created": fields.Integer(),
    "updated": fields.Integer(),
    "errors": fields.List(fields.Nested(_confirm_error_out)),
})


def _teamwork_domain() -> str | None:
    return os.environ.get("TEAMWORK_DOMAIN")


def _resolve_row(db, raw: dict, batch_ids: set[str], duplicates: set[str]) -> svc.ImportRow:
    client_repo = ClientRepository(db)
    project_repo = ProjectRepository(db)
    resource_repo = ResourceRepository(db)
    contact_repo = ClientContactRepository(db)
    ticket_repo = TicketRepository(db)

    client = client_repo.get_by_name(raw["company_name"]) if raw.get("company_name") else None
    project = (project_repo.get_by_client_and_name(client.id, raw["project_name"])
              if client and raw.get("project_name") else None)

    assignee = None
    if raw.get("assignee_name"):
        assignee = (resource_repo.get_by_email(raw["assignee_name"]) if "@" in raw["assignee_name"]
                   else resource_repo.get_by_full_name(raw["assignee_name"]))

    requester_user_id = None
    requester_contact_id = None
    if raw.get("requester_name"):
        requester_resource = (resource_repo.get_by_email(raw["requester_name"])
                              if "@" in raw["requester_name"]
                              else resource_repo.get_by_full_name(raw["requester_name"]))
        if requester_resource and requester_resource.user_id:
            requester_user_id = requester_resource.user_id
        elif client:
            contact = contact_repo.get_by_name_or_email(client.id, raw["requester_name"])
            if contact:
                requester_contact_id = contact.id

    existing = (ticket_repo.get_by_external_reference_id(raw["external_id"])
               if raw.get("external_id") else None)

    parent_external_id = raw.get("parent_external_id")
    parent_in_batch = bool(parent_external_id) and parent_external_id in batch_ids
    parent_in_db = (bool(parent_external_id) and not parent_in_batch
                    and ticket_repo.get_by_external_reference_id(parent_external_id) is not None)
    parent_resolved = svc.resolve_parent_link(parent_external_id, parent_in_batch or parent_in_db)

    resolution = {
        "client_id": client.id if client else None,
        "project_id": project.id if project else None,
        "assignee_resource_id": assignee.id if assignee else None,
        "requester_created_by_user_id": requester_user_id,
        "requester_client_contact_id": requester_contact_id,
        "duplicate_in_file": raw.get("external_id") in duplicates,
        "parent_resolved_external_id": parent_resolved,
        "existing_ticket_id": existing.id if existing else None,
    }
    return svc.classify_row(raw, resolution)


def _build_preview(db, raw_rows: list[dict]) -> dict:
    duplicates = svc.find_duplicate_external_ids(raw_rows)
    batch_ids = {r["external_id"] for r in raw_rows if r.get("external_id")}
    rows = [_resolve_row(db, raw, batch_ids, duplicates) for raw in raw_rows]
    summary = {
        "total": len(rows),
        "ready": sum(1 for r in rows if r.status == svc.STATUS_READY),
        "needs_review": sum(1 for r in rows if r.status == svc.STATUS_NEEDS_REVIEW),
        "error": sum(1 for r in rows if r.status == svc.STATUS_ERROR),
    }
    return {
        "rows": [{"source_row_number": r.source_row_number, "external_id": r.external_id,
                  "status": r.status, "issues": r.issues,
                  "resolved": _jsonable(r.resolved)} for r in rows],
        "summary": summary,
    }


def _jsonable(resolved: dict) -> dict:
    """Los `date`/`UUID` del dict `resolved` no son serializables por Flask-RESTX (`fields.Raw`
    delega en el JSON encoder estándar) — se normalizan a `str` antes de responder."""
    out = {}
    for k, v in resolved.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out


@ns.route("/preview")
class TicketImportPreview(Resource):
    @ns.doc("ticket_import_preview")
    @ns.response(200, "Vista previa del mapeo, nada insertado todavía", _preview_out)
    @ns.response(400, "Archivo inválido, columnas faltantes o 'source' inválido", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso ticket_imports:run", _error)
    @ns.response(502, "La API v3 de Teamwork no respondió (solo source=api_v3)", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("ticket_imports", "run")
    def post(self):
        """US1: `multipart/form-data` con `file` (.xlsx/.csv). US3: `application/json`
        `{"source": "api_v3"}` para sincronizar contra Teamwork directamente."""
        try:
            if request.content_type and "multipart/form-data" in request.content_type:
                file = request.files.get("file")
                if not file or not file.filename:
                    return {"error": "validation_error", "message": "El campo 'file' es requerido"}, 400
                try:
                    raw_rows = parse_file(file.filename, file.read())
                except TeamworkFileParseError as e:
                    return {"error": "validation_error", "message": str(e)}, 400
            else:
                data = request.get_json(silent=True) or {}
                if data.get("source") != "api_v3":
                    return {"error": "validation_error",
                            "message": "Se requiere 'file' (multipart) o {\"source\": \"api_v3\"}"}, 400
                from backend.infra.importers.teamwork_api_client import (
                    fetch_tasks, TeamworkApiError,
                )
                try:
                    raw_rows = fetch_tasks()
                except TeamworkApiError as e:
                    return {"error": "teamwork_api_error", "message": str(e)}, 502
            db = get_db()
            return _build_preview(db, raw_rows), 200
        except Exception:
            return server_error()


@ns.route("/confirm")
class TicketImportConfirm(Resource):
    @ns.doc("ticket_import_confirm")
    @ns.expect(_confirm_input, validate=False)
    @ns.response(200, "Importación aplicada", _confirm_out)
    @ns.response(400, "'rows' faltante o vacío", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso ticket_imports:run", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("ticket_imports", "run")
    def post(self):
        """FR-004: nada se inserta hasta este paso. Solo procesa filas 'ready'/'needs_review'
        con su `resolved` ya completado por el usuario; las 'error' se ignoran."""
        data = request.get_json(silent=True) or {}
        rows = data.get("rows")
        if not rows:
            return {"error": "validation_error", "message": "El campo 'rows' es requerido"}, 400
        try:
            db = get_db()
            record_type = CatalogRepository(db, "record-types").get_by_name("Tarea")
            if not record_type:
                return {"error": "server_error",
                        "message": "El catálogo de tipo de registro no tiene sembrado 'Tarea'"}, 500
            record_type_id = uuid.UUID(record_type["id"])
            task_list_repo = TaskListRepository(db)
            ticket_repo = TicketRepository(db)
            domain = _teamwork_domain()

            created = updated = 0
            errors: list[dict] = []
            for row in rows:
                if row.get("status") == "error":
                    continue
                resolved = row.get("resolved") or {}
                client_id = parse_optional_uuid(resolved.get("client_id"))
                project_id = parse_optional_uuid(resolved.get("project_id"))
                assignee_id = parse_optional_uuid(resolved.get("assignee_resource_id"))
                requester_contact_id = parse_optional_uuid(resolved.get("requester_client_contact_id"))
                requester_user_id = parse_optional_uuid(resolved.get("requester_created_by_user_id"))
                external_id = row.get("external_id")
                if not client_id or not external_id:
                    errors.append({"source_row_number": row.get("source_row_number"),
                                   "reason": "client_not_found"})
                    continue
                list_id = None
                if project_id and resolved.get("list_name"):
                    list_id = task_list_repo.get_or_create_by_name(project_id, resolved["list_name"]).id
                created_by = requester_user_id or g.current_user.id
                url = svc.build_external_reference_url(domain, external_id) if domain else None
                ticket, was_created = ticket_repo.upsert_from_import(
                    external_reference_id=external_id, external_reference_url=url,
                    record_type_id=record_type_id, title=resolved.get("title") or "(sin título)",
                    description=resolved.get("description") or "", client_id=client_id,
                    project_id=project_id, list_id=list_id, parent_task_id=None,
                    assignee_id=assignee_id, client_contact_id=requester_contact_id,
                    created_by=created_by,
                    estimated_resolution_minutes=resolved.get("estimated_minutes") or 0,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            # Segunda pasada: resuelve parent_task_id ahora que todas las filas del lote ya
            # tienen su Ticket propio creado/actualizado (evita depender del orden del array).
            for row in rows:
                resolved = row.get("resolved") or {}
                parent_external_id = resolved.get("parent_external_id")
                if row.get("status") == "error" or not parent_external_id or not row.get("external_id"):
                    continue
                child = ticket_repo.get_by_external_reference_id(row["external_id"])
                parent = ticket_repo.get_by_external_reference_id(parent_external_id)
                if child and parent and child.parent_task_id != parent.id:
                    ticket_repo.update_fields(child.id, parent_task_id=parent.id, list_id=parent.list_id)

            return {"created": created, "updated": updated, "errors": errors}, 200
        except Exception:
            return server_error()


def parse_optional_uuid(value):
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None
