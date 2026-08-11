"""Integración API Teamwork v3 (spec 042) — configuración de conexión, prueba de conexión,
sincronización de catálogos y homologación de entidades. Namespace nuevo, no reutiliza ni
modifica `ticket_imports` (spec 041). spec 043 amplía este mismo namespace con contexto
jerárquico, correo/rol de Personal y la acción "Migrar como Nuevo" — reutilizando sin cambios
los repos/servicios de creación ya existentes de cada tipo de entidad (research.md Decisión 5)."""
import secrets
import uuid
from datetime import date

from flask import request, g
from flask_restx import Namespace, Resource, fields

from backend.api.middleware.rbac import require_permission
from backend.api.routes._shared import error_model, server_error, parse_uuid
from backend.api.routes.users import ALLOWED_EMAIL_DOMAIN
from backend.infra.database import get_db
from backend.infra.importers import teamwork_connection_client as twc
from backend.infra.importers.teamwork_connection_client import (
    test_connection as check_connection, TeamworkConnectionError,
)
from backend.infra.repositories.teamwork_integration_repo import (
    TeamworkIntegrationConfigRepository, EntityMappingRepository,
)
from backend.infra.repositories.client_repo import ClientRepository
from backend.infra.repositories.project_repo import ProjectRepository
from backend.infra.repositories.resource_repo import ResourceRepository
from backend.infra.repositories.task_list_repo import TaskListRepository
from backend.infra.repositories.user_repo import UserRepository
from backend.infra.repositories.role_repo import RoleRepository
from backend.infra.repositories.client_contact_repo import ClientContactRepository
from backend.infra.repositories.ticket_repo import TicketRepository
from backend.infra.repositories.catalog_repo import CatalogRepository
from backend.domain.entities.client import Client
from backend.domain.entities.project import Project
from backend.domain.entities.resource import Resource as ResourceEntity
from backend.domain.entities.user import User, USUARIO_CLIENTE_ROLE_NAME
from backend.domain.entities.client_contact import ClientContact
from backend.domain.errors import DomainError
from backend.domain.services.entity_mapping_service import suggest_match, derive_sync_status
from backend.domain.services.auth_service import AuthService
from backend.domain.services.client_service import ClientService, ClientBusinessError
from backend.domain.services.project_service import ProjectService, ProjectBusinessError
from backend.domain.services.task_list_service import TaskListService, TaskListValidationError
from backend.domain.services.client_contact_service import ClientContactService
from backend.domain.services import teamwork_task_migration_service as task_migration_svc

ns = Namespace("teamwork_integration", description="Integración API Teamwork v3",
              path="/api/teamwork-integration")

_error = error_model(ns, "TeamworkIntegrationError")

_config_out = ns.model("TeamworkIntegrationConfig", {
    "site_url": fields.String(),
    "environment": fields.String(),
    "has_token": fields.Boolean(),
    "last_test_status": fields.String(),
    "last_test_at": fields.String(),
    "last_test_message": fields.String(),
})

_config_input = ns.model("TeamworkIntegrationConfigInput", {
    "site_url": fields.String(required=True),
    "environment": fields.String(required=True, enum=["test", "production"]),
    "api_token": fields.String(description="Opcional al actualizar: si se omite, se conserva el token ya guardado"),
})

_test_connection_out = ns.model("TeamworkTestConnectionResult", {
    "status": fields.String(description="success | auth_error | connection_error"),
    "message": fields.String(allow_null=True),
})

_ENVIRONMENTS = {"test", "production"}


def _serialize_config(config) -> dict:
    """`config` se obtiene siempre con `include_token=True` (solo para calcular `has_token` en
    memoria del servidor); el token en sí nunca se incluye en el dict devuelto por la API."""
    return {
        "site_url": config.site_url,
        "environment": config.environment,
        "has_token": bool(config.api_token),
        "last_test_status": config.last_test_status,
        "last_test_at": config.last_test_at.isoformat() if config.last_test_at else None,
        "last_test_message": config.last_test_message,
    }


@ns.route("/config")
class TeamworkIntegrationConfig_(Resource):
    @ns.doc("teamwork_integration_get_config")
    @ns.response(200, "Configuración actual (sin el token)", _config_out)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:manage", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "manage")
    def get(self):
        try:
            db = get_db()
            config = TeamworkIntegrationConfigRepository(db).get(include_token=True)
            if not config:
                return {"site_url": None, "environment": None, "has_token": False,
                        "last_test_status": None, "last_test_at": None,
                        "last_test_message": None}, 200
            return _serialize_config(config), 200
        except Exception:
            return server_error()

    @ns.doc("teamwork_integration_save_config")
    @ns.expect(_config_input, validate=False)
    @ns.response(200, "Configuración guardada", _config_out)
    @ns.response(400, "site_url/environment inválidos", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:manage", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "manage")
    def put(self):
        data = request.get_json(silent=True) or {}
        site_url = (data.get("site_url") or "").strip()
        environment = data.get("environment")
        if not site_url.startswith("http://") and not site_url.startswith("https://"):
            return {"error": "validation_error", "message": "site_url debe ser una URL http(s) válida"}, 400
        if environment not in _ENVIRONMENTS:
            return {"error": "validation_error",
                    "message": "environment debe ser 'test' o 'production'"}, 400
        try:
            db = get_db()
            repo = TeamworkIntegrationConfigRepository(db)
            repo.upsert(
                site_url=site_url, environment=environment, api_token=data.get("api_token") or None,
                updated_by=g.current_user.id,
            )
            config = repo.get(include_token=True)
            return _serialize_config(config), 200
        except Exception:
            return server_error()


@ns.route("/test-connection")
class TeamworkIntegrationTestConnection(Resource):
    @ns.doc("teamwork_integration_test_connection")
    @ns.response(200, "Resultado de la prueba (siempre 200, el estado va en el body)", _test_connection_out)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:manage", _error)
    @ns.response(409, "No hay configuración guardada", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "manage")
    def post(self):
        try:
            db = get_db()
            repo = TeamworkIntegrationConfigRepository(db)
            config = repo.get(include_token=True)
            if not config:
                return {"error": "no_config", "message": "No hay configuración guardada todavía"}, 409
            result = check_connection(config.site_url, config.api_token)
            repo.record_test_result(result["status"], result["message"])
            return result, 200
        except Exception:
            return server_error()


def _entity_mapping_out(mapping, sytix_name: str | None) -> dict:
    return {
        "id": str(mapping.id),
        "entity_type": mapping.entity_type,
        "teamwork_id": mapping.teamwork_id,
        "teamwork_name": mapping.teamwork_name,
        "sytix_entity_type": mapping.sytix_entity_type,
        "sytix_id": str(mapping.sytix_id) if mapping.sytix_id else None,
        "sytix_name": sytix_name,
        "match_method": mapping.match_method,
        "teamwork_email": mapping.teamwork_email,
        "teamwork_metadata": mapping.teamwork_metadata,
        "migration_status": derive_sync_status(mapping),
    }


_SYNC_FETCHERS = {
    "company": twc.fetch_companies,
    "project": twc.fetch_projects,
    "person": twc.fetch_people,
    "tasklist": twc.fetch_tasklists,
}

_SYTIX_ENTITY_TYPE = {"company": "client", "project": "project", "person": "resource",
                      "tasklist": "task_list"}


def _sytix_candidates(db, entity_type: str) -> list[dict]:
    """FR-006: candidatos de SYTIX contra los que automapear, por tipo de entidad. `tasklist`
    no tiene un listado global propio (solo por proyecto) — queda sin automapeo, homologación
    manual únicamente."""
    if entity_type == "company":
        clients, _ = ClientRepository(db).list_paginated(page=1, page_size=500)
        return [{"id": str(c.id), "name": c.name} for c in clients]
    if entity_type == "project":
        projects, _ = ProjectRepository(db).list_paginated(page=1, page_size=500)
        return [{"id": str(p.id), "name": p.name} for p in projects]
    if entity_type == "person":
        resources, _ = ResourceRepository(db).list_paginated(page=1, page_size=500)
        return [{"id": str(r.id), "name": r.full_name, "email": r.email} for r in resources]
    return []

_sync_out = ns.model("TeamworkSyncResult", {
    "entity_type": fields.String(),
    "synced": fields.Integer(),
    "new": fields.Integer(),
    "updated": fields.Integer(),
})


@ns.route("/sync/<string:entity_type>")
class TeamworkIntegrationSync(Resource):
    @ns.doc("teamwork_integration_sync")
    @ns.response(200, "Catálogo sincronizado", _sync_out)
    @ns.response(400, "entity_type inválido", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(409, "La conexión no ha sido probada con éxito", _error)
    @ns.response(502, "La API v3 de Teamwork no respondió", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self, entity_type: str):
        fetcher = _SYNC_FETCHERS.get(entity_type)
        if not fetcher:
            return {"error": "validation_error",
                    "message": f"entity_type inválido: {entity_type}"}, 400
        try:
            db = get_db()
            config_repo = TeamworkIntegrationConfigRepository(db)
            config = config_repo.get(include_token=True)
            if not config or config.last_test_status != twc.STATUS_SUCCESS:
                return {"error": "connection_not_tested",
                        "message": "Probá la conexión con éxito antes de sincronizar"}, 409
            try:
                items = fetcher(config.site_url, config.api_token)
            except TeamworkConnectionError as e:
                return {"error": "teamwork_api_error", "message": str(e)}, 502
            mapping_repo = EntityMappingRepository(db)
            candidates = _sytix_candidates(db, entity_type)
            new_count = updated_count = 0
            for item in items:
                suggestion = suggest_match(item, candidates)
                suggested_match = None
                if suggestion:
                    suggested_match = {
                        "sytix_id": uuid.UUID(suggestion["sytix_id"]),
                        "sytix_entity_type": _SYTIX_ENTITY_TYPE[entity_type],
                        "match_method": suggestion["match_method"],
                    }
                _, is_new = mapping_repo.upsert_from_sync(
                    entity_type, item["id"], item["name"], suggested_match=suggested_match,
                    parent_teamwork_id=item.get("parent_id"), teamwork_email=item.get("email"),
                    metadata=item.get("metadata"))
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1
            return {"entity_type": entity_type, "synced": len(items),
                    "new": new_count, "updated": updated_count}, 200
        except Exception:
            return server_error()


_entity_mapping_out_model = ns.model("TeamworkEntityMapping", {
    "id": fields.String(),
    "entity_type": fields.String(),
    "teamwork_id": fields.String(),
    "teamwork_name": fields.String(allow_null=True),
    "sytix_entity_type": fields.String(allow_null=True),
    "sytix_id": fields.String(allow_null=True),
    "sytix_name": fields.String(allow_null=True),
    "match_method": fields.String(allow_null=True),
    "teamwork_email": fields.String(allow_null=True, description="Solo para entity_type='person' (FR-008)"),
    "teamwork_metadata": fields.Raw(allow_null=True, description="Metadatos ampliados de la API v3 por "
                                    "entity_type (spec 045 FR-013 a FR-016) — country/address/domain/phone "
                                    "(company), job_title/timezone (person), description/status (project, "
                                    "tasklist); claves ausentes = no informado en el origen"),
    "migration_status": fields.String(description="pending | linked | created | inactive (spec 045 FR-001)"),
    "parent_context": fields.Raw(description="Solo para entity_type in (project, tasklist) — "
                                 "{status: unmapped|pending|resolved, client_label, project_label}"),
})

_entity_mapping_list_out = ns.model("TeamworkEntityMappingList", {
    "rows": fields.List(fields.Nested(_entity_mapping_out_model)),
})

_entity_mapping_input = ns.model("TeamworkEntityMappingInput", {
    "sytix_id": fields.String(allow_null=True, description="null limpia la homologación"),
})

_SYTIX_REPO_BY_TYPE = {
    "client": lambda db: ClientRepository(db),
    "project": lambda db: ProjectRepository(db),
    "resource": lambda db: ResourceRepository(db),
    "task_list": lambda db: TaskListRepository(db),
    "user": lambda db: UserRepository(db),
}
_SYTIX_NAME_ATTR = {"client": "name", "project": "name", "resource": "full_name",
                    "task_list": "name", "user": "username"}


def _resolve_sytix_name(db, sytix_entity_type: str | None, sytix_id) -> str | None:
    if not sytix_entity_type or not sytix_id:
        return None
    repo_factory = _SYTIX_REPO_BY_TYPE.get(sytix_entity_type)
    if not repo_factory:
        return None
    entity = repo_factory(db).get_by_id(sytix_id)
    return getattr(entity, _SYTIX_NAME_ATTR[sytix_entity_type], None) if entity else None


def _resolve_parent_link(db, parent_entity_type: str, parent_teamwork_id: str | None):
    """spec 043 research.md Decisión 2: `sytix_id` del padre jerárquico (Empresa para un
    Proyecto, Proyecto para una Lista de Tareas) si ya está homologado/migrado, o `None`."""
    if not parent_teamwork_id:
        return None
    parent = EntityMappingRepository(db).get_by_teamwork_key(parent_entity_type, parent_teamwork_id)
    return parent.sytix_id if parent and parent.sytix_id else None


def _resolve_parent_context(db, mapping) -> dict | None:
    """Contexto jerárquico para las columnas "Cliente Asociado" (Proyecto) / "Cliente"+"Proyecto"
    (Lista de Tareas) — spec 043 US2 — y "Compañía/Empresa de Origen" (Personal) — spec 044 US1,
    research.md Decisión 2. `None` si `entity_type` no aplica."""
    if mapping.entity_type not in ("project", "tasklist", "person"):
        return None
    if mapping.entity_type in ("project", "person"):
        client_sytix_id = _resolve_parent_link(db, "company", mapping.parent_teamwork_id)
        client = ClientRepository(db).get_by_id(client_sytix_id) if client_sytix_id else None
        status = "resolved" if client else ("pending" if mapping.parent_teamwork_id else "unmapped")
        return {"status": status, "client_label": client.name if client else None, "project_label": None,
                "client_id": str(client.id) if client else None, "project_id": None}

    project_sytix_id = _resolve_parent_link(db, "project", mapping.parent_teamwork_id)
    project = ProjectRepository(db).get_by_id(project_sytix_id) if project_sytix_id else None
    status = "resolved" if project else ("pending" if mapping.parent_teamwork_id else "unmapped")
    client = ClientRepository(db).get_by_id(project.client_id) if project else None
    return {
        "status": status,
        "client_label": client.name if client else None,
        "project_label": project.name if project else None,
        "client_id": str(client.id) if client else None,
        "project_id": str(project.id) if project else None,
    }


@ns.route("/entity-mappings")
class TeamworkEntityMappingList(Resource):
    @ns.doc("teamwork_entity_mappings_list")
    @ns.response(200, "Homologaciones", _entity_mapping_list_out)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def get(self):
        entity_type = request.args.get("entity_type")
        unresolved_only = request.args.get("unresolved_only") == "true"
        try:
            db = get_db()
            mappings = EntityMappingRepository(db).list(
                entity_type=entity_type, unresolved_only=unresolved_only)
            rows = []
            for m in mappings:
                row = _entity_mapping_out(m, _resolve_sytix_name(db, m.sytix_entity_type, m.sytix_id))
                parent_context = _resolve_parent_context(db, m)
                if parent_context is not None:
                    row["parent_context"] = parent_context
                rows.append(row)
            return {"rows": rows}, 200
        except Exception:
            return server_error()


@ns.route("/entity-mappings/<string:mapping_id>")
class TeamworkEntityMappingDetail(Resource):
    @ns.doc("teamwork_entity_mapping_update")
    @ns.expect(_entity_mapping_input, validate=False)
    @ns.response(200, "Homologación actualizada", _entity_mapping_out_model)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(404, "Homologación no encontrada", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def put(self, mapping_id: str):
        data = request.get_json(silent=True) or {}
        mapping_uuid = parse_uuid(mapping_id)
        if not mapping_uuid:
            return {"error": "not_found", "message": "Homologación no encontrada"}, 404
        try:
            db = get_db()
            repo = EntityMappingRepository(db)
            existing = repo.get_by_id(mapping_uuid)
            if not existing:
                return {"error": "not_found", "message": "Homologación no encontrada"}, 404
            sytix_id = parse_uuid(data.get("sytix_id")) if data.get("sytix_id") else None
            sytix_entity_type = _SYTIX_ENTITY_TYPE[existing.entity_type]
            updated = repo.set_manual_mapping(
                mapping_uuid, sytix_id, sytix_entity_type, updated_by=g.current_user.id)
            return _entity_mapping_out(
                updated, _resolve_sytix_name(db, updated.sytix_entity_type, updated.sytix_id)), 200
        except Exception:
            return server_error()


# ── "Migrar como Nuevo" (spec 043 US1-US3) ──────────────────────────────────────────────────
# Crea el registro de SYTIX a partir de los datos de Teamwork ya guardados en la fila de
# homologación, reutilizando sin cambios los repos/servicios de creación ya existentes de cada
# tipo de entidad (research.md Decisión 5) — nunca reimplementa su validación.

def _unique_username(user_repo: UserRepository, email: str) -> str:
    base = (email.split("@")[0] or "usuario").strip() or "usuario"
    username = base
    suffix = 1
    while user_repo.get_by_username_or_email(username):
        suffix += 1
        username = f"{base}{suffix}"
    return username


def _create_new_client(db):
    def _create(mapping, data):
        name = (mapping.teamwork_name or "").strip()
        if not name:
            return None, ({"error": "validation_error", "message": "La Empresa de Teamwork no tiene nombre"}, 400)
        try:
            ClientService().validate_unique_name(name, repo=ClientRepository(db))
        except ClientBusinessError as e:
            return None, ({"error": e.code, "message": e.message, **e.extra}, e.status_code)
        client = ClientRepository(db).create(Client.create(name=name))
        return (client.id, client.name, "client"), None
    return _create


def _create_new_project(db):
    def _create(mapping, data):
        client_sytix_id = _resolve_parent_link(db, "company", mapping.parent_teamwork_id)
        if not client_sytix_id:
            return None, ({"error": "parent_not_resolved",
                          "message": "Homologá o migrá primero la Empresa dueña de este Proyecto"}, 409)
        name = (mapping.teamwork_name or "").strip()
        try:
            ProjectService().validate_create(
                client_sytix_id, name, date.today(), None,
                clients_repo=ClientRepository(db), projects_repo=ProjectRepository(db))
        except ProjectBusinessError as e:
            return None, ({"error": e.code, "message": e.message, **e.extra}, e.status_code)
        project = ProjectRepository(db).create(
            Project.create(client_id=client_sytix_id, name=name, start_date=date.today()))
        return (project.id, project.name, "project"), None
    return _create


def _create_new_task_list(db):
    def _create(mapping, data):
        project_sytix_id = _resolve_parent_link(db, "project", mapping.parent_teamwork_id)
        if not project_sytix_id:
            return None, ({"error": "parent_not_resolved",
                          "message": "Homologá o migrá primero el Proyecto dueño de esta Lista de Tareas"}, 409)
        name = (mapping.teamwork_name or "").strip()
        try:
            clean_name = TaskListService().validate_create(
                project_sytix_id, name, ProjectRepository(db), task_lists_repo=TaskListRepository(db))
        except TaskListValidationError as e:
            return None, ({"error": e.code, "message": e.message, **e.extra}, e.status_code)
        task_list = TaskListRepository(db).get_or_create_by_name(project_sytix_id, clean_name)
        return (task_list.id, task_list.name, "task_list"), None
    return _create


def _create_new_person(db):
    def _create(mapping, data):
        email = (mapping.teamwork_email or "").strip().lower()
        if not email:
            return None, ({"error": "validation_error", "message": "La Persona de Teamwork no tiene correo"}, 400)
        role_id = parse_uuid(data.get("role_id") or "")
        if not role_id:
            return None, ({"error": "validation_error", "message": "El campo 'role_id' es requerido"}, 400)
        role = RoleRepository(db).get_by_id(role_id)
        if not role:
            return None, ({"error": "role_not_found", "message": "Rol no encontrado"}, 404)
        user_repo = UserRepository(db)
        if user_repo.get_by_email(email):
            return None, ({"error": "email_in_use",
                          "message": "Ya existe un usuario con ese correo — usá 'Homologar' en su lugar"}, 409)
        username = _unique_username(user_repo, email)
        provisional_password = secrets.token_urlsafe(9)

        if role.name == USUARIO_CLIENTE_ROLE_NAME:
            client_id = parse_uuid(data.get("client_id") or "")
            if not client_id:
                return None, ({"error": "validation_error",
                              "message": "El campo 'client_id' es requerido para el rol Usuario/cliente"}, 400)
            try:
                ClientContactService().validate_create(
                    client_id=client_id, email=email, clients_repo=ClientRepository(db), users_repo=user_repo)
            except DomainError as e:
                return None, ({"error": e.code, "message": e.message, **e.extra}, e.status_code)
            new_user = User(id=uuid.uuid4(), email=email, username=username, role=role,
                            password_hash=AuthService().hash_password(provisional_password))
            created_user = user_repo.create(new_user)
            ClientContactRepository(db).create(
                ClientContact(id=uuid.uuid4(), user_id=created_user.id, client_id=client_id))
            return (created_user.id, created_user.username, "user"), None

        if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
            return None, ({"error": "invalid_email_domain",
                          "message": f"El email debe ser @{ALLOWED_EMAIL_DOMAIN}"}, 400)
        resource_repo = ResourceRepository(db)
        if resource_repo.get_by_email(email):
            return None, ({"error": "email_in_use",
                          "message": "Ya existe un recurso con ese correo — usá 'Homologar' en su lugar"}, 409)
        new_user = User(id=uuid.uuid4(), email=email, username=username, role=role,
                        password_hash=AuthService().hash_password(provisional_password))
        created_user = user_repo.create(new_user)
        full_name = (mapping.teamwork_name or username).strip()
        resource = resource_repo.create(ResourceEntity.create(full_name=full_name, email=email, user_id=created_user.id))
        return (resource.id, resource.full_name, "resource"), None
    return _create


_CREATE_NEW_HANDLERS = {
    "company": _create_new_client,
    "project": _create_new_project,
    "tasklist": _create_new_task_list,
    "person": _create_new_person,
}


def _build_create_new_candidates(db, mapping) -> tuple[dict | None, tuple | None]:
    """Devuelve (`candidates`, `None`) o (`None`, `(error_dict, status_code)`)."""
    if mapping.entity_type == "person":
        roles, _ = RoleRepository(db).list_paginated(page=1, page_size=100, active=True)
        clients, _ = ClientRepository(db).list_paginated(page=1, page_size=500, active=True)
        return {
            "defaults": {"name": mapping.teamwork_name, "email": mapping.teamwork_email},
            "roles": [{"id": str(r.id), "name": r.name} for r in roles],
            "clients": [{"id": str(c.id), "name": c.name} for c in clients],
        }, None
    if mapping.entity_type == "project":
        if not _resolve_parent_link(db, "company", mapping.parent_teamwork_id):
            return None, ({"error": "parent_not_resolved",
                          "message": "Homologá o migrá primero la Empresa dueña de este Proyecto"}, 409)
        return {"defaults": {"name": mapping.teamwork_name}}, None
    if mapping.entity_type == "tasklist":
        if not _resolve_parent_link(db, "project", mapping.parent_teamwork_id):
            return None, ({"error": "parent_not_resolved",
                          "message": "Homologá o migrá primero el Proyecto dueño de esta Lista de Tareas"}, 409)
        return {"defaults": {"name": mapping.teamwork_name}}, None
    return {"defaults": {"name": mapping.teamwork_name}}, None


_create_new_candidates_out = ns.model("TeamworkCreateNewCandidates", {
    "defaults": fields.Raw(),
    "roles": fields.List(fields.Raw()),
    "clients": fields.List(fields.Raw()),
})

_create_new_input = ns.model("TeamworkCreateNewInput", {
    "role_id": fields.String(description="Requerido solo para entity_type='person'"),
    "client_id": fields.String(description="Requerido solo si el rol elegido es 'Usuario/cliente'"),
})

_create_new_out = ns.model("TeamworkCreateNewResult", {
    "mapping": fields.Nested(_entity_mapping_out_model),
    "created": fields.Raw(),
})


@ns.route("/entity-mappings/<string:mapping_id>/create-new-candidates")
class TeamworkEntityMappingCreateNewCandidates(Resource):
    @ns.doc("teamwork_entity_mapping_create_new_candidates")
    @ns.response(200, "Datos por defecto y catálogos auxiliares para el modal de migración", _create_new_candidates_out)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(404, "Homologación no encontrada", _error)
    @ns.response(409, "Fila ya vinculada, o Empresa/Proyecto padre sin homologar", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def get(self, mapping_id: str):
        mapping_uuid = parse_uuid(mapping_id)
        if not mapping_uuid:
            return {"error": "not_found", "message": "Homologación no encontrada"}, 404
        try:
            db = get_db()
            mapping = EntityMappingRepository(db).get_by_id(mapping_uuid)
            if not mapping:
                return {"error": "not_found", "message": "Homologación no encontrada"}, 404
            if mapping.sytix_id:
                return {"error": "already_linked", "message": "Esta fila ya está vinculada a un registro de SYTIX"}, 409
            candidates, error = _build_create_new_candidates(db, mapping)
            if error:
                return error
            return candidates, 200
        except Exception:
            return server_error()


@ns.route("/entity-mappings/<string:mapping_id>/create-new")
class TeamworkEntityMappingCreateNew(Resource):
    @ns.doc("teamwork_entity_mapping_create_new")
    @ns.expect(_create_new_input, validate=False)
    @ns.response(200, "Registro creado en SYTIX y vinculado a la fila", _create_new_out)
    @ns.response(400, "role_id/client_id faltante para entity_type='person', o correo/nombre "
                      "de Teamwork vacío", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(404, "Homologación o Rol no encontrado", _error)
    @ns.response(409, "Fila ya vinculada, padre sin homologar, nombre duplicado o correo ya en uso", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self, mapping_id: str):
        data = request.get_json(silent=True) or {}
        mapping_uuid = parse_uuid(mapping_id)
        if not mapping_uuid:
            return {"error": "not_found", "message": "Homologación no encontrada"}, 404
        try:
            db = get_db()
            mapping_repo = EntityMappingRepository(db)
            mapping = mapping_repo.get_by_id(mapping_uuid)
            if not mapping:
                return {"error": "not_found", "message": "Homologación no encontrada"}, 404
            if mapping.sytix_id:
                return {"error": "already_linked", "message": "Esta fila ya está vinculada a un registro de SYTIX"}, 409
            handler_factory = _CREATE_NEW_HANDLERS.get(mapping.entity_type)
            if not handler_factory:
                return {"error": "validation_error", "message": "entity_type inválido"}, 400
            result, error = handler_factory(db)(mapping, data)
            if error:
                return error
            (created_id, created_name, sytix_entity_type) = result
            updated = mapping_repo.set_created_new_mapping(
                mapping_uuid, created_id, sytix_entity_type, updated_by=g.current_user.id)
            return {
                "mapping": _entity_mapping_out(updated, created_name),
                "created": {"id": str(created_id), "name": created_name},
            }, 200
        except Exception:
            return server_error()


# ── Acciones masivas de migración/inactivación (spec 044 US2, generalizada en spec 045 US2) ──
# research.md Decisión 2 (spec 045): reutiliza sin cambios el mismo `_CREATE_NEW_HANDLERS` que ya
# despacha el endpoint individual, fila por fila, sin transacción envolvente sobre todo el lote
# (cada fila se confirma independientemente) — `role_id` ahora es opcional, solo exigido cuando la
# selección incluye filas `entity_type='person'`.

_bulk_create_new_input = ns.model("TeamworkBulkCreateNewInput", {
    "mapping_ids": fields.List(fields.String(), required=True),
    "role_id": fields.String(description="Requerido solo si la selección incluye filas entity_type='person'"),
    "client_id": fields.String(allow_null=True, description="Requerido solo si el rol elegido es 'Usuario/cliente'"),
})

_bulk_create_new_created_out = ns.model("TeamworkBulkCreateNewCreated", {
    "mapping_id": fields.String(),
    "sytix_id": fields.String(),
    "sytix_name": fields.String(allow_null=True),
})

_bulk_create_new_skipped_out = ns.model("TeamworkBulkCreateNewSkipped", {
    "mapping_id": fields.String(),
    "reason": fields.String(),
})

_bulk_create_new_out = ns.model("TeamworkBulkCreateNewResult", {
    "created": fields.List(fields.Nested(_bulk_create_new_created_out)),
    "skipped": fields.List(fields.Nested(_bulk_create_new_skipped_out)),
})


@ns.route("/entity-mappings/bulk-create-new")
class TeamworkEntityMappingBulkCreateNew(Resource):
    @ns.doc("teamwork_entity_mapping_bulk_create_new")
    @ns.expect(_bulk_create_new_input, validate=False)
    @ns.response(200, "Filas migradas/omitidas", _bulk_create_new_out)
    @ns.response(400, "'mapping_ids' vacío, o 'role_id' inválido", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(404, "role_id no existe", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        data = request.get_json(silent=True) or {}
        mapping_ids = data.get("mapping_ids") or []
        if not mapping_ids:
            return {"error": "validation_error", "message": "'mapping_ids' es requerido"}, 400
        role_id = None
        if data.get("role_id"):
            role_id = parse_uuid(data.get("role_id"))
            if not role_id:
                return {"error": "validation_error", "message": "'role_id' inválido"}, 400
        try:
            db = get_db()
            if role_id and not RoleRepository(db).get_by_id(role_id):
                return {"error": "role_not_found", "message": "Rol no encontrado"}, 404
            mapping_repo = EntityMappingRepository(db)
            create_person = _create_new_person(db)
            created: list[dict] = []
            skipped: list[dict] = []
            for raw_id in mapping_ids:
                mapping_uuid = parse_uuid(raw_id)
                mapping = mapping_repo.get_by_id(mapping_uuid) if mapping_uuid else None
                if not mapping:
                    skipped.append({"mapping_id": raw_id, "reason": "not_found"})
                    continue
                if mapping.sytix_id:
                    skipped.append({"mapping_id": raw_id, "reason": "already_linked"})
                    continue
                if mapping.is_discarded:
                    skipped.append({"mapping_id": raw_id, "reason": "discarded"})
                    continue
                if mapping.entity_type == "person":
                    if not role_id:
                        skipped.append({"mapping_id": raw_id, "reason": "role_id_required"})
                        continue
                    result, error = create_person(mapping, data)
                else:
                    handler_factory = _CREATE_NEW_HANDLERS.get(mapping.entity_type)
                    if not handler_factory:
                        skipped.append({"mapping_id": raw_id, "reason": "unsupported_entity_type"})
                        continue
                    result, error = handler_factory(db)(mapping, data)
                if error:
                    error_body, _status = error
                    skipped.append({"mapping_id": raw_id, "reason": error_body.get("error", "error")})
                    continue
                (created_id, created_name, sytix_entity_type) = result
                mapping_repo.set_created_new_mapping(
                    mapping_uuid, created_id, sytix_entity_type, updated_by=g.current_user.id)
                created.append({"mapping_id": raw_id, "sytix_id": str(created_id), "sytix_name": created_name})
            return {"created": created, "skipped": skipped}, 200
        except Exception:
            return server_error()


# ── Inactivar/Reactivar en lote (spec 045 US2, FR-010/FR-006) ──────────────────────────────
# research.md Decisión 3: simétrico a `bulk-create-new` — mismo shape de respuesta, cada fila se
# procesa independientemente sin transacción envolvente sobre todo el lote.

_bulk_status_input = ns.model("TeamworkBulkStatusInput", {
    "mapping_ids": fields.List(fields.String(), required=True),
})

_bulk_status_updated_out = ns.model("TeamworkBulkStatusUpdated", {
    "mapping_id": fields.String(),
})

_bulk_status_out = ns.model("TeamworkBulkStatusResult", {
    "updated": fields.List(fields.Nested(_bulk_status_updated_out)),
    "skipped": fields.List(fields.Nested(_bulk_create_new_skipped_out)),
})


def _bulk_set_discarded(discarded: bool):
    def _run():
        data = request.get_json(silent=True) or {}
        mapping_ids = data.get("mapping_ids") or []
        if not mapping_ids:
            return {"error": "validation_error", "message": "'mapping_ids' es requerido"}, 400
        try:
            db = get_db()
            mapping_repo = EntityMappingRepository(db)
            updated: list[dict] = []
            skipped: list[dict] = []
            for raw_id in mapping_ids:
                mapping_uuid = parse_uuid(raw_id)
                mapping = mapping_repo.get_by_id(mapping_uuid) if mapping_uuid else None
                if not mapping:
                    skipped.append({"mapping_id": raw_id, "reason": "not_found"})
                    continue
                if discarded:
                    # FR-001: Inactivo es exclusivo de filas sin registro de SYTIX asociado.
                    if mapping.sytix_id:
                        skipped.append({"mapping_id": raw_id, "reason": "already_linked"})
                        continue
                    if mapping.is_discarded:
                        skipped.append({"mapping_id": raw_id, "reason": "already_discarded"})
                        continue
                else:
                    if not mapping.is_discarded:
                        skipped.append({"mapping_id": raw_id, "reason": "not_discarded"})
                        continue
                mapping_repo.set_discarded(mapping_uuid, discarded, updated_by=g.current_user.id)
                updated.append({"mapping_id": raw_id})
            return {"updated": updated, "skipped": skipped}, 200
        except Exception:
            return server_error()
    return _run


@ns.route("/entity-mappings/bulk-discard")
class TeamworkEntityMappingBulkDiscard(Resource):
    @ns.doc("teamwork_entity_mapping_bulk_discard")
    @ns.expect(_bulk_status_input, validate=False)
    @ns.response(200, "Filas marcadas como Inactivo/omitidas", _bulk_status_out)
    @ns.response(400, "'mapping_ids' vacío", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        return _bulk_set_discarded(True)()


@ns.route("/entity-mappings/bulk-reactivate")
class TeamworkEntityMappingBulkReactivate(Resource):
    @ns.doc("teamwork_entity_mapping_bulk_reactivate")
    @ns.expect(_bulk_status_input, validate=False)
    @ns.response(200, "Filas revertidas a Pendiente/omitidas", _bulk_status_out)
    @ns.response(400, "'mapping_ids' vacío", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        return _bulk_set_discarded(False)()


# ── Migración masiva de Tareas/Subtareas (spec 044 US3) ─────────────────────────────────────
# research.md Decisión 8: cada Tarea se resuelve automáticamente contra las homologaciones ya
# existentes (sin homologación manual propia) y se crea/actualiza vía
# `TicketRepository.upsert_from_import` (spec 041, sin modificar ese método).

_sync_tasks_skipped_out = ns.model("TeamworkTaskSyncSkipped", {
    "teamwork_id": fields.String(),
    "reason": fields.String(),
})

_sync_tasks_out = ns.model("TeamworkTaskSyncResult", {
    "synced": fields.Integer(),
    "created": fields.Integer(),
    "updated": fields.Integer(),
    "skipped": fields.List(fields.Nested(_sync_tasks_skipped_out)),
})


@ns.route("/sync/tasks")
class TeamworkTaskSync(Resource):
    @ns.doc("teamwork_task_sync")
    @ns.response(200, "Tareas/Subtareas migradas", _sync_tasks_out)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(409, "La conexión no ha sido probada con éxito", _error)
    @ns.response(502, "La API v3 de Teamwork no respondió", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def post(self):
        try:
            db = get_db()
            config_repo = TeamworkIntegrationConfigRepository(db)
            config = config_repo.get(include_token=True)
            if not config or config.last_test_status != twc.STATUS_SUCCESS:
                return {"error": "connection_not_tested",
                        "message": "Probá la conexión con éxito antes de sincronizar"}, 409
            try:
                raw_tasks = twc.fetch_tasks(config.site_url, config.api_token)
            except TeamworkConnectionError as e:
                return {"error": "teamwork_api_error", "message": str(e)}, 502

            record_type = CatalogRepository(db, "record-types").get_by_name("Tarea")
            if not record_type:
                return {"error": "server_error",
                        "message": "El catálogo de tipo de registro no tiene sembrado 'Tarea'"}, 500
            record_type_id = uuid.UUID(record_type["id"])

            mapping_repo = EntityMappingRepository(db)
            project_repo = ProjectRepository(db)
            ticket_repo = TicketRepository(db)
            site_url = config.site_url.rstrip("/")

            created_count = updated_count = 0
            skipped: list[dict] = []
            rows: list[task_migration_svc.TeamworkTaskRow] = []
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
                row = task_migration_svc.classify_task(raw, resolution)
                rows.append(row)
                if row.status == task_migration_svc.STATUS_SKIPPED:
                    skipped.append({"teamwork_id": row.teamwork_id, "reason": row.skip_reason})
                    continue
                url = f"{site_url}/app/tasks/{row.teamwork_id}"
                _ticket, was_created = ticket_repo.upsert_from_import(
                    external_reference_id=row.teamwork_id, external_reference_url=url,
                    record_type_id=record_type_id, title=row.name, description=row.description or "",
                    client_id=client_id, project_id=project_sytix_id, list_id=list_sytix_id,
                    parent_task_id=None, assignee_id=assignee_resource_id, client_contact_id=None,
                    created_by=g.current_user.id, estimated_resolution_minutes=0,
                )
                if was_created:
                    created_count += 1
                else:
                    updated_count += 1

            # Segunda pasada: resuelve parent_task_id de Subtareas ahora que todo el lote ya
            # tiene su Ticket creado/actualizado (mismo patrón que ticket_imports.py).
            for row in rows:
                if row.status == task_migration_svc.STATUS_SKIPPED or not row.parent_task_teamwork_id:
                    continue
                child = ticket_repo.get_by_external_reference_id(row.teamwork_id)
                parent = ticket_repo.get_by_external_reference_id(row.parent_task_teamwork_id)
                if child and parent and child.parent_task_id != parent.id:
                    ticket_repo.update_fields(child.id, parent_task_id=parent.id, list_id=parent.list_id)

            return {"synced": len(raw_tasks), "created": created_count, "updated": updated_count,
                    "skipped": skipped}, 200
        except Exception:
            return server_error()


# ── Distintivo de trazabilidad en pantallas principales de SYTIX (spec 044 US5) ─────────────

_MIGRATED_REFS_ENTITY_TYPES = {"client", "project", "task_list", "resource", "user"}

_migrated_refs_out = ns.model("TeamworkMigratedRefs", {
    "sytix_ids": fields.List(fields.String()),
})


@ns.route("/migrated-refs")
class TeamworkMigratedRefs(Resource):
    @ns.doc("teamwork_migrated_refs")
    @ns.response(200, "IDs de SYTIX homologados/migrados desde Teamwork", _migrated_refs_out)
    @ns.response(400, "sytix_entity_type inválido", _error)
    @ns.response(401, "No autenticado", _error)
    @ns.response(403, "Sin permiso teamwork_integration:operate", _error)
    @ns.response(500, "Error interno del servidor", _error)
    @require_permission("teamwork_integration", "operate")
    def get(self):
        sytix_entity_type = request.args.get("sytix_entity_type")
        if sytix_entity_type not in _MIGRATED_REFS_ENTITY_TYPES:
            return {"error": "validation_error",
                    "message": "sytix_entity_type debe ser uno de: "
                               f"{', '.join(sorted(_MIGRATED_REFS_ENTITY_TYPES))}"}, 400
        try:
            db = get_db()
            ids = EntityMappingRepository(db).list_sytix_ids_by_type(sytix_entity_type)
            return {"sytix_ids": [str(i) for i in ids]}, 200
        except Exception:
            return server_error()
