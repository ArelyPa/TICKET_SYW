"""Cliente de Capa 2 (spec 042) para probar conexión y sincronizar catálogos contra la API v3 de
Teamwork usando credenciales configuradas por el usuario (no variables de entorno — a diferencia
de `teamwork_api_client.py` de spec 041, ver research.md Decisión 1).

Autenticación: Basic Auth con el API token como usuario (password arbitrario) — mismo mecanismo
documentado por Teamwork ya usado en `teamwork_api_client.py`.
"""
import requests

STATUS_SUCCESS = "success"
STATUS_AUTH_ERROR = "auth_error"
STATUS_CONNECTION_ERROR = "connection_error"

_ENDPOINTS = {
    "company": "companies.json",
    "project": "projects.json",
    "person": "people.json",
    "tasklist": "tasklists.json",
}

# Clave de la lista dentro del payload JSON:API de cada endpoint (verificado contra
# apidocs.teamwork.com al momento de esta sesión, sin smoke-test contra una cuenta real — mismo
# caso ya documentado en spec 041).
_RESULT_KEYS = {
    "company": "companies",
    "project": "projects",
    "person": "people",
    "tasklist": "tasklists",
}


def _base_url(site_url: str) -> str:
    return site_url.rstrip("/")


def test_connection(site_url: str, api_token: str) -> dict:
    """`GET /projects/api/v3/projects.json?pageSize=1` — no necesita traer resultados reales,
    solo confirmar autenticación. Devuelve `{"status": ..., "message": str | None}`."""
    url = f"{_base_url(site_url)}/projects/api/v3/projects.json"
    try:
        response = requests.get(url, auth=(api_token, "x"), params={"pageSize": 1}, timeout=15)
    except requests.RequestException as e:
        return {"status": STATUS_CONNECTION_ERROR, "message": str(e)}
    if response.status_code == 401:
        return {"status": STATUS_AUTH_ERROR, "message": "Token de API inválido o vencido"}
    if response.status_code >= 400:
        return {"status": STATUS_CONNECTION_ERROR,
                "message": f"La API de Teamwork respondió {response.status_code}"}
    return {"status": STATUS_SUCCESS, "message": None}


def _fetch_all_pages(url: str, auth: tuple, params: dict, result_key: str) -> list[dict]:
    """research.md Decisión 1: la API v3 de Teamwork limita cada respuesta a un tope propio del
    servidor sin importar el `pageSize` pedido (causa raíz confirmada de "150 reportados vs. 60
    renderizados") — recorre `page=1,2,3…` hasta que una página devuelve menos elementos que
    `pageSize` (o ninguno), sin depender de un campo `meta.page.*` no verificable contra una
    cuenta real en este entorno."""
    page_size = params.get("pageSize", 250)
    all_items: list[dict] = []
    page = 1
    while True:
        try:
            response = requests.get(url, auth=auth, params={**params, "page": page}, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise TeamworkConnectionError(f"No se pudo conectar con la API v3 de Teamwork: {e}") from e
        try:
            payload = response.json()
        except ValueError as e:
            raise TeamworkConnectionError("Respuesta de la API v3 de Teamwork no es JSON válido") from e
        items = payload.get(result_key, [])
        all_items.extend(items)
        if len(items) < page_size or not items:
            break
        page += 1
    return all_items


def _fetch_entity(site_url: str, api_token: str, entity_type: str) -> list[dict]:
    endpoint = _ENDPOINTS[entity_type]
    url = f"{_base_url(site_url)}/projects/api/v3/{endpoint}"
    items = _fetch_all_pages(url, (api_token, "x"), {"pageSize": 250}, _RESULT_KEYS[entity_type])
    if entity_type == "person":
        # FR-006: el correo habilita el automapeo por email contra Recursos/Usuarios de SYTIX.
        # FR-001 (spec 044): `parent_id` es la Compañía de origen de la Persona, mismo campo
        # `company`/`companyId` ya leído por `_parent_id` para project/tasklist.
        return [{"id": str(item.get("id")), "name": _person_name(item),
                 "email": item.get("email"), "parent_id": _parent_id(item),
                 "metadata": _person_metadata(item)} for item in items]
    if entity_type in ("project", "tasklist"):
        # spec 043 FR-005/FR-007: `parent_id` es la Empresa dueña (project) o el Proyecto dueño
        # (tasklist), verificado contra apidocs.teamwork.com sin smoke-test contra una cuenta
        # real (mismo caso ya documentado en spec 041/042) — `None` si el payload real no trae
        # el campo esperado, sin romper la sincronización existente.
        return [{"id": str(item.get("id")), "name": item.get("name") or item.get("companyName"),
                 "parent_id": _parent_id(item), "metadata": _work_item_metadata(item)} for item in items]
    return [{"id": str(item.get("id")), "name": item.get("name") or item.get("companyName"),
             "metadata": _company_metadata(item)} for item in items]


def _company_metadata(item: dict) -> dict:
    """spec 045 FR-013: País/Dirección/Dominio/Teléfono de una Empresa — verificado contra
    apidocs.teamwork.com sin smoke-test contra una cuenta real (mismo caso ya documentado en
    specs 041-044). Una clave se omite por completo si el campo no viene informado en el origen
    (FR-016), nunca se guarda como `null` explícito."""
    metadata: dict = {}
    country = item.get("country") or item.get("countryCode")
    if country:
        metadata["country"] = country
    address_parts = [
        item.get("addressOne") or item.get("address1"), item.get("addressTwo") or item.get("address2"),
        item.get("city"), item.get("state"), item.get("zip"),
    ]
    address = ", ".join(str(p) for p in address_parts if p)
    if address:
        metadata["address"] = address
    domain = item.get("companyDomain") or item.get("website") or item.get("domain")
    if domain:
        metadata["domain"] = domain
    phone = item.get("phone") or item.get("companyPhone")
    if phone:
        metadata["phone"] = phone
    return metadata


def _person_metadata(item: dict) -> dict:
    """spec 045 FR-014: Cargo/Título y Zona horaria de una Persona (Correo y Compañía ya
    cubiertos por columnas propias desde specs 043/044, no se duplican acá)."""
    metadata: dict = {}
    job_title = item.get("jobTitle") or item.get("title") or item.get("position")
    if job_title:
        metadata["job_title"] = job_title
    timezone = item.get("timezone") or item.get("userTimezone")
    if timezone:
        metadata["timezone"] = timezone
    return metadata


def _work_item_metadata(item: dict) -> dict:
    """spec 045 FR-015: descripción y estado activo/archivado de un Proyecto o Lista de Tareas."""
    metadata: dict = {}
    description = item.get("description")
    if description:
        metadata["description"] = description
    status = item.get("status")
    if status:
        metadata["status"] = "archived" if str(status).lower() in ("archived", "completed") else "active"
    else:
        is_archived = item.get("isArchived")
        if is_archived is None:
            is_archived = item.get("archived")
        if is_archived is not None:
            metadata["status"] = "archived" if is_archived else "active"
    return metadata


def _parent_id(item: dict) -> str | None:
    company = item.get("company") or {}
    if company.get("id"):
        return str(company["id"])
    if item.get("companyId"):
        return str(item["companyId"])
    project = item.get("project") or {}
    if project.get("id"):
        return str(project["id"])
    if item.get("projectId"):
        return str(item["projectId"])
    return None


def _person_name(item: dict) -> str | None:
    first = item.get("firstName")
    last = item.get("lastName")
    if first or last:
        return " ".join(p for p in (first, last) if p)
    return item.get("email")


def fetch_companies(site_url: str, api_token: str) -> list[dict]:
    return _fetch_entity(site_url, api_token, "company")


def fetch_projects(site_url: str, api_token: str) -> list[dict]:
    return _fetch_entity(site_url, api_token, "project")


def fetch_people(site_url: str, api_token: str) -> list[dict]:
    return _fetch_entity(site_url, api_token, "person")


def fetch_tasklists(site_url: str, api_token: str) -> list[dict]:
    return _fetch_entity(site_url, api_token, "tasklist")


def _task_related_id(item: dict, direct_key: str, nested_key: str) -> str | None:
    nested = item.get(nested_key) or {}
    if nested.get("id"):
        return str(nested["id"])
    if item.get(direct_key):
        return str(item[direct_key])
    return None


def fetch_tasks(site_url: str, api_token: str) -> list[dict]:
    """spec 044 US3/research.md Decisión 8: `GET /projects/api/v3/tasks.json`, reutilizando
    `_fetch_all_pages` (Decisión 1). SYTIX no soporta múltiples asignados por Ticket — la
    reducción de `task.assignees` (lista) a un único `assignee_id` ocurre acá en Capa 2 (primer
    elemento, o `None` si viene vacía), no en la Capa 3.

    `created_at`/`due_date` (spec 045 US4, research.md Decisión 7) son exclusivos del filtro de
    fecha del Importador de Tareas — no se persisten en el Ticket creado (mismo criterio ya
    establecido en spec 041 para Start/Due date), quedan como string cruda de Teamwork sin
    parsear acá, la Capa 1 del importador decide con cuál de los dos filtrar."""
    url = f"{_base_url(site_url)}/projects/api/v3/tasks.json"
    items = _fetch_all_pages(url, (api_token, "x"), {"pageSize": 250}, "tasks")
    result = []
    for item in items:
        assignees = item.get("assignees") or {}
        assignee_ids = assignees.get("userIds") if isinstance(assignees, dict) else assignees
        result.append({
            "id": str(item.get("id")),
            "name": item.get("name"),
            "description": item.get("description"),
            "project_id": _task_related_id(item, "projectId", "project"),
            "tasklist_id": _task_related_id(item, "tasklistId", "tasklist"),
            "parent_task_id": _task_related_id(item, "parentTaskId", "parentTask"),
            "assignee_id": str(assignee_ids[0]) if assignee_ids else None,
            "created_at": item.get("createdAt"),
            "due_date": item.get("dueDate"),
        })
    return result


class TeamworkConnectionError(Exception):
    pass
