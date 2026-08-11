"""Cliente de Capa 2 (spec 041, US3) para la API v3 de Teamwork —
`GET /projects/api/v3/tasks.json`. Homologa la respuesta a las mismas claves que emite
`teamwork_file_parser.py` para que `teamwork_import_service.py` (Capa 1) sea agnóstico al origen.

Forma de la respuesta (verificada contra apidocs.teamwork.com/docs/teamwork/v3/tasks al momento
de esta sesión; sin acceso a una cuenta real de Teamwork para smoke-test — revisar contra un
sandbox real antes de depender de esto en producción): estilo JSON:API — cada tarea trae
relaciones por ID (`projectId`, `tasklistId`, `parentTaskId`, `assignees[].id`, `createdBy.id`) y
un bloque `included` con los objetos completos (`projects`, `companies`, `tasklists`, `users`)
indexados por ID en forma de string.

Autenticación: Basic Auth con el API token de Teamwork como usuario (password arbitrario) — mismo
mecanismo documentado por Teamwork para su REST API. Configuración vía variables de entorno del
backend (nunca expuestas al frontend, Principio IV):
- TEAMWORK_DOMAIN: subdominio de la cuenta (ej. "sywork" para sywork.teamwork.com)
- TEAMWORK_API_TOKEN: API token de la cuenta de servicio usada para la sincronización
"""
import os

import requests


class TeamworkApiError(Exception):
    pass


def fetch_tasks() -> list[dict]:
    domain = os.environ.get("TEAMWORK_DOMAIN")
    token = os.environ.get("TEAMWORK_API_TOKEN")
    if not domain or not token:
        raise TeamworkApiError(
            "Falta configurar TEAMWORK_DOMAIN/TEAMWORK_API_TOKEN en el backend")
    url = f"https://{domain}.teamwork.com/projects/api/v3/tasks.json"
    try:
        response = requests.get(url, auth=(token, "x"), params={"pageSize": 250}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise TeamworkApiError(f"No se pudo conectar con la API v3 de Teamwork: {e}") from e
    try:
        payload = response.json()
    except ValueError as e:
        raise TeamworkApiError("Respuesta de la API v3 de Teamwork no es JSON válido") from e
    return _homologate_all(payload)


def _homologate_all(payload: dict) -> list[dict]:
    included = payload.get("included") or {}
    projects = included.get("projects") or {}
    companies = included.get("companies") or {}
    tasklists = included.get("tasklists") or {}
    users = included.get("users") or {}

    def user_name(user_id) -> str | None:
        user = users.get(str(user_id)) if user_id is not None else None
        return user.get("name") or user.get("firstName") if user else None

    def project_and_company(project_id):
        project = projects.get(str(project_id)) if project_id is not None else None
        if not project:
            return None, None
        company = companies.get(str(project.get("companyId")))
        return project.get("name"), (company.get("name") if company else None)

    rows: list[dict] = []
    for task in payload.get("tasks", []):
        project_name, company_name = project_and_company(task.get("projectId"))
        tasklist = tasklists.get(str(task.get("tasklistId"))) if task.get("tasklistId") else None
        assignees = task.get("assignees") or []
        assignee_id = assignees[0].get("id") if assignees else None
        rows.append({
            "row_number": task.get("id"),
            "external_id": str(task["id"]) if task.get("id") is not None else None,
            "company_name": company_name,
            "project_name": project_name,
            "list_name": tasklist.get("name") if tasklist else None,
            "title": task.get("name"),
            "description": task.get("description") or "",
            "start_date": _parse_date(task.get("startDate")),
            "due_date": _parse_date(task.get("dueDate")),
            "assignee_name": user_name(assignee_id),
            "requester_name": user_name((task.get("createdBy") or {}).get("id")),
            "estimated_minutes": task.get("estimateMinutes") or 0,
            "parent_external_id": (str(task["parentTaskId"])
                                   if task.get("parentTaskId") else None),
        })
    return rows


def _parse_date(value):
    """Teamwork v3 puede devolver la fecha en `YYYY-MM-DD` (ISO) o `YYYYMMDD` (convención
    heredada de la API v1/v2) según el endpoint — se intentan ambos formatos."""
    if not value:
        return None
    from datetime import datetime
    text = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text.replace("-", "") if fmt == "%Y%m%d" else text, fmt).date()
        except ValueError:
            continue
    return None
